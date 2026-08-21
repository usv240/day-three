"""The decision the demo could not previously show.

Every other control demonstrates the agent acting on evidence it has. The harder behaviour,
and the one that lived only in the unit tests, is what it does with evidence it does not have:
it looks, finds no culture, registers exactly one more check, and then refuses to register
another. These tests pin both branches through the HTTP route a judge actually presses.
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from service.day_three_routes import build_router
from spine.state import MemoryStateStore, Runner
from spine.wake import MemoryWakeStore, WakeScheduler

from fakes import FakeFirestore, FrozenSimClock


def build():
    store = FakeFirestore()
    clock = FrozenSimClock()
    state_store = MemoryStateStore()
    wakes = MemoryWakeStore()
    scheduler = WakeScheduler(wakes, clock)

    app = FastAPI()
    app.include_router(build_router(
        store,
        clock,
        lambda: scheduler,
        lambda: Runner(state_store, clock, owner="test-worker"),
        None,
    ))
    return TestClient(app), wakes, store


def test_the_first_wake_finds_no_culture_and_books_one_more_check():
    client, wakes, _ = build()

    body = client.post("/day-three/wake-without-evidence").json()

    assert body["action"] == "culture_result_missing"
    assert body["recheck_registered"] is True
    assert body["attempt"] == 1
    assert body["recheck_due_at"] is not None
    assert "refused to guess" in body["detail"] or "instead of guessing" in body["detail"]


def test_the_second_wake_refuses_to_book_another():
    """A missing result must not become an endless loop."""
    client, _, _ = build()

    client.post("/day-three/wake-without-evidence")
    body = client.post("/day-three/wake-without-evidence").json()

    assert body["action"] == "culture_result_missing"
    assert body["recheck_registered"] is False, "the agent booked a second recheck"
    assert body["attempt"] == 2
    assert body["recheck_due_at"] is None


def test_the_recheck_is_a_real_wake_on_the_scheduler():
    """The reply is not a story about a wake; a wake exists."""
    client, wakes, _ = build()

    client.post("/day-three/wake-without-evidence")

    registered = [
        w for w in wakes._wakes.values()
        if int(w.payload.get("recheck_count", 0)) == 1
    ]
    assert len(registered) == 1, f"expected one recheck wake, found {len(registered)}"
    assert registered[0].status == "pending"


def test_it_never_claims_a_clinical_action():
    client, _, _ = build()

    body = client.post("/day-three/wake-without-evidence").json()

    assert body["external_side_effect"] is False
    assert body["requires_pharmacist_approval"] is True


def test_it_does_not_touch_the_public_antibiogram():
    """Pressing this cannot disturb the grid a judge is looking at."""
    client, _, _ = build()

    before = client.get("/day-three/antibiogram").json()
    client.post("/day-three/wake-without-evidence")
    after = client.get("/day-three/antibiogram").json()

    assert before.get("revision") == after.get("revision")
