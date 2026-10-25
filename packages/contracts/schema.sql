-- Winner Signal — SQLite schema for local demo
-- See IMPLEMENTATION.md §5 for data contracts

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  owner_id TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  visibility TEXT NOT NULL DEFAULT 'draft' CHECK (visibility IN ('draft', 'published')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS submission_versions (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  project_id TEXT NOT NULL REFERENCES projects(id),
  version_number INTEGER NOT NULL DEFAULT 1,
  video_source_url TEXT,
  video_asset_id TEXT,
  video_sha256 TEXT,
  repository_url TEXT,
  commit_sha TEXT,
  live_demo_url TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE(project_id, version_number)
);

CREATE TABLE IF NOT EXISTS private_artifacts (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  owner_id TEXT NOT NULL,
  version_id TEXT NOT NULL REFERENCES submission_versions(id),
  kind TEXT NOT NULL,
  storage_key TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  media_type TEXT,
  byte_size INTEGER,
  provenance TEXT NOT NULL DEFAULT 'participant_supplied',
  redaction_status TEXT DEFAULT 'none',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS analysis_runs (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  version_id TEXT NOT NULL REFERENCES submission_versions(id),
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  attempt_number INTEGER NOT NULL DEFAULT 1,
  model_id TEXT,
  prompt_version TEXT,
  rubric_version TEXT,
  input_manifest_sha256 TEXT,
  cost_limit REAL,
  observed_usage REAL,
  evidence_root TEXT,
  seal TEXT,
  failure_code TEXT,
  started_at TEXT,
  completed_at TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  run_id TEXT NOT NULL REFERENCES analysis_runs(id),
  text TEXT NOT NULL,
  video_start_ms INTEGER,
  video_end_ms INTEGER,
  observation_or_assertion TEXT NOT NULL DEFAULT 'assertion' CHECK (observation_or_assertion IN ('observation', 'assertion')),
  evidence_state TEXT NOT NULL DEFAULT 'unresolved' CHECK (evidence_state IN ('shown', 'code_supported', 'execution_verified', 'unresolved')),
  explanation TEXT,
  limitations TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS evidence_links (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  claim_id TEXT NOT NULL REFERENCES claims(id),
  source_kind TEXT NOT NULL,
  artifact_id TEXT,
  locator TEXT NOT NULL,
  relation TEXT NOT NULL DEFAULT 'supports' CHECK (relation IN ('supports', 'contradicts', 'contextualizes', 'insufficient')),
  provenance TEXT NOT NULL DEFAULT 'repository_snapshot'
);

CREATE TABLE IF NOT EXISTS recommendations (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  run_id TEXT NOT NULL REFERENCES analysis_runs(id),
  priority INTEGER NOT NULL,
  claim_ids TEXT, -- JSON array of claim IDs
  action TEXT NOT NULL,
  rationale TEXT NOT NULL,
  proposed_verification TEXT
);

CREATE TABLE IF NOT EXISTS engagement_events (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  event_id TEXT UNIQUE NOT NULL, -- client-supplied idempotency key
  version_id TEXT NOT NULL REFERENCES submission_versions(id),
  anonymous_session_id TEXT NOT NULL,
  type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  player_capability TEXT,
  eligible_for_metrics INTEGER NOT NULL DEFAULT 1,
  playback_session_id TEXT,
  binding_id TEXT,
  source TEXT,
  media_position_ms INTEGER,
  duration_ms INTEGER,
  playback_rate REAL,
  client_sequence INTEGER,
  server_received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  is_diagnostic INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  version_id TEXT NOT NULL REFERENCES submission_versions(id),
  visitor_or_user_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('use_this', 'question', 'feedback')),
  text TEXT,
  moderation_status TEXT NOT NULL DEFAULT 'visible' CHECK (moderation_status IN ('visible', 'hidden', 'reported')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS video_analytics_bindings (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  version_id TEXT NOT NULL REFERENCES submission_versions(id),
  mode TEXT NOT NULL DEFAULT 'hosted' CHECK (mode IN ('hosted', 'embed', 'host_api', 'host_export', 'link_only')),
  provider TEXT,
  provider_video_id TEXT,
  capabilities TEXT, -- JSON
  status TEXT NOT NULL DEFAULT 'configured' CHECK (status IN ('configured', 'verified', 'limited', 'disconnected', 'failed')),
  verified_at TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_projects_visibility ON projects(visibility);
CREATE INDEX IF NOT EXISTS idx_versions_project ON submission_versions(project_id);
CREATE INDEX IF NOT EXISTS idx_events_version ON engagement_events(version_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON engagement_events(anonymous_session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_version ON feedback(version_id);
CREATE INDEX IF NOT EXISTS idx_claims_run ON claims(run_id);
CREATE INDEX IF NOT EXISTS idx_analysis_version ON analysis_runs(version_id);
