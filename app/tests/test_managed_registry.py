from __future__ import annotations

import pytest

from day_three.managed_registry import ManagedAgentRegistry, ManagedRegistryError


class Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        return self.response


def test_lists_only_managed_day_three_agents_and_flattens_interfaces():
    response = Response(
        200,
        {
            "agents": [
                {
                    "name": "projects/p/locations/us-central1/agents/a",
                    "agentId": "urn:a",
                    "displayName": "Day Three Curator",
                    "description": "Curates",
                    "protocols": [
                        {
                            "type": "CUSTOM",
                            "interfaces": [
                                {"url": "https://example.test/consume", "protocolBinding": "HTTP_JSON"}
                            ],
                        }
                    ],
                },
                {"displayName": "Workspace Built-in", "protocols": []},
            ]
        },
    )
    session = Session(response)
    registry = ManagedAgentRegistry("p", session_factory=lambda: session)

    assert registry.list_day_three_agents() == [
        {
            "name": "projects/p/locations/us-central1/agents/a",
            "agent_id": "urn:a",
            "display_name": "Day Three Curator",
            "description": "Curates",
            "interfaces": [
                {"url": "https://example.test/consume", "protocolBinding": "HTTP_JSON"}
            ],
            "managed": True,
        }
    ]
    assert session.calls[0][1] == 8


def test_managed_registry_failure_is_explicit_not_replaced_with_local_data():
    registry = ManagedAgentRegistry(
        "p", session_factory=lambda: Session(Response(403, {"error": "forbidden"}))
    )

    with pytest.raises(ManagedRegistryError, match="HTTP 403"):
        registry.list_day_three_agents()
