import type { Pick, Report, Takeaway } from "../api";
import { fmt } from "../summary";
import { Kind } from "./bits";

const ROLE: Record<Pick["role"], string> = {
  recommended: "Use",
  most_accurate: "Most accurate",
  fastest: "Fastest",
  cheapest: "Cheapest",
};

function PickLine({ pick, kind }: { pick: Pick; kind?: string }) {
  return (
    <div className={`pick ${pick.role}`}>
      <span className="role">{ROLE[pick.role]}</span>
      <div>
        <div className="pick-head">
          <b>{pick.model}</b>
          {kind && <Kind kind={kind} />}
          <span className="muted num">
            {fmt.pct(pick.accuracy)} · {fmt.ms(pick.p50_ms)} · {fmt.usd(pick.cost_per_1k)}/1k
          </span>
        </div>
        <div className="ink-2">{pick.why}</div>
      </div>
    </div>
  );
}

/** One recommendation block: picks, models to avoid, and notes. */
export function TakeawayCard({ t, report, title }: { t: Takeaway; report: Report; title: string }) {
  const kinds = Object.fromEntries(report.models.map((m) => [m.name, m.kind]));
  return (
    <div className="card takeaway">
      <div className="card-head">
        <h2>{title}</h2>
        <span className="muted" style={{ fontSize: 12 }}>
          Rule-based from this run · {t.n} examples
        </span>
      </div>
      <div className="card-body" style={{ display: "grid", gap: 12 }}>
        {t.picks.map((p) => (
          <PickLine key={p.role} pick={p} kind={kinds[p.model]} />
        ))}
        {t.avoid.map((a) => (
          <div key={a.model} className="pick avoid">
            <span className="role">Avoid</span>
            <div>
              <div className="pick-head">
                <b>{a.model}</b>
                <span className="muted num">{fmt.pct(a.accuracy)}</span>
              </div>
              <div className="ink-2">{a.why}</div>
            </div>
          </div>
        ))}
        {t.notes.length > 0 && (
          <ul className="notes">
            {t.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/** "Best model for what": one row per dataset / use case. */
export function UseCaseTable({ report, onOpen }: { report: Report; onOpen: (d: string) => void }) {
  const kinds = Object.fromEntries(report.models.map((m) => [m.name, m.kind]));
  return (
    <div className="card">
      <div className="card-head">
        <h2>Best model for each use case</h2>
        <span className="muted" style={{ fontSize: 12 }}>
          Cheapest and fastest among models within 2 points of the top
        </span>
      </div>
      <div className="card-body table-wrap">
        <table>
          <thead>
            <tr>
              <th>Use case</th>
              <th>Use</th>
              <th className="num">Accuracy</th>
              <th className="num">p50</th>
              <th className="num">$ / 1k</th>
              <th>Cheaper / faster alternatives</th>
              <th>Avoid</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(report.takeaways.datasets).map(([name, t]) => {
              const rec = t.picks.find((p) => p.role === "recommended");
              const alts = t.picks.filter((p) => p.role === "fastest" || p.role === "cheapest");
              return (
                <tr key={name} className="selectable" onClick={() => onOpen(name)}>
                  <td style={{ whiteSpace: "normal", minWidth: 220 }}>
                    <div style={{ fontWeight: 500 }}>{name.replace(/_/g, " ")}</div>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {t.use_case}
                    </div>
                  </td>
                  <td>
                    {rec && (
                      <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                        <b>{rec.model}</b>
                        <Kind kind={kinds[rec.model]} />
                      </span>
                    )}
                  </td>
                  <td className="num">{fmt.pct(rec?.accuracy)}</td>
                  <td className="num">{fmt.ms(rec?.p50_ms)}</td>
                  <td className="num">{fmt.usd(rec?.cost_per_1k)}</td>
                  <td className="ink-2" style={{ fontSize: 13 }}>
                    {alts.map((a) => `${a.model} (${ROLE[a.role].toLowerCase()})`).join(", ") || "—"}
                  </td>
                  <td style={{ fontSize: 13, color: t.avoid.length ? "var(--bad-text)" : undefined }}>
                    {t.avoid.map((a) => a.model).join(", ") || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
