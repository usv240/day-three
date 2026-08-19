"""The wall-clock proof route: a wake a visitor cannot advance."""

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from day_three.live_budget import LiveCallBudget, MemoryCounterStore
from day_three.realtime_proof import PROJECT as REALTIME_PROJECT
from service.day_three_routes import build_router
from spine.state import MemoryStateStore, Runner
from fakes import FakeFirestore, FrozenSimClock

WALL = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)


class MovableClock:
    """Stands in for the wall clock so a test need not wait three real minutes."""

    def __init__(self):
        self.instant = WALL

    def now(self):
        return self.instant


def build():
    store = FakeFirestore()
    wall = MovableClock()
    state_store = MemoryStateStore()

    def runner():
        return Runner(state_store, wall, owner="test-worker")

    app = FastAPI()
    app.include_router(build_router(
        store,
        FrozenSimClock(),
        lambda: None,
        runner,
        None,
        live_budget=LiveCallBudget(MemoryCounterStore(), daily_cap=9, per_caller_cap=9),
        realtime_clock=wall,
    ))
    return TestClient(app), wall, store, state_store


def test_proof_registers_on_the_wall_clock_in_its_own_namespace():
    api, wall, store, state_store = build()
    body = api.post("/day-three/realtime-proof", json={"delay_seconds": 120}).json()
    assert body["delay_seconds"] == 120
    assert body["due_at"] == (WALL + timedelta(seconds=120)).isoformat()

    saved = list(store.collections["realtime_proofs"].documents.values())
    assert len(saved) == 1
    # The run is namespaced away from the demo project, and the due-work row lives in the proof
    # collection rather than the shared wake table, which another service scans unfiltered.
    assert state_store.get_run(saved[0].data["run_id"]).project_id == REALTIME_PROJECT


def test_a_visitor_cannot_shorten_the_wait_below_the_floor():
    api, _, _, _ = build()
    body = api.post("/day-three/realtime-proof", json={"delay_seconds": 1}).json()
    assert body["delay_seconds"] == 60


def test_proof_reports_sleeping_until_a_worker_claims_it():
    api, wall, _, _ = build()
    proof_id = api.post("/day-three/realtime-proof", json={"delay_seconds": 120}).json()["proof_id"]
    view = api.get(f"/day-three/realtime-proof/{proof_id}").json()
    assert view["status"] == "sleeping"
    assert view["fired"] is False
    assert view["clock"] == "wall"


def test_time_passing_alone_does_not_mark_it_fired():
    """Only a worker claiming the wake counts. Elapsed time is not evidence by itself."""
    api, wall, _, _ = build()
    proof_id = api.post("/day-three/realtime-proof", json={"delay_seconds": 120}).json()["proof_id"]
    wall.instant = WALL + timedelta(seconds=600)
    view = api.get(f"/day-three/realtime-proof/{proof_id}").json()
    assert view["status"] == "due"
    assert view["fired"] is False
    assert view["real_seconds_waited"] is None


def test_unknown_proof_is_404():
    api, _, _, _ = build()
    assert api.get("/day-three/realtime-proof/rt_nope").status_code == 404


def test_route_is_unavailable_when_no_wall_clock_scheduler_is_configured():
    app = FastAPI()
    app.include_router(build_router(FakeFirestore(), FrozenSimClock(), lambda: None, lambda: None, None))
    api = TestClient(app)
    assert api.post("/day-three/realtime-proof", json={}).status_code == 503


def test_proof_row_is_not_on_the_shared_wake_table():
    """Regression. The first version registered the proof as an ordinary spine wake. Another
    deployment's worker scans that table unfiltered on its own clock; it claimed the wake and
    completed it with its own handler, so the proof never recorded a firing and the evidence
    silently disappeared while the wake read `done`. The due-work row must stay in a collection
    only this service scans."""
    api, _, store, _ = build()
    api.post("/day-three/realtime-proof", json={"delay_seconds": 120})
    written = {name for name, c in store.collections.items() if c.documents}
    assert "realtime_proofs" in written
    assert "wakes" not in written
