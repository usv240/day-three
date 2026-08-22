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
        self._order = None
        self._limit = None

    def document(self, doc_id):
        return self.documents.setdefault(doc_id, Document(doc_id))

    # A query double that ignored operators, replaced rather than accumulated filters, and
    # treated limit as a no-op cannot catch a limit-versus-filter ordering bug, and did not:
    # the scanner's `limit` was applied by Firestore before an in-memory unclaimed filter, so
    # once enough claimed records existed it stopped returning pending ones. Production found
    # that, the suite did not. This models enough of the real query semantics to fail first.
    def where(self, field=None, op=None, value=None, filter=None):
        clone = self._clone()
        if filter is not None:
            clone._filters = self._filters + [(filter.field_path, filter.op_string, filter.value)]
        else:
            clone._filters = self._filters + [(field, op or "==", value)]
        return clone

    def order_by(self, field, direction="ASCENDING"):
        clone = self._clone()
        clone._order = (field, direction)
        return clone

    def limit(self, n):
        clone = self._clone()
        clone._limit = n
        return clone

    def _clone(self):
        clone = Collection()
        clone.documents = self.documents
        clone._filters = list(self._filters)
        clone._order = self._order
        clone._limit = self._limit
        return clone

    @staticmethod
    def _matches(value, op, target):
        if value is None:
            return False
        if op == "==":
            return value == target
        if op == "<=":
            return value <= target
        if op == ">=":
            return value >= target
        if op == "<":
            return value < target
        if op == ">":
            return value > target
        raise AssertionError(f"the double does not model the {op!r} operator")

    def stream(self):
        rows = [d for d in self.documents.values() if d.data is not None]
        rows = [
            d for d in rows
            if all(self._matches((d.data or {}).get(f), op, v) for f, op, v in self._filters)
        ]
        if self._order:
            field, direction = self._order
            rows.sort(key=lambda d: (d.data or {}).get(field), reverse=direction != "ASCENDING")
        if self._limit is not None:
            rows = rows[: self._limit]
        for document in rows:
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
