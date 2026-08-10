"""Regression guard for claims that the August 8 evidence audit narrowed or removed."""

from pathlib import Path


def test_public_copy_preserves_evidence_scope_and_build_honesty():
    web = Path(__file__).resolve().parents[1] / "web"
    public_copy = "\n".join(
        (web / name).read_text(encoding="utf-8")
        for name in ("index.html", "judges.html", "glossary.json", "app.js")
    ).casefold()

    for unsupported in (
        "at most small hospitals, nobody",
        "nearly all critical access hospitals",
        "only 5 percent",
        "95 percent of survivors",
        "communicating only through durable events",
        "no agent calls another directly",
        "spine-109051079423.us-central1.run.app",
        "pages the pharmacist",
        "paged the pharmacist",
        "97% of critical access",
        "16% of critical access",
    ):
        assert unsupported not in public_copy

    assert "8 of 20" in public_copy
    assert "selected 21-program evaluation" in public_copy
    assert "cumulative" in public_copy
    assert "synthetic composite" in public_copy
    assert "222 tests" in public_copy
    assert "google cloud agent registry" in public_copy
    assert "openfda" in public_copy
    assert "15 tests in" in public_copy
    assert "165 tests" not in public_copy
    assert "11 tests in" not in public_copy
    assert "bash deploy.sh spine" not in public_copy
    assert "cd app" in public_copy
    assert "-d '{}'" in public_copy
    assert "day-three-109051079423.us-central1.run.app" in public_copy
    assert "github.com/usv240/day-three" in public_copy
    assert "architecture-map" in public_copy
    assert "97%" in public_copy and "16%" in public_copy
    assert "national survey is not a critical-access-hospital rate" in public_copy
    assert "pmc11574594" in public_copy
    assert "reducing-carbapenem-use" in public_copy
    assert "disabled controls enforce that order" in public_copy
    assert "parallel rehearsal found cross-project clock interference" in public_copy
    assert "if you have sixty seconds" in public_copy
