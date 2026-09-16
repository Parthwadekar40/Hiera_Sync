"""Minimal in-memory stand-in for the Firestore client.

The routers are written as "read the collection, fall back to sample data when
it is empty", but `get_db()` used to raise 503 whenever credentials were
missing — so the documented demo mode could never actually run and every page
showed an error instead of the sample queue.

When Firestore cannot be initialised (no service-account file, offline CI,
reviewer cloning the repo) this shim is injected instead. It implements just
the surface the API uses — collections, documents, `set/update/get/delete`,
`where`, `limit`, `order_by` and `stream` — so registration, the calendar,
approvals and notifications all behave normally within one process. The data is
volatile by design and `/health` reports the mode.
"""

import threading
import uuid
from typing import Any, Dict, Iterable, List, Optional

CollectionData = Dict[str, Dict[str, Any]]


def _matches(document: Dict[str, Any], field: str, op: str, value: Any) -> bool:
    actual = document.get(field)
    try:
        if op in ("==", "in"):
            return actual in value if op == "in" else actual == value
        if op == "!=":
            return actual != value
        if actual is None:
            return False
        if op == ">":
            return actual > value
        if op == ">=":
            return actual >= value
        if op == "<":
            return actual < value
        if op == "<=":
            return actual <= value
        if op == "array_contains":
            return value in (actual or [])
    except TypeError:
        return False
    return True


class MemoryDocumentSnapshot:
    __slots__ = ("_reference", "_data")

    def __init__(self, reference: "MemoryDocument", data: Optional[Dict[str, Any]]):
        self._reference = reference
        self._data = data

    @property
    def id(self) -> str:
        return self._reference.id

    @property
    def reference(self) -> "MemoryDocument":
        return self._reference

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data) if self._data else {}


class MemoryDocument:
    __slots__ = ("_collection", "_doc_id")

    def __init__(self, collection: "MemoryCollection", doc_id: str):
        self._collection = collection
        self._doc_id = doc_id

    @property
    def id(self) -> str:
        return self._doc_id

    @property
    def path(self) -> str:
        return f"{self._collection.name}/{self._doc_id}"

    def get(self) -> MemoryDocumentSnapshot:
        return MemoryDocumentSnapshot(self, self._collection._read(self._doc_id))

    def set(self, data: Dict[str, Any], merge: bool = False) -> None:
        self._collection._write(self._doc_id, data, merge=merge)

    def update(self, data: Dict[str, Any]) -> None:
        # Unlike Firestore this never raises for a missing document: in demo mode
        # an update is treated as a create so a single write cannot 500 a request.
        self._collection._write(self._doc_id, data, merge=True)

    def delete(self) -> None:
        self._collection._delete(self._doc_id)


class MemoryQuery:
    def __init__(self, collection: "MemoryCollection", filters=None, order=None, limit_: Optional[int] = None):
        self._collection = collection
        self._filters: List[tuple] = list(filters or [])
        self._order = order
        self._limit = limit_

    def where(self, field: str, op: str, value: Any) -> "MemoryQuery":
        return MemoryQuery(
            self._collection, self._filters + [(field, op, value)], self._order, self._limit
        )

    def order_by(self, field: str, direction: str = "ASCENDING") -> "MemoryQuery":
        return MemoryQuery(
            self._collection, self._filters, (field, direction.upper()), self._limit
        )

    def limit(self, count: int) -> "MemoryQuery":
        return MemoryQuery(self._collection, self._filters, self._order, count)

    def stream(self) -> Iterable[MemoryDocumentSnapshot]:
        rows = self._collection._snapshot_rows()

        for field, op, value in self._filters:
            rows = [(doc_id, data) for doc_id, data in rows if _matches(data, field, op, value)]

        if self._order:
            field, direction = self._order
            rows.sort(
                key=lambda item: (item[1].get(field) is None, item[1].get(field)),
                reverse=direction == "DESCENDING",
            )

        if self._limit is not None:
            rows = rows[: self._limit]

        return [
            MemoryDocumentSnapshot(self._collection.document(doc_id), data)
            for doc_id, data in rows
        ]


class MemoryCollection(MemoryQuery):
    def __init__(self, name: str, store: CollectionData, lock: threading.RLock):
        super().__init__(self)
        self.name = name
        self._store = store
        self._lock = lock

    def document(self, doc_id: Optional[str] = None) -> MemoryDocument:
        return MemoryDocument(self, doc_id or uuid.uuid4().hex)

    def add(self, data: Dict[str, Any]) -> "MemoryDocument":
        reference = self.document()
        reference.set(data)
        return reference

    def _rows(self) -> List[tuple]:
        return [(doc_id, dict(data)) for doc_id, data in self._store.items()]

    def _snapshot_rows(self) -> List[tuple]:
        with self._lock:
            return self._rows()

    def _read(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._store.get(doc_id)
            return dict(data) if data else None

    def _write(self, doc_id: str, data: Dict[str, Any], merge: bool = False) -> None:
        with self._lock:
            if merge:
                current = self._store.setdefault(doc_id, {})
                current.update(data)
            else:
                self._store[doc_id] = dict(data)

    def _delete(self, doc_id: str) -> None:
        with self._lock:
            self._store.pop(doc_id, None)


class MemoryClient:
    """Thread-safe, process-local Firestore double used for demo/test runs."""

    def __init__(self) -> None:
        self._collections: Dict[str, CollectionData] = {}
        self._lock = threading.RLock()

    def collection(self, name: str) -> MemoryCollection:
        with self._lock:
            store = self._collections.setdefault(name, {})
        return MemoryCollection(name, store, self._lock)

    def collections(self) -> List[str]:
        with self._lock:
            return list(self._collections.keys())

    def seed(self, name: str, documents: List[Dict[str, Any]]) -> None:
        """Bulk-load sample documents (each must carry an `id`)."""
        collection = self.collection(name)
        for document in documents:
            doc_id = document.get("id") or uuid.uuid4().hex
            payload = {key: value for key, value in document.items() if key != "id"}
            collection.document(doc_id).set(payload)

    def clear(self) -> None:
        with self._lock:
            for store in self._collections.values():
                store.clear()


_memory_client: Optional[MemoryClient] = None


def get_memory_client() -> MemoryClient:
    global _memory_client
    if _memory_client is None:
        _memory_client = MemoryClient()
    return _memory_client
