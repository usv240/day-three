from datetime import datetime, timezone

from day_three.wake_actions import CourseActionExecutor
from spine.clock import ClockState, MemoryClockStateStore, SimulatedClock
from spine.wake import MemoryWakeStore, Wake, WakeScheduler


class Courses:
    def __init__(self):
        self.actions = []

    def get(self, course_id):
        return {"patient_id": "pt_synthetic"} if course_id == "course_demo" else None

    def record_due_action(self, course_id, action):
        self.actions.append(action)


class Isolates:
    def latest_for_patient(self, patient_id):
        return None


class MemoryBank:
    def recall_course(self, course_id):
        return {
            "recalled": True,
            "count": 1,
            "scope": {"application": "day-three", "course_ref": "hashed"},
            "facts": ["Deidentified synthetic course handoff."],
            "authoritative_store": "Firestore",
        }


def test_due_wake_recalls_managed_cross_session_handoff_without_driving_the_action():
    clock = SimulatedClock(
        MemoryClockStateStore(
            ClockState(frozen_at=datetime(2026, 8, 20, tzinfo=timezone.utc))
        )
    )
    scheduler = WakeScheduler(MemoryWakeStore(), clock)
    wake = Wake(
        wake_id="wk_memory",
        run_id="run_memory",
        kind="iv_to_oral_review",
        due_at=clock.now(),
        payload={"course_id": "course_demo"},
    )

    result = CourseActionExecutor(
        Courses(), Isolates(), scheduler, memory_bank=MemoryBank()
    ).execute(wake)

    assert result["action"] == "iv_to_oral_review_materialized"
    assert result["managed_memory"]["recalled"] is True
    assert result["managed_memory"]["authoritative_store"] == "Firestore"
    assert result["requires_pharmacist_approval"] is True
