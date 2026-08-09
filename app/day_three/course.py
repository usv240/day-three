"""Course Watch: one agent that owns an antibiotic course for about five weeks.

Rules.md line 378 requires the Fortified Enterprise Fleet track to demonstrate context maintained
"across weeks of asynchronous operations". An earlier version of this design woke once, at hour
48. That was both a rules gap and a clinical one: hour 48 is the first of five real stewardship
decision points, not the only one.

So one Course Watch owns the whole course. It registers the entire wake ladder at the start, so
the schedule survives a crash, then sleeps between decisions.

The last wake matters most architecturally. `readmission_check` feeds its outcome back into the
Curator, so a course that ends in a resistant readmission changes what the hospital believes about
its own resistance patterns. That turns the system from a pipeline into a loop: the consequence of
a decision becomes evidence for the next one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from spine.clock import Clock
from spine.wake import Wake, WakeScheduler


class WakeKind(StrEnum):
    DEESCALATION_REVIEW = "deescalation_review"
    IV_TO_ORAL_REVIEW = "iv_to_oral_review"
    STOP_DATE_CHECK = "stop_date_check"
    DISCHARGE_RECON = "discharge_recon"
    READMISSION_CHECK = "readmission_check"


class CourseStatus(StrEnum):
    ACTIVE = "active"
    DISCHARGED = "discharged"
    DISCONTINUED = "discontinued"
    CLOSED = "closed"


# The ladder, in clinical order. Each entry is (kind, offset from therapy start, why).
# Held as data rather than code so the conformance page can render it and a clinician can read it.
LADDER: tuple[tuple[WakeKind, timedelta, str], ...] = (
    (
        WakeKind.DEESCALATION_REVIEW,
        timedelta(hours=48),
        "The lab result is back. Is the patient still on the right drug, or can it be narrowed?",
    ),
    (
        WakeKind.IV_TO_ORAL_REVIEW,
        timedelta(days=5),
        "Can this patient move from an intravenous drug to a tablet? Removes line days.",
    ),
    (
        WakeKind.STOP_DATE_CHECK,
        timedelta(days=7),
        "Has the planned stop date passed with no documented reason to continue?",
    ),
    (
        WakeKind.STOP_DATE_CHECK,
        timedelta(days=10),
        "Second stop date check.",
    ),
    (
        WakeKind.STOP_DATE_CHECK,
        timedelta(days=14),
        "Prolonged therapy beyond two weeks is a documented stewardship target.",
    ),
)

# Fired relative to discharge rather than to therapy start.
READMISSION_WINDOW = timedelta(days=30)


@dataclass
class Course:
    """The durable context carried across five weeks.

    Deliberately small and structured. What we send to a model at week five is no larger than at
    hour 48, which is the property the context meter asserts.
    """

    course_id: str
    run_id: str
    patient_id: str
    started_at: datetime
    regimen: tuple[str, ...]
    indication: str
    is_empiric: bool = True
    status: CourseStatus = CourseStatus.ACTIVE
    discharged_at: datetime | None = None
    decisions: list[dict] = field(default_factory=list)

    def record_decision(self, kind: WakeKind, outcome: str, at: datetime) -> None:
        self.decisions.append({"kind": kind.value, "outcome": outcome, "at": at.isoformat()})


class CourseWatch:
    """Registers and manages the wake ladder for one antibiotic course."""

    def __init__(self, scheduler: WakeScheduler, clock: Clock) -> None:
        self._scheduler = scheduler
        self._clock = clock

    def open_course(self, course: Course) -> list[Wake]:
        """Register the entire ladder at once.

        Registering everything up front, rather than scheduling the next wake each time one
        fires, means a crash between wakes cannot lose the rest of the course. The wake ids are
        deterministic, so re-running this after a restart is a no-op rather than a duplicate.
        """
        registered: list[Wake] = []
        for kind, offset, _why in LADDER:
            registered.append(
                self._scheduler.sleep_until(
                    run_id=course.run_id,
                    kind=kind.value,
                    due_at=course.started_at + offset,
                    payload={
                        "course_id": course.course_id,
                        "patient_id": course.patient_id,
                        "offset_hours": offset.total_seconds() / 3600,
                    },
                    # Two stop date checks share a kind, so the offset disambiguates them.
                    discriminator=f"{course.course_id}:{int(offset.total_seconds())}",
                )
            )
        return registered

    def discharge(self, course: Course, at: datetime) -> tuple[int, Wake]:
        """Patient goes home.

        Two things happen. Remaining inpatient wakes are cancelled, because reviewing an
        inpatient regimen for someone who left would page a pharmacist about nothing. And a
        readmission check is armed 30 days out, which is the wake that closes the loop back into
        the antibiogram.
        """
        course.status = CourseStatus.DISCHARGED
        course.discharged_at = at

        cancelled = self._scheduler.cancel_run(course.run_id, "patient discharged")

        readmission = self._scheduler.sleep_until(
            run_id=course.run_id,
            kind=WakeKind.READMISSION_CHECK.value,
            due_at=at + READMISSION_WINDOW,
            payload={"course_id": course.course_id, "patient_id": course.patient_id},
            discriminator=f"{course.course_id}:readmission",
        )
        return cancelled, readmission

    def discontinue(self, course: Course, reason: str) -> int:
        """Therapy stopped early. Cancel everything, including any readmission check."""
        course.status = CourseStatus.DISCONTINUED
        return self._scheduler.cancel_run(course.run_id, f"therapy discontinued: {reason}")

    def horizon(self, course: Course) -> timedelta:
        """How long this agent will live. Used on the landing page and in the trace."""
        last_inpatient = max(offset for _kind, offset, _why in LADDER)
        return last_inpatient + READMISSION_WINDOW

    @staticmethod
    def explain(kind: WakeKind) -> str:
        """Plain language for the info button next to each wake in the UI."""
        for ladder_kind, _offset, why in LADDER:
            if ladder_kind is kind:
                return why
        if kind is WakeKind.DISCHARGE_RECON:
            return "Does the prescription going home match the reasoning that was used in hospital?"
        if kind is WakeKind.READMISSION_CHECK:
            return (
                "Did this patient come back within 30 days with a resistant organism? "
                "If so, the antibiogram learns from it."
            )
        return ""
