"""Read-only adapter for Google Cloud's managed Agent Registry.

The local catalogue remains the authorization policy and invocation router. This adapter proves
that the same public capabilities are also registered in the managed enterprise discovery plane.
It deliberately exposes no credentials and returns only judge-relevant metadata.
"""

from __future__ import annotations

from typing import Any, Callable

import google.auth
from google.auth.transport.requests import AuthorizedSession


class ManagedRegistryError(RuntimeError):
    """The managed registry could not be read."""


class ManagedAgentRegistry:
    API_ROOT = "https://agentregistry.googleapis.com/v1"

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

    def list_day_three_agents(self) -> list[dict[str, Any]]:
        parent = f"projects/{self.project_id}/locations/{self.location}"
        response = self._session_factory().get(
            f"{self.API_ROOT}/{parent}/agents",
            timeout=8,
        )
        if response.status_code != 200:
            raise ManagedRegistryError(
                f"Agent Registry returned HTTP {response.status_code}; no local fallback was substituted."
            )

        agents = []
        for item in response.json().get("agents", []):
            display_name = str(item.get("displayName", ""))
            if not display_name.startswith("Day Three "):
                continue
            interfaces = [
                interface
                for protocol in item.get("protocols", [])
                for interface in protocol.get("interfaces", [])
            ]
            agents.append(
                {
                    "name": item.get("name"),
                    "agent_id": item.get("agentId"),
                    "display_name": display_name,
                    "description": item.get("description"),
                    "interfaces": interfaces,
                    "managed": True,
                }
            )
        return sorted(agents, key=lambda agent: agent["display_name"])
