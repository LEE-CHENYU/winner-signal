"""Google sign-in with optional YouTube grants, with browser-bound OAuth state."""

import hashlib
import json
import os
import re
import secrets
import time
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from .auth import COOKIE, identity
from .storage import db, uid

router = APIRouter()
LOGIN_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def configured():
    return bool(os.getenv("GOOGLE_OAUTH_CLIENT_ID") and os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"))


def initialize(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS google_identities(subject TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS oauth_states(state_hash TEXT PRIMARY KEY, browser_hash TEXT NOT NULL, purpose TEXT NOT NULL, user_id TEXT, next_path TEXT NOT NULL, verifier TEXT NOT NULL, nonce TEXT NOT NULL, expires REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS youtube_reports(user_id TEXT NOT NULL, video_id TEXT NOT NULL, channel_id TEXT NOT NULL, fetched_at REAL NOT NULL, report_json TEXT NOT NULL, PRIMARY KEY(user_id,video_id,channel_id));
    CREATE TABLE IF NOT EXISTS youtube_connections(user_id TEXT PRIMARY KEY REFERENCES users(id), channel_id TEXT NOT NULL, channel_title TEXT NOT NULL, credentials TEXT NOT NULL, connected_at REAL NOT NULL);
    """)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def safe_next(value):
    return (
        value
        if re.fullmatch(r"/dashboard(?:/[a-f0-9]{32})?|/submit", value or "")
        else "/dashboard"
    )


def callback_url(purpose):
    origin = os.getenv("PUBLIC_ORIGIN", "http://localhost:3000").rstrip("/")
    path = (
        "/api/auth/google/callback" if purpose == "login" else "/api/integrations/youtube/callback"
    )
    return origin + path


def flow_for(purpose, state=None, verifier=None):
    config = {
        "web": {
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(
        config,
        scopes=LOGIN_SCOPES + YOUTUBE_SCOPES if purpose == "login" else YOUTUBE_SCOPES,
        state=state,
        code_verifier=verifier,
        autogenerate_code_verifier=not verifier,
        redirect_uri=callback_url(purpose),
    )


def start(request, purpose, next_path):
    if not configured():
        raise HTTPException(
            503,
            "Google connection is not configured yet. You can still use a username and add your demo manually.",
        )
    user = identity(request) if purpose == "youtube" else None
    if purpose == "youtube" and not os.getenv("OAUTH_TOKEN_ENCRYPTION_KEY"):
        raise HTTPException(503, "YouTube token storage is not configured")
    state, browser, nonce = (secrets.token_urlsafe(32) for _ in range(3))
    flow = flow_for(purpose, state)
    kwargs = {"prompt": "select_account", "nonce": nonce}
    if purpose == "youtube":
        kwargs.update(access_type="offline", prompt="consent select_account")
    else:
        kwargs.update(access_type="offline", prompt="consent select_account")
    url, _ = flow.authorization_url(**kwargs)
    with db() as con:
        con.execute("DELETE FROM oauth_states WHERE expires<?", (time.time(),))
        con.execute(
            "INSERT INTO oauth_states VALUES(?,?,?,?,?,?,?,?)",
            (
                digest(state),
                digest(browser),
                purpose,
                user["id"] if user else None,
                safe_next(next_path),
                flow.code_verifier,
                nonce,
                time.time() + 600,
            ),
        )
    response = RedirectResponse(url, 303)
    response.set_cookie(
        "ws_oauth_" + purpose,
        browser,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE") == "1",
        max_age=600,
    )
    return response


def exchange(purpose, code, state, verifier):
    flow = flow_for(purpose, state, verifier)
    # Accept granular grants; validate identity and feature scopes independently below.
    # Do not ask oauthlib to reject the entire sign-in for a declined optional scope.
    flow.oauth2session.scope = None
    flow.fetch_token(code=code, timeout=20)
    return flow.oauth2session.token


def verify_login(token, nonce):
    claims = id_token.verify_oauth2_token(
        token["id_token"], GoogleRequest(), os.environ["GOOGLE_OAUTH_CLIENT_ID"]
    )
    if (
        not claims.get("sub")
        or claims.get("nonce") != nonce
        or claims.get("email_verified") is not True
    ):
        raise ValueError("Invalid identity claims")
    return claims


def connect_youtube(user_id, token):
    granted = token.get("scope", [])
    if isinstance(granted, str):
        granted = granted.split()
    if not set(YOUTUBE_SCOPES).issubset(granted) or not token.get("refresh_token"):
        raise ValueError("Required permissions or offline grant missing")
    with httpx.Client(timeout=20) as client:
        r = client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": "Bearer " + token["access_token"]},
        )
        r.raise_for_status()
        channels = r.json().get("items", [])
    if len(channels) != 1:
        raise ValueError("Select one YouTube channel")
    ch = channels[0]
    encrypted = (
        Fernet(os.environ["OAUTH_TOKEN_ENCRYPTION_KEY"].encode())
        .encrypt(json.dumps({k: v for k, v in token.items() if k != "id_token"}).encode())
        .decode()
    )
    with db() as con:
        con.execute(
            "INSERT OR REPLACE INTO youtube_connections VALUES(?,?,?,?,?)",
            (user_id, ch["id"], ch["snippet"]["title"], encrypted, time.time()),
        )


def finish(request, purpose):
    state = request.query_params.get("state", "")
    browser = request.cookies.get("ws_oauth_" + purpose, "")
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM oauth_states WHERE state_hash=?", (digest(state),)
        ).fetchone()
        if (
            not row
            or row["purpose"] != purpose
            or row["expires"] <= time.time()
            or not secrets.compare_digest(row["browser_hash"], digest(browser))
        ):
            raise HTTPException(
                400,
                "Google sign-in expired or was opened in a different browser. Please start again.",
            )
        saved = dict(row)
        con.execute("DELETE FROM oauth_states WHERE state_hash=?", (digest(state),))
    destination = saved["next_path"]
    try:
        if request.query_params.get("error"):
            raise ValueError("Access declined")
        if purpose == "youtube" and identity(request)["id"] != saved["user_id"]:
            raise ValueError("Account changed")
        code = request.query_params.get("code")
        if not code:
            raise ValueError("Missing code")
        token = exchange(purpose, code, state, saved["verifier"])
        if purpose == "login":
            claims = verify_login(token, saved["nonce"])
            with db() as con:
                con.execute("BEGIN IMMEDIATE")
                linked = con.execute(
                    "SELECT user_id FROM google_identities WHERE subject=?", (claims["sub"],)
                ).fetchone()
                if linked:
                    user_id = linked["user_id"]
                else:
                    user_id = uid()
                    # No email-based linking to local accounts or YouTube connection identities.
                    prefix = (
                        re.sub(
                            r"[^a-z0-9_-]", "", claims.get("email", "builder").split("@")[0].lower()
                        )[:24]
                        or "builder"
                    )
                    con.execute(
                        "INSERT INTO users VALUES(?,?,?)", (user_id, prefix + "-" + uid()[:8], "")
                    )
                    con.execute(
                        "INSERT INTO google_identities VALUES(?,?)", (claims["sub"], user_id)
                    )
                session = secrets.token_urlsafe(32)
                con.execute(
                    "INSERT INTO sessions VALUES(?,?,?)",
                    (digest(session), user_id, time.time() + 7 * 86400),
                )
            # Never overwrite an explicitly selected uploader on later sign-ins.
            with db() as con:
                existing = con.execute(
                    "SELECT 1 FROM youtube_connections WHERE user_id=?", (user_id,)
                ).fetchone()
            if not existing:
                try:
                    connect_youtube(user_id, token)
                except Exception:
                    # Optional permissions, no channel, and provider failures cannot break login.
                    pass
            response = RedirectResponse(destination, 303)
            response.set_cookie(
                COOKIE,
                session,
                httponly=True,
                samesite="lax",
                secure=os.getenv("COOKIE_SECURE") == "1",
                max_age=7 * 86400,
            )
        else:
            connect_youtube(saved["user_id"], token)
            response = RedirectResponse(destination + "?youtube=connected", 303)
    except Exception:
        # Provider response bodies and callback codes must never appear in logs or UI.
        target = "/login" if purpose == "login" else destination
        response = RedirectResponse(
            target + "?" + urlencode({"oauth_error": "connection_failed"}), 303
        )
    response.delete_cookie("ws_oauth_" + purpose)
    return response


@router.get("/api/auth/google/status")
def status():
    return {"configured": configured()}


@router.get("/api/auth/google")
def google_start(request: Request, next: str = "/dashboard"):
    return start(request, "login", next)


@router.get("/api/auth/google/callback")
def google_callback(request: Request):
    return finish(request, "login")


@router.get("/api/integrations/youtube/connect")
def youtube_start(request: Request, next: str = "/submit"):
    return start(request, "youtube", next)


@router.get("/api/integrations/youtube/callback")
def youtube_callback(request: Request):
    return finish(request, "youtube")


@router.get("/api/integrations/youtube")
def youtube_status(request: Request):
    user = identity(request)
    with db() as con:
        row = con.execute(
            "SELECT channel_id,channel_title FROM youtube_connections WHERE user_id=?",
            (user["id"],),
        ).fetchone()
    return {
        "configured": configured() and bool(os.getenv("OAUTH_TOKEN_ENCRYPTION_KEY")),
        "connection": dict(row) if row else None,
    }


@router.delete("/api/integrations/youtube")
def youtube_disconnect(request: Request):
    user = identity(request)
    with db() as con:
        con.execute("DELETE FROM youtube_connections WHERE user_id=?", (user["id"],))
        con.execute("DELETE FROM youtube_reports WHERE user_id=?", (user["id"],))
    return {"ok": True}
