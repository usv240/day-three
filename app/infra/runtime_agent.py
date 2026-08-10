"""Managed Agent Runtime adapter for Day Three's published capabilities.

Each deployment sets ``DAY_THREE_AGENT_ROLE`` to exactly one published role. The adapter exposes
one narrow ``query`` method, screens the request and response with regional Model Armor templates,
and invokes only the backend operation owned by that role. It is intentionally a small managed
control-plane adapter around the tested Day Three workflow, not a second implementation of the
clinical logic.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import google.auth
from google.auth.transport.requests import AuthorizedSession


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
BACKEND_URL = os.environ.get(
    "DAY_THREE_BACKEND_URL", "https://day-three-109051079423.us-central1.run.app"
).rstrip("/")
ROLE = os.environ.get("DAY_THREE_AGENT_ROLE", "curator")
REQUEST_TEMPLATE = os.environ.get("MODEL_ARMOR_REQUEST_TEMPLATE", "day-three-agent-input")
RESPONSE_TEMPLATE = os.environ.get("MODEL_ARMOR_RESPONSE_TEMPLATE", "day-three-agent-output")


class GuardrailRejected(ValueError):
    """Model Armor found content this managed capability is not allowed to process."""


class CapabilityInvocationError(RuntimeError):
    """The governed capability backend could not be invoked."""


class ModelArmor:
    """Fail-closed regional Model Armor adapter with no raw content in errors."""

    def __init__(
        self,
        project_id: str = PROJECT_ID,
        location: str = LOCATION,
        request_template: str = REQUEST_TEMPLATE,
        response_template: str = RESPONSE_TEMPLATE,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.request_template = request_template
        self.response_template = response_template
        self._session_factory = session_factory or self._authorized_session

    @staticmethod
    def _authorized_session() -> AuthorizedSession:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AuthorizedSession(credentials)

    def screen_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._screen(
            self.request_template,
            "sanitizeUserPrompt",
            {"userPromptData": {"text": json.dumps(payload, sort_keys=True)}},
        )

    def screen_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._screen(
            self.response_template,
            "sanitizeModelResponse",
            {"modelResponseData": {"text": json.dumps(payload, sort_keys=True)}},
        )

    def _screen(self, template: str, method: str, body: dict[str, Any]) -> dict[str, Any]:
        name = f"projects/{self.project_id}/locations/{self.location}/templates/{template}"
        endpoint = f"https://modelarmor.{self.location}.rep.googleapis.com/v1/{name}:{method}"
        response = self._session_factory().post(endpoint, json=body, timeout=15)
        if response.status_code != 200:
            raise GuardrailRejected(f"Model Armor unavailable: HTTP {response.status_code}")
        result = response.json().get("sanitizationResult", {})
        if result.get("invocationResult") != "SUCCESS":
            raise GuardrailRejected("Model Armor did not complete successfully")
        if result.get("filterMatchState") == "MATCH_FOUND":
            raise GuardrailRejected("Model Armor blocked the content")
        return {
            "screened": True,
            "template": template,
            "filter_match_state": result.get("filterMatchState", "NO_MATCH_FOUND"),
            "invocation_result": result.get("invocationResult"),
        }


@dataclass(frozen=True)
class Capability:
    method: str
    path: str
    accepts_payload: bool


CAPABILITIES = {
    "curator": Capability("GET", "/day-three/antibiogram", False),
    "intake": Capability("POST", "/day-three/intake", True),
    "shortage-watch": Capability("GET", "/day-three/shortages", False),
    "reconciler": Capability("POST", "/day-three/reconcile", True),
}


class DayThreeRuntimeAgent:
    """One least-privilege managed role with one allowed backend operation."""

    def __init__(
        self,
        role: str = ROLE,
        backend_url: str = BACKEND_URL,
        armor: ModelArmor | None = None,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if role not in CAPABILITIES:
            raise ValueError(f"unsupported DAY_THREE_AGENT_ROLE: {role}")
        self.role = role
        self.backend_url = backend_url.rstrip("/")
        self.armor = armor or ModelArmor()
        self._opener = opener

    def query(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Screen, invoke, screen again, and return auditable guardrail evidence."""
        body = payload or {}
        request_guardrail = self.armor.screen_request(body)
        capability = CAPABILITIES[self.role]
        data = json.dumps(body).encode("utf-8") if capability.accepts_payload else None
        request = Request(
            self.backend_url + capability.path,
            data=data,
            method=capability.method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self._opener(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise CapabilityInvocationError(
                f"{self.role} backend invocation failed: {type(exc).__name__}"
            ) from exc
        response_guardrail = self.armor.screen_response(result)
        return {
            "agent_role": self.role,
            "invoked": capability.path,
            "result": result,
            "guardrails": {
                "request": request_guardrail,
                "response": response_guardrail,
            },
        }


root_agent = DayThreeRuntimeAgent()

