from pathlib import Path


WEB = Path(__file__).resolve().parents[1] / "web"


def test_live_stack_is_available_on_every_custom_public_page() -> None:
    for name in ("index.html", "developer.html", "docs.html", "judges.html"):
        html = (WEB / name).read_text(encoding="utf-8")
        assert "/static/live-stack.js" in html, name


def test_live_stack_publishes_verified_platform_layers_without_endorsement_claim() -> None:
    script = (WEB / "live-stack.js").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    for service in ("Gemini 3.5 Flash", "Cloud Run", "Firestore", "Agent Registry", "Agent Runtime", "Agent Gateway", "Model Armor", "Memory Bank", "Gemma 4"):
        assert service in script
    assert "Technology used; no endorsement implied." in script
    assert "sponsor" not in script.lower()
    assert ".live-stack:focus-within" in css
    assert 'aria-expanded="false"' in script

