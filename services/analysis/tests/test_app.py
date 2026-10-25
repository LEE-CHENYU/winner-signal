import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from analysis import storage, main


@pytest.fixture
def clients(tmp_path, monkeypatch):
    main._limits.clear()
    monkeypatch.setattr(storage, "DATA", tmp_path)
    monkeypatch.setattr(storage, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.setattr(main, "UPLOADS", tmp_path / "uploads")

    async def snap(url):
        return {
            "repository_url": "https://github.com/test/project",
            "commit_sha": "a" * 40,
            "coverage": "one test file",
            "files": {"app.py": {"text": 'def book():\n    return "mock"\n', "sha256": "b" * 64}},
        }

    monkeypatch.setattr(main, "snapshot", snap)
    with TestClient(main.app) as owner, TestClient(main.app) as stranger:
        assert (
            owner.post(
                "/api/auth/register", json={"username": "builder", "password": "long-password-123"}
            ).status_code
            == 200
        )
        assert (
            stranger.post(
                "/api/auth/register", json={"username": "stranger", "password": "long-password-123"}
            ).status_code
            == 200
        )
        yield owner, stranger


def project(owner):
    p = owner.post("/api/projects", json={"title": "Test demo", "description": "Test"}).json()
    v = owner.post(
        f"/api/projects/{p['id']}/versions",
        json={
            "repository_url": "https://github.com/test/project",
            "video_source_url": "https://example.com/video",
        },
    ).json()
    clip = storage.ROOT / "fixtures/mock_booking.mp4"
    r = owner.post(
        f"/api/versions/{v['id']}/upload-video",
        files={"file": ("demo.mp4", clip.read_bytes(), "video/mp4")},
    )
    assert r.status_code == 200, r.text
    return p, v, r.json()


def publish(owner, p, v):
    r = owner.post(
        f"/api/projects/{p['id']}/publish", json={"version_id": v["id"], "consent": True}
    )
    assert r.status_code == 200, r.text


def event(v, asset, kind="video_start", **extra):
    return {
        "event_id": storage.uid(),
        "version_id": v["id"],
        "anonymous_session_id": "viewer",
        "playback_session_id": "play",
        "binding_id": asset["binding_id"],
        "type": kind,
        "coverage_ms": 0,
        "media_position_ms": 0,
        "playback_rate": 1,
        **extra,
    }


def test_ownership_and_private_video(clients):
    owner, stranger = clients
    p, v, a = project(owner)
    for path in (
        f"/api/projects/{p['id']}",
        f"/api/projects/{p['id']}/versions",
        f"/api/projects/{p['id']}/analytics",
        f"/api/videos/{a['asset_id']}",
    ):
        assert stranger.get(path).status_code == 404
    assert (
        stranger.get(
            f"/api/projects/{p['id']}/analytics", headers={"X-Owner-Id": "builder"}
        ).status_code
        == 404
    )
    assert (
        owner.get(f"/api/videos/{a['asset_id']}", headers={"Range": "bytes=0-15"}).status_code
        == 206
    )
    publish(owner, p, v)
    assert stranger.get("/api/videos/" + a["asset_id"]).status_code == 200
    body = stranger.get("/api/demos/" + p["slug"]).json()
    assert "snapshot_json" not in body["version"] and "owner_id" not in body


def test_revision_does_not_auto_publish(clients):
    owner, viewer = clients
    p, v, a = project(owner)
    publish(owner, p, v)
    v2 = owner.post(
        f"/api/projects/{p['id']}/versions",
        json={"repository_url": "https://github.com/test/project"},
    ).json()
    assert viewer.get("/api/demos/" + p["slug"]).json()["version"]["id"] == v["id"]
    assert (
        owner.post(
            "/api/versions/" + v["id"] + "/upload-video",
            files={"file": ("a.mp4", b"x", "video/mp4")},
        ).status_code
        == 409
    )
    assert (
        owner.post(
            "/api/projects/" + p["id"] + "/publish", json={"version_id": v2["id"], "consent": True}
        ).status_code
        == 400
    )


def test_persisted_analytics_and_diagnostic_exclusion(clients):
    owner, viewer = clients
    p, v, a = project(owner)
    publish(owner, p, v)
    start = event(v, a)
    assert viewer.post("/api/events", json={"events": [start, start]}).json()["accepted"] == 1
    # Simulate elapsed wall time without waiting for an integration test video.
    with storage.db() as con:
        con.execute(
            "UPDATE engagement_events SET server_received_at=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat(),),
        )
    progress = event(v, a, "video_progress", coverage_ms=11500, media_position_ms=11500)
    viewer.post("/api/events", json={"events": [progress]})
    # End-position with zero observed coverage does not produce an additional completion.
    viewer.post(
        "/api/events",
        json={"events": [event(v, a, anonymous_session_id="seeker", playback_session_id="seek")]},
    )
    viewer.post(
        "/api/events",
        json={
            "events": [
                event(
                    v,
                    a,
                    "video_progress",
                    anonymous_session_id="seeker",
                    playback_session_id="seek",
                    media_position_ms=12000,
                )
            ]
        },
    )
    owner.post(
        "/api/events",
        json={"events": [event(v, a, anonymous_session_id="owner", playback_session_id="owner")]},
    )
    owner.post(
        "/api/events",
        json={
            "events": [
                event(
                    v,
                    a,
                    "video_progress",
                    anonymous_session_id="owner",
                    playback_session_id="owner",
                    coverage_ms=1000,
                    media_position_ms=1000,
                )
            ]
        },
    )
    metrics = owner.get("/api/projects/" + p["id"] + "/analytics").json()["metrics"]
    assert (
        metrics["video_starts"] == 2
        and metrics["completions"] == 1
        and metrics["completion_rate"] == 0.5
    )
    assert owner.post("/api/versions/" + v["id"] + "/analytics/verify").json()["verified"]
    assert viewer.post("/api/versions/" + v["id"] + "/analytics/verify").status_code == 404


def test_invalid_binding_and_fake_completion_rejected(clients):
    owner, viewer = clients
    p, v, a = project(owner)
    publish(owner, p, v)
    for bad in (
        event(v, a, binding_id="fake"),
        event(v, a, "video_complete"),
        event(v, a, playback_rate=-1),
    ):
        assert viewer.post("/api/events", json={"events": [bad]}).json()["accepted"] == 0


def test_history_private_redacted_and_removable(clients):
    owner, viewer = clients
    p, v, a = project(owner)
    r = owner.post(
        "/api/versions/" + v["id"] + "/history",
        files={"file": ("session.md", b"password=very-secret\nBuilt the app.", "text/plain")},
    )
    assert r.status_code == 200 and "very-secret" not in r.json()["preview"]
    assert viewer.get("/api/versions/" + v["id"] + "/history").status_code == 404
    assert (
        owner.delete("/api/versions/" + v["id"] + "/history/" + r.json()["id"]).status_code == 200
    )
    assert owner.get("/api/versions/" + v["id"] + "/history").json() == []


def test_host_reports_are_separate_and_bound(clients):
    owner, viewer = clients
    p, v, a = project(owner)
    report = {
        "provider": "test-host",
        "video_url": "https://example.com/video",
        "period_start": "2026-10-25",
        "period_end": "2026-10-25",
        "metrics": {"views": 500},
    }
    endpoint = "/api/versions/" + v["id"] + "/analytics/import"
    assert viewer.post(endpoint, json=report).status_code == 404
    assert (
        owner.post(endpoint, json={**report, "video_url": "https://other.example"}).status_code
        == 400
    )
    assert owner.post(endpoint, json=report).status_code == 200
    owner.post(endpoint, json=report)
    data = owner.get("/api/projects/" + p["id"] + "/analytics").json()
    assert len(data["reports"]) == 1 and data["metrics"]["video_starts"] == 0


def test_feedback_deduplicates_and_report_hides(clients):
    owner, viewer = clients
    p, v, a = project(owner)
    publish(owner, p, v)
    path = "/api/versions/" + v["id"] + "/feedback"
    headers = {"X-Session-Id": "visitor"}
    for _ in range(2):
        assert viewer.post(path, json={"kind": "use_this"}, headers=headers).status_code == 200
    assert (
        owner.get("/api/projects/" + p["id"] + "/analytics").json()["metrics"]["use_this_count"]
        == 1
    )
    viewer.post(path, json={"kind": "feedback", "text": "Interesting"}, headers=headers)
    feedback = viewer.get("/api/demos/" + p["slug"]).json()["feedback"][0]
    viewer.post("/api/feedback/" + feedback["id"] + "/report")
    assert viewer.get("/api/demos/" + p["slug"]).json()["feedback"] == []


def test_quota_configuration_never_creates_success(clients, monkeypatch):
    owner, _ = clients
    p, v, a = project(owner)
    monkeypatch.setenv("ENABLE_LIVE_ANALYSIS", "0")
    assert (
        owner.post("/api/versions/" + v["id"] + "/analyze", json={"consent": True}).status_code
        == 503
    )
    with storage.db() as con:
        assert con.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0


def test_origin_guard(clients):
    owner, _ = clients
    assert (
        owner.post(
            "/api/projects", json={"title": "x"}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_citation_validation_and_no_execution_claim():
    from analysis.gemini_analyzer import validate_review

    v = {
        "duration_ms": 10000,
        "repository_url": "https://github.com/test/repo",
        "commit_sha": "a" * 40,
        "snapshot_json": json.dumps({"files": {"app.py": {"text": "x=1\n", "sha256": "b" * 64}}}),
    }
    data = {
        "summary": "test",
        "claims": [
            {
                "text": "booking",
                "video_start_ms": 0,
                "video_end_ms": 1000,
                "observation_or_assertion": "assertion",
                "source_modality": "visual",
                "explanation": "test",
                "evidence": [
                    {
                        "file_path": "missing.py",
                        "start_line": 1,
                        "end_line": 2,
                        "relation": "supports",
                        "explanation": "fake",
                    }
                ],
            }
        ],
        "improvements": [],
    }
    result = validate_review(data, v)
    assert (
        result["claims"][0]["evidence"] == []
        and result["claims"][0]["evidence_state"] == "unresolved"
    )
    data["claims"][0]["video_end_ms"] = 11000
    with pytest.raises(ValueError):
        validate_review(data, v)


def test_evidence_tampering_detected(tmp_path, monkeypatch):
    from analysis import evidence

    monkeypatch.setattr(evidence, "DATA", tmp_path)
    root, seal = evidence.seal_review(
        "run",
        {"id": "v", "video_sha256": "c" * 64, "commit_sha": "a" * 40, "snapshot_json": "{}"},
        {"summary": "test"},
        {"model": "fixture"},
        [],
    )
    assert evidence.audit(root, seal)["verified"]
    artifact = next((Path(root) / "artifacts").rglob("*"))
    artifact = next(p for p in (Path(root) / "artifacts").rglob("*") if p.is_file())
    artifact.write_text("tampered")
    with pytest.raises(Exception):
        evidence.audit(root, seal)


def test_durable_job_idempotency_and_quota_failure(clients, monkeypatch):
    from analysis import worker

    owner, viewer = clients
    p, v, a = project(owner)
    monkeypatch.setenv("ENABLE_LIVE_ANALYSIS", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    route = "/api/versions/" + v["id"] + "/analyze"
    first = owner.post(route, json={"consent": True}).json()
    second = owner.post(route, json={"consent": True}).json()
    assert first["run_id"] == second["run_id"]
    assert viewer.get("/api/analysis/" + first["run_id"]).status_code == 404

    class QuotaError(Exception):
        code = 429

    def fail(run):
        raise QuotaError()

    monkeypatch.setattr(worker, "analyze", fail)
    assert worker.once()
    result = owner.get("/api/analysis/" + first["run_id"]).json()
    assert (
        result["run"]["status"] == "failed"
        and result["run"]["failure_code"] == "provider_quota_exhausted"
        and result["result"] is None
    )
    retry = owner.post(route, json={"consent": True}).json()
    assert retry["run_id"] != first["run_id"]


def test_real_upload_required_for_live_review(clients, monkeypatch):
    owner, _ = clients
    monkeypatch.setenv("ENABLE_LIVE_ANALYSIS", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    p = owner.post("/api/projects", json={"title": "link-only"}).json()
    v = owner.post(
        "/api/projects/" + p["id"] + "/versions",
        json={
            "repository_url": "https://github.com/test/project",
            "video_source_url": "https://example.com/video",
        },
    ).json()
    assert (
        owner.post("/api/versions/" + v["id"] + "/analyze", json={"consent": True}).status_code
        == 422
    )


def test_malformed_video_does_not_become_an_asset(clients):
    owner, _ = clients
    p = owner.post("/api/projects", json={"title": "invalid video"}).json()
    v = owner.post(
        "/api/projects/" + p["id"] + "/versions",
        json={"repository_url": "https://github.com/test/project"},
    ).json()
    assert (
        owner.post(
            "/api/versions/" + v["id"] + "/upload-video",
            files={"file": ("fake.mp4", b"not video", "video/mp4")},
        ).status_code
        == 400
    )
    assert owner.get("/api/projects/" + p["id"] + "/versions").json()[0]["video_asset_id"] is None


def test_silent_video_rejects_invented_audio():
    from analysis.gemini_analyzer import validate_review
    review = {"summary": "Narrator says a booking succeeded", "claims": [], "improvements": []}
    with pytest.raises(ValueError, match="unsupported_audio_claim"):
        validate_review(review, {"snapshot_json": "{}", "has_audio": 0, "duration_ms": 12000})


def test_daily_review_allowance_counts_failed_attempts(clients, monkeypatch):
    from analysis import worker
    owner, _ = clients
    _, v, _ = project(owner)
    monkeypatch.setenv("ENABLE_LIVE_ANALYSIS", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setenv("MAX_DAILY_ANALYSES", "1")
    route = "/api/versions/" + v["id"] + "/analyze"
    first = owner.post(route, json={"consent": True})
    assert first.status_code == 200
    assert owner.post(route, json={"consent": True}).json()["run_id"] == first.json()["run_id"]
    def fail(run):
        raise RuntimeError("analysis_cost_limit")
    monkeypatch.setattr(worker, "analyze", fail)
    worker.once()
    assert owner.post(route, json={"consent": True}).status_code == 429
