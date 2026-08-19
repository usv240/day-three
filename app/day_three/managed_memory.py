"""Bounded Agent Platform Memory Bank use for deidentified course handoffs.

Firestore remains the authoritative operational ledger. Memory Bank carries a deliberately small,
non-authoritative summary that another agent session can recall without receiving a patient
identifier or raw report text.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Callable

import google.auth
from google.auth.transport.requests import AuthorizedSession


CURATOR_RUNTIME_ID = "5315313536820314112"


class ManagedMemoryError(RuntimeError):
    """The managed memory operation failed without exposing its submitted content."""


class ManagedMemoryBank:
    """Write and recall only deidentified, synthetic course handoff summaries."""

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        runtime_id: str = CURATOR_RUNTIME_ID,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.runtime_id = runtime_id
        self._session_factory = session_factory or self._authorized_session

    @staticmethod
    def _authorized_session() -> AuthorizedSession:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AuthorizedSession(credentials)

    @property
    def parent(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/reasoningEngines/{self.runtime_id}"
        )

    @property
    def endpoint(self) -> str:
        return f"https://{self.location}-aiplatform.googleapis.com/v1beta1/{self.parent}"

    @staticmethod
    def course_scope(course_id: str) -> dict[str, str]:
        digest = hashlib.sha256(course_id.encode("utf-8")).hexdigest()[:24]
        return {"application": "day-three", "course_ref": digest}

    @staticmethod
    def _json(response: Any, operation: str) -> dict[str, Any]:
        if response.status_code != 200:
            raise ManagedMemoryError(
                f"Memory Bank {operation} returned HTTP {response.status_code}; "
                "Firestore remains authoritative."
            )
        return response.json()

    def remember_course(
        self,
        *,
        course_id: str,
        regimen: tuple[str, ...],
        indication: str,
        first_review_at: datetime,
    ) -> dict[str, Any]:
        """Create a non-identifying handoff after the durable course has been committed."""
        fact = (
            "A synthetic Day Three antibiotic course is active for "
            f"{indication or 'an unspecified indication'}. Its recorded regimen is "
            f"{', '.join(regimen) or 'not recorded'}. Five inpatient stewardship wakes are "
            f"registered through day 14; the first review is due at {first_review_at.isoformat()}. "
            "Firestore is the authoritative ledger and this memory is context only."
        )
        try:
            response = self._session_factory().post(
                f"{self.endpoint}/memories",
                json={"fact": fact, "scope": self.course_scope(course_id)},
                timeout=12,
            )
        except Exception as exc:
            raise ManagedMemoryError(
                "Memory Bank create could not be completed; Firestore remains authoritative."
            ) from exc
        payload = self._json(response, "create")
        created = payload.get("response", payload)
        return {
            "stored": True,
            "name": created.get("name"),
            "scope": self.course_scope(course_id),
            "contains_patient_identifier": False,
            "authoritative_store": "Firestore",
        }

    def recall_course(self, course_id: str) -> dict[str, Any]:
        """Retrieve the exact course scope; no similarity search crosses course boundaries."""
        try:
            response = self._session_factory().post(
                f"{self.endpoint}/memories:retrieve",
                json={"scope": self.course_scope(course_id)},
                timeout=12,
            )
        except Exception as exc:
            raise ManagedMemoryError(
                "Memory Bank retrieve could not be completed; Firestore remains authoritative."
            ) from exc
        payload = self._json(response, "retrieve")
        memories = [item.get("memory", {}) for item in payload.get("retrievedMemories", [])]
        return {
            "recalled": bool(memories),
            "count": len(memories),
            "scope": self.course_scope(course_id),
            "facts": [memory.get("fact") for memory in memories if memory.get("fact")],
            "authoritative_store": "Firestore",
        }
