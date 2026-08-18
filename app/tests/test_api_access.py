import json

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from spine.api_access import ApiKeyAuthenticator, ApiPrincipal, hash_api_key


def app_for(auth: ApiKeyAuthenticator) -> TestClient:
    app = FastAPI()

    @app.get("/v1/whoami")
    def whoami(principal: ApiPrincipal = Depends(auth)):
        return {"tenant_id": principal.tenant_id, "key_id": principal.key_id}

    return TestClient(app)


def test_key_resolves_server_controlled_tenant_and_openapi_security_scheme():
    auth = ApiKeyAuthenticator.from_plaintext({
        "dt_test_secret": {"tenant_id": "clinic_one", "label": "Clinic one", "scopes": ["day-three:use"]}
    })
    api = app_for(auth)
    response = api.get("/v1/whoami", headers={"X-API-Key": "dt_test_secret"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "clinic_one"
    assert "BetaApiKey" in api.get("/openapi.json").json()["components"]["securitySchemes"]


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_missing_or_wrong_key_is_unauthorized(headers):
    auth = ApiKeyAuthenticator.from_plaintext({
        "right": {"tenant_id": "tenant_one", "label": "One", "scopes": ["*"]}
    })
    assert app_for(auth).get("/v1/whoami", headers=headers).status_code == 401


def test_unprovisioned_beta_api_fails_closed():
    assert app_for(ApiKeyAuthenticator()).get("/v1/whoami").status_code == 503


def test_environment_contains_hashes_not_plaintext(monkeypatch):
    digest = hash_api_key("never-store-this")
    monkeypatch.setenv("BETA_API_KEY_HASHES", json.dumps({
        digest: {"tenant_id": "tenant_one", "label": "One", "scopes": ["*"]}
    }))
    auth = ApiKeyAuthenticator.from_environment()
    assert app_for(auth).get("/v1/whoami", headers={"X-API-Key": "never-store-this"}).status_code == 200

