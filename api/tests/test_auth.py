import time

import jwt
import pytest
from fastapi.testclient import TestClient

SUPABASE = "https://example.supabase.co"
SECRET = "test-secret-at-least-32-bytes-long!!"


def token(sub, email, expires_in=3600, secret=SECRET):
    now = int(time.time())
    return jwt.encode({"sub": sub, "email": email, "aud": "authenticated", "iss": f"{SUPABASE}/auth/v1",
                       "iat": now, "exp": now + expires_in}, secret, algorithm="HS256")


def bearer(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PODIUM_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("SUPABASE_URL", SUPABASE)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    from api.main import app
    from api.ratelimit import limiter

    limiter.reset()
    with TestClient(app) as c:
        yield c
    limiter.reset()


def test_requires_login(client):
    assert client.get("/api/health").json()["auth"] is True
    assert client.get("/api/rehearsals").status_code == 401
    assert client.get("/api/rehearsals", headers=bearer("not-a-jwt")).status_code == 401
    assert client.get("/api/rehearsals", headers=bearer(token("a", "a@x.com", expires_in=-10))).status_code == 401
    assert client.get("/api/rehearsals", headers=bearer(token("a", "a@x.com", secret="wrong" * 8))).status_code == 401


def test_users_only_see_their_own_rehearsals(client):
    alice, bob = bearer(token("uuid-alice", "alice@x.com")), bearer(token("uuid-bob", "bob@x.com"))
    assert client.get("/api/me", headers=alice).json()["email"] == "alice@x.com"

    r = client.post("/api/rehearsals", json={"occasion": "pitch"}, headers=alice).json()
    assert [x["id"] for x in client.get("/api/rehearsals", headers=alice).json()] == [r["id"]]
    assert client.get("/api/rehearsals", headers=bob).json() == []

    # Bob can't read, change, or delete Alice's rehearsal; it looks missing to him.
    assert client.get(f"/api/rehearsals/{r['id']}", headers=bob).status_code == 404
    assert client.post(f"/api/rehearsals/{r['id']}/takes", json={}, headers=bob).status_code == 404
    assert client.delete(f"/api/rehearsals/{r['id']}", headers=bob).status_code == 404
    take = client.post(f"/api/rehearsals/{r['id']}/takes", json={}, headers=alice).json()
    assert client.get(f"/api/takes/{take['id']}", headers=bob).status_code == 404
    # Media URLs take the token as a query parameter.
    assert client.get(f"/api/takes/{take['id']}/video?access_token={token('uuid-bob', 'bob@x.com')}").status_code == 404


def test_websocket_needs_a_valid_token(client):
    alice = token("uuid-alice", "alice@x.com")
    r = client.post("/api/rehearsals", json={"occasion": "interview", "mode": "live"}, headers=bearer(alice)).json()
    take = client.post(f"/api/rehearsals/{r['id']}/takes", json={}, headers=bearer(alice)).json()
    with client.websocket_connect(f"/api/takes/{take['id']}/live") as ws:
        assert ws.receive_json()["code"] == 401


def test_rate_limit(client, monkeypatch):
    monkeypatch.setitem(__import__("api.ratelimit", fromlist=["LIMITS"]).LIMITS, "rehearsal", (3, 3600))
    alice, bob = bearer(token("uuid-alice", "alice@x.com")), bearer(token("uuid-bob", "bob@x.com"))
    for _ in range(3):
        assert client.post("/api/rehearsals", json={"occasion": "speech"}, headers=alice).status_code == 200
    blocked = client.post("/api/rehearsals", json={"occasion": "speech"}, headers=alice)
    assert blocked.status_code == 429
    assert "try again in" in blocked.json()["detail"] and int(blocked.headers["Retry-After"]) > 0
    # Limits are per user.
    assert client.post("/api/rehearsals", json={"occasion": "speech"}, headers=bob).status_code == 200
