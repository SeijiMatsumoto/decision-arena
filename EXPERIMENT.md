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

## OpenAI baseline and 200-example expansion (2026-11-12)

User requested an OpenAI baseline and 200 total examples (initially phrased as 71 more).
Use `openai/gpt-6-luna`, OpenAI's current efficient model for focused high-volume
tasks ($0.10/M input, $0.50/M output on OpenRouter). User explicitly excluded
GPT-5 nano because API access ends December 11, 2026. No Nano calls were made.
Source: https://developers.openai.com/api/docs/models/gpt-6-luna and
https://openrouter.ai/api/v1/models (verified before inference).

The original 119 examples and all question criteria are unchanged. Add 81
assistant-authored synthetic examples/labels across all eight tasks, tagged
`synthetic-v2`; no independent human label review. The author saw prior aggregate
results and existing examples, so this is an exploratory expansion, not a blind
held-out benchmark. Freeze labels before calls and report expansion-only accuracy
as well as pooled accuracy. No tuning based on outputs. 200 is a requested size,
not a statistical power guarantee. Paired tests retain the earlier limitations.

Use the existing scoring, failure policy, eligibility and recommendation rule.
Run four models on the same 200 items with fresh local cache, concurrency 2,
no retries: 800 comparison calls. Up to three preceding Luna type checks.
Expected spend below $0.10, planning ceiling $0.20 (based on prior usage and
current catalog prices). This is the bounded comparison extension requested by
the user; no publication or deployment. Record actual costs and dataset hashes.

```bash
uv run arena run --models gemini-decision-1,jev-1.14,haiku-5.5,gpt-6-luna --fresh --attempts 1 --concurrency 2
```

Arithmetic correction before final pass: 119 + 71 = 190; added ten more to
reach the requested total of 200 (81 new examples). An incomplete 190-item pass
was stopped without inspecting predictions; its cache is preserved, excluded
from comparison, and accounted for separately. Final pass uses a new fresh cache.

## OpenAI Decisions correction

The previous OpenAI baseline used chat completions. The user identified the
dedicated Decisions API; run the already configured OpenRouter
`openai/gpt-6-luna-decisions` entry on the exact same frozen 200 items, with
concurrency 2, fresh local cache, and no retries. Official native API uses
`gpt-6-luna` through `/v1/decisions`, input $0.10/M with no output charge.
Source: https://developers.openai.com/api/docs/guides/decisions .
Budget: 200 additional calls, estimated below $0.02, ceiling $0.05.
Keep prior four-model snapshot and chat baseline. Combined snapshot must disclose
that the Decisions contender was measured in a subsequent pass; never pretend
old cached calls were fresh new latency measurements. No dataset or label edits.

## Diverse 500-example study

Extend the existing 200 examples unchanged with 10 categories of 30 examples:
evidence sufficiency, policy eligibility, temporal status, document consistency,
workflow completion, transaction reconciliation, change impact, commitment detection,
constraint selection, and content policy boundaries. New examples and labels are
assistant-authored synthetic data, not independent human ground truth. Use fictional
entities and supplied rules; no external factual retrieval. Balance new category labels,
include missing evidence, exceptions, conflicting signals, and varied representations.
Review labels against rules and freeze hashes before inference. Prior results are known;
this is exploratory, not a blind held-out study or production validation.

Primary metric remains pooled exact accuracy with errors counted wrong. Also report
an unweighted mean of all 18 category accuracies and separate old-200/new-300 accuracy.
Retain the pre-existing deterministic recommendation rule; category averages are a
sensitivity analysis, not a new post-hoc selection rule. Paired McNemar remains exploratory
because authored examples may be dependent. A 2-point gap is not automatically meaningful.

Compare Jev, Gemini Decision, OpenAI Luna Decisions, Haiku chat, and Luna chat with
identical evidence, existing untuned prompts, concurrency 2/model, fresh cache and no
retries. 2,500 requests. Expected inference spend below $0.30 based on prior usage;
planning ceiling $0.50, verified against current token sizes before starting. Preserve
all old snapshots. No push/publication or deployment is part of this extension.

Final configuration: `studies/diverse-500/models.yaml` removes the legacy 18 RPM
client cap for this study only. The key is a paid OpenRouter account; concurrency
remains two per model. Upstream rate-limit errors are recorded, never automatically
resent. Latency excludes client queuing and includes HTTP round trip from this machine.
The frozen manifest includes dataset, model configuration, and measurement source hashes.

```bash
uv run python scripts/freeze_diverse_study.py
uv run arena --models-file studies/diverse-500/models.yaml run --fresh --attempts 1 --concurrency 2 --out reports/diverse-500.json
```

Post-inference reporting correction: the old saturation boilerplate incorrectly claimed
that most models exceeding 95% meant the dataset could not distinguish quality. Replaced
that sentence with a caution to inspect paired comparisons and category results. Also
replaced the blanket instruction to treat few-point gaps as noise with uncertainty/label
cautions. No change to scoring, thresholds, selection logic, prompts, labels, or measurements.
Frozen run source hashes remain preserved; snapshot manifest separately hashes these two
reporting-only file revisions.
