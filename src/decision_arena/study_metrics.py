"""Failure-inclusive category and cohort summaries for the diverse synthetic study."""
from __future__ import annotations

import statistics
from typing import Any


def study_metrics(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for model in report['models']:
        name = model['name']
        categories = {}
        cohorts = {'previous_200': [0, 0], 'new_300': [0, 0]}
        for category, data in report['datasets'].items():
            correct = 0
            for example in data['examples']:
                expected = example['expected']
                label = ('true' if expected else 'false') if isinstance(expected, bool) else str(expected)
                pred = data['predictions'].get(name, {}).get(example['id'], {})
                hit = int('error' not in pred and pred.get('label') == label)
                correct += hit
                cohort = 'new_300' if 'synthetic-v3' in example.get('tags', []) else 'previous_200'
                cohorts[cohort][0] += hit
                cohorts[cohort][1] += 1
            if data['examples']:
                categories[category] = correct / len(data['examples'])
        result[name] = {
            'category_mean_accuracy': statistics.mean(categories.values()) if categories else None,
            'categories': categories,
            'cohorts': {key: {'correct': c, 'n': n, 'accuracy': c/n if n else None}
                        for key, (c, n) in cohorts.items()},
        }
    return result
