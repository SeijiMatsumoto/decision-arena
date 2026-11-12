from decision_arena.study_metrics import study_metrics


def test_equal_category_weighting_and_failures_in_cohorts():
    report = {'models': [{'name': 'm'}], 'datasets': {
        'small': {'examples': [{'id': 'a', 'expected': True, 'tags': []}],
                  'predictions': {'m': {'a': {'label': 'true'}}}},
        'large': {'examples': [
            {'id': 'b', 'expected': 'yes', 'tags': ['synthetic-v3']},
            {'id': 'c', 'expected': 'yes', 'tags': ['synthetic-v3']},
            {'id': 'd', 'expected': 'yes', 'tags': ['synthetic-v3']}],
                  'predictions': {'m': {'b': {'label': 'yes'}, 'c': {'error': 'timeout'}}}},
    }}
    metrics = study_metrics(report)['m']
    assert metrics['category_mean_accuracy'] == (1 + 1/3)/2
    assert metrics['cohorts']['previous_200']['accuracy'] == 1
    assert metrics['cohorts']['new_300'] == {'correct': 1, 'n': 3, 'accuracy': 1/3}


def test_saturation_note_does_not_assert_equivalent_quality():
    import json
    from pathlib import Path

    from decision_arena.recommend import recommend

    path = Path(__file__).resolve().parents[1] / 'snapshots/2026-11-12_1537/report.json'
    notes = recommend(json.loads(path.read_text()))['overall']['notes']
    assert any('High scores alone do not establish equivalent quality' in note for note in notes)
    assert not any('does not separate them on quality' in note for note in notes)
