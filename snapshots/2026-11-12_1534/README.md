# Results snapshot: 2026-11-12 15:34 UTC

4 models × 200 examples across 8 datasets, all called through OpenRouter. Latency is the client-side round trip from one machine, so it includes network time; cost is what OpenRouter reported per call at the time. The datasets are small and synthetic (see [Caveats](../../README.md#caveats)), so treat accuracy gaps of a few points as noise. The original examples predate the first run; the expansion and its labels were assistant-authored after earlier results, without independent human review. Labels were fixed before the final comparison; this is not a blind held-out test. The question format (noul / choice / score) originated with Jev, and LLMs get a plain, untuned prompt. Raw data: [`report.json`](report.json).

## Expansion protocol and provenance

All four contenders received the same 200 examples. The original 119 examples and question criteria are unchanged. The 81 expansion examples and labels were assistant-authored and are not independently human-reviewed. Labels were fixed before final inference. The author had seen earlier results, so this is exploratory rather than a blind held-out benchmark. The requested 71 additions would total 190; 81 were needed for 200.

GPT-6 Luna is the current OpenAI baseline. GPT-5 nano was excluded at the user's request because it is being retired; no Nano calls were made. All final calls used a fresh local cache, concurrency two per model, and no retries. Provider-side caching is uncontrolled. Luna request starts were limited to 18/min; client rate-limit waiting is excluded from measured latency.

### Original versus expansion accuracy (errors count as wrong)

| Model | Original (119) | Expansion (81) | Errors |
|---|---:|---:|---:|
| gemini-decision-1 | 118/119 (99.2%) | 81/81 (100.0%) | 0 |
| jev-1.14 | 119/119 (100.0%) | 80/81 (98.8%) | 0 |
| haiku-5.5 | 117/119 (98.3%) | 78/81 (96.3%) | 0 |
| gpt-6-luna | 111/119 (93.3%) | 81/81 (100.0%) | 0 |

Reported response costs: final comparison $0.028516; stopped preliminary 190-item pass $0.013073; total recorded $0.041589. The stopped pass is excluded from results. In-flight calls interrupted before a response was saved may have additional unrecorded billing.

At 200 synthetic examples, a small accuracy difference remains insufficient to claim a general quality winner. Correlated examples and unreviewed labels further limit inference. No production adoption, publication, or deployment is implied. See [protocol](../../EXPERIMENT.md) and [manifest](manifest.json).

## Overall

| Model | Kind | Accuracy | Median latency | p95 latency | $ per 1k calls |
|---|---|---:|---:|---:|---:|
| `typesafe/jev-1.14` | Decision | 99.5% (199/200) | 132ms | 224ms | $0.0181 |
| `google/gemini-decision-1` | Decision | 99.5% (199/200) | 291ms | 474ms | $0.0219 |
| `anthropic/claude-haiku-5.5` | LLM | 97.5% (195/200) | 856ms | 1.6s | $0.0587 |
| `openai/gpt-6-luna` | LLM | 96.0% (192/200) | 2.4s | 5.6s | $0.0439 |

## Accuracy by dataset

| Model | agent action risk | company match | entity resolution | lead relevance | page type | reply intent | support routing | ticket urgency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| jev-1.14 | 100% | 100% | 100% | 96.7% | 100% | 100% | 100% | 100% |
| gemini-decision-1 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 96.7% |
| haiku-5.5 | 100% | 100% | 100% | 100% | 100% | 96% | 100% | 86.7% |
| gpt-6-luna | 95.7% | 86.4% | 100% | 93.3% | 100% | 96% | 100% | 96.7% |

## Takeaways ([how these are derived](../../README.md#takeaways-which-model-to-use-for-what))

- **Use: jev-1.14.** Best combined cost and speed among models within 2 points of the top and not significantly worse (100% accurate, 132ms median, $0.0181 per 1k calls).
- **Avoid: gpt-6-luna.** Significantly less accurate than jev-1.14 (4 points lower, p=0.039).
- Most models score at least 95% here, so this dataset does not separate them on quality; the picks are driven by cost and speed. Add harder or real examples.
- Best decision model (jev-1.14, 100%) vs best LLM (haiku-5.5, 98%): no significant accuracy difference; the decision model is 6.5× faster and 3.2× cheaper.

| Use case | Use | Cheaper / faster alternative | Avoid |
|---|---|---|---|
| agent action risk | jev-1.14 | — | — |
| company match | jev-1.14 | — | — |
| entity resolution | jev-1.14 | — | — |
| lead relevance | gemini-decision-1 | — | — |
| page type | jev-1.14 | — | — |
| reply intent | jev-1.14 | — | — |
| support routing | jev-1.14 | — | — |
| ticket urgency | jev-1.14 | — | — |
