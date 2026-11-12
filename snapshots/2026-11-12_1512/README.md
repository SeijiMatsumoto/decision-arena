# Results snapshot: 2026-11-12 15:12 UTC

3 models × 119 examples across 8 datasets, all called through OpenRouter. Latency is the client-side round trip from one machine, so it includes network time; cost is what OpenRouter reported per call at the time. The datasets are small and synthetic (see [Caveats](../../README.md#caveats)), so treat accuracy gaps of a few points as noise. They were written before the first run and not changed after seeing results; the question format (noul / choice / score) originated with Jev, and LLMs get a plain, untuned prompt. Raw data: [`report.json`](report.json).

## Gemini comparison protocol and finding

This run adds Gemini Decision 1 against the previous decision-model pick and best
generative baseline. All 357 calls were fresh local requests, with two concurrent
requests per model, no retries, no errors, and $0.011960 total reported inference
cost. Three preceding Gemini type checks cost an additional $0.000066.
See the [pre-run protocol](../../EXPERIMENT.md) and [dataset hashes and run settings](manifest.json).
Historical snapshots and caches are preserved. Provider-side caching is uncontrolled.

Gemini and Jev both answered 118/119 correctly (99.2%). Gemini missed `tu-02`
(ticket urgency: level 0 instead of 1); Jev missed `lr-b6` (hospital procurement
director relevance: false instead of true). This does not establish a quality
winner. Jev remains the overall operational pick: 2.2 times faster and about 18%
cheaper per call than Gemini in this pass. Gemini was 2.9 times faster and about
63% cheaper than Haiku. Gemini is the rule's lead-relevance pick, based on one
additional correct answer in only 21 examples; that needs a larger follow-up.

## Overall

| Model | Kind | Accuracy | Median latency | p95 latency | $ per 1k calls |
|---|---|---:|---:|---:|---:|
| `typesafe/jev-1.14` | Decision | 99.2% (118/119) | 147ms | 359ms | $0.0183 |
| `google/gemini-decision-1` | Decision | 99.2% (118/119) | 322ms | 525ms | $0.0224 |
| `anthropic/claude-haiku-5.5` | LLM | 98.3% (117/119) | 943ms | 1.9s | $0.0598 |

## Accuracy by dataset

| Model | agent action risk | company match | entity resolution | lead relevance | page type | reply intent | support routing | ticket urgency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| jev-1.14 | 100% | 100% | 100% | 95.2% | 100% | 100% | 100% | 100% |
| gemini-decision-1 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 91.7% |
| haiku-5.5 | 100% | 100% | 100% | 100% | 100% | 93.8% | 100% | 91.7% |

## Takeaways ([how these are derived](../../README.md#takeaways-which-model-to-use-for-what))

- **Use: jev-1.14.** Best combined cost and speed among models within 2 points of the top and not significantly worse (99% accurate, 147ms median, $0.0183 per 1k calls).
- Most models score at least 95% here, so this dataset does not separate them on quality; the picks are driven by cost and speed. Add harder or real examples.
- Best decision model (jev-1.14, 99%) vs best LLM (haiku-5.5, 98%): no significant accuracy difference; the decision model is 6.4× faster and 3.3× cheaper.

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
