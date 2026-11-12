"""Save a completed, frozen diverse-500 report as an auditable local snapshot."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from decision_arena.datasets import load_datasets
from decision_arena.providers import load_models
from decision_arena.snapshot import save_snapshot, write_index, write_readme_pointer
from decision_arena.study_metrics import study_metrics
from decision_arena.summary import write_summary

ROOT = Path(__file__).resolve().parents[1]
study = ROOT / 'studies/diverse-500'
manifest = json.loads((study / 'manifest.json').read_text())
report = json.loads((ROOT / 'reports/diverse-500.json').read_text())
assert report['models'] == [m.model_dump() for m in load_models(study / 'models.yaml')]
assert hashlib.sha256((study / 'models.yaml').read_bytes()).hexdigest() == manifest['run_model_config_sha256']
reporting_changes = {}
for path, digest in manifest['source_hashes'].items():
    current = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    if current != digest:
        assert path in ('src/decision_arena/recommend.py', 'src/decision_arena/snapshot.py'), path
        reporting_changes[path] = current
manifest['postprocessing_source_hashes'] = reporting_changes
manifest['postprocessing_note'] = (
    'After inference, corrected saturation and small-gap caution wording only; '
    'no changes to selection rules, scoring, prompts, examples, labels, or measurements.')
for path, digest in manifest['datasets'].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
for dataset in load_datasets(ROOT / 'datasets'):
    data = report['datasets'][dataset.name]
    assert data['examples'] == [e.model_dump() for e in dataset.examples]
    assert data['question'] == dataset.question.model_dump()
    assert all(len(preds) == len(dataset.examples) for preds in data['predictions'].values())
assert sum(len(d['examples']) for d in report['datasets'].values()) == 500
stats = study_metrics(report)
folder = save_snapshot(report, ROOT / 'snapshots')
write_summary(report, ROOT, folder)
(folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(folder / 'execution.json').write_text((study / 'execution.json').read_text())
(folder / 'study-metrics.json').write_text(json.dumps(stats, indent=2) + '\n')
costs = []
unknown = 0
errors = 0
for data in report['datasets'].values():
    for preds in data['predictions'].values():
        for pred in preds.values():
            errors += 'error' in pred
            if pred.get('cost') is None:
                unknown += 1
            else:
                costs.append(pred['cost'])
text = f'''## Diverse 500-example protocol

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

Reported inference cost: ${sum(costs):.6f}; {unknown} predictions have unknown cost;
{errors} failed calls. No paid labeling or judging calls. See [frozen manifest](manifest.json),
[machine-readable category/cohort metrics](study-metrics.json), and
[pre-run protocol](../../EXPERIMENT.md#diverse-500-example-study).

'''
p = folder / 'README.md'
p.write_text(p.read_text().replace('## Overall', text + '## Overall', 1))
write_index(ROOT / 'snapshots')
write_readme_pointer(ROOT / 'README.md', ROOT / 'snapshots')
print(folder)
print(json.dumps({m: {'category_mean': d['category_mean_accuracy'], 'cohorts': d['cohorts']}
                  for m, d in stats.items()}, indent=2))
