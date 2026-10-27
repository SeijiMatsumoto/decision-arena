import type { Decision, Example, Question } from "../api";
import { displayLabel, questionLabels } from "../api";
import { accuracyStep, fmt } from "../summary";

export function HeatCell({ value, title }: { value: number | null | undefined; title?: string }) {
  const step = accuracyStep(value);
  if (step == null) return <td className="heat empty">—</td>;
  return (
    <td
      className="heat"
      title={title}
      style={{ background: `var(--seq-${step})`, color: `var(--seq-ink-${step})` }}
    >
      {fmt.pct(value)}
    </td>
  );
}

export function Kind({ kind }: { kind: string }) {
  return <span className={`kind ${kind}`}>{kind === "llm" ? "LLM" : "Decision"}</span>;
}

export function StateView({ state }: { state: Example["state"] }) {
  if (typeof state === "string") return <div className="state-box">{state}</div>;
  return (
    <div className="state-box">
      {Object.entries(state).map(([k, v]) => (
        <div key={k} style={{ marginBottom: 8 }}>
          <span className="k">{k}</span>
          {typeof v === "string" ? v : JSON.stringify(v)}
        </div>
      ))}
    </div>
  );
}

/** Probability per label for one decision; falls back to the single label when no distribution. */
export function ProbBars({ q, d, expected }: { q: Question; d: Decision; expected?: string }) {
  let probs = d.probabilities;
  if (!probs && d.label != null) probs = { [d.label]: d.confidence ?? 1 };
  if (!probs) return null;
  const labels = questionLabels(q).filter((l) => l in probs!);
  const rows = labels.map((l) => ({ l, p: probs![l] })).sort((a, b) => b.p - a.p);
  return (
    <div className="pbars">
      {rows.map(({ l, p }) => (
        <div
          key={l}
          className={`pbar ${l === d.label ? "top" : ""} ${l === expected ? "expected" : ""}`}
        >
          <span className="name" title={displayLabel(q, l)}>
            {displayLabel(q, l)}
          </span>
          <div className="track">
            <div className="fill" style={{ width: `${Math.max(1, p * 100)}%` }} />
          </div>
          <span className="num">{fmt.pct(p)}</span>
        </div>
      ))}
    </div>
  );
}

export function PredCell({ q, d, expected }: { q: Question; d?: Decision; expected: string }) {
  if (!d) return <span className="cell err">—</span>;
  if (d.error) {
    return (
      <span className="cell err" title={d.error}>
        ⚠ error
      </span>
    );
  }
  const ok = d.label === expected;
  const p = q.type === "noul" ? d.p_true : q.type === "score" ? d.score : d.confidence;
  return (
    <span className={`cell ${ok ? "ok" : "bad"}`}>
      {ok ? "✓" : "✗"} {displayLabel(q, d.label)}
      {p != null && <span className="p">{p.toFixed(2)}</span>}
    </span>
  );
}
