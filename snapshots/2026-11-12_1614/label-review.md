# Post-run author review of shared misses

Labels remain exactly as frozen. This review was performed by the original author after
seeing predictions; it is not independent adjudication or human ground truth.

- `temporal_status-v3-15`: 10:00 at UTC-05:00 is 15:00 UTC. At 14:59 UTC,
  the permission has not started. Frozen label `inactive` retained.
- `temporal_status-v3-09`: 10:00 at UTC+02:00 is 08:00 UTC, inside the
  07:00–09:00 UTC interval. Frozen label `active` retained.
- `document_consistency-v3-29`: rounding precision is explicitly unspecified.
  Rounded 100 and exact 104 may agree under one precision and disagree under another;
  the supplied rule requires `unresolved` when comparison cannot be established.
- `cm-v2-04`: the supplied search is 50–500 employees; exactly 500 is included.
  The independent US restaurant SaaS description meets all supplied constraints.
- `lr-b6`: director of strategic sourcing at a US hospital satisfies procurement
  director-or-above, consistent with the original note equating strategic sourcing
  and procurement.

The broad result should still receive independent label review before a strong public
quality claim. The Jev/Gemini comparison is close to the uncorrected p=0.05 cutoff;
correlated synthetic cases and label disagreements can materially affect that conclusion.
