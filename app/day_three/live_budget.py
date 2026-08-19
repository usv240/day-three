"""A durable spend cap for the one public route that costs real money.

Every other public control replays a recorded response, so the site is free to rehearse. The
live-call route is different: it invokes Gemini on demand for anyone who presses the button,
with no credential in front of it. That is deliberate -- a judge should be able to prove the
model is really there -- but it needs a ceiling that survives process restarts and holds across
Cloud Run instances, so the ceiling lives in Firestore rather than in memory.

Two independent limits apply:

* a global daily cap, which bounds total spend for the day, and
* a per-caller daily cap, so one caller cannot consume the global budget alone.

The counter is read before it is incremented. Two simultaneous requests can therefore both pass
a check at the boundary and overshoot by the number of concurrent instances (at most three here).
That is accepted: overshooting a 40-call cap by two costs a fraction of a cent, whereas a
read-modify-write transaction on every press would add latency to the demo. Denied requests are
never counted, so a caller who hits the wall cannot push the day further into denial.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str
    global_used: int
    global_cap: int
    caller_used: int
    caller_cap: int

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "live_calls_used_today": self.global_used,
            "live_calls_allowed_today": self.global_cap,
            "your_calls_used_today": self.caller_used,
            "your_calls_allowed_today": self.caller_cap,
        }


class CounterStore(ABC):
    """Named integer counters that survive a restart."""

    @abstractmethod
    def read(self, key: str) -> int: ...

    @abstractmethod
    def bump(self, key: str) -> int: ...


class MemoryCounterStore(CounterStore):
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def read(self, key: str) -> int:
        return self.values.get(key, 0)

    def bump(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]


class FirestoreCounterStore(CounterStore):
    """Server-side atomic increment, so concurrent instances cannot lose a count."""

    def __init__(self, client, collection: str = "live_call_budget") -> None:
        self._client = client
        self._collection = collection

    def read(self, key: str) -> int:
        snapshot = self._client.collection(self._collection).document(key).get()
        if not snapshot.exists:
            return 0
        return int((snapshot.to_dict() or {}).get("count", 0))

    def bump(self, key: str) -> int:
        from google.cloud import firestore

        document = self._client.collection(self._collection).document(key)
        document.set({"count": firestore.Increment(1)}, merge=True)
        return self.read(key)


class LiveCallBudget:
    def __init__(
        self,
        store: CounterStore,
        *,
        daily_cap: int = 40,
        per_caller_cap: int = 4,
    ) -> None:
        self._store = store
        self.daily_cap = daily_cap
        self.per_caller_cap = per_caller_cap

    @classmethod
    def from_environment(cls, store: CounterStore) -> LiveCallBudget:
        return cls(
            store,
            daily_cap=int(os.environ.get("LIVE_CALL_DAILY_CAP", "40")),
            per_caller_cap=int(os.environ.get("LIVE_CALL_PER_CALLER_CAP", "4")),
        )

    def check(self, now: datetime, caller: str) -> BudgetDecision:
        """Report whether a live call may proceed, without consuming budget."""
        day = now.strftime("%Y-%m-%d")
        global_used = self._store.read(f"global_{day}")
        caller_used = self._store.read(f"caller_{day}_{caller}")

        if global_used >= self.daily_cap:
            reason = (
                "The shared daily live-model budget for this public demo is spent. "
                "Every recorded control still works, and the budget resets at 00:00 UTC."
            )
            allowed = False
        elif caller_used >= self.per_caller_cap:
            reason = (
                "You have used this demo's per-visitor live-call allowance for today. "
                "This cap keeps a credential-free page affordable to run."
            )
            allowed = False
        else:
            reason = "within budget"
            allowed = True

        return BudgetDecision(
            allowed=allowed,
            reason=reason,
            global_used=global_used,
            global_cap=self.daily_cap,
            caller_used=caller_used,
            caller_cap=self.per_caller_cap,
        )

    def consume(self, now: datetime, caller: str) -> BudgetDecision:
        """Count one allowed call. Call this only after the model call is attempted."""
        day = now.strftime("%Y-%m-%d")
        global_used = self._store.bump(f"global_{day}")
        caller_used = self._store.bump(f"caller_{day}_{caller}")
        return BudgetDecision(
            allowed=True,
            reason="counted",
            global_used=global_used,
            global_cap=self.daily_cap,
            caller_used=caller_used,
            caller_cap=self.per_caller_cap,
        )
