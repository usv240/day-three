"""Record the two non-data-bearing Google AI onboarding assets.

These assets explain the workflow before a first-time user enters the live console. They never
contain patient data, clinical measurements, drug names, or treatment recommendations. Running
this script is the reproducible proof that the checked-in assets came from Google models on
Vertex AI rather than from a design mock.

    python scripts/record_bonus_media.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types


PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
IMAGE_LOCATION = os.environ.get("IMAGE_LOCATION", "global")
VIDEO_LOCATION = os.environ.get("VIDEO_LOCATION", "us-central1")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gemini-3.1-flash-image")
VIDEO_MODEL = os.environ.get("VIDEO_MODEL", "veo-3.1-fast-generate-001")
MEDIA = Path(__file__).resolve().parents[1] / "web" / "media"

IMAGE_PROMPT = """Create a premium editorial onboarding illustration for a hospital antibiotic
review workflow. Show an abstract, non-data-bearing path from a scanned laboratory page, through
a durable clock checkpoint, to a human review card. Use warm ivory, slate, muted teal, and one
restrained coral accent. Calm civic-technology aesthetic, dimensional paper and glass forms,
wide 16:9 composition. No people, no patient data, no readable text, no numbers, no drug names,
no medical symbols, no logos, no watermark, and no treatment recommendation."""

VIDEO_PROMPT = """A four-second premium abstract workflow animation on a warm ivory background.
A scanned-paper shape enters a precise glass verification gate, a quiet clock advances, and a
sealed review card stops before a human handoff boundary. Muted teal, slate, and restrained coral,
calm civic technology style, smooth slow camera motion. No people, no readable text, no numbers,
no patient data, no medicines, no logos, no watermark, no audio."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_image() -> dict[str, str | int]:
    client = genai.Client(vertexai=True, project=PROJECT, location=IMAGE_LOCATION)
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=IMAGE_PROMPT,
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    parts = response.candidates[0].content.parts if response.candidates else []
    image_part = next((part for part in parts if part.inline_data is not None), None)
    if image_part is None or image_part.inline_data is None or not image_part.inline_data.data:
        raise RuntimeError("Google image model returned no image bytes")
    path = MEDIA / "day-three-visual-briefing.png"
    path.write_bytes(image_part.inline_data.data)
    return {
        "model": IMAGE_MODEL,
        "location": IMAGE_LOCATION,
        "prompt": IMAGE_PROMPT,
        "asset": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def record_video(timeout_seconds: int = 900) -> dict[str, str | int]:
    client = genai.Client(vertexai=True, project=PROJECT, location=VIDEO_LOCATION)
    operation = client.models.generate_videos(
        model=VIDEO_MODEL,
        prompt=VIDEO_PROMPT,
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=4,
            number_of_videos=1,
            person_generation="dont_allow",
            resolution="720p",
        ),
    )
    deadline = time.monotonic() + timeout_seconds
    while not operation.done:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Veo operation did not finish within {timeout_seconds} seconds")
        time.sleep(15)
        operation = client.operations.get(operation)
    if not operation.response or not operation.response.generated_videos:
        raise RuntimeError(f"Veo returned no video: {operation.error}")
    video = operation.response.generated_videos[0].video
    path = MEDIA / "day-three-wake-briefing.mp4"
    if video.video_bytes:
        path.write_bytes(video.video_bytes)
    else:
        raise RuntimeError(
            "Vertex returned a storage URI instead of inline bytes; rerun with an output GCS "
            f"download path configured. URI: {video.uri or 'missing'}"
        )
    return {
        "model": VIDEO_MODEL,
        "location": VIDEO_LOCATION,
        "prompt": VIDEO_PROMPT,
        "asset": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-only", action="store_true")
    parser.add_argument("--video-only", action="store_true")
    args = parser.parse_args()
    if args.image_only and args.video_only:
        parser.error("choose at most one of --image-only and --video-only")

    MEDIA.mkdir(parents=True, exist_ok=True)
    manifest_path = MEDIA / "bonus-media-provenance.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {"project": "Day Three", "provider": "Google Vertex AI"}
    )
    if not args.video_only:
        manifest["image"] = record_image()
    if not args.image_only:
        manifest["video"] = record_video()
    manifest["recorded_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
