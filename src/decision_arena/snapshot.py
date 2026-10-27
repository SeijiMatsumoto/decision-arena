"""Dated, committed snapshots of eval runs.

Each snapshot is a folder `snapshots/<YYYY-MM-DD_HHMM>/` holding the full report (`report.json`)
and a rendered summary (`README.md`, which GitHub shows when browsing the folder).
`snapshots/README.md` indexes every snapshot, and the project README points at the latest one.
"""

from __future__ import annotations

import json
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from .recommend import recommend

START = "<!-- snapshot:start -->"
END = "<!-- snapshot:end -->"
LABELS = {
    "recommended": "Use",
    "most_accurate": "Most accurate",
    "fastest": "Fastest",
    "cheapest": "Cheapest",
}


def _expected(example: dict[str, Any]) -> str:
    x = example["expected"]
    return ("true" if x else "false") if isinstance(x, bool) else str(x)


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.1%}"


def _ms(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v / 1000:.1f}s" if v >= 1000 else f"{v:.0f}ms"


def _usd(v: float | None) -> str:
    return "—" if v is None else f"${v:.4f}"


def snapshot_name(report: dict[str, Any]) -> str:
    return datetime.fromisoformat(report["created_at"]).strftime("%Y-%m-%d_%H%M")


def pooled(report: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per model across every dataset in the report, best accuracy first."""
    rows = []
    for spec in report["models"]:
        correct = answered = errors = 0
        latencies: list[float] = []
        costs: list[float] = []
        for data in report["datasets"].values():
            preds = data["predictions"][spec["name"]]
            for example in data["examples"]:
                d = preds.get(example["id"])
                if not d or "error" in d:
                    errors += 1
                    continue
                answered += 1
                correct += d.get("label") == _expected(example)
                latencies.append(d["latency_ms"])
                if d.get("cost") is not None:
                    costs.append(d["cost"])
        rows.append(
            {
                "name": spec["name"],
                "model": spec["model"],
                "kind": spec.get("kind") or ("llm" if spec["provider"] == "llm" else "decision"),
                "accuracy": correct / answered if answered else None,
                "correct": correct,
                "n": answered + errors,
                "p50": statistics.median(latencies) if latencies else None,
                "p95": statistics.quantiles(latencies, n=20)[-1] if len(latencies) > 1 else None,
                "cost_per_1k": 1000 * sum(costs) / len(costs) if costs else None,
                "errors": errors,
            }
        )
    return sorted(rows, key=lambda r: (-(r["accuracy"] or 0), r["p50"] or 0))


def headline(report: dict[str, Any]) -> str:
    """One deterministic sentence: the overall pick plus the decision-vs-LLM comparison."""
    overall = recommend(report)["overall"]
    rec = overall["picks"][0] if overall["picks"] else None
    if not rec:
        return "No successful answers in this run."
    text = (
        f"Use **{rec['model']}** ({rec['accuracy']:.0%} accurate, {_ms(rec['p50_ms'])} median, "
        f"{_usd(rec['cost_per_1k'])} per 1k calls)."
    )
    versus = next((n for n in overall["notes"] if n.startswith("Best decision model")), None)
    return f"{text} {versus}" if versus else text


def render(report: dict[str, Any], project_readme: str = "../../README.md") -> str:
    date = datetime.fromisoformat(report["created_at"]).strftime("%Y-%m-%d %H:%M UTC")
    takeaways = recommend(report)
    rows = pooled(report)
    datasets = list(report["datasets"])
    n_examples = sum(len(d["examples"]) for d in report["datasets"].values())
    lines = [
        f"# Results snapshot: {date}",
        "",
        (
            f"{len(rows)} models × {n_examples} examples across {len(datasets)} datasets, all called "
            "through OpenRouter. Latency is the client-side round trip from one machine, so it includes "
            "network time; cost is what OpenRouter reported per call at the time. The datasets are small "
            f"and synthetic (see [Caveats]({project_readme}#caveats)), so treat accuracy gaps of a few "
            "points as noise. They were written before the first run and not changed after seeing "
            "results; the question format (noul / choice / score) originated with Jev, and LLMs get a "
            "plain, untuned prompt. Raw data: [`report.json`](report.json)."
        ),
        "",
        "## Overall",
        "",
        "| Model | Kind | Accuracy | Median latency | p95 latency | $ per 1k calls |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        kind = "Decision" if r["kind"] == "decision" else "LLM"
        lines.append(
            f"| `{r['model']}` | {kind} | {_pct(r['accuracy'])} ({r['correct']}/{r['n']}) "
            f"| {_ms(r['p50'])} | {_ms(r['p95'])} | {_usd(r['cost_per_1k'])} |"
        )

    lines += ["", "## Accuracy by dataset", ""]
    lines.append("| Model | " + " | ".join(d.replace("_", " ") for d in datasets) + " |")
    lines.append("|---|" + "---:|" * len(datasets))
    for r in rows:
        cells = [
            _pct(report["datasets"][d]["metrics"][r["name"]]["accuracy"]).replace(".0%", "%")
            for d in datasets
        ]
        lines.append(f"| {r['name']} | " + " | ".join(cells) + " |")

    overall = takeaways["overall"]
    rules = f"{project_readme}#takeaways-which-model-to-use-for-what"
    lines += ["", f"## Takeaways ([how these are derived]({rules}))", ""]
    for pick in overall["picks"]:
        lines.append(f"- **{LABELS[pick['role']]}: {pick['model']}.** {pick['why']}")
    for item in overall["avoid"]:
        lines.append(f"- **Avoid: {item['model']}.** {item['why']}")
    for note in overall["notes"]:
        lines.append(f"- {note}")

    lines += [
        "",
        "| Use case | Use | Cheaper / faster alternative | Avoid |",
        "|---|---|---|---|",
    ]
    for name, t in takeaways["datasets"].items():
        rec = next((p for p in t["picks"] if p["role"] == "recommended"), None)
        alts = [
            f"{p['model']} ({LABELS[p['role']].lower()})"
            for p in t["picks"]
            if p["role"] in ("fastest", "cheapest")
        ]
        avoid = ", ".join(a["model"] for a in t["avoid"]) or "—"
        lines.append(
            f"| {name.replace('_', ' ')} | {rec['model'] if rec else '—'} "
            f"| {', '.join(alts) or '—'} | {avoid} |"
        )
    return "\n".join(lines) + "\n"


def save_snapshot(report: dict[str, Any], snapshots_dir: Path) -> Path:
    """Write snapshots/<name>/{report.json,README.md}; rerunning on the same report overwrites it."""
    folder = snapshots_dir / snapshot_name(report)
    folder.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in report.items() if k not in ("id", "takeaways")}
    (folder / "report.json").write_text(json.dumps(clean, separators=(",", ":")))
    (folder / "README.md").write_text(render(report))
    return folder


def load_snapshots(snapshots_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """(name, report) for every snapshot, newest first."""
    return [
        (path.parent.name, json.loads(path.read_text()))
        for path in sorted(snapshots_dir.glob("*/report.json"), reverse=True)
    ]


def write_index(snapshots_dir: Path) -> None:
    lines = [
        "# Snapshots",
        "",
        "Dated eval runs, newest first. Each folder has a readable summary and the full `report.json`.",
        "Create one from your latest run with `uv run arena snapshot`.",
        "",
        "| Date | Models | Examples | Headline |",
        "|---|---:|---:|---|",
    ]
    for name, report in load_snapshots(snapshots_dir):
        n = sum(len(d["examples"]) for d in report["datasets"].values())
        lines.append(f"| [{name}]({name}/) | {len(report['models'])} | {n} | {headline(report)} |")
    (snapshots_dir / "README.md").write_text("\n".join(lines) + "\n")


def write_readme_pointer(readme: Path, snapshots_dir: Path) -> None:
    """Replace the marked block in the project README with a pointer to the newest snapshot."""
    snapshots = load_snapshots(snapshots_dir)
    if not snapshots:
        return
    name, report = snapshots[0]
    rel = snapshots_dir.relative_to(readme.parent).as_posix()
    date = datetime.fromisoformat(report["created_at"]).strftime("%Y-%m-%d")
    block = "\n".join(
        [
            START,
            "## Latest results",
            "",
            f"**[{date} snapshot]({rel}/{name}/)**: {headline(report)}",
            "",
            f"Full tables and per-use-case picks are in the snapshot; all runs are listed in [`{rel}/`]({rel}/).",
            END,
        ]
    )
    text = readme.read_text()
    if START in text and END in text:
        text = re.sub(
            re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.DOTALL
        )
    else:
        anchor = "## Datasets\n"
        text = (
            text.replace(anchor, f"{block}\n\n{anchor}", 1)
            if anchor in text
            else f"{text}\n{block}\n"
        )
    readme.write_text(text)
