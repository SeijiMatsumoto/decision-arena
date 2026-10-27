# Results snapshot: 2026-10-27 18:39 UTC

11 models × 119 examples across 8 datasets, all called through OpenRouter. Latency is the client-side round trip from one machine, so it includes network time; cost is what OpenRouter reported per call at the time. The datasets are small and synthetic (see [Caveats](../../README.md#caveats)), so treat accuracy gaps of a few points as noise. They were written before the first run and not changed after seeing results; the question format (noul / choice / score) originated with Jev, and LLMs get a plain, untuned prompt. Raw data: [`report.json`](report.json).

## Overall

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

## Accuracy by dataset

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

## Takeaways ([how these are derived](../../README.md#takeaways-which-model-to-use-for-what))

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
