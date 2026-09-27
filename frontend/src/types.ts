/** Types miroir de backend/schemas.py — S2 stable, S3 UI. */

export interface RuffIssue {
  code: string;
  message: string;
  filename: string;
  row?: number | null;
  col?: number | null;
}

export interface BanditIssue {
  test_id: string;
  severity: string;
  confidence: string;
  text: string;
  filename: string;
  line_number?: number | null;
}

export interface ReviewResponse {
  run_id: string;
  files: string[];
  ruff: RuffIssue[];
  bandit: BanditIssue[];
  tests_pass: boolean;
  coverage_pct: number | null;
  tests_output: string;
  findings: string[];
  patch_proposal: string;
  trajectoire: string[];
  latency_ms: number;
  model: string;
  prompt_version: string;
  status: string;
}

export interface TestsResponse {
  run_id: string;
  files: string[];
  tests_pass: boolean;
  coverage_pct: number | null;
  tests_output: string;
  trajectoire: string[];
  latency_ms: number;
  model: string;
  prompt_version: string;
  status: string;
}

export interface RunRecord {
  id: string;
  endpoint: string;
  status: string;
  latency_ms: number;
  created_at: string;
  request_summary: Record<string, unknown>;
  result_summary: Record<string, unknown>;
}
