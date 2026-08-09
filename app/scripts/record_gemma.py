"""Make a real Gemma call for the redaction gate's second layer, and record it.

The deterministic pattern layer catches identifiers with reliable shapes. Person names in running
prose have no shape, so Gemma reviews the already-pattern-cleaned text and returns spans only,
never a rewrite. This script proves that layer against the live model and saves the response so
every later run replays for free.

Graded, like the Gemini recording: the fixtures carry the names that should be found, so we can
report recall and false positives rather than asserting it works.

    python scripts/record_gemma.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spine.redact import GemmaReviewer, RedactionError, Redactor  # noqa: E402

RECORDINGS = Path(__file__).resolve().parent.parent / "fixtures" / "recordings"
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
LOCATION = os.environ.get("MODEL_LOCATION", "global")

# Clinical prose of the kind that appears in a chart note or a lab comment. Names here are in
# running text with no label, which is exactly what regex cannot safely catch.
CASES: list[tuple[str, str, list[str]]] = [
    (
        "handoff_note",
        "Culture results discussed at the bedside with Harold Jennings and his daughter "
        "Marie Jennings. Organism: Escherichia coli. Ceftriaxone remains appropriate. "
        "Follow up arranged with Dr. Alvarez in the outpatient clinic.",
        ["Harold Jennings", "Marie Jennings", "Alvarez"],
    ),
    (
        "pharmacy_comment",
        "Reviewed by pharmacy. Spoke with Rebecca Osei about the ceftriaxone to nitrofurantoin "
        "switch. Klebsiella pneumoniae susceptible to meropenem. No allergies documented.",
        ["Rebecca Osei"],
    ),
    (
        "clean_control",
        "Organism: Staphylococcus aureus, methicillin resistant. Vancomycin MIC 1, susceptible. "
        "Linezolid susceptible. No further action pending stewardship review.",
        [],
    ),
]


def main() -> int:
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    reviewer = GemmaReviewer(project=PROJECT, location=LOCATION)

    print(f"Live Gemma calls: model={reviewer.DEFAULT_MODEL} project={PROJECT} location={LOCATION}")
    print(f"{len(CASES)} cases. Costs real money; every later run replays these for free.\n")

    recordings: dict[str, list[str]] = {}
    found_total = expected_total = false_positives = 0

    for name, text, expected in CASES:
        print(f"  {name}")
        try:
            names = reviewer.find_names(text)
        except RedactionError as exc:
            print(f"    FAILED: {exc}\n")
            return 1

        recordings[name] = names
        hits = [e for e in expected if any(e in n or n in e for n in names)]
        extras = [n for n in names if not any(e in n or n in e for e in expected)]

        found_total += len(hits)
        expected_total += len(expected)
        false_positives += len(extras)

        print(f"    returned   : {names}")
        print(f"    recall     : {len(hits)}/{len(expected)}")
        if extras:
            print(f"    extra      : {extras}  (over-redaction is safe; under-redaction is not)")

        # Prove the end-to-end gate with this real response, not just the raw list.
        from spine.redact import ReplayReviewer

        result = Redactor(ReplayReviewer(names)).redact(text)
        leaked = [e for e in expected if e in result.text]
        print(f"    gate output: {result.text[:90]}...")
        print(f"    leaked     : {leaked or 'none'}")
        if leaked:
            print("    FAIL: an expected identifier survived the gate")
            return 1
        print()

    (RECORDINGS / "gemma_names.json").write_text(json.dumps(recordings, indent=2), encoding="utf-8")

    print("=" * 60)
    print(f"  recall           {found_total}/{expected_total}")
    print(f"  false positives  {false_positives}  (safe direction)")
    print(f"  identifiers leaked through the gate  0")
    print(f"\nRecording written to {RECORDINGS / 'gemma_names.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
