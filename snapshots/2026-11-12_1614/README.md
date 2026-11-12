# Results snapshot: 2026-11-12 16:14 UTC

5 models × 500 examples across 18 datasets, all called through OpenRouter. Latency is the client-side round trip from one machine, so it includes network time; cost is what OpenRouter reported per call at the time. The datasets are small and synthetic (see [Caveats](../../README.md#caveats)); interpret accuracy gaps with paired uncertainty and label limitations. The original examples predate the first run; the expansion and its labels were assistant-authored after earlier results, without independent human review. Labels were fixed before the final comparison; this is not a blind held-out test. The question format (noul / choice / score) originated with Jev, and LLMs get a plain, untuned prompt. Raw data: [`report.json`](report.json).

## Diverse 500-example protocol

This pass measured all five contenders on all 500 frozen examples, with a fresh local
cache, two concurrent requests per model, and no retries. No prior predictions were
replayed into this comparison. Provider-side caching is uncontrolled. Latency is the
client HTTP round trip from one machine, excluding queuing; this is one pass, not a
repeated latency study.

The original 200 examples and all eight original task definitions are unchanged.
The 300 new examples span ten new categories, 30 each, with exactly ten examples per
label in each category. Rules and evidence are self-contained and fictional. The
new labels were checked by their author against the supplied rules before inference,
but are not independently human-reviewed. Earlier model results were known when the
suite was designed; no examples or labels were changed after this pass began.
Related examples and deliberately paired boundary cases reduce independence.
500 examples is a coverage target, not a statistical-power guarantee.

Pooled exact accuracy remains the primary metric and drives the unchanged deterministic
recommendation rule. Category-average accuracy is an unweighted mean over all 18
categories, shown as a sensitivity analysis. Errors count as wrong in both and in the
old/new cohort table. Non-significance is not proof of equivalence; paired tests and
category findings are exploratory, with no multiple-comparison correction.

Reported inference cost: $0.088611; 0 predictions have unknown cost;
0 failed calls. No paid labeling or judging calls. See [frozen manifest](manifest.json),
[machine-readable category/cohort metrics](study-metrics.json), and
[pre-run protocol](../../EXPERIMENT.md#diverse-500-example-study).

## Finding

Gemini Decision is the existing rule's operational pick on this broader suite:
492/500 (98.4%), 284ms median, $0.0219 per 1,000 calls. Jev remains fastest and
cheapest (142ms, $0.0186 per 1,000) but scores 483/500 (96.6%). Its paired comparison
against Gemini is borderline at uncorrected p≈0.049 and is sensitive to synthetic
case dependence and label review; this is not a general model-quality ranking.
The equal-weight category means preserve Gemini's lead (98.5% versus Jev's 96.9%).
Luna chat reaches 299/300 on the new categories, versus Luna Decisions at 273/300,
illustrating that broader rules and reasoning can change the speed/quality tradeoff.
Jev's weakest new categories are temporal status (25/30), document consistency (26/30),
and policy eligibility (26/30). See the [post-run author label review](label-review.md).

## Overall

| Model | Kind | Accuracy | Median latency | p95 latency | $ per 1k calls |
|---|---|---:|---:|---:|---:|
| `google/gemini-decision-1` | Decision | 98.4% (492/500) | 284ms | 521ms | $0.0219 |
| `openai/gpt-6-luna` | LLM | 98.2% (491/500) | 2.5s | 5.4s | $0.0422 |
| `anthropic/claude-haiku-5.5` | LLM | 97.8% (489/500) | 855ms | 1.4s | $0.0704 |
| `typesafe/jev-1.14` | Decision | 96.6% (483/500) | 142ms | 230ms | $0.0186 |
| `openai/gpt-6-luna-decisions` | Decision | 93.2% (466/500) | 285ms | 550ms | $0.0241 |

## Category weighting and cohorts

Errors and missing predictions count as wrong. Category mean weights each dataset equally; this is a sensitivity analysis, not a different pick rule.

| Model | Category mean | Previous 200 | New 300 |
|---|---:|---:|---:|
| gemini-decision-1 | 98.5% | 99.5% (199/200) | 97.7% (293/300) |
| jev-1.14 | 96.9% | 99.0% (198/200) | 95.0% (285/300) |
| luna-decisions | 93.5% | 96.5% (193/200) | 91.0% (273/300) |
| haiku-5.5 | 97.9% | 97.5% (195/200) | 98.0% (294/300) |
| gpt-6-luna | 98.0% | 96.0% (192/200) | 99.7% (299/300) |

## Accuracy by dataset

| Model | agent action risk | change impact | commitment detection | company match | constraint selection | content boundaries | document consistency | entity resolution | evidence sufficiency | lead relevance | page type | policy eligibility | reply intent | support routing | temporal status | ticket urgency | transaction reconciliation | workflow completion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini-decision-1 | 100% | 100% | 100% | 100% | 96.7% | 100% | 93.3% | 100% | 96.7% | 100% | 100% | 96.7% | 100% | 100% | 93.3% | 96.7% | 100% | 100% |
| gpt-6-luna | 95.7% | 100% | 100% | 86.4% | 100% | 100% | 100% | 100% | 96.7% | 90% | 100% | 100% | 96% | 100% | 100% | 100% | 100% | 100% |
| haiku-5.5 | 100% | 96.7% | 96.7% | 95.5% | 96.7% | 100% | 90% | 100% | 100% | 100% | 100% | 100% | 96% | 100% | 100% | 90% | 100% | 100% |
| jev-1.14 | 100% | 100% | 100% | 100% | 100% | 96.7% | 86.7% | 100% | 100% | 93.3% | 100% | 86.7% | 100% | 100% | 83.3% | 100% | 96.7% | 100% |
| luna-decisions | 95.7% | 96.7% | 100% | 95.5% | 86.7% | 96.7% | 93.3% | 100% | 100% | 90% | 100% | 76.7% | 92% | 100% | 73.3% | 100% | 96.7% | 90% |

## Takeaways ([how these are derived](../../README.md#takeaways-which-model-to-use-for-what))

- **Use: gemini-decision-1.** Best combined cost and speed among models within 2 points of the top and not significantly worse (98% accurate, 284ms median, $0.0219 per 1k calls).
- **Avoid: luna-decisions.** Significantly less accurate than gemini-decision-1 (5 points lower, p=0.000).
- **Avoid: jev-1.14.** Significantly less accurate than gemini-decision-1 (2 points lower, p=0.049).
- Most models score at least 95% here. High scores alone do not establish equivalent quality; inspect paired comparisons and category results. Real examples and independent labels are needed to establish generalization.
- Best decision model (gemini-decision-1, 98%) vs best LLM (gpt-6-luna, 98%): no significant accuracy difference; the decision model is 8.8× faster and 1.9× cheaper.

| Use case | Use | Cheaper / faster alternative | Avoid |
|---|---|---|---|
| agent action risk | jev-1.14 | — | — |
| change impact | jev-1.14 | — | — |
| commitment detection | jev-1.14 | — | — |
| company match | jev-1.14 | — | — |
| constraint selection | jev-1.14 | — | — |
| content boundaries | gemini-decision-1 | — | — |
| document consistency | gpt-6-luna | — | — |
| entity resolution | jev-1.14 | — | — |
| evidence sufficiency | jev-1.14 | — | — |
| lead relevance | gemini-decision-1 | — | — |
| page type | jev-1.14 | — | — |
| policy eligibility | gpt-6-luna | — | luna-decisions |
| reply intent | jev-1.14 | — | — |
| support routing | jev-1.14 | — | — |
| temporal status | gpt-6-luna | — | luna-decisions |
| ticket urgency | jev-1.14 | — | — |
| transaction reconciliation | gemini-decision-1 | — | — |
| workflow completion | jev-1.14 | — | — |
