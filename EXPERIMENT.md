# Gemini Decision 1 comparison (2026-11-12)

Decide whether `google/gemini-decision-1` is worth using for this arena's bounded
classification workload compared with the current pick, `typesafe/jev-1.14`, and
the previous best generative baseline, `anthropic/claude-haiku-5.5`.
This is exploratory; no expected winner or production adoption is assumed.

Use the unchanged 119 hand-written synthetic examples in the eight existing YAML
datasets. The evaluation unit is one example/question, with identical state and
criteria for all contenders. Labels never enter real provider prompts. These are
previously used public examples, not a new held-out or production dataset. Related
examples and prior exposure limit statistical independence and generalization.
No tuning or label edits are part of this run.

Primary metric: exact label accuracy at the existing defaults (noul threshold 0.5;
score uses the most likely level). Failures count as wrong for recommendations;
the existing dataset tables report successful-answer accuracy and separate errors.
Report noul calibration/AUC, choice macro-F1, score MAE, and scenario accuracy.
Best-threshold accuracy is an exploratory in-sample diagnostic, not held-out quality.

Reuse the deterministic recommendation rule: eligible contenders have no failed
calls, are within two percentage points of the best accuracy, and are not worse
under the existing exact paired McNemar test at p < 0.05. Pick by combined cost
and latency rank; use accuracy for ties. No successful contender means no pick.
Non-significance is not equivalence; this small, multiple-comparison study can
remain inconclusive about quality even when the rule selects an operational pick.

Measure client HTTP round-trip p50/p95, excluding client rate-limit waiting;
concurrency is two requests per model. Use an isolated new cache, preserve old
caches, and disable retries (unknown billing outcomes are never resent). This
avoids local replay but does not control provider-side caching. Record cost per
1,000 calls from usage, or configured input/output token prices if unavailable;
missing cost remains unknown. There is one pass per contender, not a latency study
across repeated runs, regions, or load levels.

The user requested incorporation and comparisons, authorizing this bounded live
run. Plan: three Gemini type checks, followed by 357 fresh comparison requests.
Expected spend below $0.05; a $0.10 planning ceiling includes ample headroom based
on existing token sizes. Verified OpenRouter key budget before running: $10.1238
remaining. No labeling, retrieval, or judging calls. No deployment, publication,
production changes, or unrelated model sweep.

Reproduce:

```bash
uv run arena run --models gemini-decision-1,jev-1.14,haiku-5.5 --fresh --attempts 1 --concurrency 2
uv run arena snapshot <report.json>
```

The report retains exact model configuration, questions, examples, predictions,
usage, and timing; the snapshot is available in the existing Results UI. Retain a
SHA-256 manifest of dataset files alongside the snapshot. Success means a usable
integration for all three question types plus an auditable dated live comparison,
not evidence of production suitability or a guaranteed model-quality winner.

Sources: [Google launch](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-decisions-api/),
[OpenRouter model](https://openrouter.ai/google/gemini-decision-1).
