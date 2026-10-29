import json
from pathlib import Path

from arena_kit import contract

from decision_arena.summary import build_summary

ROOT = Path(__file__).resolve().parents[1]


def test_latest_snapshot_maps_onto_the_hub_contract():
    folder = sorted((ROOT / "snapshots").glob("*/report.json"))[-1].parent
    report = json.loads((folder / "report.json").read_text())
    summary = build_summary(report, ROOT, folder)
    contract.validate(summary)
    assert summary["mock"] is False
    assert f"**{summary['pick']['name']}**" in summary["headline"]
    assert [c["verdict"] for c in summary["contenders"]].count("pick") == 1
