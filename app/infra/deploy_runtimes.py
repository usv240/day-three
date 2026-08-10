"""Deploy the four published Day Three capabilities to managed Agent Runtime.

Prerequisites are created by ``provision_platform.ps1``. This script is intentionally idempotent:
an existing display name is reported and left untouched because an Agent Identity is immutable and
should not be silently replaced.

Run from ``app/`` with Application Default Credentials configured:

    python infra/deploy_runtimes.py
"""

from __future__ import annotations

import os

import vertexai


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
LOCATION = os.environ.get("REGION", "us-central1")
BACKEND_URL = os.environ.get(
    "DAY_THREE_BACKEND_URL", "https://day-three-109051079423.us-central1.run.app"
)
GATEWAY = f"projects/{PROJECT_ID}/locations/{LOCATION}/agentGateways/day-three-ingress"

ROLES = {
    "curator": "Maintains and returns the source-bearing CLSI M39 antibiogram.",
    "intake": "Verifies a structured isolate extraction against its synthetic source report.",
    "shortage-watch": "Returns the current source-dated openFDA shortage snapshot.",
    "reconciler": "Creates a grounded pharmacist-review draft without changing an order.",
}

QUERY_SCHEMA = [
    {
        "name": "query",
        "api_mode": "",
        "parameters": {
            "type": "object",
            "properties": {
                "payload": {
                    "type": "object",
                    "description": "The latest request only. It is screened before invocation.",
                }
            },
        },
    }
]


def main() -> None:
    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
    for role, description in ROLES.items():
        display_name = f"Day Three Runtime {role}"
        existing = list(
            client.agent_engines.list(config={"filter": f'display_name="{display_name}"'})
        )
        if existing:
            print(f"exists: {role}: {existing[0].api_resource.name}")
            continue

        remote = client.agent_engines.create(
            config={
                "display_name": display_name,
                "description": description,
                "source_packages": ["infra"],
                "entrypoint_module": "infra.runtime_agent",
                "entrypoint_object": "root_agent",
                "requirements_file": "infra/runtime_requirements.txt",
                "class_methods": QUERY_SCHEMA,
                "env_vars": {
                    "DAY_THREE_AGENT_ROLE": role,
                    "DAY_THREE_BACKEND_URL": BACKEND_URL,
                    "MODEL_ARMOR_REQUEST_TEMPLATE": "day-three-agent-input",
                    "MODEL_ARMOR_RESPONSE_TEMPLATE": "day-three-agent-output",
                },
                "identity_type": vertexai.types.IdentityType.AGENT_IDENTITY,
                "agent_gateway_config": {
                    "client_to_agent_config": {"agent_gateway": GATEWAY}
                },
                "min_instances": 0,
                "max_instances": 1,
                "container_concurrency": 10,
                "labels": {
                    "hackathon": "all-things-agentic",
                    "project": "day-three",
                    "role": role,
                },
            }
        )
        print(f"created: {role}: {remote.api_resource.name}")


if __name__ == "__main__":
    main()

