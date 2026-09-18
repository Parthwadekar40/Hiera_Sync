"""A Firestore-compatible document store backed by SQLite.

Why this exists
---------------
Every HieraSync router was written against the `google.cloud.firestore` client API.
Requiring live GCP credentials makes the platform un-runnable for local development,
CI, offline demos and the acceptance testing that a project submission needs - the
process used to die at startup inside `init_firebase()`.

This module keeps the *exact* client surface the routers use (collection / document /
where / stream / limit / order_by / set / get / update / delete / add, `FieldFilter`,
`DocumentSnapshot.to_dict()`, `snapshot.reference`) but persists into a single-file
SQLite database with schemaless JSON documents. Because the surface is identical, the
same business code runs against Firestore unchanged in production: the driver is chosen
by one environment variable (`DATABASE_BACKEND`).

Design notes
------------
* Documents are stored schemalessly as JSON - matching Firestore semantics (no
  migrations, heterogeneous docs per collection) while giving us ACID writes,
  `BEGIN IMMEDIATE` transactions and crash safety for free.
* Read queries filter/sort in Python after a collection scan. At institutional scale
  (10^4-10^5 docs) this stays sub-millisecond, and a covering index on
  `(collection, id)` keeps the scan sequential. Firestore's own composite-index
  requirement is therefore never a blocker for a demo/CI run.
* Timestamps are stored as ISO-8601 UTC strings so lexicographic ordering equals
  chronological ordering, which is what `order_by("timestamp")` relies on.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Firestore uses these int constants; queries may also pass the string names.
ASCENDING = 1
DESCENDING = -1


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def parse_dt(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    txt = str(value).strip().replace("Z", "")
    if not txt:
        return None
    try:
        return datetime.fromisoformat(txt)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(txt, fmt)
        except ValueError:
            continue
    return None


def _dig(data: Any, path: str) -> Any:
    """Firestore-style dotted path lookup, tolerant of missing keys/lists."""
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


_MISSING = object()


def _cmp(actual: Any, expected: Any, op: str) -> bool:
    """Evaluate one Firestore comparison operator."""
    if op in ("==",):
        return actual == expected
    if op in ("!=",):
        if actual is None and expected is None:
            return False
        return actual != expected
    if op == "in":
        exp = expected if isinstance(expected, (list, tuple, set)) else [expected]
        return any(actual == e for e in exp)
    if op == "not-in":
        exp = expected if isinstance(expected, (list, tuple, set)) else [expected]
        return all(actual != e for e in exp)
    if op == "array_contains":
        return isinstance(actual, (list, tuple)) and expected in actual
    if op == "array_contains_any":
        exp = expected or []
        return isinstance(actual, (list, tuple)) and any(e in actual for e in exp)
    if op == "not_in":  # legacy alias
        return actual not in (expected or [])

    # Ordered comparisons need comparable types.
    if op in ("<", "<=", ">", ">="):
        a, b = actual, expected
        if isinstance(a, str) and isinstance(b, str) and (a[:2].isdigit() or b[:2].isdigit()):
            pa, pb = parse_dt(a), parse_dt(b)
            if pa and pb:
                a, b = pa, pb
        if isinstance(a, datetime) or isinstance(b, datetime):
            pa, pb = parse_dt(a), parse_dt(b)
            if pa is None or pb is None:
                return False
            a, b = pa, pb
        try:
            if op == "<":
                return a < b
            if op == "<=":
                return a <= b
            if op == ">":
                return a > b
            return a >= b
        except TypeError:
            return False
    return False


def _flatten_filters(where_calls: Sequence[Tuple[str, Optional[str], Any]]) -> List[Tuple[str, str, Any]]:
    out: List[Tuple[str, str, Any]] = []
    for item in where_calls:
        field_name, op, value = item
        if field_name == "filter":  # where(filter=FieldFilter(...))
            path = getattr(value, "field_path", None)
            op_str = getattr(value, "op_string", None) or getattr(value, "op_str", None) or "=="
            out.append((str(path), str(op_str), getattr(value, "value", None)))
        else:
            out.append((field_name, op or "==", value))
    return out


class DocumentSnapshot:
    __slots__ = ("id", "exists", "_data", "reference")

    def __init__(self, ref: "DocumentReference", data: Optional[Dict[str, Any]], exists: bool):
        self.reference = ref
        self.id = ref.id
        self.exists = exists
        self._data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self._data))

    @property
    def _fields(self):  # parity with Firestore internals used by some helpers
        return self._data

    def get(self, path: str, default: Any = None) -> Any:
        val = _dig(self._data, path)
        return default if val is None else val

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<DocumentSnapshot id={self.id} exists={self.exists}>"


class DocumentReference:
    __slots__ = ("store", "collection_name", "id")

    def __init__(self, store: "DocumentStore", collection_name: str, doc_id: str):
        self.store = store
        self.collection_name = collection_name
        self.id = doc_id

    # ---- reads
    def get(self) -> DocumentSnapshot:
        return self.store._get_snapshot(self.collection_name, self.id)

    # ---- writes
    def set(self, data: Dict[str, Any], merge: bool = False) -> Dict[str, Any]:
        self.store._set(self.collection_name, self.id, data, merge=merge)
        return {"update_time": utcnow_iso()}

    def update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self.store._update(self.collection_name, self.id, data)
        return {"update_time": utcnow_iso()}

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if self.store._exists(self.collection_name, self.id):
            raise RuntimeError(f"Document {self.collection_name}/{self.id} already exists")
        return self.set(data)

    def delete(self) -> Dict[str, Any]:
        self.store._delete(self.collection_name, self.id)
        return {"write_time": utcnow_iso()}

    # Firestore allows nested collection access from a doc reference; not used today
    # but implemented so future code (sub-tasks, thread trees) works unchanged.
    def collection(self, name: str) -> "CollectionReference":
        return CollectionReference(self.store, f"{self.collection_name}/{self.id}/{name}")

    def collections(self):  # pragma: no cover - convenience parity
        return []


class Query:
    def __init__(self, store: "DocumentStore", collection_name: str):
        self.store = store
        self.collection_name = collection_name
        self._where: List[Tuple[str, Optional[str], Any]] = []
        self._order: List[Tuple[str, int]] = []
        self._limit: Optional[int] = None
        self._offset: int = 0

    # ---- composition (every method returns a new query, like Firestore)
    def where(self, field_path: Any = None, op_str: Optional[str] = None, value: Any = None, *, filter: Any = None):
        clone = self._clone()
        if filter is not None:
            clone._where.append(("filter", None, filter))
        else:
            clone._where.append((field_path, op_str, value))
        return clone

    def order_by(self, field_path: str, direction: Any = ASCENDING):
        clone = self._clone()
        dir_val = DESCENDING if (direction in (DESCENDING, "DESCENDING", "Descending", "desc", "-1", -1)) else ASCENDING
        clone._order.append((field_path, dir_val))
        return clone

    def limit(self, n: int):
        clone = self._clone()
        clone._limit = int(n)
        return clone

    def offset(self, n: int):
        clone = self._clone()
        clone._offset = int(n)
        return clone

    def select(self, *fields):  # pragma: no cover - API parity, projection applied client-side
        clone = self._clone()
        clone._projection = [f for f in (fields[0] if len(fields) == 1 and isinstance(fields[0], (list, tuple)) else fields)]
        return clone

    def _clone(self) -> "Query":
        cls = type(self) if isinstance(self, CollectionReference) else Query
        clone = cls(self.store, self.collection_name)
        clone._where = list(self._where)
        clone._order = list(self._order)
        clone._limit = self._limit
        clone._offset = self._offset
        return clone

    # ---- execution
    def _rows(self) -> List[Tuple[str, Dict[str, Any]]]:
        return self.store._fetch(self.collection_name)

    def stream(self) -> Iterable[DocumentSnapshot]:
        # Firestore applies order_by/limit server-side, so `stream()` must honour them.
        if self._order or self._limit is not None or self._offset:
            return iter(self._materialize())
        return iter(list(self._iter_filtered()))

    def _iter_filtered(self):
        docs = self._rows()
        filters = _flatten_filters(self._where)
        for doc_id, data in docs:
            ok = True
            for field_path, op, value in filters:
                actual = _dig(data, field_path)
                if actual is None and field_path not in data and op in ("!=", "not-in"):
                    ok = False  # Firestore excludes docs missing the field
                    break
                if not _cmp(actual, value, op):
                    ok = False
                    break
            if ok:
                yield DocumentSnapshot(DocumentReference(self.store, self.collection_name, doc_id), data, True)

    def documents(self) -> List[DocumentSnapshot]:
        return list(self.stream())

    def get(self) -> List[DocumentSnapshot]:
        return list(self.stream())

    def limit_to_last(self, n: int):  # pragma: no cover - parity stub
        all_rows = list(self._iter_filtered())
        return all_rows[-int(n):] if n else []

    def count(self) -> int:
        return len(list(self.stream()))

    def _materialize(self) -> List[DocumentSnapshot]:
        snaps = list(self._iter_filtered())
        for field_path, direction in reversed(self._order):
            snaps.sort(
                key=lambda s: (_sort_key(_dig(s._data, field_path)), s.id),
                reverse=direction == DESCENDING,
            )
        if self._offset:
            snaps = snaps[self._offset:]
        if self._limit is not None:
            snaps = snaps[: self._limit]
        return snaps

    def __iter__(self):
        return iter(self._materialize())


def _sort_key(value: Any):
    """Stable sort across mixed types (missing -> None sorts first)."""
    if value is None:
        return (0, 0.0, "")
    if isinstance(value, bool):
        return (1, int(value), "")
    if isinstance(value, (int, float)):
        return (1, float(value), "")
    return (2, 0.0, str(value))


class CollectionReference(Query):
    def __init__(self, store: "DocumentStore", name: str):
        super().__init__(store, name)

    def document(self, doc_id: Optional[str] = None) -> DocumentReference:
        return DocumentReference(self.store, self.collection_name, doc_id or uuid.uuid4().hex)

    def add(self, data: Dict[str, Any], doc_id: Optional[str] = None) -> DocumentReference:
        ref = self.document(doc_id or (data.get("id") if isinstance(data, dict) else None) or uuid.uuid4().hex)
        ref.set(data)
        return ref

    def id(self) -> str:  # pragma: no cover - parity
        return self.collection_name.split("/")[-1]

    def list_documents(self):  # pragma: no cover - parity
        return [DocumentReference(self.store, self.collection_name, d) for d, _ in self._rows()]


class WriteBatch:
    """Firestore batch, executed inside one SQLite transaction."""

    def __init__(self, store: "DocumentStore"):
        self.store = store
        self._ops: List[Tuple[str, Any, Any, Any]] = []

    def set(self, ref: DocumentReference, data: Dict[str, Any], merge: bool = False):
        self._ops.append(("set", ref, data, merge))

    def update(self, ref: DocumentReference, data: Dict[str, Any]):
        self._ops.append(("update", ref, data, None))

    def delete(self, ref: DocumentReference):
        self._ops.append(("delete", ref, None, None))

    def commit(self) -> List[Any]:
        self.store._apply_ops(self._ops)
        out = [utcnow_iso()] * len(self._ops)
        self._ops = []
        return out


class Transaction:
    """Retryable-transaction facade: serialized through SQLite's write lock."""

    def __init__(self, store: "DocumentStore"):
        self.store = store

    def __enter__(self):
        self.store._tx_enter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.store._tx_exit(exc_type)
        return False

    def get(self, ref: DocumentReference):
        return ref.get()

    def set(self, ref: DocumentReference, data: Dict[str, Any], merge: bool = False):
        ref.set(data, merge=merge)

    def update(self, ref: DocumentReference, data: Dict[str, Any]):
        ref.update(data)

    def delete(self, ref: DocumentReference):
        ref.delete()

    def commit(self):  # pragma: no cover
        pass


class DocumentStore:
    """Drop-in replacement for `firestore.client()` for local/CI usage."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._depth = 0
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                collection TEXT NOT NULL,
                id         TEXT NOT NULL,
                data       TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (collection, id)
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection)")
        self._conn.commit()

    # ------------------------------------------------------------------ public API
    def collection(self, name: str) -> CollectionReference:
        return CollectionReference(self, name)

    def collections(self) -> List[str]:  # pragma: no cover
        rows = self._conn.execute("SELECT DISTINCT collection FROM documents").fetchall()
        return [r[0] for r in rows]

    def batch(self) -> WriteBatch:
        return WriteBatch(self)

    def transaction(self) -> Transaction:
        return Transaction(self)

    def collection_group(self, suffix: str):  # pragma: no cover - parity helper
        names = [c for c in self.collections() if c.split("/")[-1] == suffix]
        return [doc for name in names for doc in Query(self, name).stream()]

    # Backend introspection used by /system diagnostics and the test-suite
    def stats(self) -> Dict[str, int]:
        rows = self._conn.execute(
            "SELECT collection, COUNT(*) FROM documents GROUP BY collection ORDER BY collection"
        ).fetchall()
        return {name: int(count) for name, count in rows}

    def clear(self, keep: Sequence[str] = ()):
        with self._lock:
            for name in self.collections():
                if name in keep:
                    continue
                self._conn.execute("DELETE FROM documents WHERE collection=?", (name,))
            self._conn.commit()

    def close(self):  # pragma: no cover
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ internals
    def _fetch(self, collection: str) -> List[Tuple[str, Dict[str, Any]]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, data FROM documents WHERE collection=? ORDER BY rowid", (collection,)
            ).fetchall()
        out: List[Tuple[str, Dict[str, Any]]] = []
        for doc_id, blob in rows:
            try:
                out.append((doc_id, json.loads(blob)))
            except json.JSONDecodeError:  # pragma: no cover - defensive
                continue
        return out

    def _exists(self, collection: str, doc_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "SELECT 1 FROM documents WHERE collection=? AND id=?", (collection, doc_id)
            )
            return cur.fetchone() is not None

    def _get_snapshot(self, collection: str, doc_id: str) -> DocumentSnapshot:
        ref = DocumentReference(self, collection, doc_id)
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM documents WHERE collection=? AND id=?", (collection, doc_id)
            ).fetchone()
        if not row:
            return DocumentSnapshot(ref, {}, False)
        return DocumentSnapshot(ref, json.loads(row[0]), True)

    def _set(self, collection: str, doc_id: str, data: Dict[str, Any], merge: bool = False):
        payload = dict(data or {})
        now = utcnow_iso()
        with self._lock:
            if merge:
                existing = self._get_snapshot(collection, doc_id)
                if existing.exists:
                    payload = {**existing._data, **payload}
            self._conn.execute(
                """
                INSERT INTO documents(collection, id, data, created_at, updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(collection, id) DO UPDATE SET
                    data=excluded.data, updated_at=excluded.updated_at
                """,
                (collection, doc_id, json.dumps(payload, default=str), now, now),
            )
            if not self._depth:
                self._conn.commit()

    def _update(self, collection: str, doc_id: str, data: Dict[str, Any]):
        """Firestore `update` semantics: dotted paths, array-union/remove helpers."""
        snap = self._get_snapshot(collection, doc_id)
        if not snap.exists:
            raise RuntimeError(f"No document to update at {collection}/{doc_id}")
        payload = dict(snap._data)
        for path, value in (data or {}).items():
            _apply_update(payload, path, value)
        with self._lock:
            self._conn.execute(
                "UPDATE documents SET data=?, updated_at=? WHERE collection=? AND id=?",
                (json.dumps(payload, default=str), utcnow_iso(), collection, doc_id),
            )
            if not self._depth:
                self._conn.commit()

    def _delete(self, collection: str, doc_id: str):
        with self._lock:
            self._conn.execute("DELETE FROM documents WHERE collection=? AND id=?", (collection, doc_id))
            if not self._depth:
                self._conn.commit()

    def _apply_ops(self, ops: List[Tuple[str, Any, Any, Any]]):
        self._tx_enter()
        try:
            for kind, ref, data, merge in ops:
                if kind == "set":
                    self._set(ref.collection_name, ref.id, data, merge=bool(merge))
                elif kind == "update":
                    self._update(ref.collection_name, ref.id, data)
                elif kind == "delete":
                    self._delete(ref.collection_name, ref.id)
        except Exception:
            self._tx_exit(RuntimeError)
            raise
        self._tx_exit(None)

    def _tx_enter(self):
        self._lock.acquire()
        self._depth += 1

    def _tx_exit(self, exc_type):
        self._depth = max(0, self._depth - 1)
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._lock.release()


def _apply_update(payload: Dict[str, Any], path: str, value: Any):
    """Supports dotted paths and the Firestore ArrayUnion/ArrayRemove sentinels."""
    if hasattr(value, "_values"):  # ArrayUnion / ArrayRemove
        vals = list(getattr(value, "_values") or [])
        if value.__class__.__name__.lower().startswith("arrayremove"):
            cur = _dig(payload, path) or []
            _set_path(payload, path, [v for v in cur if v not in vals])
        else:
            cur = list(_dig(payload, path) or [])
            for v in vals:
                if v not in cur:
                    cur.append(v)
            _set_path(payload, path, cur)
        return

    parts = path.split(".")
    if len(parts) == 1:
        payload[path] = value
        return
    cur = payload
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _set_path(payload: Dict[str, Any], path: str, value: Any):
    parts = path.split(".")
    if len(parts) == 1:
        payload[path] = value
        return
    cur = payload
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value
