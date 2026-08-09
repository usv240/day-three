"""Course Watch tests.

The property that matters here is the one Rules.md line 378 asks about: context maintained across
weeks of asynchronous operations. These tests compress five weeks and assert that the right agent
wakes at the right time, on its own, with nobody touching anything in between.
"""

from datetime import timedelta

import pytest

from day_three.course import (
    LADDER,
    READMISSION_WINDOW,
    Course,
    CourseStatus,
    CourseWatch,
    WakeKind,
)
from spine.clock import MemoryClockStateStore, SimulatedClock
from spine.wake import MemoryWakeStore, WakeScheduler, WakeStatus


@pytest.fixture
def clock():
    return SimulatedClock(MemoryClockStateStore())


@pytest.fixture
def scheduler(clock):
    return WakeScheduler(MemoryWakeStore(), clock)


@pytest.fixture
def watch(scheduler, clock):
    return CourseWatch(scheduler, clock)


@pytest.fixture
def course(clock):
    return Course(
        course_id="crs_1",
        run_id="run_1",
        patient_id="pt_1",
        started_at=clock.now(),
        regimen=("piperacillin-tazobactam", "vancomycin"),
        indication="suspected sepsis",
    )


def test_opening_a_course_registers_the_whole_ladder(watch, scheduler, course):
    """Registered up front so a crash between wakes cannot lose the rest of the course."""
    registered = watch.open_course(course)
    assert len(registered) == len(LADDER)
    assert len(scheduler.pending_for("run_1")) == len(LADDER)


def test_reopening_a_course_is_idempotent(watch, scheduler, course):
    watch.open_course(course)
    watch.open_course(course)
    assert len(scheduler.pending_for("run_1")) == len(LADDER)


def test_the_two_stop_date_checks_are_distinct_wakes(watch, scheduler, course):
    """They share a kind, so the offset has to disambiguate them or one would overwrite the other."""
    watch.open_course(course)
    stop_checks = [
        w for w in scheduler.pending_for("run_1") if w.kind == WakeKind.STOP_DATE_CHECK.value
    ]
    assert len(stop_checks) == 3
    assert len({w.wake_id for w in stop_checks}) == 3


def test_the_ladder_fires_in_clinical_order_over_five_weeks(watch, scheduler, clock, course):
    watch.open_course(course)

    fired: list[str] = []
    for _ in range(20):
        clock.advance(timedelta(days=1))
        for wake in scheduler.scan_due():
            fired.append(wake.kind)
            scheduler.complete(wake.wake_id)

    assert fired == [
        WakeKind.DEESCALATION_REVIEW.value,
        WakeKind.IV_TO_ORAL_REVIEW.value,
        WakeKind.STOP_DATE_CHECK.value,
        WakeKind.STOP_DATE_CHECK.value,
        WakeKind.STOP_DATE_CHECK.value,
    ]


def test_nothing_fires_in_the_first_forty_seven_hours(watch, scheduler, clock, course):
    watch.open_course(course)
    clock.advance(timedelta(hours=47))
    assert scheduler.scan_due() == []


def test_the_agent_wakes_itself_at_hour_forty_eight(watch, scheduler, clock, course):
    watch.open_course(course)
    clock.advance(timedelta(hours=49))
    fired = scheduler.scan_due()
    assert [w.kind for w in fired] == [WakeKind.DEESCALATION_REVIEW.value]


def test_the_course_horizon_is_about_five_weeks(watch, course):
    horizon = watch.horizon(course)
    assert timedelta(days=40) <= horizon <= timedelta(days=50)


# --- Discharge -------------------------------------------------------------------


def test_discharge_cancels_remaining_inpatient_wakes(watch, scheduler, clock, course):
    """Reviewing an inpatient regimen for someone who went home would prepare an escalation about
    nothing."""
    watch.open_course(course)
    clock.advance(timedelta(days=3))
    for wake in scheduler.scan_due():
        scheduler.complete(wake.wake_id)

    cancelled, _readmission = watch.discharge(course, clock.now())
    assert cancelled >= 1
    assert course.status is CourseStatus.DISCHARGED


def test_discharge_arms_the_readmission_check(watch, scheduler, clock, course):
    watch.open_course(course)
    _cancelled, readmission = watch.discharge(course, clock.now())
    assert readmission.kind == WakeKind.READMISSION_CHECK.value

    clock.advance(READMISSION_WINDOW + timedelta(days=1))
    fired = scheduler.scan_due()
    assert [w.kind for w in fired] == [WakeKind.READMISSION_CHECK.value]


def test_the_readmission_check_survives_the_discharge_cancellation(watch, scheduler, clock, course):
    """It is registered after the cancellation sweep, so it must not be caught by it."""
    watch.open_course(course)
    watch.discharge(course, clock.now())
    pending = scheduler.pending_for("run_1")
    assert [w.kind for w in pending] == [WakeKind.READMISSION_CHECK.value]


def test_cancelled_wakes_are_marked_not_deleted(watch, scheduler, clock, course):
    """The audit trail must show what would have happened and why it did not."""
    watch.open_course(course)
    watch.discharge(course, clock.now())

    all_wakes = scheduler._store.for_run("run_1")
    cancelled = [w for w in all_wakes if w.status is WakeStatus.CANCELLED]
    assert len(cancelled) == len(LADDER)
    assert all(w.cancelled_reason == "patient discharged" for w in cancelled)


def test_discontinuing_therapy_cancels_everything(watch, scheduler, clock, course):
    watch.open_course(course)
    cancelled = watch.discontinue(course, "adverse reaction")
    assert cancelled == len(LADDER)
    assert course.status is CourseStatus.DISCONTINUED

    clock.advance(timedelta(days=60))
    assert scheduler.scan_due() == []


# --- Durable context -------------------------------------------------------------


def test_decisions_accumulate_as_small_structured_records(watch, clock, course):
    """Facts, not transcripts. This is why week five costs no more context than hour 48."""
    course.record_decision(WakeKind.DEESCALATION_REVIEW, "narrowed to ceftriaxone", clock.now())
    course.record_decision(WakeKind.IV_TO_ORAL_REVIEW, "switched to oral", clock.now())
    assert len(course.decisions) == 2
    assert course.decisions[0]["outcome"] == "narrowed to ceftriaxone"


def test_every_wake_kind_has_a_plain_language_explanation():
    """Each one appears behind an info button in the UI. No jargon without a definition."""
    for kind in WakeKind:
        explanation = CourseWatch.explain(kind)
        assert len(explanation) > 20, f"{kind} has no explanation"
        assert explanation[0].isupper()


def test_the_readmission_explanation_names_the_feedback_loop():
    text = CourseWatch.explain(WakeKind.READMISSION_CHECK)
    assert "antibiogram" in text.lower()
