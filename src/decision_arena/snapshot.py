"""Render a report as a dated Markdown results section, for pasting into (or updating) the README."""

from __future__ import annotations

import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from .recommend import recommend

START = "<!-- snapshot:start -->"
END = "<!-- snapshot:end -->"


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


def render(report: dict[str, Any]) -> str:
    date = datetime.fromisoformat(report["created_at"]).strftime("%Y-%m-%d")
    takeaways = recommend(report)
    rows = pooled(report)
    datasets = list(report["datasets"])
    n_examples = sum(len(d["examples"]) for d in report["datasets"].values())
    lines = [
        f"## Results snapshot ({date})",
        "",
        (
            f"One run on {date}: {len(rows)} models × {n_examples} examples across {len(datasets)} datasets, "
            "all called through OpenRouter. Latency is the client-side round trip from one machine, so it "
            "includes network time; cost is what OpenRouter reported per call at the time. The datasets are "
            "small and synthetic (see Caveats), so treat accuracy gaps of a few points as noise. The datasets "
            "were written before the first run and not changed after seeing results; the question format "
            "(noul / choice / score) originated with Jev and LLMs get a plain, untuned prompt. "
            "Regenerate this section with `uv run arena snapshot --write`."
        ),
        "",
        "### Overall",
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

    lines += ["", "### Accuracy by dataset", ""]
    lines.append("| Model | " + " | ".join(d.replace("_", " ") for d in datasets) + " |")
    lines.append("|---|" + "---:|" * len(datasets))
    for r in rows:
        cells = [
            _pct(report["datasets"][d]["metrics"][r["name"]]["accuracy"]).replace(".0%", "%")
            for d in datasets
        ]
        lines.append(f"| {r['name']} | " + " | ".join(cells) + " |")

    overall = takeaways["overall"]
    labels = {
        "recommended": "Use",
        "most_accurate": "Most accurate",
        "fastest": "Fastest",
        "cheapest": "Cheapest",
    }
    lines += ["", "### Takeaways (rules described in the Takeaways section above)", ""]
    for pick in overall["picks"]:
        lines.append(f"- **{labels[pick['role']]}: {pick['model']}.** {pick['why']}")
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
            f"{p['model']} ({labels[p['role']].lower()})"
            for p in t["picks"]
            if p["role"] in ("fastest", "cheapest")
        ]
        avoid = ", ".join(a["model"] for a in t["avoid"]) or "—"
        lines.append(
            f"| {name.replace('_', ' ')} | {rec['model'] if rec else '—'} | {', '.join(alts) or '—'} | {avoid} |"
        )
    return "\n".join(lines) + "\n"


def write_readme(readme: Path, section: str) -> None:
    """Replace the marked snapshot block, or insert one before the Datasets section."""
    text = readme.read_text()
    block = f"{START}\n{section}{END}"
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
