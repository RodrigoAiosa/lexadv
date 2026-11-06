"""Supabase falso em memória, suficiente para testar rotas e templates sem rede."""
import copy
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from supabase import AuthApiError


class Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class FakeQuery:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.action = "select"
        self.payload = None
        self.filters = []
        self._order = None
        self._limit = None
        self._count = None

    # -- construção
    def select(self, *_args, count=None, **_kwargs):
        self._count = count
        return self

    def insert(self, payload):
        self.action, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.action, self.payload = "update", payload
        return self

    def delete(self):
        self.action = "delete"
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def neq(self, col, val):
        self.filters.append(("neq", col, val))
        return self

    def gt(self, col, val):
        self.filters.append(("gt", col, val))
        return self

    def is_(self, col, val):
        self.filters.append(("is", col, None if val == "null" else val))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    # -- execução
    def _match(self, row):
        for op, col, val in self.filters:
            cur = row.get(col)
            if op == "eq" and cur != val:
                return False
            if op == "neq" and cur == val:
                return False
            if op == "gt" and not (cur is not None and str(cur) > str(val)):
                return False
            if op == "is" and cur != val:
                return False
        return True

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.action == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            created = []
            for item in items:
                row = {"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(), **item}
                if self.table == "cases":
                    row.setdefault("status", "aberto")
                    row.setdefault("protocol", "LEX-2026-000001")
                    row.setdefault("assigned_lawyer_id", None)
                rows.append(row)
                created.append(copy.deepcopy(row))
            return Result(created)
        matched = [r for r in rows if self._match(r)]
        if self.action == "update":
            for row in matched:
                row.update(self.payload)
            return Result(copy.deepcopy(matched))
        if self.action == "delete":
            for row in matched:
                rows.remove(row)
            return Result(copy.deepcopy(matched))
        if self._order:
            col, desc = self._order
            matched = sorted(matched, key=lambda r: str(r.get(col, "")), reverse=desc)
        if self._limit is not None:
            matched = matched[: self._limit]
        return Result(copy.deepcopy(matched), count=len(matched) if self._count else None)


class FakeRpc:
    def __init__(self, db, name, params):
        self.db, self.name, self.params = db, name, params

    def execute(self):
        self.db.rpc_calls.append((self.name, self.params))
        return Result(self.db.rpc_returns.get(self.name))


class FakeBucket:
    def __init__(self, db):
        self.db = db

    def upload(self, path, file, file_options=None):
        self.db.uploads[path] = (file, file_options)

    def create_signed_url(self, path, expires_in):
        return {"signedURL": f"https://files.test/{path}?t=1"}


class FakeStorage:
    def __init__(self, db):
        self.db = db

    def from_(self, _bucket):
        return FakeBucket(self.db)


class FakeAuth:
    def __init__(self, db):
        self.db = db

    def sign_in_with_password(self, creds):
        user = self.db.users.get(creds["email"])
        if not user or user["password"] != creds["password"]:
            raise AuthApiError("Invalid login credentials", 400, "invalid_credentials")
        return SimpleNamespace(
            session=SimpleNamespace(access_token="tok", refresh_token="ref", expires_at=9999999999),
            user=SimpleNamespace(id=user["id"], email=creds["email"]),
        )

    def sign_up(self, data):
        self.db.signups.append(data)
        return SimpleNamespace(session=None, user=SimpleNamespace(id=str(uuid.uuid4()), email=data["email"]))

    def refresh_session(self, _token):
        return SimpleNamespace(
            session=SimpleNamespace(access_token="tok2", refresh_token="ref2", expires_at=9999999999)
        )


class FakeDB:
    def __init__(self):
        self.tables = {}
        self.users = {}
        self.signups = []
        self.rpc_calls = []
        self.rpc_returns = {}
        self.uploads = {}
        self.auth = FakeAuth(self)
        self.storage = FakeStorage(self)

    def table(self, name):
        return FakeQuery(self, name)

    def rpc(self, name, params=None):
        return FakeRpc(self, name, params or {})

    def seed(self, table, *rows):
        self.tables.setdefault(table, []).extend(rows)
