"""Issuance of short-lived, tenant-scoped developer API keys.

Issuance can run in one of two modes. With an invitation hash configured it is invite-gated.
With BETA_OPEN_ISSUANCE set it is open: anyone can mint a key for their own tenant, which is
what makes the beta self-serve for an evaluator who has no way to ask us for a code.

Open issuance is only defensible because the money is bounded somewhere else. A key grants
one scope, expires on its own, and the single keyed route that invokes a model is capped per
key and per day. What is capped *here* is issuance itself, so an open form cannot be used to
manufacture keys without limit.
"""

from __future__ import annotations

import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr

from spine.api_access import ApiKeyAuthenticator, ApiPrincipal, hash_api_key, require_scope


class ApiKeyStore(Protocol):
    def get(self, digest: str) -> dict[str, Any] | None: ...
    def issue(self, digest: str, **record: Any) -> None: ...
    def revoke(self, digest: str, revoked_at: datetime) -> bool: ...


class KeyRequest(BaseModel):
    # Optional: required in invite-gated mode, ignored when issuance is open.
    invitation_code: SecretStr | None = None
    tenant_id: str = Field(min_length=2, max_length=48, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    label: str = Field(min_length=2, max_length=80)
    acknowledge_terms: Literal[True]


class KeyIssuer:
    def __init__(
        self,
        store: ApiKeyStore,
        *,
        product: str,
        scope: str,
        prefix: str,
        invitation_hash: str = "",
        ttl_hours: int = 168,
        open_issuance: bool = False,
    ) -> None:
        self.open_issuance = open_issuance
        self.store = store
        self.product = product
        self.scope = scope
        self.prefix = prefix
        self.invitation_hash = invitation_hash.strip().lower()
        if self.invitation_hash and (
            len(self.invitation_hash) != 64
            or any(char not in "0123456789abcdef" for char in self.invitation_hash)
        ):
            raise RuntimeError("BETA_ENROLLMENT_CODE_HASH must be a lowercase SHA-256 digest")
        if not 1 <= ttl_hours <= 168:
            raise RuntimeError("BETA_DEVELOPER_KEY_TTL_HOURS must be between 1 and 168")
        self.ttl = timedelta(hours=ttl_hours)

    @classmethod
    def from_environment(
        cls, store: ApiKeyStore, *, product: str, scope: str, prefix: str
    ) -> "KeyIssuer":
        raw_ttl = os.environ.get("BETA_DEVELOPER_KEY_TTL_HOURS", "168")
        try:
            ttl = int(raw_ttl)
        except ValueError as exc:
            raise RuntimeError("BETA_DEVELOPER_KEY_TTL_HOURS must be an integer") from exc
        return cls(
            store,
            product=product,
            scope=scope,
            prefix=prefix,
            invitation_hash=os.environ.get("BETA_ENROLLMENT_CODE_HASH", ""),
            ttl_hours=ttl,
            open_issuance=os.environ.get("BETA_OPEN_ISSUANCE", "").strip().lower()
            in {"1", "true", "yes"},
        )

    @property
    def enabled(self) -> bool:
        return self.open_issuance or bool(self.invitation_hash)

    @property
    def mode(self) -> str:
        return "open" if self.open_issuance else "invite_only"

    def issue(self, request: KeyRequest) -> dict[str, Any]:
        if not self.enabled:
            raise HTTPException(status_code=503, detail="Developer key issuance is not enabled.")
        if not self.open_issuance:
            supplied = hash_api_key(
                (request.invitation_code.get_secret_value() if request.invitation_code else "")
                .strip()
            )
            if not hmac.compare_digest(supplied, self.invitation_hash):
                raise HTTPException(status_code=401, detail="The invitation code is invalid.")
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + self.ttl
        api_key = f"{self.prefix}_{secrets.token_urlsafe(32)}"
        digest = hash_api_key(api_key)
        self.store.issue(
            digest,
            tenant_id=request.tenant_id,
            label=request.label.strip(),
            scopes=[self.scope],
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return {
            "api_key": api_key,
            "key_id": digest[:12],
            "tenant_id": request.tenant_id,
            "scope": self.scope,
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "shown_once": True,
        }


def _issuance_caller(request: Request) -> str:
    """A coarse per-address key for the issuance ceiling. Not an authentication boundary."""
    import hashlib

    forwarded = request.headers.get("x-forwarded-for", "")
    address = forwarded.split(",")[0].strip() if forwarded else ""
    if not address and request.client is not None:
        address = request.client.host or ""
    return hashlib.sha256((address or "unknown").encode("utf-8")).hexdigest()[:16]


def build_developer_router(
    issuer: KeyIssuer,
    auth: ApiKeyAuthenticator,
    *,
    product: str,
    scope: str,
    issuance_budget=None,
) -> APIRouter:
    router = APIRouter(tags=["developer-access"])

    @router.get("/developer/config")
    def config() -> dict[str, Any]:
        return {
            "product": product,
            "issuance": issuer.mode if issuer.enabled else "disabled",
            "ttl_hours": int(issuer.ttl.total_seconds() // 3600),
            "scope": scope,
            "header": "X-API-Key",
            "docs": "/docs",
            # Served rather than written into the page, so the number a visitor reads is the
            # number the deployment actually enforces.
            "keys_per_day": (
                issuance_budget.per_caller_cap if issuance_budget is not None else None
            ),
        }

    @router.post("/developer/keys", status_code=201)
    def issue_key(request: KeyRequest, http_request: Request) -> dict[str, Any]:
        # With no invitation code in front of it, issuance itself is the thing that needs a
        # ceiling: otherwise one script can fill the key store. Bounded per address per day.
        if issuance_budget is not None:
            now = datetime.now(timezone.utc)
            caller = _issuance_caller(http_request)
            decision = issuance_budget.check(now, caller)
            if not decision.allowed:
                raise HTTPException(status_code=429, detail=decision.reason)
            issued = issuer.issue(request)
            issuance_budget.consume(now, caller)
            return issued
        return issuer.issue(request)

    @router.delete("/v1/key")
    def revoke_key(principal: ApiPrincipal = Depends(auth)) -> dict[str, Any]:
        require_scope(principal, scope)
        revoked = issuer.store.revoke(principal.key_digest, datetime.now(timezone.utc))
        if not revoked:
            raise HTTPException(
                status_code=409,
                detail="This operator-managed key must be revoked by the project owner.",
            )
        return {"revoked": True, "key_id": principal.key_id}

    return router
