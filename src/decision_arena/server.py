from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .datasets import Example, Question, load_datasets
from .providers import Decision, build_provider, load_models
from .recommend import recommend
from .runner import run_eval, save_report

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = PROJECT_ROOT / "datasets"
MODELS_FILE = PROJECT_ROOT / "models.yaml"
REPORTS_DIR = PROJECT_ROOT / "reports"
SNAPSHOTS_DIR = PROJECT_ROOT / "snapshots"
CACHE_DIR = PROJECT_ROOT / ".cache"
WEB_DIST = PROJECT_ROOT / "web" / "dist"

load_dotenv(PROJECT_ROOT / ".env")
app = FastAPI(title="Decision Arena")

# In-memory run registry; a run only lives as long as the server process.
runs: dict[str, dict[str, Any]] = {}


class RunRequest(BaseModel):
    models: list[str]
    datasets: list[str] | None = None
    limit: int | None = None
    concurrency: int = 8


class AskRequest(BaseModel):
    models: list[str]
    question: Question
    state: dict[str, Any] | str


@app.get("/api/models")
def get_models() -> list[dict[str, Any]]:
    return [m.model_dump() for m in load_models(MODELS_FILE, all_models=True)]


@app.get("/api/datasets")
def get_datasets() -> list[dict[str, Any]]:
    return [d.model_dump() for d in load_datasets(DATASETS_DIR)]


def report_paths() -> dict[str, Path]:
    """Local runs (git-ignored) plus committed snapshots, so a fresh clone has results to browse."""
    paths = {p.stem: p for p in REPORTS_DIR.glob("run-*.json")}
    paths.update({f"snapshot-{p.parent.name}": p for p in SNAPSHOTS_DIR.glob("*/report.json")})
    return paths


@app.get("/api/reports")
def list_reports() -> list[dict[str, Any]]:
    out = []
    for report_id, path in report_paths().items():
        report = json.loads(path.read_text())
        out.append(
            {
                "id": report_id,
                "created_at": report["created_at"],
                "models": [m["name"] for m in report["models"]],
                "datasets": list(report["datasets"]),
                "snapshot": report_id.startswith("snapshot-"),
            }
        )
    return sorted(out, key=lambda r: (r["created_at"], r["snapshot"]), reverse=True)


@app.get("/api/reports/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    path = report_paths().get(report_id)
    if path is None:
        raise HTTPException(404, "report not found")
    report = json.loads(path.read_text())
    return {"id": report_id, **report, "takeaways": recommend(report)}


@app.post("/api/runs")
async def start_run(body: RunRequest) -> dict[str, Any]:
    try:
        models = load_models(MODELS_FILE, body.models)
        datasets = load_datasets(DATASETS_DIR, body.datasets)
    except SystemExit as exc:
        raise HTTPException(400, str(exc)) from exc
    if not models:
        raise HTTPException(400, "pick at least one model")
    if body.limit:
        for d in datasets:
            d.examples = d.examples[: body.limit]

    run_id = uuid.uuid4().hex[:8]
    total = sum(len(d.examples) for d in datasets) * len(models)
    run = runs[run_id] = {"id": run_id, "status": "running", "done": 0, "total": total}

    def on_progress(done: int, total: int) -> None:
        run["done"], run["total"] = done, total

    async def job() -> None:
        try:
            report = await run_eval(datasets, models, CACHE_DIR, body.concurrency, on_progress)
            run["report_id"] = save_report(report, REPORTS_DIR).stem
            run["status"] = "done"
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            run["status"], run["error"] = "failed", f"{type(exc).__name__}: {exc}"

    run["task"] = asyncio.create_task(job())
    return {k: v for k, v in run.items() if k != "task"}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    if run_id not in runs:
        raise HTTPException(404, "run not found")
    return {k: v for k, v in runs[run_id].items() if k != "task"}


@app.post("/api/ask")
async def ask(body: AskRequest) -> list[dict[str, Any]]:
    """Playground: one ad-hoc question to several models at once."""
    try:
        models = load_models(MODELS_FILE, body.models)
    except SystemExit as exc:
        raise HTTPException(400, str(exc)) from exc
    example = Example(id="playground", state=body.state, expected=body.question.labels[0])

    async with httpx.AsyncClient(timeout=60) as client:

        async def one(spec) -> dict[str, Any]:
            provider = build_provider(spec, CACHE_DIR / spec.name.replace("/", "_"), client)
            try:
                decision = await provider.decide(body.question, example)
            except Exception as exc:  # noqa: BLE001 - shown per model card
                decision = Decision(error=f"{type(exc).__name__}: {exc}")
            return {"model": spec.name, "kind": spec.kind, **decision.model_dump(exclude_none=True)}

        return await asyncio.gather(*(one(spec) for spec in models))


if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        return FileResponse(WEB_DIST / "index.html")
