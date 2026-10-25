// Shared browser/API response contracts for the implemented local MVP.
export type Version = {
  id: string;
  project_id: string;
  version_number: number;
  video_source_url: string | null;
  video_asset_id: string | null;
  duration_ms: number | null;
  repository_url: string;
  commit_sha: string;
  live_demo_url: string | null;
  is_fixture: number;
};
export type Project = {
  id: string;
  slug: string;
  title: string;
  description: string;
  visibility: string;
  published_version_id: string | null;
};
export type Binding = {
  id: string;
  status: string;
  verified_at: string | null;
};
export type Feedback = {
  id: string;
  kind: string;
  text: string;
  created_at: string;
};
export type Card = {
  slug: string;
  title: string;
  description: string;
  builder_display_name: string;
  version: Version;
};
export type Demo = Card & {
  binding: Binding | null;
  feedback: Feedback[];
  is_owner: boolean;
};
export type Metrics = {
  page_visitors: number;
  video_starts: number;
  completions: number;
  completion_rate: number | null;
  github_clicks: number;
  livedemo_clicks: number;
  use_this_count: number;
  small_sample: boolean;
};
export type Analytics = {
  version_id: string;
  period: string;
  metrics: Metrics | null;
  binding: Binding | null;
  feedback: Feedback[];
  reports: {
    id: string;
    provider: string;
    video_id: string;
    period_start: string;
    period_end: string;
    metrics_json: string;
    created_at: string;
  }[];
  latest_run: {
    id: string;
    status: string;
    failure_code: string | null;
    mode: string;
  } | null;
};
export type Review = {
  run: {
    id: string;
    status: string;
    model_id: string;
    failure_code: string | null;
    mode: string;
  };
  result: null | {
    summary: string;
    trace_status?: string;
    trace_findings?: {
      artifact_id: string; quote: string; actor: string; action: string;
      outcome: string; outcome_status: string; assessment: string;
      start_char: number; end_char: number; artifact_sha256: string;
      evidence: {file_path: string; start_line: number; end_line: number; url: string; relation: string; explanation: string}[];
    }[];
    limitations: string[];
    claims: {
      text: string;
      video_start_ms: number;
      video_end_ms: number;
      evidence_state: string;
      explanation: string;
      evidence: {
        file_path: string;
        start_line: number;
        end_line: number;
        url: string;
        relation: string;
        explanation: string;
      }[];
    }[];
    improvements: {
      action: string;
      rationale: string;
      proposed_verification: string;
    }[];
  };
};
