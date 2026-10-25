import hashlib
import hmac
import secrets
import time
from fastapi import HTTPException, Request
from .storage import db

COOKIE = "ws_session"


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return (
        salt + ":" + hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    )


def check_password(password, stored):
    return bool(stored) and hmac.compare_digest(password_hash(password, stored.split(":")[0]), stored)


def identity(request: Request, required=True):
    token = request.cookies.get(COOKIE, "")
    with db() as con:
        row = con.execute(
            "SELECT u.id,u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=? AND expires>?",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
    if row:
        return dict(row)
    if required:
        raise HTTPException(401, "Sign in to access your projects")
    return None


def own_project(con, project_id, user):
    row = con.execute(
        "SELECT * FROM projects WHERE id=? AND owner_id=?", (project_id, user["id"])
    ).fetchone()
    if not row:
        raise HTTPException(404, "Project not found")
    return dict(row)


def own_version(con, version_id, user):
    row = con.execute(
        "SELECT v.* FROM submission_versions v JOIN projects p ON p.id=v.project_id WHERE v.id=? AND p.owner_id=?",
        (version_id, user["id"]),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Version not found")
    return dict(row)
