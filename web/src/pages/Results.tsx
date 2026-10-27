import { useEffect, useState } from "react";
import { api, type Report, type ReportSummary } from "../api";
import { navigate } from "../router";
import { DatasetView } from "./DatasetView";
import { Overview } from "./Overview";

export function Results({ reportId, dataset }: { reportId?: string; dataset?: string }) {
  const [reports, setReports] = useState<ReportSummary[] | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.reports().then(setReports).catch((e) => setError(e.message));
  }, [reportId]);

  const activeId = reportId ?? reports?.[0]?.id;
  useEffect(() => {
    if (!activeId) return;
    api.report(activeId).then(setReport).catch((e) => setError(e.message));
  }, [activeId]);

  if (error) return <div className="card empty">Couldn’t load reports: {error}</div>;
  if (reports && !reports.length) {
    return (
      <div className="card empty">
        No runs yet. <a href="#/run">Start one</a>, or run <code>uv run arena run</code>.
      </div>
    );
  }

  return (
    <>
      <div className="toolbar">
        <div className="page-title">
          <h1>
            {dataset ? (
              <>
                <a href={`#/results/${activeId}`} style={{ color: "var(--muted)", fontWeight: 500 }}>
                  Results
                </a>{" "}
                / {dataset.replace(/_/g, " ")}
              </>
            ) : (
              "Results"
            )}
          </h1>
        </div>
        <span className="spacer" />
        {dataset && report && (
          <select value={dataset} onChange={(e) => navigate(`/results/${activeId}/${e.target.value}`)}>
            {Object.keys(report.datasets).map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        )}
        <select
          value={activeId ?? ""}
          onChange={(e) => navigate(`/results/${e.target.value}${dataset ? `/${dataset}` : ""}`)}
          aria-label="Report"
        >
          {reports?.map((r) => (
            <option key={r.id} value={r.id}>
              {new Date(r.created_at).toLocaleString()} · {r.models.length} models{r.snapshot ? " · snapshot" : ""}
            </option>
          ))}
        </select>
      </div>
      <div className="stack" style={{ opacity: report?.id === activeId ? 1 : 0.5 }}>
        {report &&
          (dataset ? (
            <DatasetView report={report} name={dataset} />
          ) : (
            <Overview report={report} onOpenDataset={(d) => navigate(`/results/${report.id}/${d}`)} />
          ))}
      </div>
    </>
  );
}
