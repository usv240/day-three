"""Expose the collected test count so a test can check what we publish about it.

Three public places quote this number, and they had drifted to three different values while the
real total was a fourth. Numbers on the public pages are this project's currency, so the count
checks itself the same way the extraction accuracy figure does.
"""

from pathlib import Path

import pytest

_SESSION = {"count": 0, "full_run": False}


def pytest_collection_modifyitems(session, config, items):
    _SESSION["count"] = len(items)
    # Only a whole-suite run knows the real total. A single file or a -k selection collects a
    # subset, and asserting the published number against it would fail for the wrong reason.
    #
    # This used to require no file_or_dir argument at all, which meant the documented command,
    # `python -m pytest -q` run from app/ with a tests target, never counted as a full run. The
    # guard skipped silently on every invocation anybody actually used, and the published count
    # drifted four tests behind before a human noticed. Pointing at the tests directory itself is
    # a full run.
    targets = [Path(t).resolve() for t in (config.getoption("file_or_dir") or [])]
    here = Path(__file__).resolve().parent
    whole_suite = not targets or all(t in (here, here.parent) for t in targets)
    _SESSION["full_run"] = whole_suite and not config.getoption("keyword")


@pytest.fixture
def collected_test_count() -> int:
    if not _SESSION["full_run"]:
        pytest.skip("published test count is only checkable on a full-suite run")
    return _SESSION["count"]
