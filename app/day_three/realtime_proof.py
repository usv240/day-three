"""Proof that a wake fires on wall-clock time, with nobody watching.

Why this exists. The judge console compresses a fourteen-day review ladder into a few button
presses by advancing a simulated clock, and it says so on screen. That is honest, but it leaves
the headline claim -- *the agent wakes itself* -- resting on a clock the visitor just moved. A
sceptical reader is right to discount it.

This module registers a wake against the **real** clock, on its own project namespace, and
records nothing but observable facts: when it was registered, when it was due, when a worker
claimed it, which worker, and how many seconds of real time actually elapsed. No simulated clock
can touch it, and the visitor cannot advance it. The wait is the evidence.

Why this does not ride the shared wake table. The spine substrate is shared with another
deployment whose scheduled worker scans that table unfiltered, on its own simulated clock. It
claimed and completed the first version of these proof wakes with *its* handler, which meant the
proof record was never marked fired and the evidence silently vanished while the wake showed
`done`. A proof that another service can consume is not a proof. So the due-work record lives in
its own collection that only this service scans, and only `/internal/scan-due-realtime` -- driven
by `day-three-realtime-wake-scan` every minute on wall-clock time -- can claim it.

It is still a durable wake in every sense that matters: a persisted due time, an unattended
worker that discovers it, real elapsed time, and an idempotent claim.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

PROJECT = "day-three-realtime"
KIND = "realtime_wake_proof"
COLLECTION = "realtime_proofs"

MIN_DELAY_SECONDS = 60
#: How far back the scanner looks. Comfortably beyond MAX_DELAY_SECONDS so a legitimate proof
#: cannot age out, short enough that fired records leave the query window quickly.
LOOKBACK = timedelta(hours=2)
MAX_DELAY_SECONDS = 900
DEFAULT_DELAY_SECONDS = 180


@dataclass(frozen=True)
class ProofRecord:
    proof_id: str
    run_id: str
    wake_id: str
    registered_at: datetime
    due_at: datetime
    fired_at: datetime | None
    fired_by: str | None

    @property
    def fired(self) -> bool:
        return self.fired_at is not None

    def view(self, now: datetime) -> dict[str, Any]:
        waited = (self.fired_at - self.registered_at).total_seconds() if self.fired_at else None
        remaining = max(0.0, (self.due_at - now).total_seconds())
        return {
            "proof_id": self.proof_id,
            "run_id": self.run_id,
            "wake_id": self.wake_id,
            "clock": "wall",
            "registered_at": self.registered_at.isoformat(),
            "due_at": self.due_at.isoformat(),
            "fired_at": self.fired_at.isoformat() if self.fired_at else None,
            "fired_by_worker": self.fired_by,
            "fired": self.fired,
            "real_seconds_waited": round(waited, 1) if waited is not None else None,
            "seconds_until_due": round(remaining, 1) if not self.fired else 0.0,
            "status": "fired" if self.fired else ("due" if remaining <= 0 else "sleeping"),
            "note": (
                "Registered against the wall clock and dispatched by the scheduled worker. "
                "The simulated demo clock cannot advance, delay, or dispatch this record."
            ),
        }


class RealtimeProofStore:
    def __init__(self, client, collection: str = COLLECTION) -> None:
        self._collection = client.collection(collection)

    def save(self, record: ProofRecord) -> None:
        self._collection.document(record.proof_id).set({
            "proof_id": record.proof_id,
            "run_id": record.run_id,
            "wake_id": record.wake_id,
            "registered_at": record.registered_at,
            "due_at": record.due_at,
            "fired_at": record.fired_at,
            "fired_by": record.fired_by,
        })

    def get(self, proof_id: str) -> ProofRecord | None:
        snapshot = self._collection.document(proof_id).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return ProofRecord(
            proof_id=data["proof_id"],
            run_id=data["run_id"],
            wake_id=data["wake_id"],
            registered_at=_as_datetime(data.get("registered_at")),
            due_at=_as_datetime(data.get("due_at")),
            fired_at=_as_datetime(data.get("fired_at")),
            fired_by=data.get("fired_by"),
        )

    def mark_fired(self, proof_id: str, fired_at: datetime, worker: str) -> None:
        """Idempotent by proof_id: a second claim overwrites with the same observable facts."""
        self._collection.document(proof_id).set(
            {"fired_at": fired_at, "fired_by": worker}, merge=True
        )

    def due(self, now: datetime, limit: int = 20) -> list[ProofRecord]:
        """Proof records whose due time has passed and which no worker has claimed yet.

        Ordering is by due time on a single field so this needs no composite index; the
        unclaimed filter is applied in memory, which is safe at this collection's size.

        Uses the keyword `FieldFilter` form like the rest of the codebase. The positional form
        still works but emits a UserWarning on every call, and this runs once a minute forever,
        so it filled Cloud Logging with deprecation noise a judge would scroll through.
        """
        from google.cloud import firestore

        # Two things went wrong here in production, and the second is the subtle one.
        #
        # The query used to carry `.limit(limit)`. Firestore applied it before the unclaimed
        # check, which runs in memory, so the page came back full of already-fired records and
        # the filter then discarded every one. Once twenty claimed proofs existed the scanner
        # stopped reaching pending ones and the timer silently never fired again. The limit now
        # applies after the filter, so a claimed record can never displace a pending one.
        #
        # Filtering unclaimed in the query instead would need a composite index on
        # (fired_at, due_at). The window below keeps this to range filters on a single field,
        # which needs no index at all, and bounds how much is ever read: a proof nobody claimed
        # within the lookback is stale, because the longest delay a caller can request is fifteen
        # minutes and an hours-old record firing now would report a wait that never happened.
        floor = now - LOOKBACK

        found: list[ProofRecord] = []
        for snapshot in (
            self._collection.where(filter=firestore.FieldFilter("due_at", ">=", floor))
            .where(filter=firestore.FieldFilter("due_at", "<=", now))
            .order_by("due_at")
            .stream()
        ):
            data = snapshot.to_dict() or {}
            if data.get("fired_at") is not None:
                continue
            if len(found) >= limit:
                break
            found.append(
                ProofRecord(
                    proof_id=data["proof_id"],
                    run_id=data.get("run_id", ""),
                    wake_id=data.get("wake_id", ""),
                    registered_at=_as_datetime(data.get("registered_at")),
                    due_at=_as_datetime(data.get("due_at")),
                    fired_at=None,
                    fired_by=None,
                )
            )
        return found


def _as_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if hasattr(value, "timestamp_pb"):  # Firestore returns its own timestamp wrapper
        return value.replace(tzinfo=value.tzinfo)
    return None


def clamp_delay(seconds: float | None) -> int:
    if seconds is None:
        return DEFAULT_DELAY_SECONDS
    return int(max(MIN_DELAY_SECONDS, min(MAX_DELAY_SECONDS, seconds)))


def new_proof_id() -> str:
    return f"rt_{uuid.uuid4().hex[:12]}"


def due_at_for(now: datetime, delay_seconds: int) -> datetime:
    return now + timedelta(seconds=delay_seconds)
