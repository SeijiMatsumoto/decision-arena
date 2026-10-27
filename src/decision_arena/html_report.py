from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

CSS = """
:root{--bg:#fbfbfa;--fg:#1d1d1b;--muted:#6b6a66;--line:#e4e2dd;--card:#fff;
--ok:#1f7a4d;--ok-bg:#e3f3ea;--bad:#b3261e;--bad-bg:#fbe5e3;--err:#8a6d00;--err-bg:#fff4cc}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe7;--muted:#9d9b95;--line:#2d2c2a;
--card:#1e1e1c;--ok:#6fd39e;--ok-bg:#16301f;--bad:#ff8a80;--bad-bg:#3a1714;--err:#f0cf5c;--err-bg:#332a06}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.45 ui-sans-serif,system-ui,-apple-system,sans-serif;padding:24px 16px}
main{max-width:1200px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}
h2{font-size:17px;margin:36px 0 2px}.muted{color:var(--muted)}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--card);margin-top:10px}
table{border-collapse:collapse;width:100%}th,td{padding:6px 10px;border-bottom:1px solid var(--line);
text-align:left;vertical-align:top;white-space:nowrap}th{font-weight:600;font-size:12px;color:var(--muted)}
td.num{text-align:right;font-variant-numeric:tabular-nums}
td.state{white-space:normal;min-width:320px;max-width:520px;font-size:13px}
.ok{background:var(--ok-bg);color:var(--ok)}.bad{background:var(--bad-bg);color:var(--bad);font-weight:600}
.err{background:var(--err-bg);color:var(--err)}.tag{display:inline-block;font-size:11px;padding:0 6px;
border:1px solid var(--line);border-radius:10px;margin:2px 2px 0 0;color:var(--muted)}
.p{font-size:11px;opacity:.75}details{margin-top:4px}summary{cursor:pointer;color:var(--muted)}
"""


def _expected(e: dict[str, Any]) -> str:
    x = e["expected"]
    return ("true" if x else "false") if isinstance(x, bool) else str(x)


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v:.0%}"


def _state_text(state: Any) -> str:
    if isinstance(state, str):
        return state
    return "\n".join(f"{k}: {v if isinstance(v, str) else json.dumps(v)}" for k, v in state.items())


def _leaderboard(data: dict[str, Any]) -> str:
    qtype = data["question"]["type"]
    cols = {"noul": [("AUC", "auc"), ("Brier", "brier"), ("NDCG", "ndcg")],
            "choice": [("Macro F1", "macro_f1")],
            "score": [("Within 1", "within_1"), ("MAE", "mae")]}[qtype]
    head = "".join(f"<th>{h}</th>" for h in ["Model", "Accuracy", *(c for c, _ in cols),
                                              "p50 ms", "$ / 1k", "Errors"])
    rows = []
    for model, m in sorted(data["metrics"].items(), key=lambda kv: -(kv[1]["accuracy"] or 0)):
        extra = "".join(
            f"<td class=num>{'-' if m.get(k) is None else f'{m[k]:.2f}'}</td>" for _, k in cols
        )
        p50 = "-" if m["latency_p50_ms"] is None else f"{m['latency_p50_ms']:.0f}"
        cost = "-" if m["cost_per_1k"] is None else f"${m['cost_per_1k']:.4f}"
        rows.append(
            f"<tr><td>{escape(model)}</td><td class=num>{_pct(m['accuracy'])}</td>{extra}"
            f"<td class=num>{p50}</td><td class=num>{cost}</td><td class=num>{m['errors'] or ''}</td></tr>"
        )
    return f"<div class=scroll><table><tr>{head}</tr>{''.join(rows)}</table></div>"


def _grid(data: dict[str, Any]) -> str:
    models = list(data["predictions"])
    head = "".join(f"<th>{h}</th>" for h in ["Example", "Expected", *map(escape, models)])
    rows = []
    for e in data["examples"]:
        expected = _expected(e)
        cells = []
        for model in models:
            d = data["predictions"][model].get(e["id"], {})
            if "error" in d:
                cells.append(f"<td class=err title='{escape(d['error'])}'>error</td>")
                continue
            label = d.get("label")
            prob = d.get("p_true")
            if prob is None:
                prob = d.get("score") if data["question"]["type"] == "score" else d.get("confidence")
            detail = "" if prob is None else f"<div class=p>{prob:.2f}</div>"
            cls = "ok" if label == expected else "bad"
            cells.append(f"<td class={cls}>{escape(str(label))}{detail}</td>")
        tags = "".join(f"<span class=tag>{escape(t)}</span>" for t in e["tags"])
        note = f"<details><summary>why</summary>{escape(e['note'])}</details>" if e.get("note") else ""
        state = escape(_state_text(e["state"])).replace("\n", "<br>")
        rows.append(
            f"<tr><td class=state><b>{escape(e['id'])}</b> {tags}<br>{state}{note}</td>"
            f"<td>{escape(expected)}</td>{''.join(cells)}</tr>"
        )
    return f"<div class=scroll><table><tr>{head}</tr>{''.join(rows)}</table></div>"


def write_html(report: dict[str, Any], path: Path) -> Path:
    sections = []
    for name, data in report["datasets"].items():
        q = data["question"]
        sections.append(
            f"<h2>{escape(name)}</h2><div class=muted>{escape(data['use_case'])} · "
            f"{q['type']} · {escape(q['instructions'])}</div>"
            f"{_leaderboard(data)}{_grid(data)}"
        )
    models = ", ".join(escape(m["name"]) for m in report["models"])
    html = (
        "<!doctype html><html><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>Decision Arena Report</title><style>{CSS}</style></head><body><main>"
        f"<h1>Decision Arena</h1><div class=muted>{report['created_at']} · {models}</div>"
        f"{''.join(sections)}</main></body></html>"
    )
    path.write_text(html)
    return path
