"""Shared fixtures for E2E tests running against a Kubernetes-deployed instance."""

import os
import uuid

import pytest
import requests
from pymongo import MongoClient


# ---------------------------------------------------------------------------
# Configuration – override with env vars when needed
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:30500")
MONGODB_URI = os.environ.get("E2E_MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError(
        "E2E_MONGODB_URI environment variable is required. "
        "Example: E2E_MONGODB_URI=mongodb://root:pass@localhost:27017/fantasy_football?authSource=admin"
    )


# ---------------------------------------------------------------------------
# MongoDB direct access (for setup / teardown / assertions)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mongo_db():
    """Direct MongoDB connection for test data manipulation."""
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client.get_default_database()
    yield db
    client.close()


@pytest.fixture(scope="session")
def mongo_port_forward():
    """Ensure MongoDB is reachable from the test host.

    Docker-Desktop K8s exposes NodePort services on localhost.  MongoDB uses
    ClusterIP so we need a port-forward.  This fixture starts one for the
    session and tears it down at the end.
    """
    import subprocess
    import time

    # Check if mongo is already reachable on 27017
    try:
        c = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        c.close()
        yield  # already reachable – nothing to do
        return
    except Exception:
        pass

    proc = subprocess.Popen(
        ["kubectl", "port-forward", "svc/mongodb", "27017:27017"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    yield
    proc.terminate()
    proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# Unique user helper
# ---------------------------------------------------------------------------


def _unique_username():
    return f"testuser_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def unique_user():
    """Return a dict with unique username / password for a fresh test user."""
    return {
        "username": _unique_username(),
        "password": "TestPass123!",
    }


# ---------------------------------------------------------------------------
# requests-based helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_session():
    """A requests.Session pre-configured for the app."""
    s = requests.Session()
    s.headers.update({"Accept": "text/html"})
    yield s
    s.close()


@pytest.fixture()
def logged_in_session(api_session, unique_user):
    """Register a fresh user and return the session already logged-in."""
    api_session.post(
        f"{BASE_URL}/register",
        data={
            "username": unique_user["username"],
            "password": unique_user["password"],
            "confirm": unique_user["password"],
        },
        allow_redirects=True,
    )
    return api_session, unique_user


# ---------------------------------------------------------------------------
# Cleanup: remove test users/leagues after tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _cleanup_test_data(mongo_db, mongo_port_forward):
    """After the entire session, remove any users/leagues created by tests."""
    yield
    mongo_db["users"].delete_many({"username": {"$regex": "^testuser_"}})
    mongo_db["leagues"].delete_many({"name": {"$regex": "^TestLeague_"}})


# ---------------------------------------------------------------------------
# Re-export BASE_URL so tests can import it
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
