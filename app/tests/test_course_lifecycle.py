"""A course has to be able to end.

CourseStatus shipped with four values and no writer, so every course read as ACTIVE forever,
including ones whose fourteen-day ladder had already run out. CourseWatch.discharge, which
cancels the reviews that no longer apply and arms the readmission check, was reachable only
from tests. These pin both transitions through the surfaces a judge can reach.
"""

from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from day_three.course import CourseStatus, LADDER, WakeKind
from day_three.wake_actions import FINAL_RUNG_HOURS
from service.day_three_routes import build_router
from spine.state import MemoryStateStore, Runner
from spine.wake import MemoryWakeStore, WakeScheduler

from fakes import FakeFirestore, FrozenSimClock


def build():
    store = FakeFirestore()
    clock = FrozenSimClock()
    scheduler = WakeScheduler(MemoryWakeStore(), clock)
    app = FastAPI()
    app.include_router(build_router(
        store, clock, lambda: scheduler,
        lambda: Runner(MemoryStateStore(), clock, owner="test-worker"), None,
    ))
    return TestClient(app), clock


def admit(client):
    return client.post("/day-three/course", json={
        "patient_id": "P-1",
        "regimen": ["piperacillin-tazobactam"],
        "indication": "suspected sepsis",
    })


def test_the_final_rung_is_derived_from_the_ladder_not_typed():
    """Adding a sixth review must move the closing point, not silently orphan it."""
    assert FINAL_RUNG_HOURS == int(
        max(offset for _k, offset, _w in LADDER).total_seconds() // 3600
    )


def test_a_new_course_is_active_and_counted_as_watched():
    client, _ = build()
    admit(client)

    body = client.get("/day-three/courses").json()

    assert body["watching"] == 1
    assert body["finished"] == 0
    assert body["by_status"][CourseStatus.ACTIVE.value] == 1


def test_discharge_cancels_the_reviews_that_no_longer_apply():
    client, _ = build()
    admit(client)

    body = client.post("/day-three/discharge").json()

    assert body["status"] == CourseStatus.DISCHARGED.value
    assert body["cancelled_wakes"] >= 1, "no inpatient review was cancelled"
    assert body["readmission_due_at"], "no readmission check was armed"
    assert body["external_side_effect"] is False


def test_discharge_arms_the_readmission_check_thirty_days_out():
    client, clock = build()
    admit(client)

    body = client.post("/day-three/discharge").json()

    from datetime import datetime
    due = datetime.fromisoformat(body["readmission_due_at"])
    assert timedelta(days=29) <= due - clock.now() <= timedelta(days=31)


def test_discharging_with_no_active_course_is_refused_rather_than_guessed():
    client, _ = build()

    assert client.post("/day-three/discharge").status_code == 409


def test_a_discharged_course_is_no_longer_counted_as_watched():
    client, _ = build()
    admit(client)
    client.post("/day-three/discharge")

    body = client.get("/day-three/courses").json()

    assert body["watching"] == 0
    assert body["by_status"][CourseStatus.DISCHARGED.value] == 1


def test_the_last_scheduled_review_closes_the_course():
    """Without this the ladder runs out and the course stays ACTIVE forever."""
    from day_three.store import CourseStore, IsolateStore
    from day_three.wake_actions import CourseActionExecutor
    from spine.wake import Wake

    store = FakeFirestore()
    clock = FrozenSimClock()
    scheduler = WakeScheduler(MemoryWakeStore(), clock)
    app = FastAPI()
    app.include_router(build_router(
        store, clock, lambda: scheduler,
        lambda: Runner(MemoryStateStore(), clock, owner="t"), None,
    ))
    client = TestClient(app)
    admit(client)
    course_id = client.get("/day-three/courses").json()["courses"][0]["course_id"]
    run_id = client.get("/day-three/courses").json()["courses"][0]["run_id"]

    CourseActionExecutor(
        CourseStore(store), IsolateStore(store), scheduler
    ).execute(Wake(
        wake_id="wk_final", run_id=run_id,
        kind=WakeKind.STOP_DATE_CHECK.value, due_at=clock.now(),
        payload={"course_id": course_id, "offset_hours": FINAL_RUNG_HOURS},
    ))

    body = client.get("/day-three/courses").json()
    assert body["by_status"][CourseStatus.CLOSED.value] == 1
    assert body["finished"] == 1


def test_an_earlier_stop_date_check_does_not_close_the_course():
    """There are two stop-date checks before the last one. Only the last one ends it."""
    from day_three.store import CourseStore, IsolateStore
    from day_three.wake_actions import CourseActionExecutor
    from spine.wake import Wake

    store = FakeFirestore()
    clock = FrozenSimClock()
    scheduler = WakeScheduler(MemoryWakeStore(), clock)
    app = FastAPI()
    app.include_router(build_router(
        store, clock, lambda: scheduler,
        lambda: Runner(MemoryStateStore(), clock, owner="t"), None,
    ))
    client = TestClient(app)
    admit(client)
    record = client.get("/day-three/courses").json()["courses"][0]

    CourseActionExecutor(
        CourseStore(store), IsolateStore(store), scheduler
    ).execute(Wake(
        wake_id="wk_day7", run_id=record["run_id"],
        kind=WakeKind.STOP_DATE_CHECK.value, due_at=clock.now(),
        payload={"course_id": record["course_id"], "offset_hours": 168},
    ))

    assert client.get("/day-three/courses").json()["watching"] == 1
