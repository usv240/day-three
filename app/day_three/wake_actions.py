"""Typed work executed when a Day Three course wake becomes due."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from day_three.course import WakeKind
from day_three.reconcile import PatientContext, Reconciler
from spine.verify import Verifier
from spine.wake import Wake


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

    def __init__(self, courses, isolates, scheduler, shortages=None) -> None:
        self._courses = courses
        self._isolates = isolates
        self._scheduler = scheduler
        self._shortages = shortages

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
                ("course_review_materialized", "A bounded pharmacist review task was created."),
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
        self._courses.record_due_action(course_id, recorded)
        return recorded

    def _reconcile_or_replan(self, wake: Wake, course: dict[str, Any]) -> dict[str, Any]:
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
        artifacts = {
            artifact_id: "\n".join(
                susceptibility.source_ref or ""
                for susceptibility in isolate.susceptibilities
                if susceptibility.source_ref
            )
        }
        shortage_snapshot = self._shortages.get() if self._shortages is not None else None
        active_shortages = frozenset((shortage_snapshot or {}).get("active_formulary_shortages", []))
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
        verifier = Verifier(artifacts=artifacts, records=reconciler.records_for(isolate))
        claims = [
            {
                "text": claim.text,
                "accepted": verifier.verify(claim).accepted,
                "quoted": claim.source_refs[0].quoted_text if claim.source_refs else None,
            }
            for claim in recommendation.claims
        ]
        grounded = all(claim["accepted"] for claim in claims)
        if not grounded:
            return {
                "action": "recommendation_halted",
                "detail": "The automatic draft failed source verification and was withheld.",
                "claims": claims,
            }
        return {
            "action": "pharmacist_review_draft_created",
            "detail": recommendation.headline,
            "recommendation_kind": recommendation.kind.value,
            "suggested": recommendation.suggested,
            "claims": claims,
            "all_claims_grounded": True,
            "shortage_source_last_updated": (shortage_snapshot or {}).get("source_last_updated"),
        }
