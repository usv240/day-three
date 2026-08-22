"""A valid key must not be an uncapped bill.

The keyed API is the path an invited tester uses with their own data. It is the only keyed
route that invokes a model, so it is the only one that can cost money, and a key that never
expired its daily allowance would make the invitation code the sole thing standing between
the internet and unbounded spend. These tests pin the cap itself, the independence of the
keyed counter from the public one, and the rule that a denied call is never charged.
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from day_three.live_budget import LiveCallBudget, MemoryCounterStore
from service.beta_routes import build_beta_router

from fakes import FakeFirestore


class _StubAgent:
    def __init__(self) -> None:
        self.calls = 0

    def parse(self, artifact_id, document, subject, image=None):
        self.calls += 1
        from day_three.intake import ExtractionError

        raise ExtractionError("stub: no model in tests")


class _Principal:
    tenant_id = "t1"
    key_id = "key_a"
    scopes = ("day-three:use",)


def _client(budget, principal=_Principal()):
    from spine.clock import RealClock

    app = FastAPI()
    agent = _StubAgent()
    app.include_router(
        build_beta_router(
            FakeFirestore(),
            RealClock(),
            lambda: principal,
            intake_factory=lambda: agent,
            budget=budget,
        )
    )
    return TestClient(app, raise_server_exceptions=False), agent


_DOCUMENT = (
    "Urine culture. Escherichia coli isolated. Nitrofurantoin susceptible. "
    "Ciprofloxacin resistant. Trimethoprim-sulfamethoxazole resistant."
)


def _post(client):
    return client.post(
        "/v1/intake",
        json={
            "document": _DOCUMENT,
            "subject_ref": "SUBJECT-a1",
            "acknowledge_deidentified": True,
        },
    )


def test_calls_are_refused_once_the_per_key_cap_is_reached():
    budget = LiveCallBudget(MemoryCounterStore(), daily_cap=100, per_caller_cap=2)
    client, agent = _client(budget)

    assert _post(client).status_code == 422  # stub agent, but the call was charged
    assert _post(client).status_code == 422
    denied = _post(client)

    assert denied.status_code == 429
    assert agent.calls == 2, "the model must not be invoked once the cap is spent"


def test_a_denied_call_is_never_charged():
    budget = LiveCallBudget(MemoryCounterStore(), daily_cap=100, per_caller_cap=1)
    client, _ = _client(budget)

    _post(client)
    for _ in range(3):
        assert _post(client).status_code == 429

    now = datetime.now(timezone.utc)
    assert budget.check(now, "key_a").caller_used == 1, "denied calls must not push the day further"


def test_a_failed_extraction_still_costs_budget():
    """The model was invoked, so the money was spent. Failing open would be a free retry loop."""
    budget = LiveCallBudget(MemoryCounterStore(), daily_cap=100, per_caller_cap=5)
    client, _ = _client(budget)

    assert _post(client).status_code == 422
    assert budget.check(datetime.now(timezone.utc), "key_a").caller_used == 1


def test_the_keyed_budget_counts_in_its_own_collection():
    """A busy public demo day must not lock out an invited tester, and vice versa."""
    from day_three.live_budget import FirestoreCounterStore

    client = FakeFirestore()
    assert (
        FirestoreCounterStore(client)._collection
        != FirestoreCounterStore(client, "beta_api_budget")._collection
    )


def test_every_deployed_budget_counts_in_its_own_collection():
    """The property, not the count: budgets may be added, but none may share a counter.

    Two budgets sharing a collection would let public demo traffic exhaust the keyed API's
    allowance, or key issuance exhaust either. Pinning the number instead would just make this
    test fail every time a legitimate budget is added.
    """
    import re
    from pathlib import Path

    main = Path("service/main.py").read_text(encoding="utf-8")
    collections = re.findall(r'FirestoreCounterStore\(client(?:,\s*"([^"]+)")?\)', main)

    assert len(collections) >= 2, f"expected several counter stores, found {collections}"
    assert len(set(collections)) == len(collections), f"budgets share a collection: {collections}"


def test_the_intake_response_names_the_model_that_answered():
    """A live model call that does not say which model answered proves nothing checkable.

    The video makes its only live Gemini call on this route, and the developer page renders what
    comes back. If the response stops naming the model, the one moment where the mandatory
    technology is visible on screen goes silent.
    """
    import json
    from pathlib import Path
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from day_three.intake import IntakeAgent, ReplayClient
    from spine.clock import RealClock

    root = Path(__file__).resolve().parent.parent
    recording = json.loads(
        (root / "fixtures" / "recordings" / "ecoli_urine.json").read_text(encoding="utf-8")
    )
    app = FastAPI()
    app.include_router(build_beta_router(
        FakeFirestore(), RealClock(), lambda: _Principal(),
        intake_factory=lambda: IntakeAgent(ReplayClient({"default": recording})),
        model_name="gemini-3.5-flash",
    ))
    # Built from the recording's own quoted lines, so the verifier can ground every value. The
    # committed scan text carries patient identifiers, which this route refuses by design.
    document = "CULTURE AND SUSCEPTIBILITY REPORT\n" + "\n".join(
        item["quoted_text"] for item in recording["susceptibilities"]
    )
    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/intake",
        json={"document": document, "subject_ref": "SUBJECT-a1", "acknowledge_deidentified": True},
    )
    assert response.status_code == 201, response.json()
    body = response.json()

    assert body["read_by"]["model"] == "gemini-3.5-flash"
    assert body["read_by"]["platform"] == "Vertex AI"


def test_the_developer_page_renders_the_model_name():
    from pathlib import Path

    js = Path("web/developer.js").read_text(encoding="utf-8")
    assert "read_by" in js, "the page no longer shows which model answered"
