"""Winner Signal local application API. Run behind the same-origin web proxy."""

import hashlib
import json
import math
import os
import re
import secrets
import subprocess
import time
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import urlparse
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from .storage import DATA, UPLOADS, db, init_db, uid, now
from .auth import COOKIE, identity, password_hash, check_password, own_project, own_version
from .repository import snapshot


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="Winner Signal", lifespan=lifespan)
from .google_oauth import router as google_router
app.include_router(google_router)
from .youtube import router as youtube_router
app.include_router(youtube_router)


@app.middleware("http")
async def browser_guard(request, call_next):
    length = request.headers.get("content-length", "0")
    if length.isdigit() and int(length) > (
        85 * 1024 * 1024 if "/upload-video" in request.url.path else 2 * 1024 * 1024
    ):
        return JSONResponse({"detail": "Request too large"}, 413)
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
        expected = os.getenv("PUBLIC_ORIGIN", "http://localhost:3000")
        if origin != expected:
            return JSONResponse({"detail": "Origin not allowed"}, 403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


# Bounded in-memory rate limiting complements persisted reaction deduplication.
_limits = {}


def limit(key, maximum=30):
    t = time.monotonic()
    entries = [v for v in _limits.get(key, []) if v > t - 60]
    if len(entries) >= maximum:
        raise HTTPException(429, "Too many requests; try again shortly")
    entries.append(t)
    _limits[key] = entries
    if len(_limits) > 10000:
        for k in list(_limits):
            if _limits[k][-1] < t - 60:
                _limits.pop(k, None)


def text(value, maxlen=4000):
    if not isinstance(value, str) or len(value) > maxlen:
        raise HTTPException(400, "Invalid or oversized text")
    return value.strip()


def url(value):
    value = text(value or "", 2000)
    if value and (
        urlparse(value).scheme not in ("http", "https")
        or not urlparse(value).hostname
        or urlparse(value).username
    ):
        raise HTTPException(400, "Use an http(s) URL")
    return value or None


def visible_version(con, vid, user=None):
    row = con.execute(
        "SELECT v.*,p.owner_id,p.published_version_id FROM submission_versions v JOIN projects p ON p.id=v.project_id WHERE v.id=?",
        (vid,),
    ).fetchone()
    if not row or (
        row["published_version_id"] != vid and (not user or user["id"] != row["owner_id"])
    ):
        raise HTTPException(404, "Demo not found")
    return dict(row)


def public_version(v):
    return {
        k: v[k]
        for k in (
            "id",
            "version_number",
            "video_source_url",
            "video_asset_id",
            "repository_url",
            "commit_sha",
            "live_demo_url",
            "duration_ms",
            "is_fixture",
        )
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "model": os.getenv("GEMINI_MODEL", "gemini-4-argon"),
        "analysis_configured": bool(
            os.getenv("GEMINI_API_KEY")
            and os.getenv("ENABLE_LIVE_ANALYSIS") == "1"
            and all(
                float(os.getenv(k, "0")) > 0
                for k in ("MAX_ANALYSIS_USD", "INPUT_USD_PER_MILLION", "OUTPUT_USD_PER_MILLION")
            )
        ),
        "provider": "Gemini API (not Antigravity)",
        "worker_required": True,
    }


@app.post("/api/auth/{action}")
async def auth(action: str, request: Request):
    if action not in ("register", "login", "logout"):
        raise HTTPException(404)
    limit(("auth", request.client.host), 10)
    if action == "logout":
        with db() as con:
            con.execute(
                "DELETE FROM sessions WHERE token_hash=?",
                (hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest(),),
            )
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE)
        return response
    body = await request.json()
    username = text(body.get("username", ""), 40).lower()
    password = text(body.get("password", ""), 200)
    if not re.fullmatch(r"[a-z0-9_-]{3,40}", username) or len(password) < 10:
        raise HTTPException(
            400, "Use a 3–40 character username and a password of at least 10 characters"
        )
    with db() as con:
        user = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if action == "register":
            if user:
                raise HTTPException(409, "Username unavailable")
            user = {"id": uid(), "username": username}
            con.execute(
                "INSERT INTO users VALUES(?,?,?)", (user["id"], username, password_hash(password))
            )
        elif not user or not check_password(password, user["password_hash"]):
            raise HTTPException(401, "Invalid username or password")
        token = secrets.token_urlsafe(32)
        con.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), user["id"], time.time() + 7 * 86400),
        )
        con.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
    response = JSONResponse({"id": user["id"], "username": username})
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE") == "1",
        max_age=7 * 86400,
    )
    return response


@app.get("/api/me")
def me(request: Request):
    return identity(request, False)


@app.post("/api/projects")
async def create_project(request: Request):
    user = identity(request)
    body = await request.json()
    title = text(body.get("title", ""), 120)
    if not title:
        raise HTTPException(400, "Title is required")
    pid = uid()
    slug = re.sub("[^a-z0-9]+", "-", title.lower()).strip("-")[:60] + "-" + pid[:6]
    with db() as con:
        con.execute(
            "INSERT INTO projects(id,owner_id,slug,title,description) VALUES(?,?,?,?,?)",
            (pid, user["id"], slug, title, text(body.get("description", ""))),
        )
        return dict(con.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())


@app.get("/api/my-projects")
def my_projects(request: Request):
    user = identity(request)
    with db() as con:
        return [
            dict(r)
            for r in con.execute(
                "SELECT * FROM projects WHERE owner_id=? ORDER BY created_at DESC", (user["id"],)
            )
        ]


@app.get("/api/projects/{pid}")
def get_project(pid: str, request: Request):
    with db() as con:
        return own_project(con, pid, identity(request))


@app.post("/api/projects/{pid}/versions")
async def create_version(pid: str, request: Request):
    user = identity(request)
    body = await request.json()
    with db() as con:
        own_project(con, pid, user)
    repo = await snapshot(text(body.get("repository_url", ""), 2000))
    vid = uid()
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        n = con.execute(
            "SELECT COALESCE(MAX(version_number),0)+1 FROM submission_versions WHERE project_id=?",
            (pid,),
        ).fetchone()[0]
        con.execute(
            "INSERT INTO submission_versions(id,project_id,version_number,video_source_url,repository_url,commit_sha,live_demo_url,snapshot_json) VALUES(?,?,?,?,?,?,?,?)",
            (
                vid,
                pid,
                n,
                url(body.get("video_source_url")),
                repo["repository_url"],
                repo["commit_sha"],
                url(body.get("live_demo_url")),
                json.dumps(repo),
            ),
        )
        return dict(con.execute("SELECT * FROM submission_versions WHERE id=?", (vid,)).fetchone())


@app.get("/api/projects/{pid}/versions")
def versions(pid: str, request: Request):
    with db() as con:
        own_project(con, pid, identity(request))
        return [
            {k: v for k, v in dict(r).items() if k != "snapshot_json"}
            for r in con.execute(
                "SELECT * FROM submission_versions WHERE project_id=? ORDER BY version_number DESC",
                (pid,),
            )
        ]


@app.post("/api/projects/{pid}/publish")
async def publish(pid: str, request: Request):
    user = identity(request)
    body = await request.json()
    if body.get("consent") is not True:
        raise HTTPException(400, "Confirm public sharing of this video and project")
    with db() as con:
        own_project(con, pid, user)
        v = own_version(con, body.get("version_id"), user)
        if v["project_id"] != pid:
            raise HTTPException(400, "Version mismatch")
        if not v["video_asset_id"] and not v["video_source_url"]:
            raise HTTPException(400, "Add a demo video first")
        con.execute(
            "UPDATE projects SET visibility='published',published_version_id=? WHERE id=?",
            (v["id"], pid),
        )
        return {"published_version_id": v["id"]}


@app.post("/api/versions/{vid}/upload-video")
async def upload_video(vid: str, request: Request, file: UploadFile = File(...)):
    user = identity(request)
    with db() as con:
        v = own_version(con, vid, user)
        if (
            v["video_asset_id"]
            or con.execute("SELECT id FROM analysis_runs WHERE version_id=?", (vid,)).fetchone()
        ):
            raise HTTPException(409, "Create a new version to replace a video")
        if con.execute("SELECT id FROM projects WHERE published_version_id=?", (vid,)).fetchone():
            raise HTTPException(409, "Published versions are immutable")
    aid = uid()
    path = UPLOADS / aid
    total = 0
    digest = hashlib.sha256()
    try:
        with path.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > 80 * 1024 * 1024:
                    raise HTTPException(413, "Maximum video size is 80 MB")
                digest.update(chunk)
                f.write(chunk)
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=15,
        )
        info = json.loads(probe.stdout)
        duration = float(info["format"]["duration"]) * 1000
        if (
            not any(s["codec_type"] == "video" for s in info["streams"])
            or not 0 < duration <= 120000
        ):
            raise ValueError()
        has_audio = any(s.get("codec_type") == "audio" for s in info["streams"])
        fmt = info["format"]["format_name"]
        mime = "video/webm" if "webm" in fmt else "video/mp4" if "mp4" in fmt else None
        if not mime:
            raise ValueError()
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "Upload a valid MP4/WebM video of at most 2 minutes")
    bid = uid()
    with db() as con:
        # Serialize finalization; a simultaneous upload must not replace an existing asset.
        con.execute("BEGIN IMMEDIATE")
        current = own_version(con, vid, user)
        if (
            current["video_asset_id"]
            or con.execute(
                "SELECT id FROM projects WHERE published_version_id=?", (vid,)
            ).fetchone()
        ):
            path.unlink(missing_ok=True)
            raise HTTPException(409, "Version already finalized")
        con.execute(
            "UPDATE submission_versions SET video_asset_id=?,video_sha256=?,duration_ms=?,video_mime=?,has_audio=? WHERE id=?",
            (aid, digest.hexdigest(), int(duration), mime, int(has_audio), vid),
        )
        con.execute(
            "INSERT INTO video_analytics_bindings(id,version_id,mode,status,capabilities) VALUES(?,?,'hosted','configured',?)",
            (bid, vid, json.dumps(["start", "progress", "completion"])),
        )
    return {"asset_id": aid, "binding_id": bid, "duration_ms": int(duration)}


@app.get("/api/videos/{aid}")
def video(aid: str, request: Request):
    with db() as con:
        v = con.execute(
            "SELECT id FROM submission_versions WHERE video_asset_id=?", (aid,)
        ).fetchone()
        if not v:
            raise HTTPException(404)
        v = visible_version(con, v["id"], identity(request, False))
    return FileResponse(UPLOADS / aid, media_type=v["video_mime"])


@app.get("/api/gallery")
def gallery(sort: str = "discovery", seed: str = "default"):
    with db() as con:
        rows = con.execute(
            "SELECT p.slug,p.title,p.description,u.username AS builder_display_name,v.* FROM projects p JOIN users u ON u.id=p.owner_id JOIN submission_versions v ON v.id=p.published_version_id WHERE p.visibility='published' ORDER BY v.created_at DESC"
        ).fetchall()
    cards = [
        {
            "slug": r["slug"],
            "title": r["title"],
            "description": r["description"],
            "builder_display_name": r["builder_display_name"],
            "version": public_version(r),
        }
        for r in rows
    ]
    if sort != "newest":
        cards.sort(key=lambda r: hashlib.sha256((seed[:100] + r["slug"]).encode()).hexdigest())
    return cards


@app.get("/api/demos/{slug}")
def demo(slug: str, request: Request):
    with db() as con:
        p = con.execute(
            "SELECT p.*,u.username FROM projects p JOIN users u ON u.id=p.owner_id WHERE slug=? AND visibility='published'",
            (slug,),
        ).fetchone()
        if not p:
            raise HTTPException(404, "Demo not found")
        v = con.execute(
            "SELECT * FROM submission_versions WHERE id=?", (p["published_version_id"],)
        ).fetchone()
        binding = con.execute(
            "SELECT * FROM video_analytics_bindings WHERE version_id=?", (v["id"],)
        ).fetchone()
        feedback = [
            dict(r)
            for r in con.execute(
                "SELECT id,kind,text,created_at FROM feedback WHERE version_id=? AND moderation_status='visible' AND kind!='use_this' ORDER BY created_at DESC LIMIT 50",
                (v["id"],),
            )
        ]
    user = identity(request, False)
    return {
        "title": p["title"],
        "description": p["description"],
        "builder_display_name": p["username"],
        "version": public_version(v),
        "binding": dict(binding) if binding else None,
        "feedback": feedback,
        "is_owner": bool(user and user["id"] == p["owner_id"]),
    }


@app.post("/api/events")
async def events(request: Request):
    limit(("events", request.client.host), 180)
    body = await request.json()
    batch = body.get("events", [])
    if not isinstance(batch, list) or not 0 < len(batch) <= 100:
        raise HTTPException(400, "Send 1–100 events")
    user = identity(request, False)
    accepted = 0
    with db() as con:
        for e in batch:
            if not isinstance(e, dict):
                continue
            kind = e.get("type")
            sid = e.get("anonymous_session_id")
            eid = e.get("event_id")
            if kind not in (
                "page_view",
                "video_start",
                "video_progress",
                "github_click",
                "livedemo_click",
            ) or not all(isinstance(x, str) and 1 <= len(x) <= 100 for x in (sid, eid)):
                continue
            try:
                v = visible_version(con, e.get("version_id"), user)
            except HTTPException:
                continue
            diagnostic = (
                bool(user and user["id"] == v["owner_id"])
                or bool(e.get("is_diagnostic"))
                or bool(v["is_fixture"])
            )
            coverage = 0.0
            duration = v["duration_ms"]
            playback = e.get("playback_session_id")
            bid = e.get("binding_id")
            if kind.startswith("video_"):
                if (
                    not v["video_asset_id"]
                    or not isinstance(playback, str)
                    or not 1 <= len(playback) <= 100
                ):
                    continue
                binding = con.execute(
                    "SELECT id FROM video_analytics_bindings WHERE id=? AND version_id=?",
                    (bid, v["id"]),
                ).fetchone()
                if not binding:
                    continue
                try:
                    coverage = float(e.get("coverage_ms", 0))
                    position = float(e.get("media_position_ms", 0))
                    rate = float(e.get("playback_rate", 1))
                    if (
                        not all(math.isfinite(x) for x in (coverage, position, rate))
                        or not 0 <= coverage <= duration + 100
                        or not 0 <= position <= duration + 100
                        or not 0.25 <= rate <= 4
                    ):
                        continue
                except (TypeError, ValueError):
                    continue
                if kind == "video_start":
                    coverage = 0
                else:
                    start = con.execute(
                        "SELECT server_received_at FROM engagement_events WHERE version_id=? AND anonymous_session_id=? AND playback_session_id=? AND type='video_start' ORDER BY server_received_at LIMIT 1",
                        (v["id"], sid, playback),
                    ).fetchone()
                    if not start:
                        continue
                    elapsed = (
                        datetime.now().timestamp()
                        - datetime.fromisoformat(start[0].replace("Z", "+00:00")).timestamp()
                    ) * 1000
                    if coverage > max(0, elapsed) * 4 + 2000:
                        continue
            try:
                inserted = con.execute(
                    """INSERT OR IGNORE INTO engagement_events(id,event_id,version_id,anonymous_session_id,type,occurred_at,playback_session_id,binding_id,source,media_position_ms,duration_ms,playback_rate,coverage_ms,is_diagnostic,eligible_for_metrics,server_received_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        uid(),
                        eid,
                        v["id"],
                        sid,
                        kind,
                        now(),
                        playback,
                        bid,
                        "winner_signal",
                        e.get("media_position_ms"),
                        duration,
                        e.get("playback_rate"),
                        coverage,
                        int(diagnostic),
                        int(not diagnostic),
                        now(),
                    ),
                ).rowcount
                accepted += inserted
            except (TypeError, ValueError):
                continue
    return {"accepted": accepted, "total": len(batch)}


@app.post("/api/versions/{vid}/feedback")
async def feedback(vid: str, request: Request):
    limit(("feedback", request.client.host), 10)
    body = await request.json()
    kind = body.get("kind")
    sid = text(request.headers.get("X-Session-Id", ""), 100)
    if kind not in ("use_this", "question", "feedback") or not sid:
        raise HTTPException(400, "Invalid feedback")
    content = text(body.get("text", ""), 2000)
    if kind != "use_this" and not content:
        raise HTTPException(400, "Add your question or feedback")
    with db() as con:
        visible_version(con, vid)
        if (
            kind == "use_this"
            and con.execute(
                "SELECT id FROM feedback WHERE version_id=? AND visitor_or_user_id=? AND kind=?",
                (vid, sid, kind),
            ).fetchone()
        ):
            return {"ok": True}
        con.execute(
            "INSERT INTO feedback(id,version_id,visitor_or_user_id,kind,text) VALUES(?,?,?,?,?)",
            (uid(), vid, sid, kind, content),
        )
    return {"ok": True}


@app.post("/api/feedback/{fid}/report")
def report(fid: str, request: Request):
    limit(("report", request.client.host), 10)
    with db() as con:
        con.execute("UPDATE feedback SET moderation_status='reported' WHERE id=?", (fid,))
    return {"ok": True}


@app.get("/api/projects/{pid}/analytics")
def analytics(pid: str, request: Request, version_id: str | None = None):
    with db() as con:
        own_project(con, pid, identity(request))
        v = con.execute(
            "SELECT * FROM submission_versions WHERE project_id=? AND (? IS NULL OR id=?) ORDER BY version_number DESC LIMIT 1",
            (pid, version_id, version_id),
        ).fetchone()
        if not v:
            return {"metrics": None, "reports": []}
        vid = v["id"]
        rows = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM engagement_events WHERE version_id=? AND eligible_for_metrics=1",
                (vid,),
            )
        ]

        def count(kind):
            return len({r["anonymous_session_id"] for r in rows if r["type"] == kind})

        starts = {r["anonymous_session_id"] for r in rows if r["type"] == "video_start"}
        complete = {
            r["anonymous_session_id"]
            for r in rows
            if r["type"] == "video_progress"
            and v["duration_ms"]
            and (r["coverage_ms"] or 0) >= 0.9 * v["duration_ms"]
        } & starts
        binding = con.execute(
            "SELECT * FROM video_analytics_bindings WHERE version_id=?", (vid,)
        ).fetchone()
        feedback = [
            dict(r)
            for r in con.execute(
                "SELECT id,kind,text,created_at,moderation_status FROM feedback WHERE version_id=? ORDER BY created_at DESC LIMIT 50",
                (vid,),
            )
        ]
        reports = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM host_reports WHERE version_id=? ORDER BY created_at DESC", (vid,)
            )
        ]
        run = con.execute(
            "SELECT id,status,mode,failure_code FROM analysis_runs WHERE version_id=? ORDER BY created_at DESC LIMIT 1",
            (vid,),
        ).fetchone()
    return {
        "version_id": vid,
        "period": "All time, UTC",
        "metrics": {
            "page_visitors": count("page_view"),
            "video_starts": len(starts),
            "completions": len(complete),
            "completion_rate": len(complete) / len(starts) if starts and binding else None,
            "github_clicks": count("github_click"),
            "livedemo_clicks": count("livedemo_click"),
            "use_this_count": len([f for f in feedback if f["kind"] == "use_this"]),
            "small_sample": len(starts) < 20,
        },
        "feedback": feedback,
        "binding": dict(binding) if binding else None,
        "reports": reports,
        "latest_run": dict(run) if run else None,
    }


@app.post("/api/versions/{vid}/analytics/verify")
def verify(vid: str, request: Request):
    with db() as con:
        own_version(con, vid, identity(request))
        rows = con.execute(
            "SELECT playback_session_id,type FROM engagement_events WHERE version_id=? AND is_diagnostic=1 AND type IN ('video_start','video_progress')",
            (vid,),
        ).fetchall()
        groups = {}
        for r in rows:
            groups.setdefault(r["playback_session_id"], set()).add(r["type"])
        ok = any(len(types) == 2 for types in groups.values())
        if ok:
            con.execute(
                "UPDATE video_analytics_bindings SET status='verified',verified_at=? WHERE version_id=?",
                (now(), vid),
            )
    return {"verified": ok, "diagnostic_events_received": len(rows)}


@app.post("/api/versions/{vid}/analytics/import")
async def import_report(vid: str, request: Request):
    user = identity(request)
    body = await request.json()
    with db() as con:
        v = own_version(con, vid, user)
        if body.get("video_url") != v["video_source_url"] or not v["video_source_url"]:
            raise HTTPException(
                400, "Report video_url must match this version’s original video URL"
            )
        provider = text(body.get("provider", ""), 80)
        start = text(body.get("period_start", ""), 40)
        end = text(body.get("period_end", ""), 40)
        try:
            if datetime.fromisoformat(start) > datetime.fromisoformat(end):
                raise ValueError()
        except ValueError:
            raise HTTPException(400, "Use valid ISO dates with start before end")
        metrics = body.get("metrics", {})
        if not provider or not isinstance(metrics, dict) or not 1 <= len(metrics) <= 20:
            raise HTTPException(400, "Provide provider and metric values")
        for k, vv in metrics.items():
            if (
                not re.fullmatch(r"[a-z_]{1,40}", k)
                or isinstance(vv, bool)
                or not isinstance(vv, (int, float))
                or not math.isfinite(vv)
                or vv < 0
            ):
                raise HTTPException(400, "Metrics must be named nonnegative numbers")
        rid = hashlib.sha256(json.dumps([vid, body], sort_keys=True).encode()).hexdigest()
        con.execute(
            "INSERT OR IGNORE INTO host_reports VALUES(?,?,?,?,?,?,?,?)",
            (rid, vid, provider, v["video_source_url"], start, end, json.dumps(metrics), now()),
        )
    return {"id": rid, "source": "participant_supplied_export"}


@app.delete("/api/versions/{vid}/analytics/import/{rid}")
def delete_report(vid: str, rid: str, request: Request):
    with db() as con:
        own_version(con, vid, identity(request))
        con.execute("DELETE FROM host_reports WHERE id=? AND version_id=?", (rid, vid))
    return {"ok": True}


@app.post("/api/versions/{vid}/history")
async def history_upload(vid: str, request: Request, file: UploadFile = File(...)):
    user = identity(request)
    raw = await file.read(1_000_001)
    if len(raw) > 1_000_000:
        raise HTTPException(413, "History limit is 1 MB")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "Upload UTF-8 JSON, JSONL, Markdown or text")
    if PathSuffix(file.filename) not in (".json", ".jsonl", ".md", ".txt"):
        raise HTTPException(400, "Unsupported history format")
    redacted, n = re.subn(
        r"\b(?:sk-proj-|sk-ant-|ghp_|github_pat_|AIza)[A-Za-z0-9_-]{20,}|(?im:((?:api[_-]?key|token|password|secret)\s*[=:]\s*)[^\s,;]+)",
        "[REDACTED]",
        content,
    )
    redacted, n2 = re.subn(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
        "[REDACTED]",
        redacted,
    )
    aid = uid()
    data = redacted.encode()
    with db() as con:
        own_version(con, vid, user)
        if (
            con.execute(
                "SELECT COUNT(*) FROM private_artifacts WHERE version_id=?", (vid,)
            ).fetchone()[0]
            >= 5
        ):
            raise HTTPException(400, "Maximum five history files per version")
        (UPLOADS / aid).write_bytes(data)
        con.execute(
            "INSERT INTO private_artifacts(id,owner_id,version_id,kind,storage_key,sha256,media_type,byte_size,redaction_status) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                aid,
                user["id"],
                vid,
                "build_history",
                aid,
                hashlib.sha256(data).hexdigest(),
                "text/plain",
                len(data),
                f"{n + n2} replacements; best effort",
            ),
        )
    return {"id": aid, "preview": redacted, "redactions": n + n2}


def PathSuffix(name):
    from pathlib import Path

    return Path(name or "").suffix.lower()


@app.get("/api/versions/{vid}/history")
def histories(vid: str, request: Request):
    with db() as con:
        own_version(con, vid, identity(request))
        return [
            {
                "id": r["id"],
                "preview": (UPLOADS / r["storage_key"]).read_text(),
                "redaction_status": r["redaction_status"],
            }
            for r in con.execute(
                "SELECT * FROM private_artifacts WHERE version_id=? AND kind='build_history'",
                (vid,),
            )
        ]


@app.delete("/api/versions/{vid}/history/{aid}")
def delete_history(vid: str, aid: str, request: Request):
    with db() as con:
        own_version(con, vid, identity(request))
        r = con.execute(
            "SELECT * FROM private_artifacts WHERE id=? AND version_id=?", (aid, vid)
        ).fetchone()
        if not r:
            raise HTTPException(404)
        # Sealed reviews may already contain a consented snapshot; explain this in the UI.
        con.execute("DELETE FROM private_artifacts WHERE id=?", (aid,))
        (UPLOADS / r["storage_key"]).unlink(missing_ok=True)
    return {"ok": True}


@app.post("/api/versions/{vid}/analyze")
async def analyze(vid: str, request: Request):
    user = identity(request)
    body = await request.json()
    mode = body.get("mode", "live")
    if mode != "live":
        raise HTTPException(400, "Use the labeled example project for fixture analysis")
    if not os.getenv("GEMINI_API_KEY") or os.getenv("ENABLE_LIVE_ANALYSIS") != "1":
        raise HTTPException(
            503,
            "Live analysis is not enabled. Gallery and playback analytics still work. Configure Gemini API access; Antigravity quota is not used here.",
        )
    if body.get("consent") is not True:
        raise HTTPException(
            400, "Confirm sending this video, public code and selected history to Gemini"
        )
    with db() as con:
        v = own_version(con, vid, user)
        if not v["video_asset_id"]:
            from .youtube import video_id, connection
            if not video_id(v["video_source_url"]):
                raise HTTPException(422, "Review requires a public YouTube demo URL")
            if not connection(user["id"]):
                raise HTTPException(422, "Connect the uploader's YouTube account before reviewing this link")
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute(
            "SELECT id FROM analysis_runs WHERE version_id=? AND status IN ('queued','running')",
            (vid,),
        ).fetchone()
        if existing:
            return {"run_id": existing["id"]}
        daily_limit = int(os.getenv("MAX_DAILY_ANALYSES", "0"))
        if daily_limit > 0:
            attempts_today = con.execute(
                "SELECT COUNT(*) FROM analysis_runs WHERE mode='live' AND substr(created_at,1,10)=?",
                (now()[:10],),
            ).fetchone()[0]
            if attempts_today >= daily_limit:
                raise HTTPException(429, "Today's review allowance has been reached; try again tomorrow (UTC).")
        rid = uid()
        attempt = con.execute(
            "SELECT COUNT(*)+1 FROM analysis_runs WHERE version_id=?", (vid,)
        ).fetchone()[0]
        con.execute(
            "INSERT INTO analysis_runs(id,version_id,attempt_number,model_id,include_history,prompt_version,rubric_version) VALUES(?,?,?,?,?,?,?)",
            (
                rid,
                vid,
                attempt,
                os.getenv("GEMINI_MODEL", "gemini-4-argon"),
                int(body.get("include_history") is True),
                "1",
                "1",
            ),
        )
    return {"run_id": rid, "status": "queued"}


@app.get("/api/analysis/{rid}")
def analysis_result(rid: str, request: Request):
    with db() as con:
        r = con.execute("SELECT * FROM analysis_runs WHERE id=?", (rid,)).fetchone()
        if not r:
            raise HTTPException(404)
        own_version(con, r["version_id"], identity(request))
        run = {k: v for k, v in dict(r).items() if k not in ("result_json", "evidence_root")}
        return {"run": run, "result": json.loads(r["result_json"]) if r["status"] == "succeeded" and r["result_json"] else None}


@app.get("/api/analysis/{rid}/evidence")
def evidence(rid: str, request: Request):
    with db() as con:
        r = con.execute("SELECT * FROM analysis_runs WHERE id=?", (rid,)).fetchone()
        if not r:
            raise HTTPException(404)
        own_version(con, r["version_id"], identity(request))
    if not r["evidence_root"]:
        raise HTTPException(404, "No sealed evidence yet")
    from .evidence import audit

    return audit(r["evidence_root"], r["seal"])


@app.get("/api/examples/source")
def example_source():
    from fastapi.responses import PlainTextResponse
    from .storage import ROOT

    return PlainTextResponse((ROOT / "fixtures/mock_booking.py").read_text())


@app.post("/api/examples")
def example(request: Request):
    """Create a private, conspicuously labeled controlled example. No model call."""
    import shutil
    from .storage import ROOT
    from .evidence import seal_review

    user = identity(request)
    pid = uid()
    vid = uid()
    aid = uid()
    rid = uid()
    bid = uid()
    media = ROOT / "fixtures/mock_booking.mp4"
    source = (ROOT / "fixtures/mock_booking.py").read_text()
    shutil.copyfile(media, UPLOADS / aid)
    sha = hashlib.sha256(media.read_bytes()).hexdigest()
    snapshot_data = {
        "files": {
            "mock_booking.py": {
                "text": source,
                "sha256": hashlib.sha256(source.encode()).hexdigest(),
            }
        },
        "coverage": "One controlled example file, not a real submitted repository",
    }
    version = {
        "id": vid,
        "video_sha256": sha,
        "commit_sha": None,
        "snapshot_json": json.dumps(snapshot_data),
    }
    review = {
        "summary": "The recording displays a booking confirmation, while the example implementation returns a fixed mock response.",
        "claims": [
            {
                "text": "The app shows an appointment as booked.",
                "video_start_ms": 0,
                "video_end_ms": 12000,
                "evidence_state": "unresolved",
                "explanation": "The confirmation is visible, but the code does not write to a calendar.",
                "evidence": [
                    {
                        "file_path": "mock_booking.py",
                        "start_line": 2,
                        "end_line": 3,
                        "url": "/api/examples/source",
                        "relation": "contradicts",
                        "explanation": "A constant booking identifier is returned without calling a calendar service.",
                    }
                ],
            }
        ],
        "improvements": [
            {
                "action": "Demonstrate a real calendar write and readback.",
                "rationale": "A confirmation message alone does not establish that an appointment exists.",
                "proposed_verification": "Create an appointment in a test calendar, retrieve it and show the matching ID.",
            }
        ],
        "limitations": [
            "Controlled fixture, authored for the example. No Gemini call was made.",
            "Fixture traffic is excluded from audience analytics.",
        ],
    }
    root, seal = seal_review(rid, version, review, {"mode": "fixture", "model": None}, [])
    with db() as con:
        con.execute(
            "INSERT INTO projects(id,owner_id,slug,title,description) VALUES(?,?,?,?,?)",
            (
                pid,
                user["id"],
                "controlled-booking-" + pid[:6],
                "[Example] Meeting scheduler",
                "A controlled example showing a mock confirmation and its source evidence.",
            ),
        )
        con.execute(
            "INSERT INTO submission_versions(id,project_id,video_asset_id,video_sha256,duration_ms,video_mime,snapshot_json,is_fixture,repository_url) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                vid,
                pid,
                aid,
                sha,
                12000,
                "video/mp4",
                json.dumps(snapshot_data),
                1,
                "https://github.com/aeread-org/AERead",
            ),
        )
        con.execute(
            "INSERT INTO video_analytics_bindings(id,version_id,mode,status,capabilities) VALUES(?,?,'hosted','configured',?)",
            (bid, vid, json.dumps(["start", "progress", "completion"])),
        )
        con.execute(
            "INSERT INTO analysis_runs(id,version_id,status,mode,model_id,result_json,evidence_root,seal,completed_at) VALUES(?,?,'succeeded','fixture','No model — authored fixture',?,?,?,?)",
            (rid, vid, json.dumps(review), root, seal, now()),
        )
    return {"project_id": pid}
