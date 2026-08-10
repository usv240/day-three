"""Official openFDA shortage data, bounded to the demonstration formulary.

The source is public operational data, not patient data. The watcher stores provenance and a small
normalized snapshot. It never treats an FDA record as a prescribing instruction and never changes
a medication order. A pharmacist must review any downstream draft.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import quote
from urllib.error import HTTPError
from urllib.request import Request, urlopen


OPENFDA_ENDPOINT = "https://api.fda.gov/drug/shortages.json"
OPENFDA_DOCS = "https://open.fda.gov/apis/drug/drugshortages/"
SHORTAGE_DOCUMENT = "current"
SHORTAGE_COLLECTION = "official_drug_shortages"
REFRESH_AFTER = timedelta(hours=24)

DEMO_FORMULARY = (
    "ceftriaxone",
    "cefepime",
    "ciprofloxacin",
    "meropenem",
    "piperacillin-tazobactam",
    "vancomycin",
)


class ShortageSource(Protocol):
    def fetch(self, drug: str) -> dict[str, Any]: ...


class OpenFdaClient:
    """Small stdlib client so the production feed adds no new runtime dependency."""

    def __init__(self, endpoint: str = OPENFDA_ENDPOINT, timeout: float = 8.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def fetch(self, drug: str) -> dict[str, Any]:
        query = quote(f'generic_name:"{drug}"', safe=':"')
        url = f"{self.endpoint}?search={query}&limit=100"
        request = Request(url, headers={"User-Agent": "day-three-hackathon/1.0"})
        try:
            response = urlopen(request, timeout=self.timeout)  # noqa: S310, official fixed host
        except HTTPError as exc:
            if exc.code == 404:
                return {"meta": {}, "results": []}
            raise
        with response:
            return json.loads(response.read().decode("utf-8"))


class ShortageStore:
    def __init__(self, client) -> None:
        self._document = client.collection(SHORTAGE_COLLECTION).document(SHORTAGE_DOCUMENT)

    def get(self) -> dict[str, Any] | None:
        snapshot = self._document.get()
        return snapshot.to_dict() if snapshot.exists else None

    def save(self, snapshot: dict[str, Any]) -> None:
        self._document.set(snapshot)


@dataclass
class ShortageWatch:
    source: ShortageSource
    store: ShortageStore
    clock: Any

    def refresh_if_stale(self) -> dict[str, Any]:
        existing = self.store.get()
        now = self.clock.now()
        refreshed = _as_datetime((existing or {}).get("refreshed_at"))
        if refreshed is not None and now - refreshed < REFRESH_AFTER:
            return {"status": "fresh", "snapshot": existing}
        return {"status": "refreshed", "snapshot": self.refresh()}

    def refresh(self) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        source_dates: list[str] = []
        errors: list[dict[str, str]] = []

        for drug in DEMO_FORMULARY:
            try:
                payload = self.source.fetch(drug)
            except Exception as exc:  # one unavailable query must not erase the last good snapshot
                errors.append({"drug": drug, "error": type(exc).__name__})
                continue

            source_date = str((payload.get("meta") or {}).get("last_updated", ""))
            if source_date:
                source_dates.append(source_date)
            for item in payload.get("results") or []:
                normalized = normalize_record(drug, item)
                if normalized is not None:
                    records.append(normalized)

        previous = self.store.get()
        if not records and errors and previous is not None:
            return {**previous, "last_refresh_errors": errors, "stale": True}
        if not records and errors:
            unavailable = {
                "source": "FDA openFDA Drug Shortages",
                "source_url": OPENFDA_ENDPOINT,
                "documentation_url": OPENFDA_DOCS,
                "source_last_updated": None,
                "refreshed_at": self.clock.now(),
                "formulary": list(DEMO_FORMULARY),
                "active_formulary_shortages": [],
                "records": [],
                "errors": errors,
                "stale": True,
                "safety": "The official feed could not be read. No availability inference was made. A pharmacist verifies local inventory and every medication decision.",
            }
            self.store.save(unavailable)
            return unavailable


        active = sorted({item["formulary_drug"] for item in records if item["active"]})
        snapshot = {
            "source": "FDA openFDA Drug Shortages",
            "source_url": OPENFDA_ENDPOINT,
            "documentation_url": OPENFDA_DOCS,
            "source_last_updated": max(source_dates, default=None),
            "refreshed_at": self.clock.now(),
            "formulary": list(DEMO_FORMULARY),
            "active_formulary_shortages": active,
            "records": records,
            "errors": errors,
            "stale": False,
            "safety": (
                "National availability signal only. A pharmacist verifies local inventory and "
                "approves every medication decision."
            ),
        }
        self.store.save(snapshot)
        return snapshot


def normalize_record(formulary_drug: str, item: dict[str, Any]) -> dict[str, Any] | None:
    generic = str(item.get("generic_name", "")).strip()
    if formulary_drug.lower() not in generic.lower():
        return None
    status = str(item.get("status", "")).strip()
    availability = str(item.get("availability", "")).strip()
    combined = f"{status} {availability}".lower()
    inactive = "resolved" in combined or "discontinued" in combined or availability.lower() in {"available", "available."}
    active_words = ("shortage", "unavailable", "limited availability", "currently in shortage")
    active = any(word in combined for word in active_words) and not inactive
    return {
        "formulary_drug": formulary_drug,
        "generic_name": generic,
        "status": status or None,
        "availability": availability or None,
        "update_date": item.get("update_date"),
        "company_name": item.get("company_name"),
        "presentation": item.get("presentation"),
        "active": active,
    }


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None
