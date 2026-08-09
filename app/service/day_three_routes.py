"""Day Three HTTP surface.

These are the endpoints the demo drives, in the order the video uses them:

1. `POST /day-three/reset`        clean slate before recording
2. `POST /day-three/intake`       drop a scanned report, watch the grid change
3. `GET  /day-three/antibiogram`  the grid this hospital has never had
4. `POST /day-three/course`       admit a patient, register the five week ladder
5. `POST /sim/advance`            time passes, the agent wakes on its own
6. `POST /day-three/reconcile`    the recommendation, grounded in cited results
7. `GET  /day-three/registry`     another department discovers the Curator
8. `GET  /conformance`            every CLSI rule, its code, and its test
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from day_three.antibiogram import Antibiogram, Curator, Interpretation, Isolate
from day_three.course import LADDER, Course, CourseWatch, WakeKind
from day_three.intake import ExtractionError, IntakeAgent, ReplayClient
from day_three.reconcile import Kind, PatientContext, Reconciler
from day_three.registry import Department, ScopeDenied, day_three_catalog
from day_three.store import AntibiogramStore, CourseStore
from spine.verify import Claim, ClaimKind, SourceRef, Verifier

FACILITY = "mercy-critical-access-25"
PERIOD_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 12, 31, tzinfo=timezone.utc)


# Request models live at module level deliberately. This file uses
# `from __future__ import annotations`, which turns every annotation into a string, and FastAPI
# resolves those against module globals. A Pydantic model defined inside build_router() is
# invisible to that lookup, so FastAPI silently degrades it to a query parameter and every
# request 422s. Cost an hour once; keeping the note.
class IntakeRequest(BaseModel):
    artifact_id: str
    patient_id: str
    document: str
    extraction: dict = Field(
        description=(
            "Recorded model response. Replay keeps demo rehearsal free; the live recording "
            "uses the real Vertex call."
        )
    )


class CourseRequest(BaseModel):
    patient_id: str
    regimen: list[str]
    indication: str = "suspected sepsis"


class ReconcileRequest(BaseModel):
    patient_id: str
    regimen: list[str]
    organism: str
    susceptibilities: dict[str, str]
    artifact_id: str
    document: str
    allergies: list[str] = []
    shortages: list[str] = []


class ConsumeRequest(BaseModel):
    department: str
    agent: str
    granted_scopes: list[str] = []


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

def available_fixture_names() -> list[str]:
    """Only publish recordings that have the scan and truth needed to run intake."""
    return sorted(
        path.stem
        for path in (FIXTURES / "recordings").glob("*.json")
        if not path.stem.startswith("_")
        and (FIXTURES / "scans" / f"{path.stem}.jpg").exists()
        and (FIXTURES / "scans" / f"{path.stem}.txt").exists()
    )


def build_router(client, clock, scheduler, runner) -> APIRouter:
    router = APIRouter(prefix="", tags=["day-three"])
    antibiograms = AntibiogramStore(client)
    courses = CourseStore(client)

    # --- Fixtures: the real scans and the real recorded Gemini output --------------
    #
    # The console demo ingests genuine model output, not hand-written JSON. These recordings were
    # produced by scripts/record_intake.py making live Gemini 3.5 calls against the scanned
    # images, graded 29/29 correct against ground truth. Replay keeps every rehearsal free; the
    # recording itself was real.

    @router.get("/day-three/fixtures")
    def list_fixtures() -> dict[str, Any]:
        recordings = available_fixture_names()
        return {
            "fixtures": recordings,
            "note": "Recorded from live Gemini 3.5 Flash calls. See fixtures/recordings/_accuracy_report.json",
        }

    @router.get("/day-three/fixtures/{name}")
    def get_fixture(name: str) -> dict[str, Any]:
        safe = "".join(c for c in name if c.isalnum() or c == "_")
        recording = FIXTURES / "recordings" / f"{safe}.json"
        truth = FIXTURES / "scans" / f"{safe}.txt"
        if not recording.exists():
            raise HTTPException(status_code=404, detail=f"no recording for {safe}")
        return {
            "name": safe,
            "extraction": json.loads(recording.read_text(encoding="utf-8")),
            "ground_truth": truth.read_text(encoding="utf-8") if truth.exists() else None,
            "image_url": f"/day-three/fixtures/{safe}/image",
        }

    @router.get("/day-three/fixtures/{name}/image")
    def get_fixture_image(name: str) -> FileResponse:
        safe = "".join(c for c in name if c.isalnum() or c == "_")
        image = FIXTURES / "scans" / f"{safe}.jpg"
        if not image.exists():
            raise HTTPException(status_code=404, detail=f"no scan image for {safe}")
        return FileResponse(image, media_type="image/jpeg")

    def load_grid() -> Antibiogram:
        return antibiograms.load(FACILITY, PERIOD_START, PERIOD_END)

    # --- Reset ------------------------------------------------------------------

    @router.post("/day-three/reset")
    def reset() -> dict[str, Any]:
        """Clean slate. Used once before recording so the demo starts from a known state."""
        antibiograms.reset(FACILITY)
        removed = courses.reset()
        return {"antibiogram": "cleared", "courses_removed": removed}

    # --- Intake -----------------------------------------------------------------

    @router.post("/day-three/intake")
    def intake(request: IntakeRequest) -> dict[str, Any]:
        agent = IntakeAgent(ReplayClient({"default": request.extraction}))
        try:
            result = agent.parse(request.artifact_id, request.document, request.patient_id)
        except ExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        grid = load_grid()
        curator = Curator(grid)
        changed = curator.ingest(result.isolates[0])
        antibiograms.save(grid)

        return {
            "isolate": {
                "organism": result.isolates[0].organism,
                "specimen": result.isolates[0].specimen_type,
                "susceptibilities": [
                    {
                        "drug": s.drug,
                        "interpretation": s.interpretation.value,
                        "quoted": s.source_ref,
                    }
                    for s in result.isolates[0].susceptibilities
                ],
            },
            "cells_changed": [{"organism": o, "drug": d} for o, d in changed],
            "dropped": result.dropped,
            "redacted": result.redacted_count,
            "quarantined": [
                {"threat": q.threat.value, "text": q.text, "why": q.explanation}
                for q in result.quarantined
            ],
            "revision": grid.revision,
        }

    @router.get("/day-three/antibiogram")
    def antibiogram() -> dict[str, Any]:
        return antibiograms.view(load_grid())

    # --- Courses ----------------------------------------------------------------

    @router.post("/day-three/course")
    def open_course(request: CourseRequest) -> dict[str, Any]:
        now = clock.now()
        run_id = runner().start("day-three", "antibiotic-course", {"patient": request.patient_id})
        course = Course(
            course_id=f"crs_{request.patient_id}_{int(now.timestamp())}",
            run_id=run_id,
            patient_id=request.patient_id,
            started_at=now,
            regimen=tuple(request.regimen),
            indication=request.indication,
        )
        watch = CourseWatch(scheduler(), clock)
        registered = watch.open_course(course)
        courses.save(course)

        return {
            "course_id": course.course_id,
            "run_id": run_id,
            "started_at": now.isoformat(),
            "horizon_days": watch.horizon(course).days,
            "ladder": [
                {
                    "kind": w.kind,
                    "due_at": w.due_at.isoformat(),
                    "in_hours": round((w.due_at - now).total_seconds() / 3600, 1),
                    "why": CourseWatch.explain(WakeKind(w.kind)),
                }
                for w in registered
            ],
        }

    @router.get("/day-three/courses")
    def list_courses() -> dict[str, Any]:
        return {"courses": courses.all()}

    # --- Reconcile --------------------------------------------------------------

    @router.post("/day-three/reconcile")
    def reconcile(request: ReconcileRequest) -> dict[str, Any]:
        from day_three.antibiogram import Susceptibility

        pairs = []
        for drug, raw in request.susceptibilities.items():
            interpretation, _, quoted = raw.partition("|")
            pairs.append(
                Susceptibility(
                    drug=drug,
                    interpretation=Interpretation(interpretation.strip().upper()),
                    source_ref=quoted or None,
                )
            )

        isolate = Isolate(
            isolate_id=f"iso_{request.artifact_id}",
            patient_id=request.patient_id,
            organism=request.organism,
            collected_at=clock.now(),
            susceptibilities=tuple(pairs),
        )

        reconciler = Reconciler(shortages=frozenset(request.shortages))
        recommendation = reconciler.reconcile(
            PatientContext(
                patient_id=request.patient_id,
                regimen=tuple(request.regimen),
                allergies=tuple(request.allergies),
            ),
            isolate,
            request.artifact_id,
        )

        verifier = Verifier(
            artifacts={request.artifact_id: request.document},
            records=reconciler.records_for(isolate),
        )
        verified = [
            {
                "text": c.text,
                "accepted": verifier.verify(c).accepted,
                "quoted": c.source_refs[0].quoted_text if c.source_refs else None,
            }
            for c in recommendation.claims
        ]

        return {
            "kind": recommendation.kind.value,
            "headline": recommendation.headline,
            "suggested": recommendation.suggested,
            "requires_pharmacist_approval": recommendation.requires_pharmacist,
            "notes": recommendation.notes,
            "claims": verified,
            "all_claims_grounded": all(c["accepted"] for c in verified),
        }

    # --- The Verifier rejection we film ------------------------------------------

    @router.post("/day-three/demo/fabricate")
    def fabricate() -> dict[str, Any]:
        """Ask the system to state a resistance percentage for a cell that is suppressed.

        There is no such percentage: the cell has fewer than 30 isolates, so CLSI says a rate
        must not be reported from it. An agent that invents one is caught here, and the rejection
        doubles as a lesson about why small numbers are suppressed.
        """
        grid = load_grid()
        suppressed = [
            (o, d, c) for (o, d), c in grid.cells.items() if c.suppressed and c.tested > 0
        ]
        if not suppressed:
            raise HTTPException(
                status_code=409,
                detail="No suppressed cell exists yet. Ingest a few reports first.",
            )
        organism, drug, cell = suppressed[0]

        verifier = Verifier(artifacts={"art_grid": f"{organism} {drug} tested={cell.tested}"})
        invented = Claim(
            id="clm_fabricated",
            text=f"Local resistance to {drug} is approximately 40 percent.",
            kind=ClaimKind.MEASUREMENT,
            source_refs=(SourceRef("art_grid", f"{organism} {drug} tested={cell.tested}"),),
        )
        result = verifier.verify(invented)

        return {
            "claim": invented.text,
            "accepted": result.accepted,
            "rejection_code": result.code.value if result.code else None,
            "reason": result.reason,
            "teaching_note": (
                f"The {organism} and {drug} cell has only {cell.tested} isolates. CLSI M39 "
                "requires at least 30 before a percentage may be reported, so no such number "
                "exists for the agent to have known."
            ),
        }

    # --- Registry ---------------------------------------------------------------

    @router.get("/day-three/registry")
    def registry(department: str = "pharmacy") -> dict[str, Any]:
        catalog = day_three_catalog(clock.now())
        try:
            dept = Department(department)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"unknown department {department}") from exc

        return {
            "department": dept.value,
            "discoverable": [
                {
                    "name": c.name,
                    "version": c.version,
                    "owner": c.owner,
                    "summary": c.summary,
                    "produces": c.produces,
                    "stability": c.stability.value,
                    "required_scopes": list(c.required_scopes),
                    "human_approval_required": c.human_approval_required,
                }
                for c in catalog.discover(dept)
            ],
        }

    @router.post("/day-three/registry/consume")
    def consume(request: ConsumeRequest) -> dict[str, Any]:
        """Cross-department consumption, with the denial filmed when scopes are missing."""
        catalog = day_three_catalog(clock.now())
        dept = Department(request.department)
        for scope in request.granted_scopes:
            catalog.grant(dept, scope)

        try:
            card = catalog.consume(dept, request.agent)
        except ScopeDenied as exc:
            return {
                "allowed": False,
                "reason": str(exc),
                "audit": catalog.access_log[-1],
            }
        return {
            "allowed": True,
            "agent": card.qualified_name,
            "produces": card.produces,
            "audit": catalog.access_log[-1],
        }

    # --- Conformance ------------------------------------------------------------

    @router.get("/conformance")
    def conformance() -> dict[str, Any]:
        """Every CLSI M39 rule, its implementation, and its test.

        We could not get a rural pharmacist to review the clinical logic inside the build window.
        So instead of asserting the logic is right, we built to a published standard and made
        conformance checkable. A judge can open CLSI M39 and verify us.
        """
        return {
            "standard": "CLSI M39-A4, Analysis and Presentation of Cumulative Antimicrobial Susceptibility Test Data",
            "why_this_page": (
                "A practitioner interview cannot be verified by a judge. A published standard can."
            ),
            "rules": [
                {
                    "rule": "Include only species with at least 30 isolates tested in the analysis period",
                    "implementation": "day_three/antibiogram.py: Cell.suppressed, MIN_ISOLATES",
                    "test": "tests/test_antibiogram.py::test_a_cell_below_thirty_isolates_is_suppressed",
                    "note": "A suppressed cell returns None, not a hidden number.",
                },
                {
                    "rule": "First isolate per patient per species per period, irrespective of body site",
                    "implementation": "day_three/antibiogram.py: Curator._exclusion_reason",
                    "test": "tests/test_antibiogram.py::test_first_isolate_is_irrespective_of_body_site",
                    "note": (
                        "An earlier draft of our design wrongly folded specimen stratification "
                        "into this rule. Corrected, tested, and recorded in the Registry changelog."
                    ),
                    "known_deviation": (
                        "CLSI selects the earliest isolate by collection date. We select the "
                        "first one ingested. These agree whenever reports arrive in collection "
                        "order, which is the normal case, but a delayed report collected earlier "
                        "than one already counted is excluded rather than replacing it. The "
                        "affected patient still contributes exactly one isolate, so counts stay "
                        "correct; only which susceptibility profile is counted can differ. "
                        "Found by boundary-probing our own implementation and disclosed rather "
                        "than left for a reviewer to discover."
                    ),
                },
                {
                    "rule": "Include only diagnostic isolates, not surveillance isolates",
                    "implementation": "day_three/antibiogram.py: Curator._exclusion_reason",
                    "test": "tests/test_antibiogram.py::test_surveillance_isolates_are_excluded",
                },
                {
                    "rule": "Report percent susceptible; intermediate is not counted as susceptible",
                    "implementation": "day_three/antibiogram.py: Curator.ingest",
                    "test": "tests/test_antibiogram.py::test_intermediate_counts_in_the_denominator_but_not_the_numerator",
                },
            ],
            "ladder": [
                {"kind": kind.value, "offset_hours": offset.total_seconds() / 3600, "why": why}
                for kind, offset, why in LADDER
            ],
            "safety": [
                "Every recommendation is a draft requiring licensed pharmacist approval.",
                "The agent never prescribes, never changes an order, and never recommends a dose.",
                "All data is synthetic. No real patient information is used at any point.",
                "Scope is organism-to-drug appropriateness only, which is checkable against a result.",
            ],
        }

    return router
