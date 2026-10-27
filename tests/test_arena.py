import asyncio
from pathlib import Path

import pytest

from decision_arena.datasets import Example, Question, load_datasets
from decision_arena.metrics import auc, best_threshold, macro_f1, ndcg
from decision_arena.providers import ModelSpec, normalize_decision
from decision_arena.recommend import mcnemar_p, recommend
from decision_arena.runner import run_eval
from decision_arena.snapshot import END, START, save_snapshot, write_index, write_readme_pointer

ROOT = Path(__file__).resolve().parents[1]


def test_all_datasets_load_and_labels_are_valid():
    datasets = load_datasets(ROOT / "datasets")
    assert len(datasets) >= 8
    for d in datasets:
        assert len(d.examples) >= 10, d.name
        # Each dataset should exercise more than easy cases.
        assert any(t != "clear" for e in d.examples for t in e.tags), d.name


def test_question_criteria_validation():
    with pytest.raises(ValueError):
        Question(type="noul", instructions="x", criteria={"yes": "a", "no": "b"})
    with pytest.raises(ValueError):
        Question(type="score", instructions="x", criteria={"a": "b"})


def test_normalize_answers():
    noul = Question(type="noul", instructions="x", criteria={"true": "a", "false": "b"})
    assert normalize_decision(noul, {"type": "noul", "noul": 0.2}).label == "false"

    score = Question(type="score", instructions="x", criteria=["lo", "mid", "hi"])
    d = normalize_decision(score, {"score": 1.6, "probabilities": {"0": 0.1, "1": 0.2, "2": 0.7}})
    assert d.label == "2" and d.score == 1.6
    assert normalize_decision(score, {"score": 0.4}).label == "0"


def test_metrics():
    assert auc([(True, 0.9), (False, 0.1)]) == 1.0
    assert auc([(True, 0.1), (False, 0.9)]) == 0.0
    assert best_threshold([(True, 0.3), (False, 0.2)]) == (0.3, 1.0)
    assert macro_f1([("a", "a"), ("b", "b")], ["a", "b"]) == 1.0
    assert ndcg([True, False]) == 1.0
    assert ndcg([False, True]) < 1.0


def test_mock_run_end_to_end(tmp_path):
    datasets = load_datasets(ROOT / "datasets")
    models = [
        ModelSpec(name="perfect", provider="mock", model="mock", accuracy=1.0),
        ModelSpec(name="weak", provider="mock", model="mock", accuracy=0.5),
    ]
    report = asyncio.run(run_eval(datasets, models, tmp_path))
    for name, data in report["datasets"].items():
        assert data["metrics"]["perfect"]["accuracy"] == 1.0, name
        assert data["metrics"]["perfect"]["errors"] == 0
        assert "perfect | weak" in data["agreement"]
    assert report["datasets"]["lead_relevance"]["metrics"]["perfect"]["ndcg"] == 1.0


def test_expected_label_bool():
    assert Example(id="x", state="s", expected=True).expected_label == "true"


def test_mcnemar():
    assert mcnemar_p(0, 0) == 1.0
    assert mcnemar_p(3, 3) == 1.0
    assert mcnemar_p(10, 0) < 0.01
    assert mcnemar_p(2, 0) == 0.5


def test_recommend_is_deterministic_and_flags_weak_models(tmp_path):
    datasets = load_datasets(ROOT / "datasets")
    models = [
        ModelSpec(name="perfect", provider="mock", model="mock", accuracy=1.0, mock_cost=1e-6),
        ModelSpec(
            name="pricey", provider="mock", model="mock", kind="llm", accuracy=1.0, mock_cost=1e-3
        ),
        ModelSpec(name="weak", provider="mock", model="mock", accuracy=0.5),
    ]
    report = asyncio.run(run_eval(datasets, models, tmp_path))
    first, second = recommend(report), recommend(report)
    assert first == second
    overall = first["overall"]
    assert overall["picks"][0]["model"] == "perfect"  # tied with pricey, but cheaper
    assert "weak" in {a["model"] for a in overall["avoid"]}
    assert any("decision model" in n for n in overall["notes"])


def test_snapshot_folder_index_and_readme_pointer(tmp_path):
    datasets = load_datasets(ROOT / "datasets")
    models = [ModelSpec(name="perfect", provider="mock", model="mock", accuracy=1.0)]
    report = asyncio.run(run_eval(datasets, models, tmp_path / "cache"))
    snapshots = tmp_path / "snapshots"
    folder = save_snapshot(report, snapshots)
    assert (folder / "report.json").exists()
    assert (folder / "README.md").read_text().startswith("# Results snapshot: ")
    write_index(snapshots)
    assert folder.name in (snapshots / "README.md").read_text()
    readme = tmp_path / "README.md"
    readme.write_text("# X\n\n## Datasets\n")
    write_readme_pointer(readme, snapshots)
    write_readme_pointer(readme, snapshots)  # second write replaces, never duplicates
    text = readme.read_text()
    assert text.count(START) == 1 and text.count(END) == 1
    assert f"snapshots/{folder.name}/" in text
    assert text.index(START) < text.index("## Datasets")
