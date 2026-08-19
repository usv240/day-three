"""Shared in-memory doubles for route tests.

Kept in one place so the live-model route and the wall-clock proof route are exercised against
identical storage behaviour, including `merge=True`, which the proof record relies on.
"""

from datetime import datetime, timezone


class Snapshot:
    def __init__(self, document):
        self._document = document

    @property
    def exists(self):
        return self._document.data is not None

    def to_dict(self):
        return dict(self._document.data or {})


class Document:
    def __init__(self):
        self.data = None

    def set(self, data, merge=False):
        if merge and self.data is not None:
            self.data.update(data)
        else:
            self.data = dict(data)

    def get(self):
        return Snapshot(self)


class Collection:
    def __init__(self):
        self.documents = {}
        self._filters = []

    def document(self, doc_id):
        return self.documents.setdefault(doc_id, Document())

    def where(self, field, _op, value):
        self._filters = [(field, value)]
        return self

    def limit(self, _n):
        return self

    def stream(self):
        for document in self.documents.values():
            data = document.data or {}
            if all(data.get(field) == value for field, value in self._filters):
                yield Snapshot(document)


class FakeFirestore:
    project = "test-project"

    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())


class FrozenSimClock:
    """Stands in for the simulated demo clock."""

    def now(self):
        return datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
