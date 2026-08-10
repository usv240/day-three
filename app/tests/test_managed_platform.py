from day_three.managed_platform import ManagedPlatformError, ManagedPlatformEvidence, RUNTIME_IDS


class Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class Session:
    def __init__(self, break_component=None):
        self.break_component = break_component

    def get(self, url, timeout):
        if self.break_component and self.break_component in url:
            return Response({}, 503)
        for role, engine_id in RUNTIME_IDS.items():
            if engine_id in url:
                return Response(
                    {
                        "name": f"projects/p/locations/us-central1/reasoningEngines/{engine_id}",
                        "displayName": f"Day Three Runtime {role}",
                        "spec": {
                            "identityType": "AGENT_IDENTITY",
                            "effectiveIdentity": f"identity/{engine_id}",
                            "deploymentSpec": {
                                "minInstances": 0,
                                "maxInstances": 1,
                                "agentGatewayConfig": {
                                    "clientToAgentConfig": {
                                        "agentGateway": "projects/p/locations/us-central1/agentGateways/day-three-ingress"
                                    }
                                },
                            },
                        },
                    }
                )
        if "agentGateways" in url:
            return Response(
                {
                    "name": "projects/p/locations/us-central1/agentGateways/day-three-ingress",
                    "googleManaged": {"governedAccessPath": "CLIENT_TO_AGENT"},
                    "protocols": ["MCP"],
                }
            )
        if "modelarmor" in url:
            return Response(
                {
                    "templates": [
                        {"name": "projects/p/locations/us-central1/templates/day-three-agent-input"},
                        {"name": "projects/p/locations/us-central1/templates/day-three-agent-output"},
                        {"name": "projects/p/locations/us-central1/templates/unrelated"},
                    ]
                }
            )
        raise AssertionError(url)


def test_live_platform_evidence_requires_four_unique_identities_and_one_gateway():
    evidence = ManagedPlatformEvidence("p", session_factory=Session).read()
    assert evidence["runtime_count"] == 4
    assert evidence["unique_agent_identity_count"] == 4
    assert evidence["all_agent_identities_unique"] is True
    assert evidence["all_runtimes_gateway_bound"] is True
    assert evidence["gateway"]["governed_access_path"] == "CLIENT_TO_AGENT"
    assert evidence["model_armor_template_count"] == 2


def test_platform_evidence_never_substitutes_local_claims_on_managed_failure():
    evidence = ManagedPlatformEvidence("p", session_factory=lambda: Session("networkservices"))
    try:
        evidence.read()
    except ManagedPlatformError as exc:
        assert "no local fallback" in str(exc)
    else:
        raise AssertionError("managed failure must be visible")

