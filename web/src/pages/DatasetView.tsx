import { useMemo, useState } from "react";
import { expectedLabel, displayLabel, type Example, type Report } from "../api";
import { HeatCell, Kind, PredCell, ProbBars, StateView } from "../components/bits";
import { TakeawayCard } from "../components/Takeaways";
import { fmt } from "../summary";

type RowFilter = "all" | "misses" | "disagree";

const METRIC_COLS: Record<string, [string, string][]> = {
  noul: [["AUC", "auc"], ["Brier ↓", "brier"], ["ECE ↓", "ece"], ["Best cutoff", "best_threshold"], ["Acc @ cutoff", "best_threshold_accuracy"], ["NDCG", "ndcg"]],
  choice: [["Macro F1", "macro_f1"]],
  score: [["Within 1", "within_1"], ["MAE ↓", "mae"]],
};

export function DatasetView({ report, name }: { report: Report; name: string }) {
  const data = report.datasets[name];
  const [filter, setFilter] = useState<RowFilter>("all");
  const [tag, setTag] = useState<string | null>(null);
  const [selected, setSelected] = useState<Example | null>(null);

  const models = useMemo(
    () =>
      report.models
        .map((m) => ({ ...m, metrics: data?.metrics[m.name] }))
        .sort((a, b) => (b.metrics?.accuracy ?? -1) - (a.metrics?.accuracy ?? -1)),
    [report, data],
  );
  if (!data) return <div className="empty">Dataset “{name}” isn’t in this report.</div>;

  const q = data.question;
  const tags = [...new Set(data.examples.flatMap((e) => e.tags))].sort();
  const rows = data.examples.filter((e) => {
    if (tag && !e.tags.includes(tag)) return false;
    const labels = models.map((m) => data.predictions[m.name]?.[e.id]).filter((d) => d && !d.error).map((d) => d!.label);
    if (filter === "misses") return labels.some((l) => l !== expectedLabel(e));
    if (filter === "disagree") return new Set(labels).size > 1;
    return true;
  });
  const cols = METRIC_COLS[q.type];

  return (
    <>
      <div className="card">
        <div className="card-body" style={{ display: "grid", gap: 6 }}>
          <div className="ink-2">{data.use_case}</div>
          <div>
            <span className="tag">{q.type}</span> {q.instructions}
          </div>
          <div className="muted" style={{ fontSize: 12 }}>
            Labels:{" "}
            {Array.isArray(q.criteria)
              ? q.criteria.map((c) => c.split(":")[0]).join(" < ")
              : Object.keys(q.criteria).join(" · ")}
          </div>
        </div>
      </div>

      {report.takeaways?.datasets[name] && (
        <TakeawayCard t={report.takeaways.datasets[name]} report={report} title="Which model to use here" />
      )}

      <div className="card">
        <div className="card-head">
          <h2>Metrics</h2>
        </div>
        <div className="card-body table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Kind</th>
                <th className="num">Accuracy</th>
                {cols.map(([h]) => (
                  <th key={h} className="num">
                    {h}
                  </th>
                ))}
                <th className="num">p50</th>
                <th className="num">$ / 1k</th>
                <th className="num">Errors</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.name}>
                  <td style={{ fontWeight: 500 }}>{m.name}</td>
                  <td>
                    <Kind kind={m.kind} />
                  </td>
                  <HeatCell value={m.metrics?.accuracy} />
                  {cols.map(([h, k]) => (
                    <td key={h} className="num">
                      {k.includes("accuracy") || k === "within_1" ? fmt.pct(m.metrics?.[k] as number) : fmt.num(m.metrics?.[k])}
                    </td>
                  ))}
                  <td className="num">{fmt.ms(m.metrics?.latency_p50_ms)}</td>
                  <td className="num">{fmt.usd(m.metrics?.cost_per_1k)}</td>
                  <td className="num">{m.metrics?.errors || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {q.type === "noul" && (
            <p className="muted" style={{ fontSize: 12, margin: "10px 0 0" }}>
              Models are calibrated differently, so “Best cutoff” shows the threshold on P(true) that maximizes accuracy
              for each one. NDCG scores how well P(true) ranks candidates within the same search.
            </p>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Answers side by side</h2>
          <span className="muted" style={{ fontSize: 12 }}>
            {rows.length} of {data.examples.length} examples · click a row for details
          </span>
        </div>
        <div className="card-body" style={{ display: "grid", gap: 12 }}>
          <div className="toolbar">
            <div className="seg">
              {(
                [
                  ["all", "All"],
                  ["misses", "Any model wrong"],
                  ["disagree", "Models disagree"],
                ] as const
              ).map(([k, label]) => (
                <button key={k} className={filter === k ? "on" : ""} onClick={() => setFilter(k)}>
                  {label}
                </button>
              ))}
            </div>
            <div>
              {tags.map((t) => (
                <button key={t} className={`tag ${tag === t ? "on" : ""}`} onClick={() => setTag(tag === t ? null : t)}>
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Example</th>
                  <th>Expected</th>
                  {models.map((m) => (
                    <th key={m.name}>{m.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr
                    key={e.id}
                    className={`selectable ${selected?.id === e.id ? "selected" : ""}`}
                    onClick={() => setSelected(e)}
                  >
                    <td className="state-cell">
                      <div>
                        <b style={{ color: "var(--ink)" }}>{e.id}</b>{" "}
                        {e.tags.map((t) => (
                          <span key={t} className="tag">
                            {t}
                          </span>
                        ))}
                      </div>
                      <div className="clamp">{stateSnippet(e)}</div>
                    </td>
                    <td style={{ fontWeight: 500 }}>{displayLabel(q, expectedLabel(e))}</td>
                    {models.map((m) => (
                      <td key={m.name}>
                        <PredCell q={q} d={data.predictions[m.name]?.[e.id]} expected={expectedLabel(e)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {selected && (
        <>
          <div className="drawer-backdrop" onClick={() => setSelected(null)} />
          <aside className="drawer" aria-label={`Example ${selected.id}`}>
            <div className="toolbar">
              <h2>{selected.id}</h2>
              {selected.tags.map((t) => (
                <span key={t} className="tag">
                  {t}
                </span>
              ))}
              <span className="spacer" />
              <button className="btn" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
            <StateView state={selected.state} />
            <div>
              Expected: <b>{displayLabel(q, expectedLabel(selected))}</b>
              {selected.note && <div className="ink-2" style={{ marginTop: 4 }}>{selected.note}</div>}
            </div>
            {models.map((m) => {
              const d = data.predictions[m.name]?.[selected.id];
              return (
                <div key={m.name} style={{ display: "grid", gap: 6 }}>
                  <div className="toolbar" style={{ gap: 8 }}>
                    <b>{m.name}</b>
                    <Kind kind={m.kind} />
                    <span className="spacer" />
                    {d && !d.error && (
                      <span className="muted num" style={{ fontSize: 12 }}>
                        {fmt.ms(d.latency_ms)} · {fmt.usd(d.cost)}
                      </span>
                    )}
                  </div>
                  {d?.error ? (
                    <div className="error-text">{d.error}</div>
                  ) : d ? (
                    <ProbBars q={q} d={d} expected={expectedLabel(selected)} />
                  ) : null}
                </div>
              );
            })}
          </aside>
        </>
      )}
    </>
  );
}

function stateSnippet(e: Example): string {
  if (typeof e.state === "string") return e.state;
  return Object.entries(e.state)
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(" · ");
}
