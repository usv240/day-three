"""Issuance is open, so the ceiling has to live on issuance itself.

Removing the invitation code removed the only thing that bounded how many keys could exist.
These tests pin what replaced it: a per-address daily cap, the fact that a key still cannot
be minted without accepting the terms, and that invite-gated mode still works so the change
is a configuration choice rather than a one-way door.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from day_three.live_budget import LiveCallBudget, MemoryCounterStore
from spine.api_access import hash_api_key
from spine.developer_access import KeyIssuer, build_developer_router


class _Store:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def get(self, digest):
        return self.records.get(digest)

    def issue(self, digest, **record):
        self.records[digest] = record

    def revoke(self, digest, revoked_at):
        return self.records.pop(digest, None) is not None


def _app(issuer, budget=None):
    app = FastAPI()
    app.include_router(
        build_developer_router(
            issuer,
            lambda: None,
            product="Day Three",
            scope="day-three:use",
            issuance_budget=budget,
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _body(tenant="clinic_demo"):
    return {"tenant_id": tenant, "label": "Clinic demo", "acknowledge_terms": True}


def _open_issuer(store=None):
    return KeyIssuer(
        store or _Store(), product="day-three", scope="day-three:use",
        prefix="dt_beta", open_issuance=True,
    )


def test_a_key_is_minted_with_no_invitation_code():
    client = _app(_open_issuer())
    response = client.post("/developer/keys", json=_body())

    assert response.status_code == 201
    assert response.json()["api_key"].startswith("dt_beta_")


def test_an_invitation_code_is_ignored_rather_than_rejected_when_issuance_is_open():
    """An older client that still sends the field must not start failing."""
    client = _app(_open_issuer())
    body = _body() | {"invitation_code": "anything at all"}

    assert client.post("/developer/keys", json=body).status_code == 201


def test_issuance_is_capped_per_address():
    budget = LiveCallBudget(MemoryCounterStore(), daily_cap=100, per_caller_cap=2)
    client = _app(_open_issuer(), budget)

    assert client.post("/developer/keys", json=_body()).status_code == 201
    assert client.post("/developer/keys", json=_body()).status_code == 201
    assert client.post("/developer/keys", json=_body()).status_code == 429


def test_a_global_cap_bounds_issuance_across_all_addresses():
    budget = LiveCallBudget(MemoryCounterStore(), daily_cap=1, per_caller_cap=99)
    client = _app(_open_issuer(), budget)

    assert client.post("/developer/keys", json=_body()).status_code == 201
    assert client.post("/developer/keys", json=_body()).status_code == 429


def test_a_refused_key_is_not_counted_against_the_cap():
    """A rejected request never reached the store, so it must not consume the allowance."""
    budget = LiveCallBudget(MemoryCounterStore(), daily_cap=100, per_caller_cap=2)
    client = _app(_open_issuer(), budget)

    client.post("/developer/keys", json={"tenant_id": "x", "label": "y"})  # 422, no terms
    assert client.post("/developer/keys", json=_body()).status_code == 201
    assert client.post("/developer/keys", json=_body()).status_code == 201


def test_the_terms_acknowledgement_is_still_required():
    client = _app(_open_issuer())
    body = _body()
    del body["acknowledge_terms"]

    assert client.post("/developer/keys", json=body).status_code == 422


def test_invite_gated_mode_still_rejects_a_wrong_code():
    """Opening issuance is a configuration choice, not a one-way door."""
    issuer = KeyIssuer(
        _Store(), product="day-three", scope="day-three:use", prefix="dt_beta",
        invitation_hash=hash_api_key("the-real-code"),
    )
    client = _app(issuer)

    assert client.post("/developer/keys", json=_body()).status_code == 401
    assert client.post(
        "/developer/keys", json=_body() | {"invitation_code": "wrong"}
    ).status_code == 401
    assert client.post(
        "/developer/keys", json=_body() | {"invitation_code": "the-real-code"}
    ).status_code == 201


def test_the_config_route_tells_a_client_which_mode_is_running():
    assert _app(_open_issuer()).get("/developer/config").json()["issuance"] == "open"


def test_the_page_enables_the_button_from_the_disabled_mode_not_a_list_of_allowed_modes():
    """The regression that shipped a dead form.

    developer.js gated the submit button on `issuance !== "invite_only"`, so the moment a
    second working mode existed the button was permanently disabled and nobody could mint a
    key. Enumerating the modes that mean "yes" breaks every time a mode is added; testing the
    single mode that means "no" does not.
    """
    from pathlib import Path

    js = Path("web/developer.js").read_text(encoding="utf-8")
    gate = [line for line in js.splitlines() if "button[type=submit]" in line and "disabled" in line]

    assert gate, "no line gates the submit button"
    for line in gate:
        assert "invite_only" not in line, f"button gated on a specific allowed mode: {line.strip()}"


def test_the_config_route_publishes_the_cap_the_page_displays():
    """The number under the button is served, not written into the HTML, so it cannot drift."""
    budget = LiveCallBudget(MemoryCounterStore(), daily_cap=100, per_caller_cap=7)
    config = _app(_open_issuer(), budget).get("/developer/config").json()

    assert config["keys_per_day"] == 7


def test_each_budget_states_the_limit_the_caller_actually_hit():
    """A shared message class must not tell a key-creator their 'live-call allowance' is spent.

    The issuance cap and the API model-call cap both reuse LiveCallBudget. With the message
    hardcoded, hitting the issuance limit returned the public demo's live-call wording, which
    names the wrong resource and the wrong page.
    """
    import re
    from pathlib import Path

    main = Path("service/main.py").read_text(encoding="utf-8")
    budgets = re.findall(r"LiveCallBudget\((.*?)\n\)", main, re.S)

    assert len(budgets) >= 2, f"expected several budgets, found {len(budgets)}"
    for budget in budgets:
        if "live_call_budget" in budget or "from_environment" in budget:
            continue
        assert "caller_denied" in budget, f"budget reuses the demo's wording: {budget[:80]}"


def test_a_denial_message_can_be_set_per_budget():
    from datetime import datetime, timezone

    budget = LiveCallBudget(
        MemoryCounterStore(), daily_cap=99, per_caller_cap=1,
        caller_denied="You have created the maximum number of sandbox keys from this network today.",
    )
    now = datetime.now(timezone.utc)
    budget.consume(now, "someone")

    assert "sandbox keys" in budget.check(now, "someone").reason
    assert "live-call" not in budget.check(now, "someone").reason
