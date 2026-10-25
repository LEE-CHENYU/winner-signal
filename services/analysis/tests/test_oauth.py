import json
import time
from urllib.parse import parse_qs, urlparse
import pytest
from cryptography.fernet import Fernet
from test_app import clients, project
from analysis import google_oauth as oauth, youtube, storage


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("COOKIE_SECURE", "0")
    return monkeypatch


def begin(client, path="/api/auth/google"):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 303
    return parse_qs(urlparse(r.headers["location"]).query)


def test_login_scope_state_and_safe_redirect(clients, google):
    owner, stranger = clients
    q = begin(owner, "/api/auth/google?next=https://evil.example")
    assert q["access_type"] == ["offline"]
    assert set(q["scope"][0].split()) == set(oauth.LOGIN_SCOPES + oauth.YOUTUBE_SCOPES)
    assert q["code_challenge_method"] == ["S256"]
    state = q["state"][0]
    callback = "/api/auth/google/callback?code=test&state=" + state
    assert stranger.get(callback).status_code == 400
    google.setattr(oauth, "exchange", lambda *args: {"id_token": "test"})
    google.setattr(
        oauth,
        "verify_login",
        lambda token, nonce: {"sub": "subject1", "email": "builder@example.com"},
    )
    r = owner.get(callback, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"
    identity = owner.get("/api/me").json()
    assert identity["username"] != "builder"  # no email or username-based auto merge
    assert owner.get(callback).status_code == 400  # consumed once
    q = begin(owner)
    owner.get("/api/auth/google/callback?code=test&state=" + q["state"][0], follow_redirects=False)
    assert owner.get("/api/me").json()["id"] == identity["id"]


def test_decline_keeps_existing_account_and_manual_demo(clients, google):
    owner, _ = clients
    before = owner.get("/api/me").json()
    q = begin(owner)
    r = owner.get(
        "/api/auth/google/callback?error=access_denied&state=" + q["state"][0],
        follow_redirects=False,
    )
    assert "oauth_error=" in r.headers["location"]
    assert owner.get("/api/me").json() == before
    assert owner.post("/api/projects", json={"title": "Manual demo"}).status_code == 200


def test_expired_state_rejected(clients, google):
    owner, _ = clients
    q = begin(owner)
    with storage.db() as con:
        con.execute("UPDATE oauth_states SET expires=0")
    assert (
        owner.get("/api/auth/google/callback?code=test&state=" + q["state"][0]).status_code == 400
    )


def test_youtube_grant_binds_to_app_user_and_separate_scopes(clients, google):
    owner, stranger = clients
    before = owner.get("/api/me").json()
    q = begin(owner, "/api/integrations/youtube/connect")
    assert q["access_type"] == ["offline"]
    assert set(q["scope"][0].split()) == set(oauth.YOUTUBE_SCOPES)
    assert "select_account" in q["prompt"][0]
    with storage.db() as con:
        saved = dict(con.execute("SELECT * FROM oauth_states").fetchone())
    assert saved["user_id"] == before["id"]
    assert owner.get("/api/me").json() == before
    assert (
        stranger.get(
            "/api/integrations/youtube/callback?code=test&state=" + q["state"][0]
        ).status_code
        == 400
    )


def test_youtube_channel_mismatch_does_not_fetch_analytics(clients, google):
    owner, _ = clients
    _, v, _ = project(owner)
    user = owner.get("/api/me").json()
    with storage.db() as con:
        con.execute(
            "UPDATE submission_versions SET video_source_url=? WHERE id=?",
            ("https://youtu.be/abcdefghijk", v["id"]),
        )
        con.execute(
            "INSERT INTO youtube_connections VALUES(?,?,?,?,?)",
            (user["id"], "channel-A", "A", "encrypted", time.time()),
        )
    google.setattr(youtube, "access_token", lambda conn: "access")
    calls = []

    def get(client, path, params, token, analytics=False):
        calls.append(path)
        return {"items": [{"snippet": {"channelId": "channel-B"}}]}

    google.setattr(youtube, "get", get)
    r = owner.get("/api/versions/" + v["id"] + "/youtube-analytics")
    assert r.json()["status"] == "different_channel"
    assert calls == ["videos"]
    assert owner.get("/api/me").json() == user
    assert owner.delete("/api/integrations/youtube").status_code == 200
    assert owner.get("/api/integrations/youtube").json()["connection"] is None


def test_youtube_empty_report_is_pending_not_zero(clients, google):
    owner, _ = clients
    _, v, _ = project(owner)
    user = owner.get("/api/me").json()
    with storage.db() as con:
        con.execute(
            "UPDATE submission_versions SET video_source_url=? WHERE id=?",
            ("https://youtu.be/abcdefghijk", v["id"]),
        )
        con.execute(
            "INSERT INTO youtube_connections VALUES(?,?,?,?,?)",
            (user["id"], "channel-A", "A", "encrypted", time.time()),
        )
    google.setattr(youtube, "access_token", lambda conn: "access")
    google.setattr(
        youtube,
        "get",
        lambda client, path, params, token, analytics=False: (
            {"columnHeaders": [], "rows": []}
            if analytics
            else {"items": [{"snippet": {"channelId": "channel-A"}}]}
        ),
    )
    r = owner.get("/api/versions/" + v["id"] + "/youtube-analytics").json()
    assert r["status"] == "pending_data" and r["daily"] == []
    owner.delete("/api/integrations/youtube")
    with storage.db() as con:
        assert con.execute("SELECT COUNT(*) FROM youtube_reports").fetchone()[0] == 0


def test_youtube_url_validation():
    assert youtube.video_id("https://youtu.be/abcdefghijk") == "abcdefghijk"
    assert youtube.video_id("https://www.youtube.com/watch?v=abcdefghijk") == "abcdefghijk"
    assert youtube.video_id("https://youtube.com.evil.example/watch?v=abcdefghijk") is None


def test_partial_grant_token_exchange(google):
    from requests import Response, Request
    from requests_oauthlib import OAuth2Session
    def request(self, *args, **kwargs):
        r = Response()
        r.status_code = 200
        r.request = Request("POST", "https://oauth2.googleapis.com/token").prepare()
        r._content = json.dumps({"access_token": "access", "token_type": "Bearer",
            "scope": "openid", "id_token": "signed"}).encode()
        return r
    google.setattr(OAuth2Session, "request", request)
    token = oauth.exchange("login", "code", "state", "x" * 64)
    assert token["scope"] == ["openid"]
    assert "refresh_token" not in token


@pytest.mark.parametrize("channel_available", [True, False])
def test_login_auto_connects_without_blocking_identity(clients, google, channel_available):
    owner, _ = clients
    token = {"id_token": "test", "access_token": "access", "refresh_token": "refresh",
             "scope": oauth.LOGIN_SCOPES + oauth.YOUTUBE_SCOPES}
    google.setattr(oauth, "exchange", lambda *args: token)
    google.setattr(oauth, "verify_login", lambda *args: {"sub": "autoconnect", "email": "auto@example.com"})
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"items": [{"id": "channel-A", "snippet": {"title": "Channel A"}}] if channel_available else []}
    original_get = oauth.httpx.Client.get
    def get(client, url, *args, **kwargs):
        if url == "https://www.googleapis.com/youtube/v3/channels":
            return Response()
        return original_get(client, url, *args, **kwargs)
    google.setattr(oauth.httpx.Client, "get", get)
    q = begin(owner)
    result = owner.get("/api/auth/google/callback?code=test&state=" + q["state"][0], follow_redirects=False)
    assert result.headers["location"] == "/dashboard"
    with storage.db() as con:
        connection = con.execute("SELECT * FROM youtube_connections").fetchone()
        if not channel_available:
            assert connection is None
            return
        assert connection["channel_id"] == "channel-A"
        decrypted = json.loads(Fernet(oauth.os.environ["OAUTH_TOKEN_ENCRYPTION_KEY"].encode()).decrypt(connection["credentials"].encode()))
        assert decrypted["refresh_token"] == "refresh"
        assert "id_token" not in decrypted
        con.execute("UPDATE youtube_connections SET channel_id='different-uploader'")
    # Subsequent app sign-in must not replace the chosen uploader account.
    q = begin(owner)
    owner.get("/api/auth/google/callback?code=test&state=" + q["state"][0], follow_redirects=False)
    with storage.db() as con:
        assert con.execute("SELECT channel_id FROM youtube_connections").fetchone()[0] == "different-uploader"
