"""Expose the collected test count so a test can check what we publish about it.

Three public places quote this number, and they had drifted to three different values while the
real total was a fourth. Numbers on the public pages are this project's currency, so the count
checks itself the same way the extraction accuracy figure does.
"""

import pytest

_SESSION = {"count": 0, "full_run": False}


def pytest_collection_modifyitems(session, config, items):
    _SESSION["count"] = len(items)
    # Only a whole-suite run knows the real total. When someone runs a single file or a -k
    # selection the count is a subset, and asserting against it would fail for the wrong reason.
    _SESSION["full_run"] = not config.getoption("file_or_dir") and not config.getoption("keyword")


@pytest.fixture
def collected_test_count() -> int:
    if not _SESSION["full_run"]:
        pytest.skip("published test count is only checkable on a full-suite run")
    return _SESSION["count"]
