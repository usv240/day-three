"""Firestore's document constraints, pinned.

The antibiogram is the one document this service writes repeatedly, and Firestore rejects
nested arrays. `excluded` is a list of (isolate_id, reason) pairs, which serialises to a list
of lists. It is empty on a facility's first save and only fills once the first-isolate rule
drops a repeat, so a naive round-trip test passed and production returned 500 on the *second*
ingest for any tenant. These tests exercise the second write, not just the first.
"""

from datetime import datetime, timezone

import pytest

from day_three.antibiogram import Antibiogram
from day_three.store import AntibiogramStore

from fakes import FakeFirestore


def _flatten(value, path="doc"):
    """Yield (path, value) for every array nested inside another array."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            if isinstance(item, (list, tuple)):
                yield (f"{path}[{index}]", item)
            yield from _flatten(item, f"{path}[{index}]")


def _grid():
    now = datetime.now(timezone.utc)
    return Antibiogram(facility_id="beta_x", period_start=now, period_end=now)


def test_a_grid_with_exclusions_contains_no_nested_arrays():
    grid = _grid()
    grid.excluded.append(("iso-1", "repeat isolate for patient"))
    grid.excluded.append(("iso-2", "repeat isolate for patient"))

    client = FakeFirestore()
    AntibiogramStore(client).save(grid)

    stored = client.collection("antibiograms").document("beta_x").get().to_dict()
    nested = list(_flatten(stored))
    assert not nested, f"Firestore rejects nested arrays, found: {nested}"


def test_exclusions_survive_a_save_and_load_round_trip():
    now = datetime.now(timezone.utc)
    grid = _grid()
    grid.excluded.append(("iso-1", "repeat isolate for patient"))

    store = AntibiogramStore(FakeFirestore())
    store.save(grid)
    loaded = store.load("beta_x", now, now)

    assert loaded.excluded == [("iso-1", "repeat isolate for patient")]


def test_a_legacy_list_of_lists_still_loads():
    """Documents written before the fix must not break on read."""
    now = datetime.now(timezone.utc)
    client = FakeFirestore()
    client.collection("antibiograms").document("beta_x").set(
        {"revision": 1, "cells": {}, "first_isolate": {},
         "excluded": [["iso-1", "repeat isolate for patient"]]}
    )

    loaded = AntibiogramStore(client).load("beta_x", now, now)

    assert loaded.excluded == [("iso-1", "repeat isolate for patient")]
