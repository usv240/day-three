from datetime import datetime, timedelta, timezone

from day_three.realtime_proof import (
    DEFAULT_DELAY_SECONDS,
    MAX_DELAY_SECONDS,
    MIN_DELAY_SECONDS,
    ProofRecord,
    clamp_delay,
    due_at_for,
    new_proof_id,
)

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def record(fired_at=None, fired_by=None, delay=180) -> ProofRecord:
    return ProofRecord(
        proof_id="rt_test",
        run_id="run_test",
        wake_id="wk_test",
        registered_at=NOW,
        due_at=NOW + timedelta(seconds=delay),
        fired_at=fired_at,
        fired_by=fired_by,
    )


def test_delay_is_clamped_so_a_visitor_cannot_pin_an_instance_open():
    assert clamp_delay(0) == MIN_DELAY_SECONDS
    assert clamp_delay(10_000) == MAX_DELAY_SECONDS
    assert clamp_delay(None) == DEFAULT_DELAY_SECONDS
    assert clamp_delay(300) == 300


def test_a_sleeping_proof_reports_time_remaining_and_no_fire():
    view = record().view(NOW + timedelta(seconds=30))
    assert view["status"] == "sleeping"
    assert view["fired"] is False
    assert view["fired_at"] is None
    assert view["real_seconds_waited"] is None
    assert view["seconds_until_due"] == 150.0


def test_a_due_but_unclaimed_proof_is_not_reported_as_fired():
    view = record().view(NOW + timedelta(seconds=200))
    assert view["status"] == "due"
    assert view["fired"] is False


def test_a_fired_proof_reports_real_elapsed_seconds_and_the_worker():
    fired = NOW + timedelta(seconds=214)
    view = record(fired_at=fired, fired_by="worker_rev_abc").view(fired)
    assert view["status"] == "fired"
    assert view["fired"] is True
    assert view["real_seconds_waited"] == 214.0
    assert view["fired_by_worker"] == "worker_rev_abc"


def test_the_view_states_the_clock_is_wall_clock():
    view = record().view(NOW)
    assert view["clock"] == "wall"
    assert "simulated" in view["note"]


def test_due_at_is_derived_from_the_supplied_clock():
    assert due_at_for(NOW, 120) == NOW + timedelta(seconds=120)


def test_proof_ids_are_unique():
    assert len({new_proof_id() for _ in range(200)}) == 200
