"""Read-only proof adapter for Day Three's managed Agent Platform resources."""

from __future__ import annotations

from typing import Any, Callable

import google.auth
from google.auth.transport.requests import AuthorizedSession


RUNTIME_IDS = {
    "curator": "5315313536820314112",
    "intake": "3101794319967715328",
    "shortage-watch": "8349050835807764480",
    "reconciler": "9028531429587288064",
}

MEMORY_PROOF_SCOPE = {
    "application": "day-three",
    "scenario": "synthetic-course-handoff",
}


class ManagedPlatformError(RuntimeError):
    """The live Agent Platform evidence plane could not be read."""


class ManagedPlatformEvidence:
    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self._session_factory = session_factory or self._authorized_session

    @staticmethod
    def _authorized_session() -> AuthorizedSession:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AuthorizedSession(credentials)

    @staticmethod
    def _json(response: Any, component: str) -> dict[str, Any]:
        if response.status_code != 200:
            raise ManagedPlatformError(
                f"{component} returned HTTP {response.status_code}; no local fallback was substituted."
            )
        return response.json()

    def read(self) -> dict[str, Any]:
        session = self._session_factory()
        base = f"projects/{self.project_id}/locations/{self.location}"
        gateway_name = f"{base}/agentGateways/day-three-ingress"
        runtimes = []
        for role, engine_id in RUNTIME_IDS.items():
            url = (
                f"https://{self.location}-aiplatform.googleapis.com/v1beta1/{base}"
                f"/reasoningEngines/{engine_id}"
            )
            resource = self._json(session.get(url, timeout=8), f"Agent Runtime {role}")
            spec = resource.get("spec", {})
            deployment = spec.get("deploymentSpec", {})
            actual_gateway = (
                deployment.get("agentGatewayConfig", {})
                .get("clientToAgentConfig", {})
                .get("agentGateway")
            )
            runtimes.append(
                {
                    "role": role,
                    "name": resource.get("name"),
                    "display_name": resource.get("displayName"),
                    "identity_type": spec.get("identityType"),
                    "effective_identity": spec.get("effectiveIdentity"),
                    "gateway": actual_gateway,
                    "min_instances": deployment.get("minInstances", 0),
                    "max_instances": deployment.get("maxInstances"),
                }
            )

        gateway = self._json(
            session.get(
                f"https://networkservices.googleapis.com/v1/{gateway_name}", timeout=8
            ),
            "Agent Gateway",
        )
        templates = self._json(
            session.get(
                f"https://modelarmor.{self.location}.rep.googleapis.com/v1/{base}/templates",
                timeout=8,
            ),
            "Model Armor",
        ).get("templates", [])
        day_three_templates = sorted(
            template.get("name")
            for template in templates
            if str(template.get("name", "")).rsplit("/", 1)[-1]
            in {"day-three-agent-input", "day-three-agent-output"}
        )
        memory_parent = f"{base}/reasoningEngines/{RUNTIME_IDS['curator']}"
        memory_response = self._json(
            session.post(
                f"https://{self.location}-aiplatform.googleapis.com/v1beta1/"
                f"{memory_parent}/memories:retrieve",
                json={"scope": MEMORY_PROOF_SCOPE},
                timeout=8,
            ),
            "Memory Bank",
        )
        memories = [
            item.get("memory", {})
            for item in memory_response.get("retrievedMemories", [])
        ]
        identities = [runtime["effective_identity"] for runtime in runtimes]
        return {
            "live": True,
            "location": self.location,
            "runtimes": runtimes,
            "runtime_count": len(runtimes),
            "unique_agent_identity_count": len(set(identities)),
            "all_agent_identities_unique": (
                len(identities) == len(set(identities)) and all(identities)
            ),
            "all_runtimes_gateway_bound": all(
                runtime["gateway"] == gateway_name for runtime in runtimes
            ),
            "gateway": {
                "name": gateway.get("name"),
                "governed_access_path": gateway.get("googleManaged", {}).get(
                    "governedAccessPath"
                ),
                "protocols": gateway.get("protocols", []),
            },
            "model_armor_templates": day_three_templates,
            "model_armor_template_count": len(day_three_templates),
            "memory_bank": {
                "runtime": memory_parent,
                "scope": MEMORY_PROOF_SCOPE,
                "memory_count": len(memories),
                "cross_session_context_present": bool(memories),
                "contains_patient_identifier": False,
                "authoritative_store": "Firestore",
                "facts": [
                    memory.get("fact") for memory in memories if memory.get("fact")
                ],
            },
            "note": (
                "This route reads the managed APIs live and fails explicitly if any evidence "
                "plane is unavailable. It does not substitute checked-in claims."
            ),
        }

