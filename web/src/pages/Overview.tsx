import { useMemo, useState } from "react";
import type { Kind as KindT, Report } from "../api";
import { HeatCell, Kind } from "../components/bits";
import { TakeawayCard, UseCaseTable } from "../components/Takeaways";
import { KindLegend, Scatter, type Point } from "../components/Scatter";
import { fmt, summarize, type ModelSummary } from "../summary";

type KindFilter = "all" | KindT;

export function Overview({ report, onOpenDataset }: { report: Report; onOpenDataset: (d: string) => void }) {
  const [kindFilter, setKindFilter] = useState<KindFilter>("all");
  const all = useMemo(() => summarize(report), [report]);
  const rows = all
    .filter((m) => kindFilter === "all" || m.kind === kindFilter)
    .sort((a, b) => (b.accuracy ?? -1) - (a.accuracy ?? -1));
  const datasets = Object.keys(report.datasets);
  const tags = [...new Set(rows.flatMap((m) => Object.keys(m.byTag)))].sort();
  const nExamples = Object.values(report.datasets).reduce((s, d) => s + d.examples.length, 0);

  const details = (m: ModelSummary): [string, string][] => [
    ["Accuracy", fmt.pct(m.accuracy)],
    ["p50 latency", fmt.ms(m.p50)],
    ["Cost / 1k calls", fmt.usd(m.costPer1k)],
    ["Kind", m.kind === "llm" ? "LLM" : "Decision"],
  ];
  const latencyPoints: Point[] = rows
    .filter((m) => m.accuracy != null && m.p50 != null)
    .map((m) => ({ name: m.name, kind: m.kind, x: m.p50!, y: m.accuracy!, details: details(m) }));
  const costPoints: Point[] = rows
    .filter((m) => m.accuracy != null && m.costPer1k)
    .map((m) => ({ name: m.name, kind: m.kind, x: m.costPer1k!, y: m.accuracy!, details: details(m) }));

  return (
    <>
      {report.takeaways && (
        <>
          <TakeawayCard t={report.takeaways.overall} report={report} title="Takeaways across all use cases" />
          <UseCaseTable report={report} onOpen={onOpenDataset} />
        </>
      )}
      <div className="toolbar" style={{ marginTop: 8 }}>
        <div className="seg" role="group" aria-label="Model kind">
          {(["all", "decision", "llm"] as const).map((k) => (
            <button key={k} className={kindFilter === k ? "on" : ""} onClick={() => setKindFilter(k)}>
              {k === "all" ? "All models" : k === "llm" ? "LLMs" : "Decision models"}
            </button>
          ))}
        </div>
        <span className="muted">
          {rows.length} models · {datasets.length} datasets · {nExamples} examples
        </span>
      </div>

      <Tiles rows={rows} />

      <div className="charts">
        <div className="card">
          <div className="card-head">
            <h2>Quality vs. latency</h2>
            <KindLegend />
          </div>
          <div className="card-body">
            <Scatter points={latencyPoints} xLabel="p50 latency" formatX={fmt.ms} />
          </div>
        </div>
        <div className="card">
          <div className="card-head">
            <h2>Quality vs. cost</h2>
            <KindLegend />
          </div>
          <div className="card-body">
            <Scatter points={costPoints} xLabel="USD per 1k calls" formatX={fmt.usd} />
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Leaderboard</h2>
          <span className="muted" style={{ fontSize: 12 }}>
            Click a dataset to see example-level answers
          </span>
        </div>
        <div className="card-body table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Kind</th>
                <th className="num">Overall</th>
                {datasets.map((d) => (
                  <th key={d} className="clickable num" onClick={() => onOpenDataset(d)}>
                    {d.replace(/_/g, " ")} →
                  </th>
                ))}
                <th className="num">p50</th>
                <th className="num">p95</th>
                <th className="num">$ / 1k</th>
                <th className="num">Errors</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.name}>
                  <td style={{ fontWeight: 500 }}>{m.name}</td>
                  <td>
                    <Kind kind={m.kind} />
                  </td>
                  <HeatCell value={m.accuracy} title={`${m.correct}/${m.answered}`} />
                  {datasets.map((d) => (
                    <HeatCell key={d} value={m.byDataset[d]} />
                  ))}
                  <td className="num">{fmt.ms(m.p50)}</td>
                  <td className="num">{fmt.ms(m.p95)}</td>
                  <td className="num">{fmt.usd(m.costPer1k)}</td>
                  <td className="num" style={{ color: m.errors ? "var(--bad-text)" : undefined }}>
                    {m.errors || ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Accuracy by scenario</h2>
          <span className="muted" style={{ fontSize: 12 }}>
            Pooled across datasets — where each model breaks
          </span>
        </div>
        <div className="card-body table-wrap">
          <table>
            <thead>
              <tr>
                <th>Scenario</th>
                <th className="num">n</th>
                {rows.map((m) => (
                  <th key={m.name} className="num">
                    {m.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tags.map((t) => (
                <tr key={t}>
                  <td>{t}</td>
                  <td className="num muted">{Math.max(...rows.map((m) => m.byTag[t]?.n ?? 0))}</td>
                  {rows.map((m) => {
                    const c = m.byTag[t];
                    return <HeatCell key={m.name} value={c ? c.hits / c.n : null} title={c && `${c.hits}/${c.n}`} />;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function Tiles({ rows }: { rows: ModelSummary[] }) {
  const scored = rows.filter((m) => m.accuracy != null);
  if (!scored.length) return null;
  const best = scored.reduce((a, b) => (b.accuracy! > a.accuracy! ? b : a));
  const fastest = scored.filter((m) => m.p50 != null).reduce((a, b) => (b.p50! < a.p50! ? b : a), scored[0]);
  const priced = scored.filter((m) => m.costPer1k);
  const cheapest = priced.length ? priced.reduce((a, b) => (b.costPer1k! < a.costPer1k! ? b : a)) : null;
  // Best value: cheapest model within 3 points of the top score.
  const nearTop = priced.filter((m) => m.accuracy! >= best.accuracy! - 0.03);
  const value = nearTop.length ? nearTop.reduce((a, b) => (b.costPer1k! < a.costPer1k! ? b : a)) : null;

  return (
    <div className="tiles">
      <div className="card tile">
        <div className="label">Most accurate</div>
        <div className="value">{fmt.pct(best.accuracy)}</div>
        <div className="sub">{best.name}</div>
      </div>
      <div className="card tile">
        <div className="label">Fastest (p50)</div>
        <div className="value">{fmt.ms(fastest.p50)}</div>
        <div className="sub">
          {fastest.name} · {fmt.pct(fastest.accuracy)} accurate
        </div>
      </div>
      {cheapest && (
        <div className="card tile">
          <div className="label">Cheapest per 1k calls</div>
          <div className="value">{fmt.usd(cheapest.costPer1k)}</div>
          <div className="sub">
            {cheapest.name} · {fmt.pct(cheapest.accuracy)} accurate
          </div>
        </div>
      )}
      {value && (
        <div className="card tile">
          <div className="label">Best value (within 3 pts of top)</div>
          <div className="value">{value.name}</div>
          <div className="sub">
            {fmt.pct(value.accuracy)} at {fmt.usd(value.costPer1k)} / 1k
            {value.name !== best.name && best.costPer1k && value.costPer1k
              ? ` · ${Math.round(best.costPer1k / value.costPer1k)}× cheaper than top`
              : ""}
          </div>
        </div>
      )}
    </div>
  );
}
