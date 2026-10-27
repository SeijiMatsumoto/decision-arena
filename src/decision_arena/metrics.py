from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations
from typing import Any

from .datasets import Dataset
from .providers import Decision

Predictions = dict[str, Decision]  # example id -> decision for one model


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[index]


def macro_f1(pairs: list[tuple[str, str]], labels: list[str]) -> float:
    scores = []
    for label in labels:
        tp = sum(1 for y, p in pairs if y == label and p == label)
        fp = sum(1 for y, p in pairs if y != label and p == label)
        fn = sum(1 for y, p in pairs if y == label and p != label)
        if tp + fp + fn == 0:
            continue  # label absent from both truth and predictions
        scores.append(2 * tp / (2 * tp + fp + fn))
    return sum(scores) / len(scores) if scores else 0.0


def auc(scored: list[tuple[bool, float]]) -> float | None:
    """Probability a random positive outranks a random negative (ties count half)."""
    positives = [s for y, s in scored if y]
    negatives = [s for y, s in scored if not y]
    if not positives or not negatives:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


def expected_calibration_error(scored: list[tuple[bool, float]], bins: int = 5) -> float | None:
    """ECE on P(true): how far stated probabilities sit from observed frequencies."""
    if not scored:
        return None
    buckets: dict[int, list[tuple[bool, float]]] = defaultdict(list)
    for y, p in scored:
        buckets[min(int(p * bins), bins - 1)].append((y, p))
    return sum(
        len(items)
        / len(scored)
        * abs(sum(y for y, _ in items) / len(items) - sum(p for _, p in items) / len(items))
        for items in buckets.values()
    )


def best_threshold(scored: list[tuple[bool, float]]) -> tuple[float, float]:
    """Threshold maximizing accuracy. Decision models differ in calibration, so 0.5 is arbitrary."""
    candidates = sorted({0.5, *(p for _, p in scored)})
    best = (0.5, 0.0)
    for t in candidates:
        acc = sum((p >= t) == y for y, p in scored) / len(scored)
        if acc > best[1]:
            best = (t, acc)
    return best


def ndcg(relevance_in_rank_order: list[bool]) -> float:
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevance_in_rank_order))
    ideal = sorted(relevance_in_rank_order, reverse=True)
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg else 1.0


def model_metrics(dataset: Dataset, predictions: Predictions) -> dict[str, Any]:
    question = dataset.question
    ok = [(e, predictions[e.id]) for e in dataset.examples if not predictions[e.id].error]
    pairs = [(e.expected_label, d.label or "") for e, d in ok]
    live = [d for _, d in ok if not d.cached] or [d for _, d in ok]
    costs = [d.cost for _, d in ok if d.cost is not None]

    result: dict[str, Any] = {
        "n": len(dataset.examples),
        "errors": len(dataset.examples) - len(ok),
        "accuracy": sum(y == p for y, p in pairs) / len(pairs) if pairs else None,
        "latency_p50_ms": percentile([d.latency_ms for d in live], 0.5),
        "latency_p95_ms": percentile([d.latency_ms for d in live], 0.95),
        "cost_total": sum(costs) if costs else None,
        "cost_per_1k": 1000 * sum(costs) / len(costs) if costs else None,
    }

    by_tag: dict[str, list[bool]] = defaultdict(list)
    for e, d in ok:
        for tag in e.tags:
            by_tag[tag].append(e.expected_label == d.label)
    result["by_tag"] = {tag: sum(hits) / len(hits) for tag, hits in sorted(by_tag.items())}

    if question.type == "choice":
        result["macro_f1"] = macro_f1(pairs, question.labels)
        confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for y, p in pairs:
            confusion[y][p] += 1
        result["confusion"] = {y: dict(row) for y, row in confusion.items()}

    if question.type == "noul":
        scored = [(e.expected_label == "true", d.p_true) for e, d in ok if d.p_true is not None]
        if scored:
            result["auc"] = auc(scored)
            result["brier"] = sum((p - y) ** 2 for y, p in scored) / len(scored)
            result["ece"] = expected_calibration_error(scored)
            result["best_threshold"], result["best_threshold_accuracy"] = best_threshold(scored)
        groups: dict[str, list[tuple[bool, float]]] = defaultdict(list)
        for e, d in ok:
            if e.group and d.p_true is not None:
                groups[e.group].append((e.expected_label == "true", d.p_true))
        if groups:
            ranked = {
                g: [y for y, _ in sorted(items, key=lambda x: -x[1])] for g, items in groups.items()
            }
            result["ndcg"] = sum(ndcg(r) for r in ranked.values()) / len(ranked)
            result["top1_hit"] = sum(r[0] for r in ranked.values()) / len(ranked)

    if question.type == "score":
        # (expected level, predicted position, predicted level) for answers that carry a score.
        levels = [
            (int(e.expected_label), d.score, int(d.label))
            for e, d in ok
            if d.score is not None and d.label is not None
        ]
        result["mae"] = sum(abs(s - y) for y, s, _ in levels) / len(levels) if levels else None
        result["within_1"] = (
            sum(abs(p - y) <= 1 for y, _, p in levels) / len(levels) if levels else None
        )

    return result


def agreement(dataset: Dataset, by_model: dict[str, Predictions]) -> dict[str, float]:
    """Pairwise label agreement, ignoring examples where either model errored."""
    out = {}
    for a, b in combinations(by_model, 2):
        same = [
            by_model[a][e.id].label == by_model[b][e.id].label
            for e in dataset.examples
            if not by_model[a][e.id].error and not by_model[b][e.id].error
        ]
        if same:
            out[f"{a} | {b}"] = sum(same) / len(same)
    return out


def hard_examples(dataset: Dataset, by_model: dict[str, Predictions]) -> list[dict[str, Any]]:
    """Examples where at least one model is wrong, sorted by how many models missed."""
    rows = []
    for e in dataset.examples:
        answers = {m: preds[e.id] for m, preds in by_model.items() if not preds[e.id].error}
        wrong = [m for m, d in answers.items() if d.label != e.expected_label]
        if wrong:
            rows.append(
                {
                    "id": e.id,
                    "expected": e.expected_label,
                    "tags": e.tags,
                    "wrong": wrong,
                    "answers": {m: d.label for m, d in answers.items()},
                }
            )
    return sorted(rows, key=lambda r: -len(r["wrong"]))
