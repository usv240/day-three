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
from fakes import FakeFirestore

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


def test_pending_proofs_are_still_found_once_many_have_already_fired():
    """The bug that stopped the timer in production.

    Ordering by due_at and taking the first `limit` records returns the oldest, which are the
    ones already fired. Filtering the claimed ones out in memory afterwards then leaves nothing,
    so the scanner stopped reaching pending proofs entirely. It failed at twenty-one records and
    would have failed silently during the recording.
    """
    from day_three.realtime_proof import RealtimeProofStore

    store = RealtimeProofStore(FakeFirestore())
    now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)

    for index in range(25):
        registered = now - timedelta(minutes=30 + index)
        record = ProofRecord(
            proof_id=f"rt_old_{index:02d}", run_id=f"run_{index}", wake_id=f"wk_{index}",
            registered_at=registered, due_at=registered + timedelta(seconds=60),
            fired_at=registered + timedelta(seconds=90), fired_by="worker_old",
        )
        store.save(record)

    pending_registered = now - timedelta(seconds=90)
    pending = ProofRecord(
        proof_id="rt_pending", run_id="run_p", wake_id="wk_p",
        registered_at=pending_registered, due_at=pending_registered + timedelta(seconds=60),
        fired_at=None, fired_by=None,
    )
    store.save(pending)

    due = store.due(now, limit=20)

    assert [r.proof_id for r in due] == ["rt_pending"], (
        "a pending proof must be reachable regardless of how many fired records precede it"
    )


def test_a_proof_older_than_the_lookback_is_not_resurrected():
    """A stale record firing now would report a wait that never happened."""
    from day_three.realtime_proof import LOOKBACK, RealtimeProofStore

    store = RealtimeProofStore(FakeFirestore())
    now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
    registered = now - LOOKBACK - timedelta(hours=1)
    store.save(ProofRecord(
        proof_id="rt_stale", run_id="run_s", wake_id="wk_s",
        registered_at=registered, due_at=registered + timedelta(seconds=60),
        fired_at=None, fired_by=None,
    ))

    assert store.due(now, limit=20) == []
