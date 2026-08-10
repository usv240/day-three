from datetime import datetime, timezone

from day_three.antibiogram import Interpretation, Isolate, Susceptibility
from day_three.wake_actions import CourseActionExecutor
from spine.clock import ClockState, MemoryClockStateStore, SimulatedClock
from spine.wake import MemoryWakeStore, Wake, WakeScheduler


class Courses:
    def __init__(self):
        self.course = {
            "patient_id": "pt_demo",
            "regimen": ["piperacillin-tazobactam"],
            "allergies": [],
            "renal_impairment": False,
        }
        self.actions = []

    def get(self, course_id):
        return self.course if course_id == "course_demo" else None

    def record_due_action(self, course_id, action):
        self.actions = [item for item in self.actions if item["wake_id"] != action["wake_id"]]
        self.actions.append(action)


class Isolates:
    def __init__(self, present=True):
        self.present = present

    def latest_for_patient(self, patient_id):
        if not self.present:
            return None
        isolate = Isolate(
            isolate_id="iso_demo",
            patient_id=patient_id,
            organism="Escherichia coli",
            collected_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
            susceptibilities=(
                Susceptibility(
                    drug="ceftriaxone",
                    interpretation=Interpretation.S,
                    source_ref="CEFTRIAXONE <=1 S",
                ),
            ),
        )
        return {"artifact_id": "art_demo", "isolate": isolate}


def wake(kind="deescalation_review", **payload):
    return Wake(
        wake_id="wk_demo",
        run_id="run_demo",
        kind=kind,
        due_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        payload={"course_id": "course_demo", "patient_id": "pt_demo", **payload},
    )


def scheduler():
    return WakeScheduler(
        MemoryWakeStore(),
        SimulatedClock(MemoryClockStateStore(ClockState(
            frozen_at=datetime(2026, 8, 10, tzinfo=timezone.utc)
        ))),
    )


def test_hour_48_wake_creates_grounded_pharmacist_review_draft():
    courses = Courses()
    result = CourseActionExecutor(courses, Isolates(), scheduler()).execute(wake())

    assert result["action"] == "pharmacist_review_draft_created"
    assert result["recommendation_kind"] == "deescalate"
    assert result["all_claims_grounded"] is True
    assert result["requires_pharmacist_approval"] is True
    assert result["external_side_effect"] is False


def test_missing_culture_replans_once_for_hour_72_instead_of_guessing():
    courses = Courses()
    sched = scheduler()
    result = CourseActionExecutor(courses, Isolates(False), sched).execute(wake())

    assert result["action"] == "culture_result_missing"
    assert result["recheck_registered"] is True
    pending = sched.scan_due()
    assert pending == []


def test_second_missing_culture_does_not_create_an_infinite_retry_loop():
    courses = Courses()
    result = CourseActionExecutor(courses, Isolates(False), scheduler()).execute(
        wake(recheck_count=1)
    )

    assert result["recheck_registered"] is False


def test_retry_replaces_visible_action_instead_of_duplicating_it():
    courses = Courses()
    executor = CourseActionExecutor(courses, Isolates(), scheduler())
    due = wake("iv_to_oral_review")

    executor.execute(due)
    executor.execute(due)

    assert len(courses.actions) == 1
    assert courses.actions[0]["action"] == "iv_to_oral_review_materialized"
