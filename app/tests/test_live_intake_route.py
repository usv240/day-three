"""The credential-free live model route: budget, honesty, and blast radius.

The point of this route is to answer a fair criticism -- the console replays recorded model
output -- so its tests are mostly about it being *genuinely* the same call, and about it not
becoming an open model proxy or an unbounded bill.
"""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from day_three.intake import IntakeAgent, ReplayClient
from day_three.live_budget import LiveCallBudget, MemoryCounterStore
from fakes import FakeFirestore, FrozenSimClock
from service.day_three_routes import build_router

ROOT = Path(__file__).resolve().parent.parent


class RecordingAgentFactory:
    """Stands in for the Vertex call, capturing exactly what the route asked the model to do."""

    model_name = "gemini-3.5-flash"

    def __init__(self):
        self.calls = []
        recording = json.loads(
            (ROOT / "fixtures" / "recordings" / "ecoli_urine.json").read_text(encoding="utf-8")
        )
        self._recording = recording

    def __call__(self):
        outer = self

        class Agent(IntakeAgent):
            def parse(self, artifact_id, document, patient_id, image=None):
                outer.calls.append(
                    {"document": document, "image_bytes": len(image or b"")}
                )
                return super().parse(artifact_id, document, patient_id, image)

        return Agent(ReplayClient({"default": self._recording}))


def build(budget=None, factory=None) -> tuple[TestClient, RecordingAgentFactory, LiveCallBudget]:
    factory = factory or RecordingAgentFactory()
    budget = budget or LiveCallBudget(MemoryCounterStore(), daily_cap=5, per_caller_cap=2)
    app = FastAPI()
    app.include_router(build_router(
        FakeFirestore(),
        FrozenSimClock(),
        lambda: None,
        lambda: None,
        None,
        live_intake_factory=factory,
        live_budget=budget,
    ))
    return TestClient(app), factory, budget



def test_live_route_sends_the_image_with_no_source_text():
    """The recorded run transcribed a scan. If the route passed the truth file as the document
    the model would be doing an easier job and the published comparison would be meaningless."""
    api, factory, _ = build()
    response = api.post("/day-three/live-intake", json={"fixture": "ecoli_urine"})
    assert response.status_code == 200
    assert len(factory.calls) == 1
    assert factory.calls[0]["document"] == ""
    assert factory.calls[0]["image_bytes"] > 0


def test_live_response_is_labelled_live_and_graded_against_the_published_run():
    api, _, _ = build()
    body = api.post("/day-three/live-intake", json={"fixture": "ecoli_urine"}).json()
    assert body["live"] is True
    assert body["replayed"] is False
    assert body["of"] == 8
    assert body["recorded_run"]["of"] == 8
    assert "latency_ms" in body


def test_free_text_cannot_be_sent_to_the_paid_model():
    """A credential-free paid route must not become a general model proxy."""
    api, factory, _ = build()
    response = api.post(
        "/day-three/live-intake", json={"fixture": "../../etc/passwd"}
    )
    assert response.status_code == 404
    assert factory.calls == []


def test_unknown_fixture_is_refused():
    api, factory, _ = build()
    assert api.post("/day-three/live-intake", json={"fixture": "nope"}).status_code == 404
    assert factory.calls == []


def test_budget_exhaustion_returns_429_and_stops_calling_the_model():
    api, factory, _ = build(
        budget=LiveCallBudget(MemoryCounterStore(), daily_cap=1, per_caller_cap=1)
    )
    assert api.post("/day-three/live-intake", json={"fixture": "ecoli_urine"}).status_code == 200
    blocked = api.post("/day-three/live-intake", json={"fixture": "ecoli_urine"})
    assert blocked.status_code == 429
    assert len(factory.calls) == 1


def test_status_route_reports_remaining_budget_without_spending_it():
    api, factory, _ = build()
    body = api.get("/day-three/live-intake").json()
    assert body["available"] is True
    assert body["live_calls_used_today"] == 0
    assert factory.calls == []


def test_route_reports_unavailable_when_live_calls_are_not_configured():
    app = FastAPI()
    app.include_router(build_router(FakeFirestore(), FrozenSimClock(), lambda: None, lambda: None, None))
    api = TestClient(app)
    assert api.get("/day-three/live-intake").json()["available"] is False
    assert api.post("/day-three/live-intake", json={"fixture": "ecoli_urine"}).status_code == 503


def test_live_call_never_writes_to_the_antibiogram():
    """A judge must be able to press this repeatedly without disturbing demo state, and a live
    model answer must never be able to corrupt the recorded evidence grid."""
    store = FakeFirestore()
    factory = RecordingAgentFactory()
    app = FastAPI()
    app.include_router(build_router(
        store,
        FrozenSimClock(),
        lambda: None,
        lambda: None,
        None,
        live_intake_factory=factory,
        live_budget=LiveCallBudget(MemoryCounterStore(), daily_cap=9, per_caller_cap=9),
    ))
    api = TestClient(app)
    for _ in range(3):
        assert api.post("/day-three/live-intake", json={"fixture": "ecoli_urine"}).status_code == 200

    written = {
        name: collection.documents
        for name, collection in store.collections.items()
        if collection.documents
    }
    assert "antibiograms" not in written
    assert "isolates" not in written
