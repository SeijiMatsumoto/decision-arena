# Decision Arena

Run decision models (Jev and others) side by side on the same labeled evals, then compare accuracy,
calibration, latency, and cost.

Decision models answer bounded questions instead of generating text: `choice` (pick one label),
`noul` (probability that something is true), `score` (position on an ordered scale). OpenRouter
puts about 22 of them behind one Decisions API, so adding a model to this project means adding
one line with its model ID.

## Setup

```bash
uv sync
cp .env.example .env   # add OPENROUTER_API_KEY
```

## Web UI

```bash
cd web && npm install && npm run build && cd ..
uv run arena serve            # http://127.0.0.1:8000
```

- **Results:** stat tiles, quality-vs-latency and quality-vs-cost scatter plots (decision models vs. LLMs), a leaderboard heatmap per dataset, and accuracy by scenario. Click a dataset to see every model's answer per example, filter to misses or disagreements, and open any row for per-label probabilities.
- **Run evals:** pick models and datasets, start a run, and watch progress. Results open when it finishes.
- **Playground:** ask one ad-hoc question (or any dataset example) to many models at once and compare their answers, latency and cost.

To work on the UI: run `uv run arena serve --reload` in one terminal and `cd web && npm run dev` in another (Vite proxies `/api` to port 8000).

To try it with no API key, run `uv run arena run --models mock-decider,mock-decider-lite,mock-flash-llm,mock-frontier-llm` and open Results.

## CLI usage

```bash
uv run arena list                                      # datasets + models
uv run arena run                                       # all enabled models x all datasets
uv run arena run --models jev-1.14,luna-decisions --datasets lead_relevance,company_match
uv run arena run --limit 3                             # smoke test: 3 examples per dataset
uv run arena run --misses                              # also list examples models got wrong
uv run arena show --misses                             # re-print the latest report
uv run arena run --models mock-decider,mock-flash-llm   # offline, no key needed
```

Each run writes `reports/run-<timestamp>.json` and a matching `.html`. The HTML shows a grid with
one row per example and one column per model, so you can compare outputs side by side. Responses
are cached in `.cache/`, keyed on the exact request. Rerunning or adding one new model only pays for
what's new.

## Models (`models.yaml`)

| provider    | what it is                                                                 |
|-------------|----------------------------------------------------------------------------|
| `decisions` | OpenRouter `POST /api/alpha/decisions`. Jev, Luna Decisions, Microsoft Decision-1, Liquid D1, Clef, ... Set `base_url` for a Jev-compatible self-hosted server (e.g. Laya). |
| `llm`       | A normal chat model forced into the same label space via JSON schema. Enabled by default (cheap, Haiku-class only): Haiku 5.5, GPT-6 Luna, Gemini 3.5 Flash-Lite, DeepSeek V4 Flash. They answer the question: does the decision model beat a cheap LLM on speed and cost, and how much quality does that cost? |
| `mock`      | Deterministic noisy oracle, for testing the pipeline offline.               |

## Metrics

- **All:** accuracy, p50/p95 latency (cached calls excluded), cost per 1k calls, error count, accuracy by scenario tag.
- **noul:** AUC, Brier, ECE, *best threshold* and accuracy at it. Each model's probabilities are calibrated differently, so a 0.5 cutoff is unfair to some of them. Also NDCG and top-1 hit for examples grouped under one search, which shows how well `p_true` ranks candidates.
- **choice:** macro-F1 and confusion matrix (in the JSON).
- **score:** exact accuracy, within-one-level, MAE.
- **Cross-model:** pairwise agreement and a ranked list of the examples models get wrong.

## Takeaways (which model to use for what)

`recommend.py` turns a report into recommendations with fixed rules and no LLM, so the same report always gives the same answer. You see them at the top of Results, on each dataset page, and at the end of `arena show`.

1. **Contenders:** models within 2 points of the top accuracy that a paired exact McNemar test does not show to be significantly worse (p < 0.05). The test covers large datasets, where small gaps can be real; the 2-point margin covers small ones, where even a 10-point gap can fail the test.
2. **Use:** the contender with the best combined cost and latency rank, with accuracy breaking ties. **Most accurate**, **Fastest** and **Cheapest** contenders are listed when they differ.
3. **Avoid:** models significantly worse than the top, or with failed calls.
4. **Notes:**
   - Datasets where most models score at least 95%, so quality can't be compared.
   - Best decision model vs best LLM, with speed and cost ratios.
   - A better yes/no cutoff for a pick, when it gains at least 2 points.
   - Scenario tags where a pick scores below 80%.

The thresholds are constants at the top of `recommend.py`.

<!-- snapshot:start -->
## Results snapshot (2026-10-27)

One run on 2026-10-27: 11 models × 119 examples across 8 datasets, all called through OpenRouter. Latency is the client-side round trip from one machine, so it includes network time; cost is what OpenRouter reported per call at the time. The datasets are small and synthetic (see Caveats), so treat accuracy gaps of a few points as noise. The datasets were written before the first run and not changed after seeing results; the question format (noul / choice / score) originated with Jev and LLMs get a plain, untuned prompt. Regenerate this section with `uv run arena snapshot --write`.

### Overall

| Model | Kind | Accuracy | Median latency | p95 latency | $ per 1k calls |
|---|---|---:|---:|---:|---:|
| `typesafe/jev-1.14` | Decision | 99.2% (118/119) | 185ms | 348ms | $0.0183 |
| `cloudflare/clef-flash` | Decision | 98.3% (117/119) | 370ms | 568ms | $0.0056 |
| `anthropic/claude-haiku-5.5` | LLM | 98.3% (117/119) | 1.4s | 2.5s | $0.0608 |
| `openai/gpt-5.4-nano` | LLM | 97.5% (116/119) | 1.1s | 2.6s | $0.0856 |
| `liquid/d1` | Decision | 96.6% (115/119) | 229ms | 480ms | $0.0031 |
| `microsoft/microsoft-decision-1` | Decision | 96.6% (115/119) | 262ms | 421ms | $0.0062 |
| `openai/gpt-6-luna-decisions` | Decision | 95.8% (114/119) | 297ms | 517ms | $0.0252 |
| `google/gemini-3.5-flash-lite` | LLM | 95.8% (114/119) | 815ms | 1.2s | $0.1146 |
| `deepseek/deepseek-v4-flash` | LLM | 95.0% (113/119) | 1.1s | 2.7s | $0.0168 |
| `openai/gpt-6-luna` | LLM | 95.0% (113/119) | 2.0s | 5.3s | $0.0478 |
| `mistralai/mistral-small-3.2-24b-instruct` | LLM | 89.9% (107/119) | 714ms | 1.9s | $0.0174 |

### Accuracy by dataset

| Model | agent action risk | company match | entity resolution | lead relevance | page type | reply intent | support routing | ticket urgency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| jev-1.14 | 100% | 100% | 100% | 95.2% | 100% | 100% | 100% | 100% |
| clef-flash | 92.9% | 92.3% | 100% | 100% | 100% | 100% | 100% | 100% |
| haiku-5.5 | 100% | 100% | 100% | 100% | 100% | 93.8% | 100% | 91.7% |
| gpt-5.4-nano | 100% | 100% | 83.3% | 95.2% | 100% | 100% | 100% | 100% |
| liquid-d1 | 92.9% | 100% | 91.7% | 90.5% | 100% | 100% | 100% | 100% |
| ms-decision-1 | 100% | 92.3% | 100% | 95.2% | 100% | 100% | 100% | 83.3% |
| luna-decisions | 92.9% | 100% | 100% | 90.5% | 100% | 87.5% | 100% | 100% |
| gemini-3.5-flash-lite | 100% | 100% | 91.7% | 100% | 100% | 87.5% | 100% | 83.3% |
| deepseek-v4-flash | 92.9% | 92.3% | 100% | 95.2% | 100% | 100% | 100% | 75% |
| gpt-6-luna | 92.9% | 92.3% | 100% | 90.5% | 100% | 100% | 100% | 83.3% |
| mistral-small-3.2 | 85.7% | 76.9% | 83.3% | 76.2% | 100% | 100% | 100% | 100% |

### Takeaways (rules described in the Takeaways section above)

- **Use: jev-1.14.** Best combined cost and speed among models within 2 points of the top and not significantly worse (99% accurate, 185ms median, $0.0183 per 1k calls).
- **Cheapest: clef-flash.** Lowest cost, one of 4 models within 2 points of the top (98% accurate, 370ms median, $0.0056 per 1k calls).
- **Avoid: mistral-small-3.2.** Significantly less accurate than jev-1.14 (9 points lower, p=0.003).
- Most models score at least 95% here, so this dataset does not separate them on quality; the picks are driven by cost and speed. Add harder or real examples.
- Best decision model (jev-1.14, 99%) vs best LLM (haiku-5.5, 98%): no significant accuracy difference; the decision model is 7.7× faster and 3.3× cheaper.

| Use case | Use | Cheaper / faster alternative | Avoid |
|---|---|---|---|
| agent action risk | jev-1.14 | ms-decision-1 (cheapest) | — |
| company match | jev-1.14 | liquid-d1 (cheapest) | — |
| entity resolution | jev-1.14 | clef-flash (cheapest) | — |
| lead relevance | clef-flash | — | — |
| page type | liquid-d1 | — | — |
| reply intent | liquid-d1 | — | — |
| support routing | liquid-d1 | — | — |
| ticket urgency | liquid-d1 | — | — |
<!-- snapshot:end -->

## Datasets

Each YAML file holds one question definition plus labeled examples. Every example is tagged with
a scenario so weaknesses show up by category instead of disappearing into one accuracy number.

| dataset | type | scenario |
|---|---|---|
| `lead_relevance` | noul | People finder: does this profile match the search *now*? |
| `company_match` | noul | Company finder: firmographic fit, acquired companies, adjacent industries |
| `entity_resolution` | noul | Are two records the same person or company? (dedup) |
| `page_type` | choice | Crawler triage: is this a team page worth extracting people from? |
| `reply_intent` | choice | Classify replies to outreach (interested / not now / wrong person ...) |
| `support_routing` | choice | Overlapping categories, sarcasm, negation, long tickets |
| `ticket_urgency` | score | Urgency by impact, not tone |
| `agent_action_risk` | noul | Should an agent tool call be held for approval? (incl. prompt injection) |

Tags: `clear`, `edge`, `distractor` (surface features point to the wrong answer), `adversarial`
(prompt injection, misleading tone or URL), `stale-data`, `multilingual`, `negation`, `sarcasm`, `long`.

To add a dataset, drop a YAML file into `datasets/` with the same shape. Loading validates every
`expected` value against the question's labels.

## Use cases worth testing

The two you already use, relevance and type classification, cover most of a finder app.
Other uses that fit the same pattern:

1. **Pipeline stages in a finder app.** A people or company finder is really a chain of decisions: `page_type` (where people data lives), `lead_relevance` (does this person match), `entity_resolution` (merge duplicates), then `reply_intent` after outreach. Each stage is cheap enough to run on every item.
2. **Reranking.** A `noul` probability doubles as a relevance score. Sorting candidates by `p_true` gives you a reranker with no extra model (see NDCG).
3. **Agent guardrails.** Gate each tool call with a `noul` before it executes. Latency matters here because the check sits on every step of the agent.
4. **Cascades and routing.** Let the decision model handle the confident cases. Send low-confidence ones to a bigger LLM or a human. The calibration metrics tell you where to set that cutoff.
5. **LLM-output grading.** Use a `noul` or `score` as an eval judge ("is this answer grounded in the source?"). It's much cheaper than an LLM judge, so you can grade every production trace, not just a sample.
6. **Data quality.** Flag stale, garbled, or contradictory scraped fields before they reach users.
7. **Multi-question passes.** The API accepts several questions per `state`, so one call can return relevance, seniority score, and region together. That isn't benchmarked here yet; every dataset asks one question.

## Caveats

- For LLMs, `price_in`/`price_out` in `models.yaml` are only used when OpenRouter's response has no `usage.cost`. `extra` turns reasoning off on models that think by default, so latency comparisons are fair. Remove it to measure them with reasoning on.

- Model IDs come from OpenRouter's Jev guide (Oct 2026). Not every model necessarily supports every question type; unsupported ones show up as per-example errors, not crashes.
- `laya-local` is untested; check the self-hosted server's actual route before enabling it.
- About 120 hand-labeled examples is enough to spot differences between models, not to rank close ones reliably. Treat a 1-2 point gap as noise and grow the datasets that matter to you.
