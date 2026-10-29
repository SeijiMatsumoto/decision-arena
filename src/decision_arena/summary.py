"""arena-summary/1 for the arenas hub (https://github.com/SeijiMatsumoto/arenas).

Maps a report onto the shared contract using the same pooled stats and picks as the snapshot
README, so the hub card and the README never disagree. Hand-written fields come from arena.yaml.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from arena_kit import contract

from .recommend import ALPHA, TOLERANCE, _expected, _model_stats, recommend
from .snapshot import headline, snapshot_name

RULES = (
    f"Tied = within {TOLERANCE:.0%} of the top accuracy and not significantly worse "
    f"(exact McNemar, p < {ALPHA}); pick = best combined cost and latency rank among tied. "
    "Pooled over every dataset; failed calls count as wrong."
)


def build_summary(report: dict[str, Any], root: Path, folder: Path) -> dict[str, Any]:
    items, preds = [], defaultdict(dict)
    for name, data in report["datasets"].items():
        items += [(f"{name}/{e['id']}", _expected(e), e["tags"]) for e in data["examples"]]
        for model, rows in data["predictions"].items():
            for key, d in rows.items():
                preds[model][f"{name}/{key}"] = d
    overall = recommend(report)["overall"]
    pick = overall["picks"][0] if overall["picks"] else None
    tied, avoid = set(overall["top_tier"]), {a["model"] for a in overall["avoid"]}
    kinds = {m["name"]: m.get("kind") or ("llm" if m["provider"] == "llm" else "decision")
             for m in report["models"]}

    contenders = []
    for model, rows in preds.items():
        s = _model_stats(items, rows)
        verdict = ("pick" if pick and model == pick["model"] else "excluded" if s["errors"]
                   else "tied" if model in tied else "worse" if model in avoid else "other")
        contenders.append({"name": model, "kind": kinds.get(model, "other"),
                           "quality": s["accuracy"], "latency_ms": s["p50_ms"],
                           "cost_per_1k_usd": s["cost_per_1k"], "errors": s["errors"],
                           "verdict": verdict})
    contenders.sort(key=lambda c: (-(c["quality"] or 0), c["name"]))
    sid = snapshot_name(report)
    return contract.build(
        contract.load_manifest(root), snapshot_id=sid, created_at=report["created_at"],
        snapshot_path=folder.relative_to(root).as_posix(), headline=headline(report),
        pick={"name": pick["model"], "reason": pick["why"]} if pick else None,
        metric={"name": "accuracy", "label": "Accuracy", "higher_is_better": True,
                "format": "percent"},
        contenders=contenders, items=len(items), rules=RULES,
        mock=all(m["provider"] == "mock" for m in report["models"]),
    )


def write_summary(report: dict[str, Any], root: Path, folder: Path) -> Path:
    return contract.write(root, folder, build_summary(report, root, folder))
