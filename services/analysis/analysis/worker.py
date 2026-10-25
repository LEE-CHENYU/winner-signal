"""Single durable worker. Interrupted calls fail visibly; retries are new attempts."""

import fcntl
import time
from .storage import DATA, init_db, db, now
from .gemini_analyzer import analyze


def once():
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM analysis_runs WHERE status='queued' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if not row:
            return False
        run = dict(row)
        con.execute(
            "UPDATE analysis_runs SET status='running',started_at=? WHERE id=?", (now(), run["id"])
        )
    try:
        analyze(run)
    except Exception as error:
        code = getattr(error, "code", None)
        condition = (
            "provider_quota_exhausted"
            if code == 429
            else "provider_access_denied"
            if code in (401, 403)
            else "provider_model_unavailable"
            if code == 404
            else "analysis_failed"
        )
        if isinstance(error, (RuntimeError, ValueError)) and str(error) in (
            "youtube_review_requires_public_url",
            "youtube_review_requires_connection",
            "youtube_review_wrong_channel",
            "youtube_review_invalid_duration",
            "youtube_review_duration_limit",
            "unsupported_audio_claim",
            "invalid_video_timestamp",
            "provider_not_configured",
            "video_processing_failed",
            "video_processing_timeout",
            "cost_limits_not_configured",
            "analysis_cost_limit",
        ):
            condition = str(error)
        with db() as con:
            con.execute(
                "UPDATE analysis_runs SET status='failed',failure_code=?,completed_at=? WHERE id=?",
                (condition, now(), run["id"]),
            )
        # Do not log provider exception bodies: they may include credentials or submitted content.
        print(f"Review {run['id']} failed: {condition} ({type(error).__name__})", flush=True)
    return True


def main():
    init_db()
    with (DATA / "worker.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with db() as con:
            con.execute(
                "UPDATE analysis_runs SET status='failed',failure_code='worker_interrupted',completed_at=? WHERE status='running'",
                (now(),),
            )
        while True:
            if not once():
                time.sleep(1)


if __name__ == "__main__":
    main()
