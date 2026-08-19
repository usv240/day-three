"""Grading a microbiology extraction against the ground truth the fixture was rendered from.

This lives in the package rather than in `scripts/` because two callers must agree exactly:

* `scripts/record_intake.py`, which produces the published `_accuracy_report.json`, and
* the public live-call route, which grades a *fresh* Gemini response for a judge.

If those two used different graders, the live number and the published number would not be
comparable, and the comparison is the entire point of showing a live call.
"""

from __future__ import annotations

import re
from typing import Any

from day_three.intake import normalise_drug

_TRUTH_LINE = re.compile(
    r"^([A-Z][A-Z\-]{3,})\s+(<=?[\d.]+|>=?[\d.]+|[\d.]+)\s+(S|I|R|SDD|NS)\s*$"
)


def truth_susceptibilities(text: str) -> dict[str, str]:
    """Parse the ground truth the fixture was rendered from."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = _TRUTH_LINE.match(line.strip())
        if match:
            found[normalise_drug(match.group(1))] = match.group(3)
    return found


def grade(name: str, result: Any, truth: dict[str, str]) -> dict[str, Any]:
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
