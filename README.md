# Winner Signal

A measurement prototype connecting AI-assisted builds to their outputs and audience response. Our goal is to develop validated real-world feedback for AI evaluation and training beyond benchmark pass rates. Builders get a demo gallery, feedback and a private analytics dashboard; training usefulness remains a research question.

## Run

Requirements: Node.js 20.9+, npm, Python 3.12, `uv`, and FFmpeg (`ffprobe`).

```sh
cp .env.example .env # only when you do not already have .env
./start.sh
```

Open **http://localhost:3000**. Create a local builder account (username and a password of at least 10 characters). The API and worker run on the same machine; the API binds to loopback. Browser requests use the Next.js same-origin proxy.

The gallery, file upload, publishing, feedback and playback analytics work without a model API key. In the workspace, **Try a controlled example** creates a private example video, an intentionally mocked booking function, and an explicitly authored fixture review. Its review is not attributed to Gemini, and fixture traffic is excluded from audience totals.

Create a real submission with a public GitHub repository. The app resolves an immutable commit and snapshots at most 16 small source files (160 KB total). This is bounded source coverage, not a full audit. Add a hosted demo URL, then explicitly publish. No video upload is required or offered in the current UI. Video-to-code review supports existing uploaded assets and public YouTube demos up to two minutes, after connecting the uploader account. Private and unlisted links cannot be reviewed. New versions do not replace the public version until published.

## Model integration and quota

The backend uses the **Google Gemini API** (`google-genai`), not the Antigravity CLI or subscription. A working Antigravity account is not required. API access/billing/quota must independently permit the configured model. A metadata lookup alone is not proof generation will succeed.

Set `GEMINI_API_KEY`, `GEMINI_MODEL`, `ENABLE_LIVE_ANALYSIS=1`, current input/output prices, and `MAX_ANALYSIS_USD` in `.env`. No keys are sent to the browser. The worker uploads the selected video, counts input tokens, checks a conservative token-based cost ceiling, makes one bounded generation request, and deletes the provider's uploaded file best-effort afterward. The ceiling relies on configured model rates; it is not a provider-enforced account spending cap. No automatic generation retries or silent model substitution. Review consent explicitly includes video, public source snapshot and optional selected histories.

Current model integration follows [Google's video input documentation](https://ai.google.dev/api/generate-content) and [Argon model configuration](https://ai.google.dev/gemini-api/docs/latest-model). Recheck rates when changing models or after pricing changes.

Queued jobs survive service restart. A single locked worker owns processing. An interrupted running call becomes `worker_interrupted` rather than being silently retried or charged twice. Failed jobs remain visible; starting another review creates a distinct attempt. Run the worker separately with `.venv/bin/python -m analysis.worker` if not using `start.sh`.

## Analytics access

- **Uploaded videos:** instrumented HTML video player, persisted starts/progress, union of watched media intervals, completion at 90% coverage, outbound clicks and deduplicated interest.
- **Linked videos:** page visitors/outbound code or app clicks. YouTube watch metrics require an authorized uploader connection; a URL alone gives no analytics access.
- **Original-host reports:** private normalized JSON import, with exact original URL and period, labeled participant-supplied. See the dashboard for the schema. Reports never get added to first-party counts.
- **YouTube API:** owner-authorized, channel-checked video reports, fetched on dashboard access with a six-hour cache. The OAuth app remains in Testing; real participant report retrieval remains to be validated. Embed-player adapters and Loom OAuth are not implemented.

Metrics represent approximate browser sessions, not uniquely identified people or attentive watching. Client events can be blocked or manipulated. Seeking does not credit skipped intervals; repeated intervals do not inflate coverage. Owner previews are diagnostic. Diagnostics are marked verified only when a start and progress from the same playback session are read back. Different versions have independent metrics; the selector allows comparison without merging cohorts. Public discovery order is stable per browser session, with an optional Newest sort.

## Evidence and optional histories

The pinned Apache-2.0 AERead shared runner lives in `vendor/aeread/`. `PROVENANCE.json` records the exact revision and hashes; original source files are unmodified. The wrapper verifies dependency hashes, stores source/review artifacts, seals them and audits the seal against the separately persisted root. No research datasets are bundled.

Findings distinguish shown, code-supported and unresolved. This app does not run submitted code and cannot produce execution-verified claims. Source paths and line ranges are validated against the snapshot; timestamps must fit the uploaded video. Invalid citations are discarded with an explicit limitation. Sealing protects integrity after ingestion, not authenticity of supplied histories.

Optional UTF-8 JSON/JSONL/Markdown/text exports are stored as redacted text, with preview and removal. This build provides generic text ingestion, not provider-specific reconstruction of sessions. Original unredacted uploads are not retained. Secret scanning is best effort. Removing an upload prevents future inclusion; earlier authorized sealed reviews retain their snapshot. **Do not include sensitive history until you have reviewed the preview and selected the consent checkbox.**

`session-history/` contains this project's local planning conversation. It is git-ignored and is never automatically imported, published or sent to Gemini.

## Verification

```sh
.venv/bin/python -m pytest services/analysis/tests -q
cd apps/web
npm run lint
npm test
npm run build
```

Backend tests use temporary databases, local media and stubbed repository responses, not paid model calls. Frontend tests exercise continuous playback, seek-to-end, overlapping intervals and pause behavior. `STATUS.md` records actual live/browser verification and limitations.

## Storage and deployment

SQLite migrations add columns without dropping existing records. Runtime data and authentication sessions are in `data/`, excluded from Git. Videos and private artifacts are not served from a public static directory. Only the explicitly published version or its owner can retrieve its video. Passwords use salted scrypt and opaque session cookies; owner IDs cannot be supplied through a browser header.

Deployment configuration is now provided for a Vercel frontend and a single Fly.io backend with a persistent private volume, HTTPS cookies, an exact origin check, scheduled volume snapshots, and supervised API/worker processes. See [DEPLOYMENT.md](DEPLOYMENT.md) for topology, deploy commands and operating limits. Broader production work includes retention/deletion policy, account recovery, moderation operations and a tested backup-restore procedure. The local registration flow has no email verification or password recovery. Browser telemetry is not fraud-resistant. No external publication or hackathon submission is performed by the startup script.

See `IMPLEMENTATION.md` for the broader roadmap and `SUBMISSION.md` for the submission draft. Optional provider connectors and operational hardening remain separate from the implemented local flow.
