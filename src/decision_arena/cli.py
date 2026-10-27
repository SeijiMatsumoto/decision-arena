from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from .datasets import load_datasets
from .html_report import write_html
from .providers import load_models
from .recommend import recommend
from .runner import run_eval, save_report

PROJECT_ROOT = Path(__file__).resolve().parents[2]
console = Console()


def fmt(value: Any, kind: str = "pct") -> str:
    if value is None:
        return "-"
    if kind == "pct":
        return f"{value:.0%}"
    if kind == "ms":
        return f"{value:.0f}"
    if kind == "usd":
        return f"${value:.4f}"
    return f"{value:.2f}"


def dataset_table(name: str, data: dict[str, Any]) -> Table:
    qtype = data["question"]["type"]
    table = Table(
        title=f"{name}  [dim]({qtype}, n={len(data['examples'])})[/dim]",
        box=box.ROUNDED,
        title_justify="left",
        header_style="bold",
    )
    table.add_column("Model")
    table.add_column("Acc", justify="right")
    extra: list[tuple[str, str, str]] = {
        "noul": [("AUC", "auc", "num"), ("Brier", "brier", "num"), ("Best t", "best_threshold", "num"),
                 ("Acc@t", "best_threshold_accuracy", "pct"), ("NDCG", "ndcg", "num")],
        "choice": [("Macro F1", "macro_f1", "num")],
        "score": [("±1", "within_1", "pct"), ("MAE", "mae", "num")],
    }[qtype]
    for header, _, _ in extra:
        table.add_column(header, justify="right")
    for header in ("p50 ms", "$/1k", "Err"):
        table.add_column(header, justify="right")

    ranked = sorted(data["metrics"].items(), key=lambda kv: -(kv[1]["accuracy"] or 0))
    for model, m in ranked:
        table.add_row(
            model,
            fmt(m["accuracy"]),
            *(fmt(m.get(key), kind) for _, key, kind in extra),
            fmt(m["latency_p50_ms"], "ms"),
            fmt(m["cost_per_1k"], "usd"),
            str(m["errors"]) if m["errors"] else "",
        )
    return table


def tag_table(report: dict[str, Any]) -> Table:
    """Accuracy per scenario tag, pooled across datasets."""
    hits: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for data in report["datasets"].values():
        examples = {e["id"]: e for e in data["examples"]}
        for model, preds in data["predictions"].items():
            for eid, d in preds.items():
                if "error" in d:
                    continue
                expected = examples[eid]["expected"]
                expected = ("true" if expected else "false") if isinstance(expected, bool) else str(expected)
                for tag in examples[eid]["tags"]:
                    hits[tag][model].append(d.get("label") == expected)
    models = [m["name"] for m in report["models"]]
    table = Table(title="Accuracy by scenario tag (all datasets)", box=box.ROUNDED,
                  title_justify="left", header_style="bold")
    table.add_column("Tag")
    table.add_column("n", justify="right")
    for model in models:
        table.add_column(model, justify="right")
    for tag in sorted(hits):
        n = max(len(v) for v in hits[tag].values())
        table.add_row(
            tag, str(n),
            *(fmt(sum(h) / len(h)) if (h := hits[tag].get(m)) else "-" for m in models),
        )
    return table


ROLE_LABELS = {
    "recommended": "Use",
    "most_accurate": "Most accurate",
    "fastest": "Fastest",
    "cheapest": "Cheapest",
}


def print_takeaways(report: dict[str, Any]) -> None:
    takeaways = recommend(report)
    for rec in [takeaways["overall"], *takeaways["datasets"].values()]:
        title = rec["scope"] + (f" - {rec['use_case']}" if rec["use_case"] else "")
        console.print(f"\n[bold]{title}[/bold] [dim](n={rec['n']})[/dim]")
        for pick in rec["picks"]:
            console.print(f"  [green]{ROLE_LABELS[pick['role']]:>13}[/green]  {pick['model']}: {pick['why']}")
        for item in rec["avoid"]:
            console.print(f"  [red]{'Avoid':>13}[/red]  {item['model']}: {item['why']}")
        for note in rec["notes"]:
            console.print(f"  [dim]{'Note':>13}  {note}[/dim]")


def print_report(report: dict[str, Any], show_misses: bool) -> None:
    for name, data in report["datasets"].items():
        console.print(dataset_table(name, data))
        errors = {
            m: next(d["error"] for d in preds.values() if "error" in d)
            for m, preds in data["predictions"].items()
            if any("error" in d for d in preds.values())
        }
        for model, error in errors.items():
            console.print(f"  [red]{model}[/red] first error: {error[:160]}")
        if show_misses and data["hard_examples"]:
            for row in data["hard_examples"][:8]:
                console.print(
                    f"  [yellow]{row['id']}[/yellow] expected [bold]{row['expected']}[/bold] "
                    f"[dim]{','.join(row['tags'])}[/dim] -> wrong: {', '.join(row['wrong'])}"
                )
        console.print()
    if len(report["models"]) > 0:
        console.print(tag_table(report))
        console.rule("Takeaways")
        print_takeaways(report)


def cmd_list(args: argparse.Namespace) -> None:
    table = Table(title="Datasets", box=box.ROUNDED, header_style="bold", title_justify="left")
    for col in ("Name", "Type", "n", "Use case"):
        table.add_column(col)
    for d in load_datasets(args.datasets_dir):
        table.add_row(d.name, d.question.type, str(len(d.examples)), d.use_case)
    console.print(table)
    table = Table(title="Models", box=box.ROUNDED, header_style="bold", title_justify="left")
    for col in ("Name", "Provider", "Model ID", "Enabled"):
        table.add_column(col)
    for spec in load_models(args.models_file, all_models=True):
        table.add_row(spec.name, spec.provider, spec.model,
                      "yes" if spec.enabled else "[dim]no[/dim]")
    console.print(table)


def cmd_run(args: argparse.Namespace) -> None:
    datasets = load_datasets(args.datasets_dir, args.datasets)
    models = load_models(args.models_file, args.models)
    if args.limit:
        for d in datasets:
            d.examples = d.examples[: args.limit]
    console.print(
        f"Running [bold]{len(models)}[/bold] models x [bold]{len(datasets)}[/bold] datasets "
        f"({sum(len(d.examples) for d in datasets)} examples each)"
    )
    with Progress() as progress:
        bar = progress.add_task("Asking models", total=None)

        def on_progress(done: int, total: int) -> None:
            progress.update(bar, completed=done, total=total)

        report = asyncio.run(
            run_eval(datasets, models, PROJECT_ROOT / ".cache", args.concurrency, on_progress)
        )
    if args.out:
        out = args.out
        out.write_text(json.dumps(report, indent=2))
    else:
        out = save_report(report, PROJECT_ROOT / "reports")
    html = write_html(report, out.with_suffix(".html"))
    print_report(report, args.misses)
    console.print(f"\nReport: {out}\nHTML:   {html}")


def cmd_show(args: argparse.Namespace) -> None:
    path = args.report or max((PROJECT_ROOT / "reports").glob("run-*.json"), default=None)
    if path is None:
        raise SystemExit("No reports yet. Run `arena run` first.")
    print_report(json.loads(Path(path).read_text()), args.misses)


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("decision_arena.server:app", host="127.0.0.1", port=args.port, reload=args.reload)


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(prog="arena", description=__doc__)
    parser.add_argument("--datasets-dir", type=Path, default=PROJECT_ROOT / "datasets")
    parser.add_argument("--models-file", type=Path, default=PROJECT_ROOT / "models.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Show datasets and configured models").set_defaults(func=cmd_list)

    run = sub.add_parser("run", help="Run models over datasets and write a report")
    run.add_argument("--models", type=lambda s: s.split(","), help="Comma-separated model names")
    run.add_argument("--datasets", type=lambda s: s.split(","), help="Comma-separated dataset names")
    run.add_argument("--limit", type=int, help="Only the first N examples per dataset")
    run.add_argument("--concurrency", type=int, default=8, help="In-flight requests per model")
    run.add_argument("--misses", action="store_true", help="List examples models got wrong")
    run.add_argument("--out", type=Path)
    run.set_defaults(func=cmd_run)

    show = sub.add_parser("show", help="Re-print a saved report (latest by default)")
    show.add_argument("report", nargs="?", type=Path)
    show.add_argument("--misses", action="store_true")
    show.set_defaults(func=cmd_show)

    serve = sub.add_parser("serve", help="Start the API (and built web UI) on localhost")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)
