"""Deterministic takeaways: which model to use for what, derived only from a report's numbers.

The rules, in order:
1. A model is a contender when it is within TOLERANCE of the top accuracy AND an exact McNemar
   test on the paired examples does not show it is significantly worse (p < 0.05). The test
   guards against trusting noise on big datasets; the tolerance guards against small datasets,
   where even a 10-point gap can fail to reach significance.
2. Among contenders, the default pick has the best combined rank on cost and latency (ties go
   to accuracy). Separate picks name the most accurate, fastest and cheapest contenders.
3. Significantly worse models, and models with failed calls, are listed to avoid.
4. Extra notes: decision models vs LLMs, saturated datasets, per-model cutoffs for yes/no
   questions, and scenario tags where a pick struggles.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

ALPHA = 0.05
TOLERANCE = 0.02  # contenders must be within 2 accuracy points of the top model
SATURATION = 0.95  # a dataset is "saturated" when most models reach this accuracy
WEAK_TAG = 0.8  # flag a pick's scenario tag below this accuracy...
WEAK_TAG_MIN_N = 3  # ...when the tag has at least this many examples


def mcnemar_p(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value from the two discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def _expected(example: dict[str, Any]) -> str:
    x = example["expected"]
    return ("true" if x else "false") if isinstance(x, bool) else str(x)


def _model_stats(items: list[tuple[str, str, list[str]]], preds: dict[str, dict]) -> dict[str, Any]:
    """items: (key, expected, tags). Errors count as misses: a failed call is a failed decision."""
    hits: set[str] = set()
    live, all_lat, costs = [], [], []
    errors = 0
    tag_hits: dict[str, list[bool]] = defaultdict(list)
    for key, expected, tags in items:
        d = preds.get(key)
        if not d or "error" in d:
            errors += 1
            ok = False
        else:
            ok = d.get("label") == expected
            all_lat.append(d["latency_ms"])
            if not d.get("cached"):
                live.append(d["latency_ms"])
            if d.get("cost") is not None:
                costs.append(d["cost"])
        if ok:
            hits.add(key)
        for tag in tags:
            tag_hits[tag].append(ok)
    lat = live or all_lat
    return {
        "hits": hits,
        "accuracy": len(hits) / len(items) if items else None,
        "p50_ms": statistics.median(lat) if lat else None,
        "cost_per_1k": 1000 * sum(costs) / len(costs) if costs else None,
        "errors": errors,
        "by_tag": {t: (sum(v) / len(v), len(v)) for t, v in tag_hits.items()},
    }


def _fmt_model(name: str, s: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": name,
        "accuracy": s["accuracy"],
        "p50_ms": s["p50_ms"],
        "cost_per_1k": s["cost_per_1k"],
    }


def _ratio(a: float | None, b: float | None) -> float | None:
    return a / b if a and b else None


def _describe(s: dict[str, Any]) -> str:
    parts = [f"{s['accuracy']:.0%} accurate"]
    if s["p50_ms"] is not None:
        parts.append(f"{s['p50_ms']:.0f}ms median")
    if s["cost_per_1k"] is not None:
        parts.append(f"${s['cost_per_1k']:.4f} per 1k calls")
    return ", ".join(parts)


def _rank(values: dict[str, float | None]) -> dict[str, int]:
    """Rank ascending with equal ranks for ties; missing values rank last."""
    levels = sorted(set(values.values()), key=lambda value: (value is None, value or 0))
    ranks = {value: rank for rank, value in enumerate(levels)}
    return {name: ranks[value] for name, value in values.items()}


def analyze(
    scope: str,
    use_case: str | None,
    items: list[tuple[str, str, list[str]]],
    predictions: dict[str, dict[str, dict]],
    kinds: dict[str, str],
    thresholds: dict[str, tuple[float, float, float]] | None = None,
) -> dict[str, Any]:
    stats = {m: _model_stats(items, p) for m, p in predictions.items()}
    stats = {m: s for m, s in stats.items() if s["accuracy"] is not None}
    if not stats:
        return {
            "scope": scope,
            "use_case": use_case,
            "n": len(items),
            "picks": [],
            "avoid": [],
            "notes": [],
        }

    top = max(stats, key=lambda m: (stats[m]["accuracy"], -(stats[m]["p50_ms"] or math.inf)))
    keys = [k for k, _, _ in items]

    def p_vs_top(m: str) -> float:
        b = sum(1 for k in keys if k in stats[top]["hits"] and k not in stats[m]["hits"])
        c = sum(1 for k in keys if k in stats[m]["hits"] and k not in stats[top]["hits"])
        return mcnemar_p(b, c)

    p_values = {m: p_vs_top(m) for m in stats}
    worse = [m for m in stats if m != top and p_values[m] < ALPHA]
    tied = [
        m
        for m in stats
        if m not in worse and stats[m]["accuracy"] >= stats[top]["accuracy"] - TOLERANCE - 1e-9
    ]

    cost_rank = _rank({m: stats[m]["cost_per_1k"] for m in tied})
    lat_rank = _rank({m: stats[m]["p50_ms"] for m in tied})
    default = min(tied, key=lambda m: (cost_rank[m] + lat_rank[m], -stats[m]["accuracy"], m))
    fastest = min(tied, key=lambda m: (stats[m]["p50_ms"] or math.inf, m))
    cheapest = min(tied, key=lambda m: (stats[m]["cost_per_1k"] or math.inf, m))

    tied_note = (
        f"one of {len(tied)} models within {TOLERANCE * 100:.0f} points of the top"
        if len(tied) > 1
        else "the only model at top accuracy"
    )
    picks = [
        {
            "role": "recommended",
            **_fmt_model(default, stats[default]),
            "why": (
                f"Best combined cost and speed among models within {TOLERANCE * 100:.0f} points of "
                f"the top and not significantly worse ({_describe(stats[default])})."
                if len(tied) > 1
                else f"Top accuracy ({_describe(stats[default])})."
            ),
        }
    ]
    if top != default:
        picks.append(
            {
                "role": "most_accurate",
                **_fmt_model(top, stats[top]),
                "why": f"Highest raw accuracy ({_describe(stats[top])}), but not significantly better than the recommended pick.",
            }
        )
    if fastest not in (default, top):
        picks.append(
            {
                "role": "fastest",
                **_fmt_model(fastest, stats[fastest]),
                "why": f"Lowest latency, {tied_note} ({_describe(stats[fastest])}).",
            }
        )
    if cheapest not in (default, top, fastest):
        picks.append(
            {
                "role": "cheapest",
                **_fmt_model(cheapest, stats[cheapest]),
                "why": f"Lowest cost, {tied_note} ({_describe(stats[cheapest])}).",
            }
        )

    avoid = []
    for m in sorted(worse, key=lambda m: stats[m]["accuracy"]):
        gap = stats[top]["accuracy"] - stats[m]["accuracy"]
        avoid.append(
            {
                "model": m,
                "accuracy": stats[m]["accuracy"],
                "why": f"Significantly less accurate than {top} ({gap * 100:.0f} points lower, p={p_values[m]:.3f}).",
            }
        )
    for m in sorted(stats):
        if stats[m]["errors"] and m not in worse:
            avoid.append(
                {
                    "model": m,
                    "accuracy": stats[m]["accuracy"],
                    "why": f"{stats[m]['errors']} failed calls; fix or rerun before trusting it.",
                }
            )

    notes: list[str] = []
    n = len(items)
    if sum(s["accuracy"] >= SATURATION for s in stats.values()) > len(stats) / 2:
        notes.append(
            f"Most models score at least {SATURATION:.0%} here, so this dataset does not separate them "
            "on quality; the picks are driven by cost and speed. Add harder or real examples."
        )
    elif n < 50:
        notes.append(
            f"Only {n} examples: differences of a few points here are one or two answers. "
            "Treat the ranking as a hint."
        )

    decision = [m for m in stats if kinds.get(m) == "decision"]
    llm = [m for m in stats if kinds.get(m) == "llm"]
    if decision and llm:

        def best(group: list[str]) -> str:
            return max(
                group, key=lambda m: (stats[m]["accuracy"], -(stats[m]["p50_ms"] or math.inf), m)
            )

        best_d, best_l = best(decision), best(llm)
        b = sum(1 for k in keys if k in stats[best_d]["hits"] and k not in stats[best_l]["hits"])
        c = sum(1 for k in keys if k in stats[best_l]["hits"] and k not in stats[best_d]["hits"])
        p = mcnemar_p(b, c)
        if p >= ALPHA:
            quality = "no significant accuracy difference"
        elif stats[best_d]["accuracy"] > stats[best_l]["accuracy"]:
            quality = "the decision model is significantly more accurate"
        else:
            quality = "the LLM is significantly more accurate"
        extras = []
        speed = _ratio(stats[best_l]["p50_ms"], stats[best_d]["p50_ms"])
        cost = _ratio(stats[best_l]["cost_per_1k"], stats[best_d]["cost_per_1k"])
        if speed:
            extras.append(f"{speed:.1f}× faster" if speed >= 1 else f"{1 / speed:.1f}× slower")
        if cost:
            extras.append(
                f"{cost:.1f}× cheaper" if cost >= 1 else f"{1 / cost:.1f}× more expensive"
            )
        notes.append(
            f"Best decision model ({best_d}, {stats[best_d]['accuracy']:.0%}) vs best LLM "
            f"({best_l}, {stats[best_l]['accuracy']:.0%}): {quality}"
            + (f"; the decision model is {' and '.join(extras)}." if extras else ".")
        )

    for pick in picks:
        m = pick["model"]
        if thresholds and m in thresholds:
            cutoff, acc_at_half, acc_at_cutoff = thresholds[m]
            if abs(cutoff - 0.5) >= 0.1 and acc_at_cutoff - acc_at_half >= 0.02:
                notes.append(
                    f"For {m}, set the yes/no cutoff to {cutoff:.2f} instead of 0.5 "
                    f"(accuracy {acc_at_half:.0%} → {acc_at_cutoff:.0%} on this data)."
                )
        weak = [
            f"{t} ({a:.0%} of {k})"
            for t, (a, k) in sorted(stats[m]["by_tag"].items())
            if k >= WEAK_TAG_MIN_N and a < WEAK_TAG
        ]
        if weak:
            notes.append(f"{m} struggles with: {', '.join(weak)}.")

    return {
        "scope": scope,
        "use_case": use_case,
        "n": n,
        "top_tier": sorted(tied),
        "picks": picks,
        "avoid": avoid,
        "notes": notes,
    }


def recommend(report: dict[str, Any]) -> dict[str, Any]:
    kinds = {
        m["name"]: m.get("kind") or ("llm" if m["provider"] == "llm" else "decision")
        for m in report["models"]
    }
    per_dataset = {}
    pooled_items: list[tuple[str, str, list[str]]] = []
    pooled_preds: dict[str, dict[str, dict]] = defaultdict(dict)

    for name, data in report["datasets"].items():
        items = [(e["id"], _expected(e), e["tags"]) for e in data["examples"]]
        thresholds = None
        if data["question"]["type"] == "noul":
            thresholds = {
                m: (met["best_threshold"], met["accuracy"], met["best_threshold_accuracy"])
                for m, met in data["metrics"].items()
                if met.get("best_threshold") is not None and met.get("accuracy") is not None
            }
        per_dataset[name] = analyze(
            name, data["use_case"], items, data["predictions"], kinds, thresholds
        )
        for key, expected, tags in items:
            pooled_items.append((f"{name}/{key}", expected, tags))
        for m, preds in data["predictions"].items():
            for key, d in preds.items():
                pooled_preds[m][f"{name}/{key}"] = d

    return {
        "overall": analyze("all datasets", None, pooled_items, dict(pooled_preds), kinds),
        "datasets": per_dataset,
    }
