"""Firestore persistence for Day Three.

The antibiogram cannot live in process memory. Cloud Run runs several instances and scales to
zero, so an in-memory grid would appear to lose a hospital's accumulated knowledge every time the
service idled. That would be a bad look in a demo and a worse property in production.

Serialisation is explicit rather than generic, so a schema change shows up as a readable diff.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

from day_three.antibiogram import Antibiogram, Cell, Interpretation, Isolate, Susceptibility

ANTIBIOGRAM_COLLECTION = "antibiograms"
COURSES_COLLECTION = "courses"
LATEST_ISOLATES_COLLECTION = "latest_isolates"


def _cell_key(organism: str, drug: str) -> str:
    # Firestore keys cannot contain a forward slash, and organism names never contain a pipe.
    return f"{organism}|{drug}"


def _split_key(key: str) -> tuple[str, str]:
    organism, _, drug = key.partition("|")
    return organism, drug


class AntibiogramStore:
    def __init__(self, client: firestore.Client) -> None:
        self._collection = client.collection(ANTIBIOGRAM_COLLECTION)

    def load(self, facility_id: str, period_start: datetime, period_end: datetime) -> Antibiogram:
        snapshot = self._collection.document(facility_id).get()
        if not snapshot.exists:
            return Antibiogram(
                facility_id=facility_id, period_start=period_start, period_end=period_end
            )

        data = snapshot.to_dict() or {}
        grid = Antibiogram(
            facility_id=facility_id,
            period_start=_as_utc(data.get("period_start")) or period_start,
            period_end=_as_utc(data.get("period_end")) or period_end,
            revision=int(data.get("revision", 0)),
        )
        for key, raw in (data.get("cells") or {}).items():
            organism, drug = _split_key(key)
            grid.cells[(organism, drug)] = Cell(
                organism=organism,
                drug=drug,
                tested=int(raw.get("tested", 0)),
                susceptible=int(raw.get("susceptible", 0)),
                contributing_isolates=tuple(raw.get("contributing_isolates") or ()),
            )
        grid._first_isolate = {
            tuple(k.split("|", 1)): v for k, v in (data.get("first_isolate") or {}).items()
        }
        grid.excluded = [tuple(pair) for pair in (data.get("excluded") or [])]
        return grid

    def save(self, grid: Antibiogram) -> None:
        self._collection.document(grid.facility_id).set(
            {
                "period_start": grid.period_start,
                "period_end": grid.period_end,
                "revision": grid.revision,
                "updated_at": datetime.now(timezone.utc),
                "cells": {
                    _cell_key(organism, drug): {
                        "tested": cell.tested,
                        "susceptible": cell.susceptible,
                        "contributing_isolates": list(cell.contributing_isolates),
                    }
                    for (organism, drug), cell in grid.cells.items()
                },
                "first_isolate": {
                    f"{patient}|{organism}": isolate_id
                    for (patient, organism), isolate_id in grid._first_isolate.items()
                },
                "excluded": [list(pair) for pair in grid.excluded],
            }
        )

    def reset(self, facility_id: str) -> None:
        self._collection.document(facility_id).delete()

    def view(self, grid: Antibiogram) -> dict[str, Any]:
        """What the UI renders. Suppressed cells carry their reason, never a hidden number."""
        return {
            "facility_id": grid.facility_id,
            "revision": grid.revision,
            "organisms": grid.organisms(),
            "drugs": grid.drugs(),
            "excluded_count": len(grid.excluded),
            "cells": [
                {
                    "organism": organism,
                    "drug": drug,
                    "tested": cell.tested,
                    "susceptible": cell.susceptible,
                    "percent_susceptible": cell.percent_susceptible,
                    "suppressed": cell.suppressed,
                    "suppression_reason": cell.suppression_reason.value or None,
                    "contributing_isolates": list(cell.contributing_isolates),
                }
                for (organism, drug), cell in sorted(grid.cells.items())
            ],
        }


class CourseStore:
    def __init__(self, client: firestore.Client) -> None:
        self._collection = client.collection(COURSES_COLLECTION)

    def save(self, course: Any) -> None:
        self._collection.document(course.course_id).set(
            {
                "run_id": course.run_id,
                "patient_id": course.patient_id,
                "started_at": course.started_at,
                "regimen": list(course.regimen),
                "indication": course.indication,
                "allergies": list(course.allergies),
                "renal_impairment": course.renal_impairment,
                "is_empiric": course.is_empiric,
                "status": course.status.value,
                "discharged_at": course.discharged_at,
                "decisions": course.decisions,
            }
        )

    def get(self, course_id: str) -> dict[str, Any] | None:
        snapshot = self._collection.document(course_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def all(self) -> list[dict[str, Any]]:
        return [{"course_id": d.id, **(d.to_dict() or {})} for d in self._collection.stream()]

    def record_due_action(self, course_id: str, action: dict[str, Any]) -> None:
        document = self._collection.document(course_id)
        snapshot = document.get()
        if not snapshot.exists:
            raise KeyError(course_id)
        data = snapshot.to_dict() or {}
        actions = [
            item for item in data.get("due_actions", [])
            if item.get("wake_id") != action["wake_id"]
        ]
        actions.append(dict(action))
        data["due_actions"] = actions
        document.set(data)

    def reset(self) -> int:
        deleted = 0
        for doc in self._collection.stream():
            doc.reference.delete()
            deleted += 1
        return deleted


class IsolateStore:
    """Latest structured isolate per pseudonymous patient, without raw report text."""

    def __init__(self, client: firestore.Client) -> None:
        self._collection = client.collection(LATEST_ISOLATES_COLLECTION)

    @staticmethod
    def _patient_key(patient_id: str) -> str:
        return hashlib.sha256(patient_id.encode("utf-8")).hexdigest()[:24]

    def save(self, isolate: Isolate, artifact_id: str) -> None:
        self._collection.document(self._patient_key(isolate.patient_id)).set(
            {
                "patient_id": isolate.patient_id,
                "artifact_id": artifact_id,
                "isolate_id": isolate.isolate_id,
                "organism": isolate.organism,
                "collected_at": isolate.collected_at,
                "specimen_type": isolate.specimen_type,
                "is_surveillance": isolate.is_surveillance,
                "susceptibilities": [
                    {
                        "drug": item.drug,
                        "interpretation": item.interpretation.value,
                        "mic": item.mic,
                        "source_ref": item.source_ref,
                    }
                    for item in isolate.susceptibilities
                ],
                "updated_at": datetime.now(timezone.utc),
            }
        )

    def latest_for_patient(self, patient_id: str) -> dict[str, Any] | None:
        snapshot = self._collection.document(self._patient_key(patient_id)).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        isolate = Isolate(
            isolate_id=data["isolate_id"],
            patient_id=data["patient_id"],
            organism=data["organism"],
            collected_at=_as_utc(data.get("collected_at")) or datetime.now(timezone.utc),
            susceptibilities=tuple(
                Susceptibility(
                    drug=item["drug"],
                    interpretation=Interpretation(item["interpretation"]),
                    mic=item.get("mic"),
                    source_ref=item.get("source_ref"),
                )
                for item in data.get("susceptibilities", [])
            ),
            specimen_type=data.get("specimen_type", "unknown"),
            is_surveillance=bool(data.get("is_surveillance", False)),
        )
        return {"artifact_id": data["artifact_id"], "isolate": isolate}

    def reset(self) -> int:
        deleted = 0
        for doc in self._collection.stream():
            doc.reference.delete()
            deleted += 1
        return deleted


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
