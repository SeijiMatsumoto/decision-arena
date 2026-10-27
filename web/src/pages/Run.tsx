import { useEffect, useState } from "react";
import { api, type Dataset, type ModelSpec, type RunStatus } from "../api";
import { ModelPicker } from "../components/ModelPicker";
import { navigate } from "../router";

export function Run() {
  const [models, setModels] = useState<ModelSpec[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [pickedModels, setPickedModels] = useState<Set<string>>(new Set());
  const [pickedData, setPickedData] = useState<Set<string>>(new Set());
  const [limit, setLimit] = useState<string>("");
  const [run, setRun] = useState<RunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.models().then((ms) => {
      setModels(ms);
      setPickedModels(new Set(ms.filter((m) => m.enabled).map((m) => m.name)));
    });
    api.datasets().then((ds) => {
      setDatasets(ds);
      setPickedData(new Set(ds.map((d) => d.name)));
    });
  }, []);

  useEffect(() => {
    if (run?.status !== "running") return;
    const timer = setInterval(async () => {
      const next = await api.run(run.id);
      setRun(next);
      if (next.status === "done" && next.report_id) navigate(`/results/${next.report_id}`);
    }, 600);
    return () => clearInterval(timer);
  }, [run]);

  const perModel = datasets
    .filter((d) => pickedData.has(d.name))
    .reduce((s, d) => s + Math.min(d.examples.length, Number(limit) || Infinity), 0);
  const calls = perModel * pickedModels.size;

  const start = async () => {
    setError(null);
    try {
      setRun(
        await api.startRun({
          models: [...pickedModels],
          datasets: [...pickedData],
          limit: Number(limit) || undefined,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const running = run?.status === "running";
  return (
    <>
      <div className="page-title">
        <h1>New run</h1>
        <span className="muted">Every selected model answers every selected example. Cached answers are free.</span>
      </div>
      <div className="split">
        <div className="card">
          <div className="card-head">
            <h2>Models</h2>
            <span className="muted">{pickedModels.size} selected</span>
          </div>
          <div className="card-body">
            <ModelPicker models={models} selected={pickedModels} onChange={setPickedModels} />
          </div>
        </div>
        <div className="stack" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-head">
              <h2>Datasets</h2>
              <span className="muted">{pickedData.size} selected</span>
            </div>
            <div className="card-body checklist">
              {datasets.map((d) => (
                <label key={d.name} className="check">
                  <input
                    type="checkbox"
                    checked={pickedData.has(d.name)}
                    onChange={() => {
                      const next = new Set(pickedData);
                      if (next.has(d.name)) next.delete(d.name);
                      else next.add(d.name);
                      setPickedData(next);
                    }}
                  />
                  <span style={{ fontWeight: 500 }}>{d.name}</span>
                  <span className="tag">{d.question.type}</span>
                  <span className="muted" style={{ fontSize: 12 }}>
                    {d.use_case}
                  </span>
                  <span className="meta">{d.examples.length}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="card">
            <div className="card-body" style={{ display: "grid", gap: 14 }}>
              <div className="toolbar">
                <label className="field" style={{ gridAutoFlow: "column", alignItems: "center" }}>
                  <span className="muted">Examples per dataset</span>
                  <input
                    type="number"
                    min={1}
                    placeholder="all"
                    value={limit}
                    onChange={(e) => setLimit(e.target.value)}
                    style={{ width: 90 }}
                  />
                </label>
                <span className="spacer" />
                <span className="muted">{calls.toLocaleString()} calls</span>
                <button
                  className="btn primary"
                  disabled={running || !pickedModels.size || !pickedData.size}
                  onClick={start}
                >
                  {running ? "Running…" : "Start run"}
                </button>
              </div>
              {error && <div className="error-text">{error}</div>}
              {run && (
                <div style={{ display: "grid", gap: 6 }}>
                  <div className="progress">
                    <div style={{ width: `${run.total ? (100 * run.done) / run.total : 0}%` }} />
                  </div>
                  <div className="muted num" style={{ textAlign: "left", fontSize: 12 }}>
                    {run.status === "failed"
                      ? `Failed: ${run.error}`
                      : `${run.done} / ${run.total} answers${run.status === "done" ? " — done" : ""}`}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
