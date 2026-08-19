from datetime import datetime, timezone

from day_three.live_budget import LiveCallBudget, MemoryCounterStore

NOW = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
NEXT_DAY = datetime(2026, 8, 20, 0, 1, tzinfo=timezone.utc)


def budget(**kwargs) -> LiveCallBudget:
    return LiveCallBudget(MemoryCounterStore(), **kwargs)


def test_a_fresh_day_allows_the_call():
    decision = budget().check(NOW, "caller-a")
    assert decision.allowed
    assert decision.global_used == 0


def test_per_caller_cap_stops_one_visitor_without_closing_the_demo():
    b = budget(daily_cap=100, per_caller_cap=2)
    for _ in range(2):
        assert b.check(NOW, "caller-a").allowed
        b.consume(NOW, "caller-a")

    assert not b.check(NOW, "caller-a").allowed
    # A different visitor is unaffected: the cap is per caller, not a global kill switch.
    assert b.check(NOW, "caller-b").allowed


def test_global_cap_stops_everyone():
    b = budget(daily_cap=2, per_caller_cap=100)
    b.consume(NOW, "caller-a")
    b.consume(NOW, "caller-b")
    assert not b.check(NOW, "caller-c").allowed


def test_denied_calls_are_never_counted():
    """A caller at the wall must not be able to push the day deeper into denial."""
    b = budget(daily_cap=1, per_caller_cap=1)
    b.consume(NOW, "caller-a")
    before = b.check(NOW, "caller-b").global_used
    for _ in range(5):
        b.check(NOW, "caller-b")
    assert b.check(NOW, "caller-b").global_used == before


def test_budget_resets_on_the_next_day():
    b = budget(daily_cap=1, per_caller_cap=1)
    b.consume(NOW, "caller-a")
    assert not b.check(NOW, "caller-a").allowed
    assert b.check(NEXT_DAY, "caller-a").allowed


def test_decision_is_publishable_without_leaking_the_caller_key():
    payload = budget().check(NOW, "caller-a").as_dict()
    assert "caller-a" not in str(payload)
    assert payload["live_calls_allowed_today"] == 40
