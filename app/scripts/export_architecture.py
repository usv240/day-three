"""Rasterise docs/architecture.svg to docs/architecture.png.

The SVG is the source; the PNG is what Devpost carries. They drifted once, when the diagram's
stage list was corrected in the SVG and the PNG kept the old one, so the submission showed a
different architecture from the repository. This script exists so re-exporting is one command
rather than a manual step somebody forgets.

Uses headless Chrome, which is already on the machine for the demo, rather than adding a native
Cairo dependency.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SVG = ROOT / "docs" / "architecture.svg"
PNG = ROOT / "docs" / "architecture.png"
WIDTH = 2800

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "google-chrome",
    "chromium",
)


def find_chrome() -> str | None:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def main() -> int:
    if not SVG.exists():
        print(f"missing {SVG}", file=sys.stderr)
        return 1
    chrome = find_chrome()
    if chrome is None:
        print(
            "No Chrome found. Open docs/architecture.svg in any browser, screenshot at "
            f"{WIDTH}px wide, and save over docs/architecture.png.",
            file=sys.stderr,
        )
        return 1

    svg = SVG.read_text(encoding="utf-8")
    height = round(WIDTH * 626 / 1400)
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(
            "<!doctype html><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;background:#fff}"
            f"svg{{width:{WIDTH}px;height:auto;display:block}}</style>{svg}",
            encoding="utf-8",
        )
        subprocess.run(
            [
                chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
                f"--window-size={WIDTH},{height}",
                f"--screenshot={PNG}", page.as_uri(),
            ],
            check=True, capture_output=True,
        )

    data = PNG.read_bytes()
    w, h = struct.unpack(">II", data[16:24])
    print(f"wrote {PNG.relative_to(ROOT)}: {w}x{h}, {len(data):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
