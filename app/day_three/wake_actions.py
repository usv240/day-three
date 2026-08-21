"""Typed work executed when a Day Three course wake becomes due."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from day_three.managed_memory import ManagedMemoryError
from day_three.course import CourseStatus, LADDER, WakeKind
from day_three.reconcile import PatientContext, Reconciler, claim_for_rendering
from spine.verify import Verifier
from spine.wake import Wake


# The last rung of the ladder, derived rather than typed, so adding a review moves it.
FINAL_RUNG_HOURS = int(max(offset for _kind, offset, _why in LADDER).total_seconds() // 3600)


REVIEW_BY_KIND = {
    WakeKind.IV_TO_ORAL_REVIEW.value: (
        "iv_to_oral_review_materialized",
        "A pharmacist review task was created for route conversion; no medication order changed.",
    ),
    WakeKind.STOP_DATE_CHECK.value: (
        "stop_date_review_materialized",
        "A pharmacist review task was created for continued therapy; no medication order changed.",
    ),
    WakeKind.DISCHARGE_RECON.value: (
        "discharge_review_materialized",
        "A discharge reconciliation task was created; no prescription was sent or changed.",
    ),
    WakeKind.READMISSION_CHECK.value: (
        "readmission_review_materialized",
        "A readmission learning task was created for pharmacist review.",
    ),
}


class CourseActionExecutor:
    """Turn a claimed wake into a bounded, idempotent stewardship action."""

    def __init__(self, courses, isolates, scheduler, shortages=None, memory_bank=None) -> None:
        self._courses = courses
        self._isolates = isolates
        self._scheduler = scheduler
        self._shortages = shortages
        self._memory_bank = memory_bank

    def execute(self, wake: Wake) -> dict[str, Any]:
        course_id = str(wake.payload.get("course_id", ""))
        if not course_id:
            return {
                "action": "generic_wake_recorded",
                "detail": "The wake became due; it is not attached to a Day Three course.",
            }

        course = self._courses.get(course_id)
        if course is None:
            raise KeyError(f"wake {wake.wake_id} refers to missing course {course_id}")

        if wake.kind == WakeKind.DEESCALATION_REVIEW.value:
            result = self._reconcile_or_replan(wake, course)
        else:
            action, detail = REVIEW_BY_KIND.get(
                wake.kind,
                (
                    "course_review_materialized",
                    "A bounded pharmacist review task was created.",
                ),
            )
            result = {"action": action, "detail": detail}

        recorded = {
            "wake_id": wake.wake_id,
            "kind": wake.kind,
            "due_at": wake.due_at.isoformat(),
            "requires_pharmacist_approval": True,
            "external_side_effect": False,
            **result,
        }
        if self._memory_bank is not None:
            try:
                recorded["managed_memory"] = self._memory_bank.recall_course(course_id)
            except ManagedMemoryError as exc:
                recorded["managed_memory"] = {
                    "recalled": False,
                    "reason": str(exc),
                    "authoritative_store": "Firestore",
                }
        self._courses.record_due_action(course_id, recorded)
        self._close_if_ladder_exhausted(course_id, wake)
        return recorded

    def _close_if_ladder_exhausted(self, course_id: str, wake: Wake) -> None:
        """Mark a course finished once its last scheduled review has run.

        The ladder's final rung is the day-14 stop-date check. Without this the course stays
        ACTIVE forever: the wakes simply run out and nothing records that the agent is done
        watching. A course that can never reach a terminal state cannot be counted, audited, or
        handed over.
        """
        if wake.kind != WakeKind.STOP_DATE_CHECK.value:
            return
        if int(wake.payload.get("offset_hours", 0)) < FINAL_RUNG_HOURS:
            return
        try:
            self._courses.set_status(course_id, CourseStatus.CLOSED.value, wake.due_at)
        except (KeyError, AttributeError):
            # An older store without set_status must not break a wake that already succeeded.
            pass

    def _reconcile_or_replan(
        self, wake: Wake, course: dict[str, Any]
    ) -> dict[str, Any]:
        isolate_record = self._isolates.latest_for_patient(course["patient_id"])
        if isolate_record is None:
            recheck_count = int(wake.payload.get("recheck_count", 0))
            result: dict[str, Any] = {
                "action": "culture_result_missing",
                "detail": "No final culture is available, so the agent refused to guess.",
                "recheck_registered": False,
            }
            if recheck_count < 1:
                recheck = self._scheduler.sleep_until(
                    run_id=wake.run_id,
                    kind=WakeKind.DEESCALATION_REVIEW.value,
                    due_at=wake.due_at + timedelta(hours=24),
                    payload={
                        **wake.payload,
                        "recheck_count": recheck_count + 1,
                    },
                    discriminator=f"{course['patient_id']}:culture-recheck:{recheck_count + 1}",
                )
                result.update(
                    {
                        "detail": "No final culture is available. One hour-72 recheck was registered instead of guessing.",
                        "recheck_registered": True,
                        "recheck_wake_id": recheck.wake_id,
                    }
                )
            return result

        isolate = isolate_record["isolate"]
        artifact_id = isolate_record["artifact_id"]
        # Verify against the redacted report text stored at intake, never against a document
        # rebuilt from the quotes themselves. Rebuilding made the containment check circular:
        # the artifact WAS the concatenation of the quotes, so no quote could ever fail to be
        # found and a hallucinated susceptibility line would verify against itself.
        #
        # If an older record predates stored text there is nothing truthful to check against, so
        # the artifact stays empty and every quote fails. That rejects the claims and suppresses
        # the rendered sentences, which is the correct direction to fail.
        artifact_text = isolate_record.get("artifact_text") or ""
        artifacts = {artifact_id: artifact_text}
        shortage_snapshot = (
            self._shortages.get() if self._shortages is not None else None
        )
        active_shortages = frozenset(
            (shortage_snapshot or {}).get("active_formulary_shortages", [])
        )
        reconciler = Reconciler(shortages=active_shortages)
        recommendation = reconciler.reconcile(
            PatientContext(
                patient_id=course["patient_id"],
                regimen=tuple(course.get("regimen", ())),
                allergies=tuple(course.get("allergies", ())),
                renal_impairment=bool(course.get("renal_impairment", False)),
            ),
            isolate,
            artifact_id,
        )
        verifier = Verifier(
            artifacts=artifacts, records=reconciler.records_for(isolate)
        )
        claims = [
            claim_for_rendering(claim, verifier) for claim in recommendation.claims
        ]
        grounded = all(claim["accepted"] for claim in claims)
        if not grounded:
            return {
                "action": "recommendation_halted",
                "detail": "The automatic draft failed source verification and was withheld.",
                "claims": claims,
                # Stated explicitly so a client never has to infer groundedness from the absence
                # of a field. Both branches answer the same question.
                "all_claims_grounded": False,
            }
        return {
            "action": "pharmacist_review_draft_created",
            "detail": recommendation.headline,
            "recommendation_kind": recommendation.kind.value,
            "suggested": recommendation.suggested,
            "claims": claims,
            "all_claims_grounded": True,
            "shortage_source_last_updated": (shortage_snapshot or {}).get(
                "source_last_updated"
            ),
        }
