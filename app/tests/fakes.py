"""Shared in-memory doubles for route tests.

Kept in one place so the live-model route and the wall-clock proof route are exercised against
identical storage behaviour, including `merge=True`, which the proof record relies on.
"""

from datetime import datetime, timezone


class Snapshot:
    # Real snapshots carry the document id, and CourseStore.all() reads it to build the fleet
    # view. The double did not, so a route that worked in production failed only under test.
    def __init__(self, document, doc_id=""):
        self._document = document
        self.id = doc_id

    @property
    def exists(self):
        return self._document.data is not None

    def to_dict(self):
        return dict(self._document.data or {})


class Document:
    def __init__(self, doc_id=""):
        self.data = None
        self.doc_id = doc_id

    def set(self, data, merge=False):
        if merge and self.data is not None:
            self.data.update(data)
        else:
            self.data = dict(data)

    def get(self):
        return Snapshot(self, self.doc_id)


class Collection:
    def __init__(self):
        self.documents = {}
        self._filters = []

    def document(self, doc_id):
        return self.documents.setdefault(doc_id, Document(doc_id))

    def where(self, field=None, _op=None, value=None, filter=None):
        # Mirrors the real client: production uses the keyword FieldFilter form, so the double
        # must accept it, otherwise a test can pass against an API production never calls.
        if filter is not None:
            self._filters = [(filter.field_path, filter.value)]
        else:
            self._filters = [(field, value)]
        return self

    def order_by(self, _field):
        return self

    def limit(self, _n):
        return self

    def stream(self):
        for document in self.documents.values():
            data = document.data or {}
            if document.data is None:
                continue
            if all(data.get(field) == value for field, value in self._filters):
                yield Snapshot(document, document.doc_id)


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
