"""Shared fixtures for the backend checks.

The suite is deliberately runnable with no cloud project and no credentials:
pointing ``FIREBASE_PRIVATE_KEY_PATH`` at a path that cannot exist makes
``app.database.session.init_firebase()`` fall back to the in-memory double, so
every test drives the real FastAPI stack (middleware, lifespan, RBAC
dependencies, routers, schemas) over a volatile database.

    cd backend
    python -m pytest -q            # 1 test process, ~2 s
"""

import os
import uuid

import pytest

# Must be set before app modules import settings/session.
os.environ["FIREBASE_PRIVATE_KEY_PATH"] = os.path.join(os.getcwd(), "__no_credentials__.json")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
# Never let a developer's backend/.env send the suite to a live Gemini endpoint.
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import session as db_session  # noqa: E402


def memory_db():
    """The in-memory double the app is currently bound to."""
    return db_session.db


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        # Demo mode is a precondition, not a preference: a misconfigured
        # environment that reached real Firestore would mutate production data.
        assert db_session.is_memory_db(), "tests must run on the in-memory double"
        yield test_client


@pytest.fixture(scope="session")
def api(client):
    """Thin wrapper so the tests read as ``api.post("/events", ...)``."""

    class Api:
        def __init__(self, client):
            self.client = client

        def request(self, method, path, token=None, **kwargs):
            headers = kwargs.pop("headers", {})
            if token:
                headers["Authorization"] = f"Bearer {token}"
            return self.client.request(method, f"/api/v1{path}", headers=headers, **kwargs)

        def get(self, path, token=None, **kw):
            return self.request("GET", path, token, **kw)

        def post(self, path, token=None, **kw):
            return self.request("POST", path, token, **kw)

        def put(self, path, token=None, **kw):
            return self.request("PUT", path, token, **kw)

        def patch(self, path, token=None, **kw):
            return self.request("PATCH", path, token, **kw)

        def delete(self, path, token=None, **kw):
            return self.request("DELETE", path, token, **kw)

    return Api(client)


@pytest.fixture(scope="session")
def unique_email():
    def make(prefix="person"):
        return f"{prefix}.{uuid.uuid4().hex[:10]}@sbjit.edu.in"

    return make


@pytest.fixture(scope="session")
def register(api, unique_email):
    """Register an account and return its bearer token.

    In demo mode ``POST /auth/register`` activates the account immediately; the
    Firebase-backed path would leave it PENDING until a HOD approves a join
    request, which is covered by the UI walkthrough instead.
    """

    def make(role="FACULTY", name=None):
        email = unique_email(role.lower())
        payload = {
            "name": name or f"{role.title()} Tester",
            "email": email,
            "password": "Hiera@Test1",
            "role": role,
        }
        created = api.post("/auth/register", json=payload)
        assert created.status_code == 200, created.text
        login = api.post("/auth/login", json={"email": email, "password": "Hiera@Test1"})
        assert login.status_code == 200, login.text
        return login.json()["access_token"], email, created.json()

    return make


@pytest.fixture(scope="session")
def hod(register):
    token, email, profile = register("HOD", "Dr Hod Tester")
    return {"token": token, "email": email, "id": profile["id"], "name": profile["name"]}


@pytest.fixture(scope="session")
def teacher(register):
    token, email, profile = register("FACULTY", "Ms Teacher Tester")
    return {"token": token, "email": email, "id": profile["id"], "name": profile["name"]}
