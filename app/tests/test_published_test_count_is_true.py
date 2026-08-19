"""The test total quoted on the public pages must be the real one.

README, the judge evidence page, and the submission kit each quote a test count. They had drifted
to 253, 253 and 280 while the suite actually collected 281, so a judge running the documented
command would have got a different number from the page that told them to run it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

SOURCES = {
    "README.md": r"\|\s*Standalone automated tests\s*\|\s*\*\*(\d+) passed\*\*\s*\|",
    "SUBMISSION_KIT.md": r"18/18 acceptance,\s*(\d+) tests,",
    "app/web/judges.html": r"python -m pytest -q</code> - (\d+) tests",
    "docs/research-traceability.md": r"repository passes (\d+) tests",
    "VALIDATION_EVIDENCE.md": r"Standalone test suite \| (\d+) passed",
}


def published() -> dict[str, int]:
    found = {}
    for name, pattern in SOURCES.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        match = re.search(pattern, text)
        assert match, f"{name} no longer states a test count in the expected form"
        found[name] = int(match.group(1))
    return found


def test_every_public_page_quotes_the_same_test_count():
    counts = published()
    assert len(set(counts.values())) == 1, f"published test counts disagree: {counts}"


def test_the_published_count_is_what_the_suite_actually_collects(collected_test_count):
    counts = published()
    for name, value in counts.items():
        assert value == collected_test_count, (
            f"{name} claims {value} tests but the suite collects {collected_test_count}. "
            "Update the published number, or a judge running the documented command sees "
            "something different from the page that told them to run it."
        )
