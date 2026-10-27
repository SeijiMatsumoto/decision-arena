import { useEffect, useState } from "react";
import { api, displayLabel, type AskResult, type Dataset, type ModelSpec, type Question, type QuestionType } from "../api";
import { Kind, ProbBars } from "../components/bits";
import { ModelPicker } from "../components/ModelPicker";
import { fmt } from "../summary";

type Row = { key: string; text: string };

const DEFAULT_ROWS: Record<QuestionType, Row[]> = {
  noul: [
    { key: "true", text: "" },
    { key: "false", text: "" },
  ],
  choice: [
    { key: "option_a", text: "" },
    { key: "option_b", text: "" },
  ],
  score: [
    { key: "0", text: "Low" },
    { key: "1", text: "Medium" },
    { key: "2", text: "High" },
  ],
};

function toRows(q: Question): Row[] {
  return Array.isArray(q.criteria)
    ? q.criteria.map((text, i) => ({ key: String(i), text }))
    : Object.entries(q.criteria).map(([key, text]) => ({ key, text }));
}

function stateToText(state: unknown): string {
  return typeof state === "string" ? state : JSON.stringify(state, null, 2);
}

export function Playground() {
  const [models, setModels] = useState<ModelSpec[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [template, setTemplate] = useState("");
  const [type, setType] = useState<QuestionType>("noul");
  const [instructions, setInstructions] = useState("");
  const [rows, setRows] = useState<Row[]>(DEFAULT_ROWS.noul);
  const [stateText, setStateText] = useState("");
  const [results, setResults] = useState<AskResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.models().then((ms) => {
      setModels(ms);
      setPicked(new Set(ms.filter((m) => m.enabled).map((m) => m.name)));
    });
    api.datasets().then((ds) => {
      setDatasets(ds);
      if (ds.length) loadTemplate(ds[0], 0);
    });
  }, []);

  function loadTemplate(d: Dataset, exampleIndex: number) {
    setTemplate(d.name);
    setType(d.question.type);
    setInstructions(d.question.instructions);
    setRows(toRows(d.question));
    setStateText(stateToText(d.examples[exampleIndex]?.state ?? ""));
    setResults(null);
  }

  const question: Question = {
    type,
    instructions,
    criteria:
      type === "score"
        ? rows.map((r) => r.text)
        : Object.fromEntries(rows.map((r) => [r.key.trim(), r.text])),
  };

  const ask = async () => {
    setBusy(true);
    setError(null);
    let state: Record<string, unknown> | string = stateText;
    if (stateText.trim().startsWith("{")) {
      try {
        state = JSON.parse(stateText);
      } catch {
        /* treat as plain text */
      }
    }
    try {
      const out = await api.ask({ models: [...picked], question, state });
      setResults(out.sort((a, b) => (a.error ? 1 : 0) - (b.error ? 1 : 0) || a.latency_ms - b.latency_ms));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const tmpl = datasets.find((d) => d.name === template);
  const labels = results?.filter((r) => !r.error).map((r) => r.label) ?? [];
  const agreeCount = labels.length ? Math.max(...labels.map((l) => labels.filter((x) => x === l).length)) : 0;

  return (
    <>
      <div className="page-title">
        <h1>Playground</h1>
        <span className="muted">Ask one question to many models at once and compare answers, latency and cost.</span>
      </div>
      <div className="split">
        <div className="card">
          <div className="card-head">
            <h2>Models</h2>
            <span className="muted">{picked.size} selected</span>
          </div>
          <div className="card-body">
            <ModelPicker models={models} selected={picked} onChange={setPicked} />
          </div>
        </div>

        <div className="stack" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-body" style={{ display: "grid", gap: 14 }}>
              <div className="toolbar">
                <label className="field" style={{ flex: 1, minWidth: 200 }}>
                  <label>Start from a dataset</label>
                  <select
                    value={template}
                    onChange={(e) => {
                      const d = datasets.find((x) => x.name === e.target.value);
                      if (d) loadTemplate(d, 0);
                    }}
                  >
                    {datasets.map((d) => (
                      <option key={d.name} value={d.name}>
                        {d.name} — {d.use_case}
                      </option>
                    ))}
                  </select>
                </label>
                {tmpl && (
                  <label className="field" style={{ minWidth: 160 }}>
                    <label>Example</label>
                    <select onChange={(e) => setStateText(stateToText(tmpl.examples[Number(e.target.value)].state))}>
                      {tmpl.examples.map((ex, i) => (
                        <option key={ex.id} value={i}>
                          {ex.id} {ex.tags.length ? `(${ex.tags.join(", ")})` : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>

              <div className="field">
                <label>Question type</label>
                <div className="seg" style={{ justifySelf: "start" }}>
                  {(["noul", "choice", "score"] as const).map((t) => (
                    <button
                      key={t}
                      className={type === t ? "on" : ""}
                      onClick={() => {
                        setType(t);
                        setRows(DEFAULT_ROWS[t]);
                      }}
                    >
                      {t === "noul" ? "Yes / no (noul)" : t === "choice" ? "Pick one (choice)" : "Scale (score)"}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field">
                <label>Instructions</label>
                <textarea rows={2} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
              </div>

              <div className="field">
                <label>{type === "score" ? "Levels (lowest first)" : type === "noul" ? "Criteria" : "Options"}</label>
                {rows.map((r, i) => (
                  <div key={i} className="crit-row">
                    <input
                      type="text"
                      value={type === "score" ? `level ${i}` : r.key}
                      disabled={type !== "choice"}
                      onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, key: e.target.value } : x)))}
                    />
                    <input
                      type="text"
                      value={r.text}
                      placeholder="What this means"
                      onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
                    />
                    {type !== "noul" && rows.length > 2 ? (
                      <button className="icon-btn" aria-label="Remove" onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                        ×
                      </button>
                    ) : (
                      <span />
                    )}
                  </div>
                ))}
                {type !== "noul" && (
                  <button
                    className="btn"
                    style={{ justifySelf: "start" }}
                    onClick={() => setRows([...rows, { key: type === "score" ? String(rows.length) : `option_${rows.length + 1}`, text: "" }])}
                  >
                    + Add {type === "score" ? "level" : "option"}
                  </button>
                )}
              </div>

              <div className="field">
                <label>Input (plain text, or a JSON object)</label>
                <textarea
                  rows={6}
                  value={stateText}
                  onChange={(e) => setStateText(e.target.value)}
                  style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 13 }}
                />
              </div>

              <div className="toolbar">
                {error && <span className="error-text">{error}</span>}
                <span className="spacer" />
                <button className="btn primary" disabled={busy || !picked.size || !stateText.trim()} onClick={ask}>
                  {busy ? "Asking…" : `Ask ${picked.size} model${picked.size === 1 ? "" : "s"}`}
                </button>
              </div>
            </div>
          </div>

          {results && (
            <>
              <div className="toolbar">
                <h2>Answers</h2>
                <span className="muted">
                  {agreeCount} of {labels.length} agree · sorted fastest first
                </span>
              </div>
              <div className="answers" style={{ opacity: busy ? 0.5 : 1 }}>
                {results.map((r) => (
                  <div key={r.model} className="card answer">
                    <div className="toolbar" style={{ gap: 8 }}>
                      <b>{r.model}</b>
                      <span className="spacer" />
                      <Kind kind={r.kind} />
                    </div>
                    {r.error ? (
                      <div className="error-text">{r.error}</div>
                    ) : (
                      <>
                        <div className="big">{displayLabel(question, r.label)}</div>
                        <div className="stats">
                          <span>{fmt.ms(r.latency_ms)}{r.cached ? " (cached)" : ""}</span>
                          <span>{fmt.usd(r.cost)}</span>
                          {r.input_tokens != null && <span>{r.input_tokens} tok in</span>}
                        </div>
                        <ProbBars q={question} d={r} />
                      </>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
