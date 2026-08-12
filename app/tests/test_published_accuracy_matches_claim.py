"""The number on the site must equal the number in the shipped evidence.

This exists because they once disagreed. The site claimed 29 of 29 susceptibility results while
`_accuracy_report.json` summed to 21, because re-recording a single fixture overwrote the report
with only that fixture. Nobody noticed: every test passed, the page looked right, and the
discrepancy was only visible to someone who opened the linked JSON and added the rows up.

For a project whose entire pitch is that claims are checkable, a checkable claim that does not
check out is the most expensive kind of bug.
"""

import json
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
REPORT = APP / "fixtures" / "recordings" / "_accuracy_report.json"
SCANS = APP / "fixtures" / "scans"


def test_every_recorded_fixture_appears_in_the_published_report():
    rows = json.loads(REPORT.read_text(encoding="utf-8"))
    recorded = {
        p.stem
        for p in (APP / "fixtures" / "recordings").glob("*.json")
        if not p.stem.startswith("_") and (SCANS / f"{p.stem}.txt").exists()
    }
    assert {r["fixture"] for r in rows} == recorded, (
        "a fixture was dropped from the report; rebuild it with "
        "`python scripts/record_intake.py --rescore`, which costs nothing"
    )


def test_the_report_totals_are_perfect_and_nothing_was_invented():
    rows = json.loads(REPORT.read_text(encoding="utf-8"))
    assert sum(len(r["invented"]) for r in rows) == 0
    assert sum(len(r["wrong_interpretation"]) for r in rows) == 0
    assert sum(r["correct"] for r in rows) == sum(r["truth_count"] for r in rows)


def test_the_public_pages_state_the_same_total_the_report_proves():
    rows = json.loads(REPORT.read_text(encoding="utf-8"))
    total = sum(r["truth_count"] for r in rows)
    correct = sum(r["correct"] for r in rows)

    # Any "N/29" or "N of 29" on the page is a claim about this report and must equal it.
    pattern = re.compile(rf"(\d+)\s*(?:/|\s+of\s+)\s*{total}\b")
    for page in ("index.html", "judges.html"):
        text = (APP / "web" / page).read_text(encoding="utf-8")
        claimed = pattern.findall(text)
        assert claimed, f"{page} no longer states a recorded-accuracy figure"
        for got in claimed:
            assert int(got) == correct, (
                f"{page} claims {got} of {total} but the shipped report proves {correct}/{total}"
            )
