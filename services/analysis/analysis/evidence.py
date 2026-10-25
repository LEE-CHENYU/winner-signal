"""Thin adapter over an unmodified, pinned Apache-2.0 AERead source snapshot."""

import dataclasses
import hashlib
import json
import sys
from .storage import ROOT, DATA

VENDOR = ROOT / "vendor/aeread"
MANIFEST = json.loads((VENDOR / "PROVENANCE.json").read_text())
# Verify the dependency bytes at import; never import from a mutable live checkout.
for name, digest in MANIFEST["files"].items():
    if hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() != digest:
        raise RuntimeError("AERead dependency integrity mismatch")
sys.path.insert(0, str(VENDOR / "src"))
from aeread.shared_runner.task.execution import EvidenceStore


def seal_review(run_id, version, review, request_record, histories):
    root = DATA / "evidence" / run_id
    with EvidenceStore(
        root,
        run_plan_id="review_" + run_id,
        cell_id="submission_" + version["id"],
        episode_id="review_" + run_id,
        episode_attempt_id=run_id,
    ) as store:
        store.append_event(
            "source_ingested",
            {
                "video_sha256": version["video_sha256"],
                "remote_media": version.get("remote_media"),
                "commit_sha": version["commit_sha"],
                "repository": json.loads(version["snapshot_json"] or "{}"),
                "aeread_revision": MANIFEST["revision"],
            },
        )
        for history in histories:
            store.append_event("submitted_history_imported", history)
        store.append_event("model_response_recorded", request_record)
        store.append_event("review_validated", review)
        seal = dataclasses.asdict(store.seal())
    with EvidenceStore.audit_existing(root) as store:
        store.verify_seal()
    return str(root), json.dumps(seal, sort_keys=True)


def audit(root, expected):
    with EvidenceStore.audit_existing(root) as store:
        actual = dataclasses.asdict(store.verify_seal())
        if actual != json.loads(expected):
            raise RuntimeError("Stored root differs from independently recorded seal")
        return {"verified": True, "seal": actual, "aeread_revision": MANIFEST["revision"]}
