"""Idempotently register Day Three's public capabilities in Google Cloud Agent Registry.

Run from app/ after Application Default Credentials are configured:

    python infra/register_agents.py

The service uses standard REST registration because the runtime is Cloud Run plus FastAPI, not
Agent Runtime. Agent Registry projects each writable Service into a read-only discoverable Agent.
"""

from __future__ import annotations

import os
import time

import google.auth
from google.auth.transport.requests import AuthorizedSession


PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
LOCATION = os.environ.get("REGION", "us-central1")
SERVICE_URL = os.environ.get(
    "DAY_THREE_URL", "https://day-three-109051079423.us-central1.run.app"
)
API_ROOT = "https://agentregistry.googleapis.com/v1"

CAPABILITIES = {
    "day-three-curator": (
        "Day Three Curator",
        "Maintains a provenance-bearing local antibiogram for scoped cross-department discovery.",
        "/day-three/registry/consume",
    ),
    "day-three-intake": (
        "Day Three Intake",
        "Converts synthetic scanned microbiology reports into verified structured isolates.",
        "/day-three/intake",
    ),
    "day-three-shortage-watch": (
        "Day Three Shortage Watch",
        "Refreshes official openFDA shortage data and filters it to the demonstration formulary.",
        "/day-three/shortages",
    ),
    "day-three-reconciler": (
        "Day Three Reconciler",
        "Creates a source-grounded pharmacist review draft from a final isolate and current regimen.",
        "/day-three/reconcile",
    ),
}

def wait_for_operation(session: AuthorizedSession, response) -> None:
    """Wait until registry metadata is projected, instead of printing success on submission."""
    operation = response.json()
    name = str(operation.get("name", ""))
    if "/operations/" not in name or operation.get("done"):
        return
    for _ in range(60):
        status = session.get(f"{API_ROOT}/{name}", timeout=15)
        status.raise_for_status()
        operation = status.json()
        if operation.get("done"):
            if operation.get("error"):
                raise RuntimeError(f"Agent Registry operation failed: {operation['error']}")
            return
        time.sleep(1)
    raise TimeoutError(f"Agent Registry operation did not complete: {name}")



def main() -> None:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = AuthorizedSession(credentials)
    parent = f"projects/{PROJECT}/locations/{LOCATION}"

    for service_id, (display_name, description, path) in CAPABILITIES.items():
        body = {
            "displayName": display_name,
            "description": description,
            "interfaces": [
                {"url": SERVICE_URL + path, "protocolBinding": "HTTP_JSON"}
            ],
            "agentSpec": {"type": "NO_SPEC"},
        }
        resource = f"{API_ROOT}/{parent}/services/{service_id}"
        current = session.get(resource, timeout=15)
        if current.status_code == 404:
            response = session.post(
                f"{API_ROOT}/{parent}/services",
                params={"serviceId": service_id},
                json=body,
                timeout=30,
            )
            action = "created"
        else:
            current.raise_for_status()
            response = session.patch(
                resource,
                params={"updateMask": "displayName,description,interfaces,agentSpec"},
                json={"name": resource.removeprefix(API_ROOT + "/"), **body},
                timeout=30,
            )
            action = "updated"
        response.raise_for_status()
        wait_for_operation(session, response)
        print(f"{action}: {service_id}")


if __name__ == "__main__":
    main()
