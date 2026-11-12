"""Validate the 500-item study and freeze auditable inputs before inference."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import yaml

from decision_arena.datasets import load_datasets

ROOT = Path(__file__).resolve().parents[1]
selected = ['gemini-decision-1', 'jev-1.14', 'luna-decisions', 'haiku-5.5', 'gpt-6-luna']
previous = json.loads((ROOT/'snapshots/2026-11-12_1537/report.json').read_text())
datasets = load_datasets(ROOT/'datasets')
assert len(datasets) == 18
assert sum(len(d.examples) for d in datasets) == 500
new = [d for d in datasets if d.name not in previous['datasets']]
assert len(new) == 10
for d in datasets:
    if d.name in previous['datasets']:
        prior = previous['datasets'][d.name]
        assert d.question.model_dump() == prior['question']
        assert [e.model_dump() for e in d.examples] == prior['examples']
    else:
        assert len(d.examples) == 30
        assert sorted(Counter(e.expected_label for e in d.examples).values()) == [10, 10, 10]
        assert all('synthetic-v3' in e.tags for e in d.examples)
    states = [json.dumps(e.state, sort_keys=True) for e in d.examples]
    assert len(states) == len(set(states)), d.name
specs = yaml.safe_load((ROOT/'models.yaml').read_text())['models']
specs = [s for s in specs if s['name'] in selected]
assert len(specs) == 5
for spec in specs:
    # Run-specific concurrency two, without the legacy conservative RPM cap.
    # Paid OpenRouter key; upstream limits remain possible and failures count wrong.
    spec.pop('rpm', None)
    spec['max_attempts'] = 1
out = ROOT/'studies/diverse-500'
out.mkdir(parents=True, exist_ok=True)
config = out/'models.yaml'
config.write_text(yaml.safe_dump({'models': specs}, sort_keys=False))
manifest = {
    'study': 'diverse-500', 'source_revision': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'items': 500, 'previous_items': 200, 'new_items': 300, 'categories': 18,
    'new_categories': [d.name for d in new], 'models': selected,
    'concurrency_per_model': 2, 'max_attempts': 1, 'local_cache': 'fresh',
    'label_provenance': '119 original hand-written; 381 assistant-authored; no independent human review',
    'datasets': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted((ROOT/'datasets').glob('*.yaml'))},
    'run_model_config_sha256': hashlib.sha256(config.read_bytes()).hexdigest(),
    'source_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted((ROOT/'src/decision_arena').glob('*.py'))},
}
(out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(f'Frozen {len(datasets)} categories / 500 examples / 5 contenders at {out}')
