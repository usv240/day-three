from datetime import datetime, timedelta, timezone

from day_three.shortages import DEMO_FORMULARY, ShortageWatch, normalize_record


class Clock:
    def __init__(self):
        self.value = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)

    def now(self):
        return self.value


class Store:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def save(self, value):
        self.value = value


class Source:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def fetch(self, drug):
        self.calls.append(drug)
        if self.fail:
            raise TimeoutError("offline")
        availability = "Limited availability" if drug == "ceftriaxone" else "Available"
        return {
            "meta": {"last_updated": "2026-08-08"},
            "results": [
                {
                    "generic_name": f"{drug.title()} Injection",
                    "status": "Current",
                    "availability": availability,
                    "update_date": "08/08/2026",
                    "company_name": "Synthetic manufacturer label",
                }
            ],
        }


def test_official_feed_is_filtered_to_formulary_and_keeps_provenance():
    source = Source()
    store = Store()
    snapshot = ShortageWatch(source, store, Clock()).refresh()

    assert source.calls == list(DEMO_FORMULARY)
    assert snapshot["active_formulary_shortages"] == ["ceftriaxone"]
    assert snapshot["source"] == "FDA openFDA Drug Shortages"
    assert snapshot["source_last_updated"] == "2026-08-08"
    assert "pharmacist" in snapshot["safety"].lower()


def test_fresh_snapshot_prevents_repeated_external_calls():
    clock = Clock()
    existing = {"refreshed_at": clock.now(), "active_formulary_shortages": []}
    source = Source()
    result = ShortageWatch(source, Store(existing), clock).refresh_if_stale()

    assert result["status"] == "fresh"
    assert source.calls == []


def test_stale_snapshot_refreshes_after_twenty_four_hours():
    clock = Clock()
    existing = {
        "refreshed_at": clock.now() - timedelta(hours=25),
        "active_formulary_shortages": [],
    }
    source = Source()
    result = ShortageWatch(source, Store(existing), clock).refresh_if_stale()

    assert result["status"] == "refreshed"
    assert source.calls


def test_total_feed_failure_preserves_last_good_snapshot():
    clock = Clock()
    previous = {
        "refreshed_at": clock.now() - timedelta(days=2),
        "active_formulary_shortages": ["cefepime"],
    }
    snapshot = ShortageWatch(Source(fail=True), Store(previous), clock).refresh()
    assert snapshot["active_formulary_shortages"] == ["cefepime"]
    assert snapshot["stale"] is True
    assert len(snapshot["last_refresh_errors"]) == len(DEMO_FORMULARY)


def test_first_refresh_failure_is_explicitly_stale_not_false_all_clear():
    clock = Clock()
    store = Store()
    snapshot = ShortageWatch(Source(fail=True), store, clock).refresh()

    assert snapshot["stale"] is True
    assert snapshot["active_formulary_shortages"] == []
    assert len(snapshot["errors"]) == len(DEMO_FORMULARY)
    assert "could not be read" in snapshot["safety"]
    assert store.value == snapshot



def test_available_is_not_misread_as_unavailable():
    active = normalize_record(
        "ceftriaxone",
        {
            "generic_name": "Ceftriaxone Injection",
            "status": "Current",
            "availability": "Limited availability",
        },
    )
    available = normalize_record(
        "ceftriaxone",
        {
            "generic_name": "Ceftriaxone Injection",
            "status": "Current",
            "availability": "Available",
        },
    )

    assert active["active"] is True
    assert available["active"] is False
