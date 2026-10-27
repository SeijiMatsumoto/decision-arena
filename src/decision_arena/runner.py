from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .datasets import Dataset
from .metrics import agreement, hard_examples, model_metrics
from .providers import Decision, ModelSpec, build_provider


async def run_eval(
    datasets: list[Dataset],
    models: list[ModelSpec],
    cache_dir: Path,
    concurrency: int = 8,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Ask every model every example, then score. Each model gets its own concurrency budget."""
    results: dict[str, dict[str, dict[str, Decision]]] = {
        d.name: {m.name: {} for m in models} for d in datasets
    }
    total = sum(len(d.examples) for d in datasets) * len(models)
    done = 0

    async with httpx.AsyncClient(timeout=60) as client:

        async def ask(spec: ModelSpec, gate: asyncio.Semaphore, dataset: Dataset, example):
            nonlocal done
            provider = build_provider(spec, cache_dir / spec.name.replace("/", "_"), client)
            async with gate:
                try:
                    decision = await provider.decide(dataset.question, example)
                except Exception as exc:  # noqa: BLE001 - recorded per example so one bad model can't sink a run
                    decision = Decision(error=f"{type(exc).__name__}: {exc}")
            results[dataset.name][spec.name][example.id] = decision
            done += 1
            if on_progress:
                on_progress(done, total)

        tasks = []
        for spec in models:
            gate = asyncio.Semaphore(concurrency)
            for dataset in datasets:
                for example in dataset.examples:
                    tasks.append(ask(spec, gate, dataset, example))
        await asyncio.gather(*tasks)

    report: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": [m.model_dump() for m in models],
        "datasets": {},
    }
    for dataset in datasets:
        by_model = results[dataset.name]
        report["datasets"][dataset.name] = {
            "description": dataset.description,
            "use_case": dataset.use_case,
            "question": dataset.question.model_dump(),
            "examples": [e.model_dump() for e in dataset.examples],
            "predictions": {
                m: {eid: d.model_dump(exclude_none=True) for eid, d in preds.items()}
                for m, preds in by_model.items()
            },
            "metrics": {m: model_metrics(dataset, preds) for m, preds in by_model.items()},
            "agreement": agreement(dataset, by_model),
            "hard_examples": hard_examples(dataset, by_model),
        }
    return report


def save_report(report: dict[str, Any], reports_dir: Path) -> Path:
    stamp = report["created_at"].replace(":", "").replace("-", "")[:15]
    path = reports_dir / f"run-{stamp}.json"
    path.write_text(json.dumps(report, indent=2))
    return path
