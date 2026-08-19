"""Create the public, deidentified Memory Bank proof record once.

Run from ``app/`` after ``provision_memory_bank.ps1``. The script is idempotent and never stores a
patient identifier, raw report, susceptibility value, or recommendation.
"""

from __future__ import annotations

import os

import google.auth
from google.auth.transport.requests import AuthorizedSession


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
LOCATION = os.environ.get("REGION", "us-central1")
CURATOR_RUNTIME_ID = "5315313536820314112"
SCOPE = {"application": "day-three", "scenario": "synthetic-course-handoff"}
FACT = (
    "Day Three uses Firestore as the authoritative operational ledger and this managed Memory "
    "Bank for a deidentified cross-session course handoff. The synthetic demonstration "
    "registers five inpatient stewardship reviews through day 14."
)


def main() -> None:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = AuthorizedSession(credentials)
    parent = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}"
        f"/reasoningEngines/{CURATOR_RUNTIME_ID}"
    )
    endpoint = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/{parent}"
    retrieved = session.post(
        f"{endpoint}/memories:retrieve", json={"scope": SCOPE}, timeout=30
    )
    retrieved.raise_for_status()
    memories = retrieved.json().get("retrievedMemories", [])
    if memories:
        print(f"exists: {len(memories)} deidentified proof memory")
        return

    created = session.post(
        f"{endpoint}/memories",
        json={"fact": FACT, "scope": SCOPE},
        timeout=30,
    )
    created.raise_for_status()
    print("created: deidentified Day Three Memory Bank proof")


if __name__ == "__main__":
    main()
