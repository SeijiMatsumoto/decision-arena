export type QuestionType = "noul" | "choice" | "score";
export type Kind = "decision" | "llm";

export interface Question {
  type: QuestionType;
  instructions: string;
  criteria: Record<string, string> | string[];
}

export interface Example {
  id: string;
  state: Record<string, unknown> | string;
  expected: boolean | string | number;
  tags: string[];
  group?: string | null;
  note?: string | null;
}

export interface Dataset {
  name: string;
  description: string;
  use_case: string;
  question: Question;
  examples: Example[];
}

export interface ModelSpec {
  name: string;
  provider: "decisions" | "llm" | "mock";
  model: string;
  kind: Kind;
  enabled: boolean;
}

export interface Decision {
  label?: string;
  p_true?: number;
  score?: number;
  confidence?: number;
  probabilities?: Record<string, number>;
  latency_ms: number;
  cost?: number;
  input_tokens?: number;
  output_tokens?: number;
  cached?: boolean;
  error?: string;
}

export interface Metrics {
  n: number;
  errors: number;
  accuracy: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  cost_total: number | null;
  cost_per_1k: number | null;
  by_tag: Record<string, number>;
  [key: string]: unknown;
}

export interface ReportDataset {
  description: string;
  use_case: string;
  question: Question;
  examples: Example[];
  predictions: Record<string, Record<string, Decision>>;
  metrics: Record<string, Metrics>;
  agreement: Record<string, number>;
}

export interface Pick {
  role: "recommended" | "most_accurate" | "fastest" | "cheapest";
  model: string;
  accuracy: number;
  p50_ms: number | null;
  cost_per_1k: number | null;
  why: string;
}

export interface Takeaway {
  scope: string;
  use_case: string | null;
  n: number;
  top_tier: string[];
  picks: Pick[];
  avoid: { model: string; accuracy: number; why: string }[];
  notes: string[];
}

export interface Report {
  id: string;
  created_at: string;
  models: ModelSpec[];
  datasets: Record<string, ReportDataset>;
  takeaways: { overall: Takeaway; datasets: Record<string, Takeaway> };
}

export interface ReportSummary {
  id: string;
  created_at: string;
  models: string[];
  datasets: string[];
  snapshot: boolean;
}

export interface RunStatus {
  id: string;
  status: "running" | "done" | "failed";
  done: number;
  total: number;
  report_id?: string;
  error?: string;
}

export interface AskResult extends Decision {
  model: string;
  kind: Kind;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  models: () => call<ModelSpec[]>("/api/models"),
  datasets: () => call<Dataset[]>("/api/datasets"),
  reports: () => call<ReportSummary[]>("/api/reports"),
  report: (id: string) => call<Report>(`/api/reports/${id}`),
  startRun: (body: { models: string[]; datasets?: string[]; limit?: number }) =>
    call<RunStatus>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  run: (id: string) => call<RunStatus>(`/api/runs/${id}`),
  ask: (body: { models: string[]; question: Question; state: Example["state"] }) =>
    call<AskResult[]>("/api/ask", { method: "POST", body: JSON.stringify(body) }),
};

export function expectedLabel(e: Example): string {
  if (typeof e.expected === "boolean") return e.expected ? "true" : "false";
  return String(e.expected);
}

export function questionLabels(q: Question): string[] {
  return Array.isArray(q.criteria) ? q.criteria.map((_, i) => String(i)) : Object.keys(q.criteria);
}

/** Human label for a prediction; score levels get their short name. */
export function displayLabel(q: Question, label: string | undefined): string {
  if (label === undefined) return "—";
  if (Array.isArray(q.criteria)) {
    const text = q.criteria[Number(label)] ?? label;
    return text.split(":")[0];
  }
  return label;
}
