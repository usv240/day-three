"""Make real Gemini multimodal calls against the scanned fixtures and record the responses.

This is the one thing that cannot be faked. Everything else in the demo runs on recorded
responses so rehearsal is free, but those recordings have to come from somewhere real. This
script is where the actual model call happens.

It also grades the result. Each fixture ships with the ground truth text it was rendered from,
so we can measure what the model got right, what it dropped, and what it invented. A number we
measured is worth more than a claim that it works.

    python scripts/record_intake.py                 # all fixtures
    python scripts/record_intake.py ecoli_urine     # one
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from day_three.grading import grade, truth_susceptibilities  # noqa: E402
from day_three.intake import (  # noqa: E402
    EXTRACTION_SCHEMA,
    ReplayClient,
    SYSTEM_PROMPT,
    ExtractionError,
    IntakeAgent,
    VertexClient,
)

SCANS = Path(__file__).resolve().parent.parent / "fixtures" / "scans"
RECORDINGS = Path(__file__).resolve().parent.parent / "fixtures" / "recordings"

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
LOCATION = os.environ.get("MODEL_LOCATION", "global")  # Gemini 3.x is global-only
MODEL = os.environ.get("INTAKE_MODEL", "gemini-3.5-flash")


def rescore_from_recordings() -> int:
    """Rebuild the full accuracy report from saved recordings, with no model calls.

    Why this exists. Re-recording a single fixture used to rewrite `_accuracy_report.json` with
    only that fixture, silently shrinking the published evidence: the site said 29 of 29
    susceptibility results while the shipped report summed to 21, because one of the four
    fixtures had been dropped from it. The recordings themselves were never lost, so the report
    can always be rebuilt from them for free. Grading uses the same `grade` function as the live
    path, so a rebuilt row is identical to the row the live run wrote.
    """
    rows: list[dict] = []
    for path in sorted(RECORDINGS.glob("*.json")):
        if path.stem.startswith("_") or not (SCANS / f"{path.stem}.txt").exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        result = IntakeAgent(ReplayClient({"default": raw})).parse(
            artifact_id=path.stem,
            document="",
            patient_id=f"pt_{path.stem}",
            image=(SCANS / f"{path.stem}.jpg").read_bytes(),
        )
        truth = truth_susceptibilities((SCANS / f"{path.stem}.txt").read_text(encoding="utf-8"))
        rows.append(grade(path.stem, result, truth))

    (RECORDINGS / "_accuracy_report.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )
    total_truth = sum(r["truth_count"] for r in rows)
    total_correct = sum(r["correct"] for r in rows)
    total_invented = sum(len(r["invented"]) for r in rows)
    for row in rows:
        print(f"  {row['fixture']:<24} {row['correct']}/{row['truth_count']}")
    print("=" * 60)
    print(f"  correct   {total_correct}/{total_truth} across {len(rows)} fixtures")
    print(f"  invented  {total_invented}  (must be 0)")
    return 0 if total_invented == 0 and total_correct == total_truth else 1


def main() -> int:
    argv = sys.argv[1:]
    if "--rescore" in argv:
        # No live calls, no cost. Use this whenever the report needs to be rebuilt.
        return rescore_from_recordings()

    wanted = argv or None
    RECORDINGS.mkdir(parents=True, exist_ok=True)

    images = sorted(SCANS.glob("*.jpg"))
    if wanted:
        images = [p for p in images if p.stem in wanted]
    if not images:
        print("No fixtures found. Run scripts/make_fixtures.py first.")
        return 1
    if wanted:
        print(
            "Recording a subset. The report will be rebuilt from every saved recording afterwards "
            "so this run cannot shrink the published evidence.\n"
        )

    print(f"Live Gemini calls: model={MODEL} project={PROJECT} location={LOCATION}")
    print(f"{len(images)} image(s). This costs real money, unlike every other path in the demo.\n")

    client = VertexClient(project=PROJECT, location=LOCATION, model=MODEL)
    agent = IntakeAgent(client)
    report: list[dict] = []

    for path in images:
        print(f"  {path.name}")
        image_bytes = path.read_bytes()
        try:
            result = agent.parse(
                artifact_id=path.stem, document="", patient_id=f"pt_{path.stem}", image=image_bytes
            )
        except ExtractionError as exc:
            print(f"    FAILED: {exc}\n")
            report.append({"fixture": path.stem, "error": str(exc)})
            continue

        (RECORDINGS / f"{path.stem}.json").write_text(
            json.dumps(result.raw, indent=2), encoding="utf-8"
        )

        truth = truth_susceptibilities((SCANS / f"{path.stem}.txt").read_text(encoding="utf-8"))
        scored = grade(path.stem, result, truth)
        report.append(scored)

        print(f"    organism   : {scored['organism']}")
        print(f"    extracted  : {scored['extracted']} of {scored['truth_count']} truth rows")
        print(f"    correct    : {scored['correct']}")
        if scored["wrong_interpretation"]:
            print(f"    WRONG      : {scored['wrong_interpretation']}")
        if scored["invented"]:
            print(f"    INVENTED   : {scored['invented']}")
        if scored["missed"]:
            print(f"    missed     : {list(scored['missed'])}")
        if scored["dropped_by_guard"]:
            print(f"    guard drop : {scored['dropped_by_guard']}")
        if scored["quarantined"]:
            print(f"    quarantine : {scored['quarantined']}")
        print()

    # Rebuild from every saved recording, not just the ones re-recorded in this run. Writing
    # `report` directly is what dropped a fixture from the published evidence before.
    if wanted:
        print("Rebuilding the full report from all saved recordings.\n")
        return rescore_from_recordings()

    (RECORDINGS / "_accuracy_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    scored = [r for r in report if "error" not in r]
    total_truth = sum(r["truth_count"] for r in scored)
    total_correct = sum(r["correct"] for r in scored)
    total_invented = sum(len(r["invented"]) for r in scored)
    total_wrong = sum(len(r["wrong_interpretation"]) for r in scored)

    print("=" * 60)
    print(f"  correct        {total_correct}/{total_truth}")
    print(f"  wrong          {total_wrong}")
    print(f"  invented       {total_invented}  (must be 0: the guard drops unquotable values)")
    print(f"\nRecordings written to {RECORDINGS}")
    return 0 if total_invented == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
