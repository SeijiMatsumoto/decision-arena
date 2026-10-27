import { expectedLabel, type Kind, type Report } from "./api";

export interface ModelSummary {
  name: string;
  kind: Kind;
  accuracy: number | null;
  correct: number;
  answered: number;
  errors: number;
  p50: number | null;
  p95: number | null;
  costPer1k: number | null;
  byDataset: Record<string, number | null>;
  byTag: Record<string, { hits: number; n: number }>;
}

function percentile(values: number[], q: number): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(q * sorted.length) - 1))];
}

/** Pool every dataset in a report into one row per model. */
export function summarize(report: Report): ModelSummary[] {
  return report.models.map((spec) => {
    let correct = 0;
    let answered = 0;
    let errors = 0;
    const latLive: number[] = [];
    const latAll: number[] = [];
    const costs: number[] = [];
    const byDataset: Record<string, number | null> = {};
    const byTag: Record<string, { hits: number; n: number }> = {};

    for (const [name, data] of Object.entries(report.datasets)) {
      byDataset[name] = data.metrics[spec.name]?.accuracy ?? null;
      const preds = data.predictions[spec.name] ?? {};
      for (const ex of data.examples) {
        const d = preds[ex.id];
        if (!d || d.error) {
          errors += 1;
          continue;
        }
        const hit = d.label === expectedLabel(ex);
        answered += 1;
        correct += hit ? 1 : 0;
        latAll.push(d.latency_ms);
        if (!d.cached) latLive.push(d.latency_ms);
        if (d.cost != null) costs.push(d.cost);
        for (const tag of ex.tags) {
          byTag[tag] ??= { hits: 0, n: 0 };
          byTag[tag].n += 1;
          byTag[tag].hits += hit ? 1 : 0;
        }
      }
    }
    const lat = latLive.length ? latLive : latAll;
    return {
      name: spec.name,
      kind: spec.kind,
      accuracy: answered ? correct / answered : null,
      correct,
      answered,
      errors,
      p50: percentile(lat, 0.5),
      p95: percentile(lat, 0.95),
      costPer1k: costs.length ? (1000 * costs.reduce((a, b) => a + b, 0)) / costs.length : null,
      byDataset,
      byTag,
    };
  });
}

export const fmt = {
  pct: (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`),
  ms: (v: number | null | undefined) =>
    v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v.toFixed(0)}ms`,
  usd: (v: number | null | undefined) => {
    if (v == null) return "—";
    if (v === 0) return "$0";
    if (v < 0.01) return `$${v.toPrecision(2)}`;
    return `$${v.toFixed(2)}`;
  },
  num: (v: unknown) => (typeof v === "number" ? v.toFixed(2) : "—"),
};

/** Sequential step for an accuracy cell: 0 (lightest) .. 5 (darkest). */
export function accuracyStep(v: number | null | undefined): number | null {
  if (v == null) return null;
  if (v < 0.5) return 0;
  return Math.min(5, Math.floor((v - 0.5) / 0.1) + 1);
}
