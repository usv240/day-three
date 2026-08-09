"""Regression guard for claims that the August 8 evidence audit narrowed or removed."""

from pathlib import Path


def test_public_copy_preserves_evidence_scope_and_build_honesty():
    web = Path(__file__).resolve().parents[1] / "web"
    public_copy = "\n".join(
        (web / name).read_text(encoding="utf-8")
        for name in ("index.html", "judges.html", "glossary.json")
    ).casefold()

    for unsupported in (
        "at most small hospitals, nobody",
        "nearly all critical access hospitals",
        "only 5 percent",
        "95 percent of survivors",
        "nine agents",
        "shortage-watch",
    ):
        assert unsupported not in public_copy

    assert "8 of 20" in public_copy
    assert "selected 21-program evaluation" in public_copy
    assert "cumulative" in public_copy
    assert "synthetic composite" in public_copy
