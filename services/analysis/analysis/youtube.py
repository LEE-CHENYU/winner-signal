"""Owner-authorized YouTube reads; a connected channel never changes app identity."""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Request
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from .auth import identity, own_version
from .google_oauth import YOUTUBE_SCOPES
from .storage import db

router = APIRouter()


def video_id(url):
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        result = parsed.path.strip("/")
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        parts = parsed.path.strip("/").split("/")
        result = (
            parse_qs(parsed.query).get("v", [""])[0]
            if parsed.path == "/watch"
            else parts[1]
            if len(parts) == 2 and parts[0] in ("shorts", "embed", "live")
            else ""
        )
    else:
        return None
    return result if re.fullmatch(r"[A-Za-z0-9_-]{11}", result) else None


def connection(user_id):
    with db() as con:
        row = con.execute(
            "SELECT * FROM youtube_connections WHERE user_id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def access_token(conn):
    cipher = Fernet(os.environ["OAUTH_TOKEN_ENCRYPTION_KEY"].encode())
    token = json.loads(cipher.decrypt(conn["credentials"].encode()))
    if token.get("expires_at", 0) > time.time() + 60:
        return token["access_token"]
    credentials = Credentials(
        token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        scopes=YOUTUBE_SCOPES,
    )
    credentials.refresh(GoogleRequest())
    token.update(access_token=credentials.token, expires_at=time.time() + 3500)
    encrypted = cipher.encrypt(json.dumps(token).encode()).decode()
    with db() as con:
        con.execute(
            "UPDATE youtube_connections SET credentials=? WHERE user_id=? AND credentials=?",
            (encrypted, conn["user_id"], conn["credentials"]),
        )
    return credentials.token


def get(client, path, params, token, analytics=False):
    origin = (
        "https://youtubeanalytics.googleapis.com/v2/"
        if analytics
        else "https://www.googleapis.com/youtube/v3/"
    )
    response = client.get(
        origin + path, params=params, headers={"Authorization": "Bearer " + token}
    )
    response.raise_for_status()
    return response.json()


@router.get("/api/integrations/youtube/videos")
def videos(request: Request):
    user = identity(request)
    conn = connection(user["id"])
    if not conn:
        raise HTTPException(
            409, "Connect the Google account that owns your demo, or paste the link instead."
        )
    try:
        token = access_token(conn)
        with httpx.Client(timeout=20) as client:
            channels = get(client, "channels", {"part": "contentDetails", "mine": "true"}, token)[
                "items"
            ]
            ch = next(c for c in channels if c["id"] == conn["channel_id"])
            playlist = ch["contentDetails"]["relatedPlaylists"]["uploads"]
            items = get(
                client,
                "playlistItems",
                {"part": "snippet,contentDetails", "playlistId": playlist, "maxResults": 25},
                token,
            ).get("items", [])
        return [
            {"id": i["contentDetails"]["videoId"], "title": i["snippet"]["title"]} for i in items
        ]
    except Exception:
        raise HTTPException(
            502,
            "Could not load YouTube videos. Reconnect the uploader account, or add your demo by link.",
        )


@router.get("/api/versions/{vid}/youtube-analytics")
def analytics(vid: str, request: Request):
    user = identity(request)
    with db() as con:
        version = own_version(con, vid, user)
    video = video_id(version["video_source_url"])
    if not video:
        return {"status": "not_youtube"}
    conn = connection(user["id"])
    if not conn:
        return {"status": "not_connected"}
    with db() as con:
        cached = con.execute(
            "SELECT * FROM youtube_reports WHERE user_id=? AND video_id=? AND channel_id=?",
            (user["id"], video, conn["channel_id"]),
        ).fetchone()
    if cached and cached["fetched_at"] > time.time() - 6 * 3600:
        return json.loads(cached["report_json"])
    try:
        token = access_token(conn)
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=28)
        with httpx.Client(timeout=20) as client:
            items = get(client, "videos", {"part": "snippet", "id": video}, token).get("items", [])
            if not items or items[0]["snippet"]["channelId"] != conn["channel_id"]:
                return {"status": "different_channel", "channel_title": conn["channel_title"]}
            report = get(
                client,
                "reports",
                {
                    "ids": "channel==MINE",
                    "startDate": str(start),
                    "endDate": str(end),
                    "dimensions": "day",
                    "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
                    "filters": "video==" + video,
                    "sort": "day",
                },
                token,
                analytics=True,
            )
        names = [h["name"] for h in report.get("columnHeaders", [])]
        rows = [dict(zip(names, row)) for row in report.get("rows", [])]
        payload = {
            "status": "connected" if rows else "pending_data",
            "source": "youtube_oauth",
            "video_id": video,
            "channel_title": conn["channel_title"],
            "period_start": str(start),
            "period_end": str(end),
            "latest_available_day": rows[-1].get("day") if rows else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "daily": rows,
        }
        with db() as con:
            # Do not persist data after a concurrent disconnect or channel switch.
            current = con.execute(
                "SELECT channel_id FROM youtube_connections WHERE user_id=?", (user["id"],)
            ).fetchone()
            if current and current["channel_id"] == conn["channel_id"]:
                con.execute(
                    "INSERT OR REPLACE INTO youtube_reports VALUES(?,?,?,?,?)",
                    (user["id"], video, conn["channel_id"], time.time(), json.dumps(payload)),
                )
        return payload
    except Exception:
        return {
            "status": "connection_error",
            "message": "YouTube could not supply this report. Reconnect the uploader account or use an exported report.",
        }


def review_media(version, user_id):
    """Validate an owned public short video before a Gemini URL review."""
    video = video_id(version.get("video_source_url"))
    if not video:
        raise ValueError("youtube_review_requires_public_url")
    conn = connection(user_id)
    if not conn:
        raise ValueError("youtube_review_requires_connection")
    with httpx.Client(timeout=20) as client:
        items = get(client, "videos", {"part": "snippet,contentDetails,status", "id": video}, access_token(conn)).get("items", [])
    if len(items) != 1 or items[0]["snippet"]["channelId"] != conn["channel_id"]:
        raise ValueError("youtube_review_wrong_channel")
    item = items[0]
    if item.get("status", {}).get("privacyStatus") != "public":
        raise ValueError("youtube_review_requires_public_url")
    duration = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", item.get("contentDetails", {}).get("duration", ""))
    if not duration:
        raise ValueError("youtube_review_invalid_duration")
    hours, minutes, seconds = (float(n or 0) for n in duration.groups())
    milliseconds = int((hours * 3600 + minutes * 60 + seconds) * 1000)
    if not 0 < milliseconds <= 120000 or item["snippet"].get("liveBroadcastContent", "none") != "none":
        raise ValueError("youtube_review_duration_limit")
    return {"kind": "youtube_url", "url": "https://www.youtube.com/watch?v=" + video,
            "video_id": video, "channel_id": conn["channel_id"], "duration_ms": milliseconds,
            "has_audio": None, "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "content_hash_available": False}
