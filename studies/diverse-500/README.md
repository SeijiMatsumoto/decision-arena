# Diverse 500-example study

Frozen before inference: `manifest.json` hashes every dataset and measurement source file;
`models.yaml` captures the five selected contenders and run-specific settings. The original
200 examples are preserved byte-for-byte in their YAML files and semantically checked
against the previous snapshot by `scripts/freeze_diverse_study.py`.

The new 300 examples and labels were authored by the assistant, with 30 examples per new
category and exactly ten per label. Label review was by the same author, not an independent
reviewer. Rules distinguish missing evidence from explicit disqualification, use inclusive
and exclusive temporal boundaries, account for signed amendments, distinguish pending from
failed workflow steps, and define transaction fees and settlement. No external knowledge,
paid labeling, or model judging is used.

Known limits:

- This is intentionally synthetic and balanced, not sampled production traffic.
- Previously observed model results informed the choice to expand the suite.
- Constraint-selection examples deliberately include paired variants; other scenarios also
  share structure. Treat row-level paired significance tests as exploratory.
- All ten new categories are three-way choice tasks. The original suite retains Boolean
  and ordinal-score tasks. This expansion tests breadth, not every possible output format.
- Multilingual cases are a small slice, not a multilingual capability benchmark.
- The equal-weight mean over 18 category accuracies is a sensitivity analysis. The existing
  recommendation still uses pooled exact accuracy and the prior eligibility/cost/speed rule.

No dataset or label changes are permitted between freeze and completion. Any later label
correction must be versioned and reported alongside the original result, never silently
substituted into it. The final dated snapshot records actual predictions, cost, latency,
errors, category metrics, and old/new cohort accuracy.
