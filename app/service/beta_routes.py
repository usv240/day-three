"""Authenticated, de-identified clinical integration sandbox for Day Three."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from day_three.antibiogram import Antibiogram, Curator
from day_three.intake import ExtractionError, IntakeAgent, VertexClient
from day_three.store import AntibiogramStore
from spine.api_access import ApiKeyAuthenticator, ApiPrincipal, require_scope
from spine.redact import GemmaReviewer, RedactionError, Redactor


class BetaIntakeRequest(BaseModel):
    document: str = Field(min_length=40, max_length=30_000)
    subject_ref: str = Field(
        min_length=3, max_length=40, pattern=r"^SUBJECT-[A-Za-z0-9._-]+$"
    )
    acknowledge_deidentified: Literal[True]


def _facility_id(tenant_id: str) -> str:
    digest = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:20]
    return f"beta_{digest}"


def _period(clock) -> tuple[datetime, datetime]:
    year = clock.now().year
    return (
        datetime(year, 1, 1, tzinfo=timezone.utc),
        datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    )


def _reject_obvious_identifiers(document: str) -> None:
    found = Redactor().redact(document).replacements
    if found:
        kinds = sorted({item.kind for item in found})
        raise HTTPException(
            status_code=422,
            detail=(
                "The clinical beta accepts de-identified text only. Remove these detected "
                f"identifier types before retrying: {', '.join(kinds)}."
            ),
        )


def build_beta_router(
    client,
    clock,
    auth: ApiKeyAuthenticator,
    *,
    intake_factory: Callable[[], IntakeAgent] | None = None,
    project_id: str = "",
    model_location: str = "global",
    model_name: str = "gemini-3.5-flash",
    budget=None,
) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["beta-api"])
    antibiograms = AntibiogramStore(client)

    def authorize(principal: ApiPrincipal) -> None:
        require_scope(principal, "day-three:use")

    def agent() -> IntakeAgent:
        if intake_factory is not None:
            return intake_factory()
        return IntakeAgent(
            VertexClient(project_id, model_location, model_name),
            reviewer=GemmaReviewer(project_id, model_location),
        )

    def load_grid(principal: ApiPrincipal) -> Antibiogram:
        start, end = _period(clock)
        return antibiograms.load(_facility_id(principal.tenant_id), start, end)

    @router.get("")
    def api_info(principal: ApiPrincipal = Depends(auth)) -> dict[str, Any]:
        authorize(principal)
        return {
            "product": "Day Three",
            "api_version": "v1",
            "tenant": principal.tenant_id,
            "key_id": principal.key_id,
            "input": "De-identified microbiology report text only.",
            "output": "A tenant-specific cumulative antibiogram with CLSI suppression.",
            "boundary": (
                "Screening and stewardship support only. No patient order, dose, or prescribing action."
            ),
        }

    @router.post("/intake", status_code=201)
    def intake(
        request: BetaIntakeRequest,
        principal: ApiPrincipal = Depends(auth),
    ) -> dict[str, Any]:
        authorize(principal)
        _reject_obvious_identifiers(request.document)
        # The only keyed route that invokes a model, so the only one that can cost money.
        # A valid key is not a blank cheque: the same durable counter that bounds the
        # credential-free demo bounds each key here, per key and per day.
        # Wall clock, never the injectable one: a simulated jump must not reset a spend cap.
        now = datetime.now(timezone.utc)
        if budget is not None:
            decision = budget.check(now, principal.key_id)
            if not decision.allowed:
                raise HTTPException(status_code=429, detail=decision.reason)
        artifact_id = f"beta_{principal.key_id}_{uuid.uuid4().hex[:12]}"
        subject = f"{principal.tenant_id}:{request.subject_ref}"
        try:
            result = agent().parse(artifact_id, request.document, subject)
        except RedactionError as exc:
            raise HTTPException(
                status_code=503,
                detail="Privacy review unavailable; the report was not processed.",
            ) from exc
        except ExtractionError as exc:
            if budget is not None:
                budget.consume(now, principal.key_id)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if budget is not None:
            budget.consume(now, principal.key_id)
        grid = load_grid(principal)
        changed = Curator(grid).ingest(result.isolates[0])
        antibiograms.save(grid)
        return {
            "isolate": {
                "organism": result.isolates[0].organism,
                "specimen": result.isolates[0].specimen_type,
                "susceptibilities": [
                    {
                        "drug": item.drug,
                        "interpretation": item.interpretation.value,
                        "quoted_text": item.source_ref,
                    }
                    for item in result.isolates[0].susceptibilities
                ],
            },
            "cells_changed": [{"organism": organism, "drug": drug} for organism, drug in changed],
            "dropped": result.dropped,
            "redacted": result.redacted_count,
            "raw_document_persisted": False,
            "revision": grid.revision,
            "safety": "No clinical action was taken. All cells below 30 isolates remain suppressed.",
        }

    @router.get("/antibiogram")
    def antibiogram(principal: ApiPrincipal = Depends(auth)) -> dict[str, Any]:
        authorize(principal)
        view = antibiograms.view(load_grid(principal))
        view["tenant"] = principal.tenant_id
        view["clinical_action"] = "none"
        return view

    return router
