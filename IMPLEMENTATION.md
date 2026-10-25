# Winner Signal — implementation handoff

Status: original implementation specification. A working local MVP now exists; see `STATUS.md` for verified implementation, live integration evidence, and remaining extensions. This roadmap includes future work and is not itself proof of completion.
Prepared: 2026-10-25. Workspace: `/Users/chenyusu/winner-signal`.

## 1. Objective and decisions

Build a measurement layer connecting AI-assisted work to real-world outcomes, with the long-term goal of producing validated feedback for AI evaluation and training. The gallery is the initial recruitment and distribution surface: builders get viewers and feedback, while versioned demos, code and optional session exports can be associated with observed outcomes.

Core research question: **Which observable outcomes of AI-assisted work provide reliable feedback for improving the agents that produced it?** Benchmark pass rates remain useful measures of task correctness; the missing evidence is whether actual outputs function, get used and create value.

Keep signal types distinct: (1) build context and actions, (2) artifact and implementation evidence, (3) audience response, (4) reproduced functionality and downstream use, and eventually (5) measured economic outcomes. Current engagement metrics are proxies, not validated training rewards. Source inspection is not execution verification, and popularity is not utility. The prototype does not yet establish training gains or causal attribution to a particular model or action.

Current intake supersedes the original upload requirement below: hosted demo link plus public repository; optional build-history exports. Video upload controls were removed. YouTube reports require owner authorization; a link alone never implies analytics access. Gemini review of public YouTube links up to two minutes is implemented with uploader verification. Private/unlisted links are excluded; a full run on our own linked project still needs verification.

Next validation work: link outcomes to versions and observed periods; preserve exposure/source information; obtain separate research/training consent; collect independent functionality and repeat-use evidence; evaluate candidate signals on held-out projects before using them for training. Keep builders, projects and related versions together when splitting data to avoid leakage. No automatic training use is authorized by a demo submission or review consent.

The user approved these product directions:
- Public gallery with simple demo cards and individual demo pages.
- Video plus public source repository as core inputs.
- Optional exported coding-agent conversation/build history.
- Timestamped claims linked to code and, where available, execution evidence.
- Private builder dashboard with engagement, feedback, and evidence review.
- Real video analytics access is a core requirement: a pasted video link alone is insufficient. The current UI uses owner-authorized YouTube analytics and manual report import; existing uploaded assets retain instrumented playback. The earlier direct-upload intake is superseded.
- Separate audience popularity from implementation evidence and judging quality.
- Reuse AERead infrastructure selectively.

The organizer's form, pasted by the user, requires a public GitHub repository and a 1-minute demo video. An announcement says submissions close at 5:00 PM on October 25, 2026, Pacific time. Treat that as historical event context if executing later; do not infer current eligibility or deadlines. Winner Signal is an independent tool, not the organizer's submission portal or official judge.

Execute the MVP locally through working UI and verification. Do not stop at scaffolding. Do not submit the hackathon entry, contact participants, or publish externally solely on the authority of this document. Prepare a concrete deployment artifact if deployment has not been separately authorized. Do not launch paid model calls without an available authorized key and explicit configured cost limit. If credentials are missing, finish and label the fixture-backed flow and state exactly what remains unverified.

## 2. Scope and priorities

### P0 — usable gallery and ownership
1. Builder signs in, creates a draft, supplies title, short description, video and repository.
2. Public repository reference resolves to an immutable commit SHA.
3. Builder explicitly publishes a public projection of the draft.
4. Visitors browse rotating cards, watch demos, open repositories/live demos, and react.
5. Owner returns to a private dashboard with real observed engagement and feedback.
6. Direct video upload -> instrumented player -> persisted playback metrics -> owner dashboard must work end to end. Link-only listing is a limited fallback, not completion of the analytics requirement.

### P1 — differentiated evidence review
1. Extract claims and observed actions from a video using Gemini.
2. Inspect a bounded snapshot of the pinned public repository as text.
3. Link each claim to video timestamps and exact file/line evidence.
4. Produce evidence states, limitations, and three prioritized improvements.
5. Persist analysis artifacts using AERead EvidenceStore; verify the seal.

### P2 — optional build history and revisions
1. Upload selected JSON, JSONL, Markdown, or text conversation exports.
2. Preview and redact before sending their contents to the model.
3. Link relevant history events to claims without treating imported logs as observed execution.
4. Create a new immutable video/repository version and compare reviews and engagement.

Do not build winner probabilities, global quality leaderboards, arbitrary repository execution, automatic local-history harvesting, account integrations for coding agents, a full AERead benchmark family, or a generic observability platform in this MVP.

## 3. Suggested implementation stack

These are implementation choices, not pre-existing workspace capabilities:
- Next.js/TypeScript web frontend; choose current stable dependencies and lock them.
- Small Python FastAPI analysis service to import AERead directly.
- PostgreSQL for production metadata and analytics; SQLite is acceptable for a clearly labeled local demo. Keep migrations explicit.
- Private file/object storage for original videos, histories, and evidence bundles.
- Durable jobs table and one Python worker initially; no in-process fire-and-forget analysis.
- Use established authentication, with server-side owner checks. Local development may have an explicit dev-only identity; production must fail closed if real auth is not configured.

Suggested directories:
```
apps/web/
services/analysis/
packages/contracts/
fixtures/                 # synthetic or explicitly authorized demo material
session-history/          # local handoff context; never public or sent automatically
```

Prefer a single coherent stack over multiple abstractions. Keep the public gallery usable while analysis is queued or fails. Provide `.env.example` without real secrets, setup instructions, migrations, seed fixtures, and a one-command local startup script.

## 4. Screens and behavior

### `/` — gallery
- Cards: thumbnail, title, one-line description, builder display name, Watch action.
- Default rotating discovery order, stable per browsing session; Newest filter.
- Do not sort by popularity by default or display an AI-generated overall winner score.
- Real empty state; seeded fixtures must be visibly labeled examples.
- Owner preview, bots, and reloads should not inflate meaningful interest metrics.

### `/d/[slug]` — public demo
- Video player, description, GitHub link pinned to the displayed version, optional live-demo link.
- “I'd use this,” question, and feedback actions.
- Version indicator; show which version comments refer to.
- Report/hide path for abusive comments; basic rate limiting.
- No private history, raw model output, secrets, or private evidence on this route.
- Prefer an instrumented hosted player. Link-only videos may open externally if embedding is unavailable, but show “Link clicks only — playback analytics unavailable” and offer upload or connection setup. Never label these videos analytics-connected.

### `/submit` and `/dashboard/[projectId]`
- Draft/published state, edit and preview controls.
- Private review with timestamped evidence cards and source links.
- Audience panel separate from evidence panel.
- Analytics setup offers “Upload video — recommended,” “Use supported embed,” and “Connect host analytics / import export.” Show actual capabilities and connection status before claiming tracking is enabled.
- Dashboard separates “Views on Winner Signal” from “Original-host analytics,” with source, window, last sync and unavailable metrics.
- Optional history upload with disclosure, preview, redaction, remove control, and export instructions.
- Explicit Publish button and preview of the public fields.
- New version action creates a new immutable version; never silently rewrites a reviewed version.

Minimal visual direction: simple, readable video cards and evidence references. Prioritize watching and understanding a demo over decorative charts. Use accessible controls, mobile layouts, loading, empty, error, and unavailable states.

## 5. Data contracts

Use server-generated IDs and UTC timestamps. Every review and engagement event refers to a submission version.

- `Project`: id, owner_id, slug, title, description, visibility, created_at.
- `SubmissionVersion`: id, project_id, version_number, video_source_url, video_asset_id, video_sha256 (nullable until bytes acquired), repository_url, commit_sha, live_demo_url, created_at.
- `PrivateArtifact`: id, owner_id, version_id, kind, storage_key, sha256, media_type, byte_size, provenance, redaction_status, created_at.
- `AnalysisRun`: id, version_id, status, attempt_number, model_id, prompt_version, rubric_version, adapter_revision, aeread_revision, input_manifest_sha256, cost_limit, observed_usage, evidence_root, seal, failure_code, timestamps.
- `Claim`: id, run_id, text, video_start_ms, video_end_ms, observation_or_assertion, evidence_state, explanation, limitations.
- `EvidenceLink`: id, claim_id, source_kind, artifact_id, locator, relation, provenance.
- `Recommendation`: id, run_id, priority, claim_ids, action, rationale, proposed_verification.
- `EngagementEvent`: id, event_id, version_id, anonymous_session_id, type, occurred_at, player_capability, eligible_for_metrics.
- `Feedback`: id, version_id, visitor_or_user_id, kind, text, moderation_status, created_at.
- `VideoAnalyticsBinding`: id, version_id, mode (hosted/embed/host_api/host_export/link_only), provider, provider_video_id, capabilities, status, verified_at. A version may have multiple bindings.
- `AnalyticsConnection`: id, owner_id, provider, provider_account_id, encrypted_token_reference, granted_scopes, status, last_success_at, last_error. Tokens never enter browser payloads, evidence bundles or logs.
- `HostAnalyticsSnapshot`: id, binding_id, provider_report_id, source_kind (api/export), period_start, period_end, provider_timezone, fetched_at, metric_definitions_version, metrics, provenance_artifact_id. Store source-defined aggregates separately from first-party events.

`source_kind`: video, repository, submitted_build_history, submitted_runtime_trace, observed_execution.
`relation`: supports, contradicts, contextualizes, insufficient.
`provenance`: participant_supplied, repository_snapshot, winner_signal_observed.

Evidence states:
- `shown`: visible in the recorded demo; does not establish repeatability.
- `code_supported`: relevant implementation found; does not establish it ran.
- `execution_verified`: an authorized instrumented run observed the stated outcome. Disabled in MVP unless implemented and tested.
- `unresolved`: evidence is missing, inaccessible, ambiguous, or conflicting.

Keep all supporting sources, even if the UI chooses one summary badge. Absence of evidence is not evidence of failure. A model's confidence is not a calibrated probability. Explicitly distinguish an observed UI action from a narrator's claim.

Repository locator: commit SHA, relative file path, start/end line and source hash. Validate line references against stored bytes. Video locator: offsets in the exact analyzed asset. History locator: artifact hash, event/line range, original timestamp if available. Preserve source timestamps separately from ingestion timestamps.

## 6. Analysis pipeline

1. Validate owner, input size/type, source URLs, and input version.
2. Resolve public repository to a SHA and fetch a bounded snapshot without running hooks or project code. Reject path traversal, symlink escapes, excessive archives, and oversized binary content.
3. Acquire an analyzable video file. Do not assume any YouTube/Loom/share URL is downloadable. When supported access fails, retain the gallery link and request a direct upload for analysis.
4. Hash source bytes and build a manifest. Capture repository SHA, video identity, optional history identity, and all analysis versions.
5. Gemini video pass: return schema-validated claims, visible actions, timestamps, and observations. Do not ask for hidden reasoning.
6. Repository pass: bounded search/read tools retrieve relevant code. Treat repository text and session contents as untrusted data, never as instructions to execute commands or disclose data.
7. Optional history pass: parse only supplied files, normalize selected events, apply redaction, and preserve omissions/partial-export status.
8. Review pass: link claims to evidence, identify contradictions and unknowns, and produce at most three high-value improvements.
9. Validate citations mechanically. Reject fabricated file paths/lines, out-of-range timestamps, and execution_verified claims without actual observed-execution records.
10. Seal and audit evidence; persist successful review. Failed analysis remains a typed failure, not a zero quality score.

Use job states queued/running/succeeded/failed/cancelled. Persist phase progress. Each retry creates a new attempt and preserves prior failures; never overwrite a sealed attempt. Set input, output, time, cost, concurrency and retry limits in configuration. Surface truncation and partial repository coverage in the review.

Record request configuration and returned structured output, usage when available, and failure status. Replaying stored findings is different from rerunning a nondeterministic model. Do not claim deterministic judgment replay.

## 7. AERead reuse boundary

Prior inspection examined `/Users/chenyusu/AERead` at HEAD `02740a20`; focused execution/receipt/tool tests passed 71 tests. This is a historical inspection, not a guarantee of the executing agent's checkout. Recheck revision and API signatures before integration. The live checkout has unrelated changes; do not edit it.

Relevant modules:
- `aeread.shared_runner.task.execution.EvidenceStore`: byte artifacts, hash-chained events, seal, audit.
- `aeread.shared_runner.task.tools.ToolRuntime`: declared tools and invocation records; mutating tools require a state reader.
- `aeread.shared_runner.measurement`: separates deterministic, stochastic and judge-dependent measurement types.
- `aeread.shared_runner.task.receipts.EvaluationReceipt`: defer full use until legitimate plan/case/scoring/replay contracts exist.

Use a pinned dependency or isolated source snapshot with required license/notice files. Do not rely on a developer-specific absolute PYTHONPATH in the shipped app. Record the exact dependency commit and test against it. Do not copy the entire research repository or its evidence datasets into Winner Signal.

Wrap EvidenceStore behind `EvidenceBackend`; avoid coupling UI contracts to AERead's benchmark schema. Give each analysis run stable run/cell/episode/attempt identifiers, with documented application meanings. These IDs do not turn a review into a benchmark result.

Store original artifacts plus normalized findings. Suggested application events: source_ingested, video_claims_extracted, repository_evidence_linked, history_imported, review_validated, review_completed. Use a distinct namespace for imported histories; do not fabricate native tool/provider events for actions Winner Signal did not observe. One writer per evidence store. Use a new store for each attempt/version; call seal and then audit_existing/verify_seal before marking the evidence bundle complete.

Gemini video handling belongs in an application adapter initially: the inspected CanonicalMessage API has text content. Do not force video through a string field or modify AERead's kernel merely to ship this demo.

The existing sanitized trajectory exporter omits prompts, messages, raw responses, and environment state; it is not a session-history viewer. Build an explicit private/public projection for this app. A visibility label alone is not access control.

Integrity limits: hashes detect changes relative to recorded roots, not authenticity of uploaded logs or proof that code ran in a video. Secure the stored seal/root separately from writable uploads. AERead tool contracts are not an arbitrary-code security sandbox. Do not execute submitted repositories in MVP.

## 8. Analytics access and measurement — required, not link-only

### 8.1 Access paths and priority

**Required MVP route: upload the same demo file and play it inside Winner Signal.** This avoids requiring access to the builder's video-host account and gives us first-party playback events from viewers we attract. Obtain explicit permission to host/play the uploaded copy. Keep upload private until Publish; serving the public video must not expose other private artifacts. Preserve the original submission URL as a separate field.

| Route | What we can measure | Implementation requirement |
| --- | --- | --- |
| Hosted upload — P0 | Playback on Winner Signal: starts, playback coverage, completion and engagement | HTML video or chosen hosted player's documented event API, server-side ingestion, persistence and dashboard |
| Supported embed — P1 | Events exposed by the embedded player on Winner Signal only | Provider adapter with a tested capability matrix; never assume an iframe exposes playback |
| Owner-authorized host API — P2 | Historical/off-site metrics actually exposed for the connected video | Official API, least-privilege authorization, video/account ownership verification, server-side tokens, refresh/revoke and sync |
| Owner-provided host analytics export — P1 fallback | Snapshot of supplied off-site metrics | CSV/JSON parser for verified formats, video ID/window mapping, source provenance and manual-import label |
| Link only — fallback | Our page visitors and outbound clicks | Explicitly unavailable playback metrics; prompt upload/connect/import |

An embed does not grant access to the host account's historical analytics. A public view count is not owner analytics access. A video link or upload does not authorize account access. Obtain the owner's provider authorization for API access; never ask them to paste cookies/passwords. Before implementing any named provider connector, verify its current official API documentation, scopes, account/plan eligibility, supported metrics, latency, quotas and application-review requirements. Do not promise YouTube, Loom or another provider's analytics until the integration is verified. If APIs are unavailable, implement the hosted path and clearly labeled supported exports; do not scrape private dashboards as an implicit substitute.

### 8.2 Onboarding and connection verification

1. Builder supplies original video URL and repository, then chooses an analytics route. Recommend upload of the same one-minute file.
2. Hosted route validates and processes the file, binds its hash to the version, and shows a playable preview. Embed route validates the provider and video ID against an explicit supported-provider registry.
3. Run a diagnostic playback in the owner preview. Confirm events reach the backend and appear in a private diagnostics panel; mark these events test-only and exclude them from audience metrics.
4. A working player is not enough: mark first-party tracking `verified` only after the supported start/progress events are persisted and read back. Distinguish configured, verified, limited, disconnected and failed.
5. External API route verifies authorized account/video access and reads a report. No data yet is distinct from an authorization error. Display a last-success timestamp and exact metric coverage. Bind exports to a video/version and report window; never silently accept mismatched IDs.
6. Give builders the Winner Signal page as their shareable link. Explain that first-party metrics cover viewers on that page, not all viewers of the original host URL.
7. Let builders disconnect integrations and remove imported reports; stop future syncs and revoke/delete stored credentials as supported. State the retention behavior for already collected aggregates.

### 8.3 First-party metric definitions

Track only events the application can actually observe. Use minimal anonymous identifiers; do not store raw IP addresses in analytics. Rate-limit at the edge/service separately.

- Demo-page visitors: distinct eligible anonymous sessions per version in the selected period; label as an estimate, not unique people.
- Video starts: distinct eligible sessions with an actual player start event; distinguish autoplay from user-initiated starts.
- Playback coverage: union of observed advancing media-time intervals, clamped to video duration. Do not credit the skipped range after a seek or double-count replayed intervals. Bound intervals using elapsed time and playback rate. This is observed playback, not proof of attention.
- Completion: eligible started sessions with at least 90% observed playback coverage / eligible started sessions, only for adapters that support adequate progress telemetry. An ended event or seeking to 90% alone does not establish completion.
- Milestones: 25/50/75/90% coverage, emitted once per playback session; use a stable playback_session_id and idempotent event IDs. Distinguish playback sessions from anonymous visitor sessions.
- Watch duration: if supported, observed wall-clock playback duration; label separately from media coverage and exclude paused intervals. Handle visibility/page lifecycle explicitly and disclose what is measured.
- GitHub/live-demo clicks: distinct eligible sessions clicking each outbound destination.
- “I'd use this”: deduplicated reactions; expressed interest, not validated demand.
- Feedback/questions: visible moderated responses, tied to the version.

Minimum event payload adds playback_session_id, binding_id, source, media_position_ms, duration_ms, playback_rate, client_sequence, server_received_at and diagnostic flag where relevant. Validate these fields server-side. Handle pause, seeking/seeked, ended, time updates and pagehide/best-effort final flush; persist batches during playback so leaving the page does not lose the entire session. SDK-specific equivalents are allowed, with documented capability limits.

Video external-link clicks are not starts. Unsupported completion metrics show “Unavailable,” not zero. Owner previews and development fixtures are excluded. Reject duplicate event IDs, unknown versions, malformed types and implausible values. Debounce client events and enforce server-side checks; browser telemetry remains approximate and manipulable. Blocked scripts/consent and lost events can cause undercounting; do not promise exhaustive tracking.

### 8.4 Original-host analytics and comparisons

Show imported/API metrics in a distinct panel with provider, video ID, reporting period, timezone, fetched/imported time and original metric definitions. Do not relabel a provider's views as our unique visitors or compute host completion from unrelated denominators. Manual exports are participant-supplied reports, not independently authenticated API results. Keep missing, stale, unsupported, zero and disconnected states distinct.

Do not sum host views and Winner Signal starts: embedded views may already be counted by the host, and cross-source deduplication is generally unavailable. Compare versions only within matching sources and definitions. Show counts, denominators, time windows, and a small-sample label (initial product heuristic: fewer than 20 starts). Do not claim causal improvement: audience, exposure and timing can differ.

**Analytics release gate:** a fresh non-owner browser session watches a hosted demo; the backend persists start/progress/completion; the owner sees the resulting metrics after reload. Seeking to the end does not count as completion. This must work without a host API key or fabricated analytics. Host connectors are additional capabilities, not a substitute for this gate.

## 9. Optional history and privacy

Only voluntary uploads; no browser-side filesystem scanning. Never upload the current project's own `session-history/` folder as sample data or send it to a model without explicit authorization.

Supported first adapters: generic Markdown/text and structured JSON/JSONL with clear role/content/timestamp fields. Add tool-specific formats only after inspecting genuine authorized examples. Treat unknown JSON as an attachment with a partial/unsupported parsing notice; do not invent events.

Before model processing, show selected contents, detected redactions and file limits. Credentials/private data scanning is best effort, not a guarantee. Preserve originals only in restricted storage according to a documented retention policy; do not place sensitive raw exports in public source control. Hash redacted copies separately and record transformation provenance. Missing history must not reduce project quality scores.

Export prompt for participants:

> I want to export the coding-agent conversation used to build this project for an optional Winner Signal review. Identify which coding agent you are running in and locate saved history for THIS conversation and project. Inspect documented export options and relevant local session metadata first; do not guess paths or invent messages. Do not search unrelated projects, modify originals, or upload anything. If accessible, export this session into a new local `winner-signal-export` folder as JSONL/JSON, or Markdown/text. Preserve available timestamps, message roles, tool calls/results, edits and test outcomes; do not reconstruct missing content or include hidden reasoning. Redact credentials, tokens, passwords and unrelated personal information in the exported copy, replacing values with [REDACTED]. Include a README with agent/version if available, session ID/date range, project commit, completeness, omissions and redaction categories. Show file paths, sizes and limitations so I can review before uploading. If you cannot access history, explain the limitation and provide manual export steps you can verify.

Public fields are an allowlist. Enforce ownership on every private artifact, review, job and analytics endpoint. Use short-lived signed URLs for private assets, sanitize Markdown, validate links, and protect server-side fetches against private-network destinations and redirect-based SSRF. Prevent uploaded/repository text from overriding analysis instructions. Include file deletion/retention behavior in the UI and README.

## 10. API sketch

- `POST /api/projects` — create owned draft.
- `POST /api/projects/:id/versions` — create immutable input version.
- `POST /api/versions/:id/artifacts` — private bounded upload.
- `POST /api/projects/:id/publish` — explicit public projection.
- `GET /api/gallery` / `GET /api/demos/:slug` — public fields only.
- `POST /api/versions/:id/analyze` — idempotent owned job creation.
- `GET /api/analysis/:id` — owner-only status/results.
- `POST /api/events` — validated, deduplicated engagement event.
- `POST /api/versions/:id/feedback` — rate-limited reaction/question.
- `GET /api/projects/:id/analytics` — owner-only aggregates split by source and version.
- `POST /api/versions/:id/analytics/verify` — run/read back diagnostic tracking status; exclude diagnostic events from audience counts.
- `POST /api/analytics/connections/:provider/start` and provider callback — owner-authorized integration setup, only for implemented providers.
- `DELETE /api/analytics/connections/:id` — disconnect and stop sync.
- `POST /api/versions/:id/analytics/import` — owner-supplied report with explicit video/window mapping.
- `POST /api/analytics/connections/:id/sync` — bounded, deduplicated report sync; private job status.

Endpoints are a proposed contract, not existing APIs. Resolve browser authentication at the web server and authenticate service-to-service requests; never trust owner_id supplied by a browser. Run workers outside request lifetime.

## 11. Build sequence and checkpoints

### A. Foundation and first working slice
Scaffold app/services, schema/migrations, private storage, development identity and clearly labeled fixtures. Deliver submit draft -> publish -> gallery -> detail -> dashboard. Check mobile layout and owner access boundaries. This slice must work independently of model availability.

### B. Real engagement
Implement the required direct-upload/instrumented-player route and capability-aware analytics setup. Wire page visits, playback intervals, outbound clicks, reactions and feedback. Pass the Section 8 analytics release gate before calling this milestone complete. Verify seeking, pause/resume, reload persistence, deduplication, unavailable metrics, owner exclusion and per-version attribution. Then add supported embed adapters and report import; host OAuth/API connectors follow when official access is verified. Do not populate the dashboard with invented live numbers or treat a video URL as analytics access.

### C. Evidence integration
Import pinned AERead evidence layer; create a wrapper and a smoke flow that stores an artifact, appends an event, seals, reopens and audits. Confirm tampering is detected. Avoid full EvaluationReceipt unless its contract is actually met.

### D. Video and repository review
Implement Gemini extraction, pinned repository retrieval, source citations, validation and private evidence cards. Show at least one fixture where a spoken claim has a mock implementation and is flagged without asserting a real execution failure. Add one authorized real video/repository integration run if credentials and budget permit; otherwise label it unverified.

### E. History and versions
Implement optional exports, preview/redaction, event links, immutable new versions and comparisons. Keep missing history neutral. Verify private data never appears in public API responses.

### F. Demo and handoff
Record a short product demonstration using authorized/fixture inputs: discover a project -> view engagement -> inspect a timestamped claim -> open code evidence -> see a concrete improvement. Provide run instructions, environment requirements, verification results and remaining limitations. Preparing a demo is not submitting it to the organizer.

If time is tight, complete A–D first. Defer structured tool-specific history parsers and advanced comparisons, but retain the optional upload design. Do not sacrifice correct public/private boundaries or evidence labels for cosmetic features.

## 12. Acceptance checks

Required meaningful checks, not tests that mirror implementation:
- A visitor can discover and watch a published demo; unpublished drafts are inaccessible publicly.
- A second user cannot read or mutate another builder's histories, analysis, or analytics.
- Public API snapshots contain only approved fields and no private artifact URLs.
- New versions preserve prior video/commit/review/analytics associations.
- Inaccessible video or repo yields a clear partial/unavailable state, not fabricated findings.
- A cited file, line range and timestamp resolve to the exact analyzed inputs.
- Mocked booking implementation is code-supported at most; no execution_verified label is produced.
- Omitted session history does not count as negative evidence.
- Direct upload -> non-owner playback -> persisted start/progress/completion -> owner dashboard works without host API credentials.
- Seeking to the end does not count as completion; pause, resume and repeat playback do not inflate coverage.
- Diagnostic owner previews verify ingestion but are excluded from audience metrics.
- Duplicate analytics events do not inflate counts; unsupported players do not create completion data.
- Link-only projects show limited access and an actionable upload/connect/import path.
- Imported host reports preserve source/window/video identity; host counts and first-party counts are never blindly summed.
- If a host connector ships: verify authorized video access, token isolation, refresh/revocation, sync idempotency, stale data and denied-access behavior.
- Repository/history prompt injection cannot trigger command execution or secret access.
- Evidence seal verifies after restart and detects altered event/artifact bytes.
- Worker restart preserves a terminal or resumable job state; retry creates a distinct attempt.
- Model/provider errors remain visible and do not become quality scores.
- One end-to-end browser walkthrough plus focused unit/integration tests pass.

## 13. Executing-agent completion report

Report what is actually implemented, how to run it, local URL, tests run, fixture versus real-model status, costs if incurred, and outstanding blockers. Identify any departures from this specification. Do not claim launch, deployment, privacy review, authentic participant data, real viewers, or submission unless separately verified.

Read `session-history/README.md` for the provenance and limitations of the accompanying conversation export. Conversation statements are product context; this document is the scoped execution plan. The user's later instructions override it.
