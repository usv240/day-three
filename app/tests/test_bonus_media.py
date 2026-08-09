import hashlib
import json
from pathlib import Path


APP = Path(__file__).resolve().parents[1]
WEB = APP / "web"
MEDIA = WEB / "media"


def _manifest() -> dict:
    return json.loads((MEDIA / "bonus-media-provenance.json").read_text(encoding="utf-8"))


def test_bonus_media_is_real_recorded_google_output_with_integrity_hashes():
    manifest = _manifest()
    assert manifest["provider"] == "Google Vertex AI"
    assert manifest["project"] == "Day Three"
    assert manifest["image"]["model"] == "gemini-3.1-flash-image"
    assert manifest["video"]["model"] == "veo-3.1-fast-generate-001"
    for kind, magic in (("image", b"\x89PNG"), ("video", None)):
        record = manifest[kind]
        asset = MEDIA / record["asset"]
        payload = asset.read_bytes()
        assert len(payload) == record["bytes"] > 100_000
        assert hashlib.sha256(payload).hexdigest() == record["sha256"]
        if magic:
            assert payload.startswith(magic)
        else:
            assert b"ftyp" in payload[:64]


def test_bonus_media_is_optional_labelled_and_never_autoplays():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "Gemini 3.1 Flash Image" in html
    assert "Veo 3.1 Fast" in html
    assert "Onboarding only; never clinical evidence" in html
    assert "/static/media/bonus-media-provenance.json" in html
    assert "controls muted playsinline" in html
    assert "autoplay" not in html
    assert "no patient data" in html
    assert "never enter the clinical execution path" in (
        WEB / "judges.html"
    ).read_text(encoding="utf-8")


def test_bonus_media_recording_is_reproducible_and_non_data_bearing():
    script = (APP / "scripts" / "record_bonus_media.py").read_text(encoding="utf-8")
    assert 'IMAGE_MODEL", "gemini-3.1-flash-image"' in script
    assert 'VIDEO_MODEL", "veo-3.1-fast-generate-001"' in script
    for forbidden in ("marta", "ceftriaxone", "ciprofloxacin", "escherichia coli"):
        assert forbidden not in script.casefold()
    assert "sha256" in script
    demo = (APP / "scripts" / "demo_flow.py").read_text(encoding="utf-8")
    assert "/static/media/bonus-media-provenance.json" in demo
    assert "hashlib.sha256" in demo
    assert 'person_generation="dont_allow"' in script