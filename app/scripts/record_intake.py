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
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from day_three.intake import (  # noqa: E402
    EXTRACTION_SCHEMA,
    SYSTEM_PROMPT,
    ExtractionError,
    IntakeAgent,
    VertexClient,
    normalise_drug,
)

SCANS = Path(__file__).resolve().parent.parent / "fixtures" / "scans"
RECORDINGS = Path(__file__).resolve().parent.parent / "fixtures" / "recordings"

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
LOCATION = os.environ.get("MODEL_LOCATION", "global")  # Gemini 3.x is global-only
MODEL = os.environ.get("INTAKE_MODEL", "gemini-3.5-flash")


def truth_susceptibilities(text: str) -> dict[str, str]:
    """Parse the ground truth the fixture was rendered from."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Z][A-Z\-]{3,})\s+(<=?[\d.]+|>=?[\d.]+|[\d.]+)\s+(S|I|R|SDD|NS)\s*$", line.strip())
        if match:
            found[normalise_drug(match.group(1))] = match.group(3)
    return found


def grade(name: str, result, truth: dict[str, str]) -> dict:
    got = {s.drug: s.interpretation.value for s in result.isolates[0].susceptibilities}

    correct = {d: v for d, v in got.items() if truth.get(d) == v}
    wrong = {d: (got[d], truth.get(d)) for d in got if truth.get(d) not in (None, got[d])}
    invented = {d: v for d, v in got.items() if d not in truth}
    missed = {d: v for d, v in truth.items() if d not in got}

    return {
        "fixture": name,
        "organism": result.isolates[0].organism,
        "truth_count": len(truth),
        "extracted": len(got),
        "correct": len(correct),
        "wrong_interpretation": wrong,
        "invented": invented,
        "missed": missed,
        "dropped_by_guard": result.dropped,
        "quarantined": [q.threat.value for q in result.quarantined],
    }


def main() -> int:
    wanted = sys.argv[1:] or None
    RECORDINGS.mkdir(parents=True, exist_ok=True)

    images = sorted(SCANS.glob("*.jpg"))
    if wanted:
        images = [p for p in images if p.stem in wanted]
    if not images:
        print("No fixtures found. Run scripts/make_fixtures.py first.")
        return 1

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
