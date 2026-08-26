"""Task 2 status keeps legacy and current scorer provenance visible."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from memcommit.commands.semantic_eval.command import eval_app


def _write(directory: Path, name: str, value: dict[str, object]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(value), encoding="utf-8")


def _base_record(*, kind: str, started_at: str) -> dict[str, object]:
    return {
        "kind": kind,
        "started_at": started_at,
        "contract_valid": True,
        "pipeline": "same-pipeline",
        "effective_thinking": False,
        "provider": {
            "provider": "ollama",
            "model": "fixture-model",
            "model_digest": "a" * 64,
            "reasoning_effort": None,
        },
        "corpus": {
            "input_digest": "same-input",
            "selected_group_count": 1,
            "selected_left_count": 1,
            "selected_right_count": 1,
        },
        "timing": {
            "provider_completion_seconds": 1.0,
            "pipeline_seconds": 1.0,
            "total_seconds": 1.0,
        },
        "ledger_path": f"fixture-{started_at}.json",
    }


def test_task2_status_does_not_collapse_legacy_and_v2_scores(tmp_path: Path) -> None:
    legacy_v1 = _base_record(
        kind="memcommit.semantic-eval.task2-discovery",
        started_at="2026-01-01T00:00:00Z",
    )
    legacy_v1["lock"] = None
    legacy_v1["score"] = {
        "exact_structure_groups": 1,
        "exact_band_groups": 1,
        "expected_groups": 1,
        "member_counterpart_exact": 2,
        "member_counterpart_total": 2,
    }
    current_v1 = json.loads(json.dumps(legacy_v1))
    current_v1["started_at"] = "2026-01-01T00:00:01Z"
    current_v1["scorer_version"] = 2
    current_v1["lock"] = {"corpus_locked": True}

    legacy_v2 = _base_record(
        kind="memcommit.semantic-eval.task2-discovery-v2",
        started_at="2026-01-01T00:00:00Z",
    )
    legacy_v2["lock"] = None
    legacy_v2["score"] = {
        "exact_structure_groups": 1,
        "expected_groups": 1,
        "member_counterpart_exact": 2,
        "member_counterpart_total": 2,
    }
    current_v2 = json.loads(json.dumps(legacy_v2))
    current_v2["started_at"] = "2026-01-01T00:00:01Z"
    current_v2["scorer_version"] = 2
    current_v2["lock"] = {"corpus_locked": True}

    _write(tmp_path / "task2-discovery", "legacy.json", legacy_v1)
    _write(tmp_path / "task2-discovery", "current.json", current_v1)
    _write(tmp_path / "task2-discovery-v2", "legacy.json", legacy_v2)
    _write(tmp_path / "task2-discovery-v2", "current.json", current_v2)

    result = CliRunner().invoke(
        eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert result.output.count("scorer legacy-v1 · PRE-LOCK") == 2
    assert result.output.count("scorer v2 · LOCKED") == 2
    assert result.output.count("ollama:fixture-model") == 4
