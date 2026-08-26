"""CLI contracts for staged semantic evaluation campaigns."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import memcommit.commands.semantic_eval.command as command
from memcommit.provider_types import ProviderIdentity
from memcommit.query_provider import QueryProviderError


runner = CliRunner(mix_stderr=False)


class FakeProvider:
    identity = ProviderIdentity(
        provider="ollama",
        model="qwen3.6:35b-a3b",
        model_digest="abcdef0123456789",
        runtime="ollama/test",
    )
    timeout = 10.0
    last_run = None

    def complete(self, prompt, *, operation, output_schema=None):
        raise AssertionError("the mocked campaign owns provider completion")

    def query(self, source_name, source_content, question):
        raise AssertionError("semantic eval never queries a source")


def _distribution() -> dict[str, dict[str, int]]:
    return {
        "SINGLE": {"NONE": 2, "HELPFUL": 1, "REQUIRED": 1},
        "DOMINANT": {"NONE": 1, "HELPFUL": 1, "REQUIRED": 1},
        "COMPETING": {"NONE": 1, "HELPFUL": 1, "REQUIRED": 1},
    }


def _run_record(
    *,
    run_id: str = "20260803T120000Z-a1b2c3d4",
    provider: str = "ollama",
    model: str = "qwen3.6:35b-a3b",
    passed: int = 10,
    failed: int = 0,
    started_at: str = "2026-08-03T12:00:00Z",
    ledger_path: str | None = None,
    reasoning: str | None = None,
    thinking: bool | None = None,
    runs_per_case: int = 1,
    selected_case_count: int = 10,
    corpus_role: str = "CALIBRATION",
    operation: str = "find-ambiguities",
) -> dict:
    failure_counts = {} if failed == 0 else {"LABEL_MISMATCH": failed}
    if operation == "find-duplicates":
        expected_distributions = {
            "expected_relation": {
                relation: 1
                for relation in (
                    "EXACT",
                    "SURFACE_EQUIVALENT",
                    "SEMANTIC_EQUIVALENT",
                    "OVERLAP",
                    "UNKNOWN",
                    "DISTINCT",
                )[:selected_case_count]
            }
        }
    elif selected_case_count == 10:
        expected_joint = {
            f"{interpretation}/{clarification}": count
            for interpretation, row in _distribution().items()
            for clarification, count in row.items()
        }
        expected_distributions = {"expected_joint": expected_joint}
    else:
        expected_joint = {"SINGLE/NONE": selected_case_count}
        expected_distributions = {"expected_joint": expected_joint}
    if passed + failed != selected_case_count:
        raise AssertionError("test score must match its selected case count")
    value = {
        "schema_version": 1,
        "kind": "memcommit.semantic-eval.run",
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": "2026-08-03T12:01:00Z",
        "ledger_path": ledger_path or f"/tmp/{run_id}.json",
        "status": "COMPLETED",
        "provider": {
            "provider": provider,
            "model": model,
            "model_digest": "a" * 64 if provider == "ollama" else None,
            "reasoning_effort": reasoning,
            "effective_thinking": thinking,
        },
        "pipeline": {
            "id": (
                "duplicate-relation-v1"
                if operation == "find-duplicates"
                else "ambiguity-classify-v1"
            ),
            "version": 1,
        },
        "corpus": {
            "operation": operation,
            "role": corpus_role,
            "calibration_mode": (
                "FIXED_CALIBRATION"
                if corpus_role == "HOLDOUT"
                else "LEAVE_ONE_OUT"
            ),
            "independent_holdout": corpus_role == "HOLDOUT",
            "fixture_digest": "f" * 64,
            "fixture_case_count": (
                selected_case_count if operation == "find-duplicates" else 10
            ),
            "selected_case_ids": [
                f"case-{index}" for index in range(selected_case_count)
            ],
        },
        "settings": {"runs_per_case": runs_per_case},
        "attempts": [],
        "summary": {
            "campaign_passed": failed == 0,
            "cases": {
                "total": passed + failed,
                "passed": passed,
                "failed": failed,
            },
            "attempts": {
                "exact_matches": passed * runs_per_case,
                "structurally_valid": (passed + failed) * runs_per_case,
                "total": (passed + failed) * runs_per_case,
            },
            "failures": failure_counts,
            "distributions": expected_distributions,
            "completion_seconds": {
                "mean": 1.0,
                "median": 0.9,
                "p95": 1.4,
                "max": 1.5,
            },
        },
        "timing": {
            "provider_connection_seconds": 0.125,
            "campaign_seconds": 10.0,
            "total_seconds": 10.125,
        },
    }
    return value


def _task2_v3_record(*, contract_valid: bool = True) -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-retrieval-v3",
        "schema_version": 1,
        "run_id": "20260803T230000000000Z-" + "a" * 32,
        "started_at": "2026-08-03T23:00:00Z",
        "status": "VALID" if contract_valid else "INVALID_OUTPUT",
        "contract_valid": contract_valid,
        "validation_error": None if contract_valid else "one fixed call was invalid",
        "pipeline": "task2-group-co-membership-retrieval-v3",
        "batch_size": 15,
        "expected_provider_call_count": 4,
        "provider_call_count": 4,
        "provider": {
            "provider": "ollama",
            "model": "qwen3.6:35b-a3b",
            "model_digest": "a" * 64,
            "reasoning_effort": None,
        },
        "effective_thinking": False,
        "corpus": {
            "selected_group_count": 26,
            "selected_left_count": 29,
            "selected_right_count": 27,
            "input_digest": "b" * 64,
        },
        "score": {
            "group_co_membership_retrieval": {
                "reviewed_one_to_one_subset": {
                    "overall": {
                        "exact": 48,
                        "total": 48,
                        "macro_jaccard": 1.0,
                    }
                },
                "group_co_membership": {
                    "overall": {
                        "exact": 56,
                        "total": 56,
                        "macro_jaccard": 1.0,
                    },
                    "micro": {"recall": 1.0},
                },
            },
            "grouping_diagnostics": {
                "reciprocal": {
                    "score": {
                        "exact_groups": 26,
                        "expected_groups": 26,
                        "exact_group_f1": 1.0,
                        "multi_member_group_recall": 1.0,
                    }
                },
                "union": {"score": {"exact_groups": 26, "expected_groups": 26}},
            },
        },
        "timing": {
            "provider_connection_seconds": 0.1,
            "pipeline_seconds": 4.0,
            "total_seconds": 4.1,
        },
        "ledger_path": "/tmp/task2-v3.json",
    }


def _task2_v4_record(*, contract_valid: bool = True) -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-retrieval-v4",
        "schema_version": 1,
        "status": "VALID" if contract_valid else "INVALID_OUTPUT",
        "contract_valid": contract_valid,
        "validation_error": None if contract_valid else "one fixed call was invalid",
        "pipeline": "task2-candidate-then-verify-v4",
        "expected_provider_call_count": 8,
        "provider_call_count": 8,
        "provider": {
            "provider": "ollama",
            "model": "qwen3.6:35b-a3b",
        },
        "corpus": {
            "selected_group_count": 26,
            "selected_left_count": 29,
            "selected_right_count": 27,
            "input_digest": "b" * 64,
        },
        "score": {
            "candidate_retrieval": {
                "recalled": 56,
                "expected": 56,
                "recall_at_3": 1.0,
                "macro_source_recall_at_3": 1.0,
            },
            "final_group_co_membership": {
                "reviewed_one_to_one_subset": {
                    "overall": {
                        "exact": 48,
                        "total": 48,
                        "macro_jaccard": 1.0,
                    }
                },
                "all_reviewed_groups": {
                    "overall": {
                        "exact": 56,
                        "total": 56,
                        "macro_jaccard": 1.0,
                    }
                },
            },
            "grouping_diagnostics": {
                "reciprocal": {
                    "score": {
                        "exact_groups": 26,
                        "expected_groups": 26,
                        "exact_group_f1": 1.0,
                        "multi_member_group_recall": 1.0,
                    }
                },
                "union": {"score": {"exact_groups": 26, "expected_groups": 26}},
            },
        },
        "timing": {
            "provider_connection_seconds": 0.1,
            "candidate_stage_call_seconds": 2.0,
            "verifier_stage_call_seconds": 1.5,
            "pipeline_seconds": 4.0,
            "total_seconds": 4.1,
        },
        "ledger_path": "/tmp/task2-v4.json",
    }


def _task2_candidate_v5_record(
    *, contract_valid: bool = True
) -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-candidate-ablation-v5",
        "schema_version": 1,
        "run_id": "candidate-v5-run",
        "started_at": "2026-08-03T23:30:00Z",
        "status": "VALID" if contract_valid else "INVALID_OUTPUT",
        "contract_valid": contract_valid,
        "validation_error": None if contract_valid else "one candidate call was invalid",
        "pipeline": "task2-candidate-only-top-k-ablation-v5",
        "expected_provider_call_count": 4,
        "provider_call_count": 4,
        "provider": {
            "provider": "ollama",
            "model": "qwen3.6:35b-a3b",
        },
        "effective_thinking": False,
        "condition": {"id": "TOP_5", "candidate_count": 5},
        "corpus": {
            "selected_group_count": 26,
            "selected_left_count": 29,
            "selected_right_count": 27,
            "input_digest": "b" * 64,
        },
        "lock": {"corpus_locked": True},
        "score": {
            "overall": {
                "recovered_directed_edges": 63,
                "expected_directed_edges": 64,
                "micro_recall_at_k": 63 / 64,
                "macro_source_recall_at_k": 55 / 56,
                "one_to_one": {"recovered": 47, "expected": 48},
                "multi_member_groups": {"recovered": 16, "expected": 16},
                "source_hit_distribution": {
                    "complete": 55,
                    "partial": 0,
                    "zero_hit": 1,
                },
            },
            "unique_undirected_gold_edge_recoverability": {
                "recovered": 32,
                "expected": 32,
            },
            "exact_group_recoverability": {
                "recoverable": 25,
                "expected": 26,
                "multi_member": {"recoverable": 2, "expected": 2},
            },
        },
        "timing": {
            "provider_connection_seconds": 0.1,
            "provider_call_seconds": 3.5,
            "pipeline_seconds": 4.0,
            "total_seconds": 4.1,
        },
        "ledger_path": "/tmp/task2-candidate-v5.json",
    }












def test_nested_cli_exposes_run_and_status_options():
    result = runner.invoke(
        command.eval_app,
        ["semantic", "run", "ambiguity", "--help"],
    )

    assert result.exit_code == 0, result.output
    help_text = " ".join(result.output.split())
    for option in (
        "--provider",
        "--model",
        "--preset",
        "--reasoning",
        "--thinking",
        "--pipeline",
        "--corpus",
        "--runs",
        "--case",
        "--ledger-dir",
    ):
        assert option in help_text

    status = runner.invoke(command.eval_app, ["semantic", "status", "--help"])
    assert status.exit_code == 0, status.output
    assert "--ledger-dir" in status.output

    duplicate = runner.invoke(
        command.eval_app,
        ["semantic", "run", "duplicate", "--help"],
    )
    assert duplicate.exit_code == 0, duplicate.output
    assert "--provider" in duplicate.output
    assert "--runs" in duplicate.output


def test_run_uses_transient_selection_and_passes_frozen_campaign_arguments(
    monkeypatch,
    tmp_path,
):
    connected: list[dict] = []
    campaign_calls: list[tuple[object, dict]] = []

    def connect(**kwargs):
        connected.append(kwargs)
        return FakeProvider()

    def run_campaign(provider, **kwargs):
        campaign_calls.append((provider, kwargs))
        kwargs["progress_fn"](
            {
                "index": 1,
                "total": 2,
                "case_id": "single-none-main-entrance-hours",
                "repetition": 1,
                "status": "pass",
                "completion_seconds": 0.625,
            }
        )
        return _run_record(
            ledger_path=str(tmp_path / "runs" / "run.json"),
            runs_per_case=2,
        )

    monkeypatch.setattr(command, "_connect_transient_provider", connect)
    monkeypatch.setattr(command, "run_ambiguity_campaign", run_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "ambiguity",
            "--provider",
            "ollama",
            "--model",
            "qwen3.6:35b-a3b",
            "--thinking",
            "on",
            "--runs",
            "2",
            "--case",
            "first",
            "--case",
            "second",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert connected == [
        {
            "provider_id": "ollama",
            "model": "qwen3.6:35b-a3b",
            "preset": None,
            "reasoning": None,
            "thinking": "on",
        }
    ]
    provider, kwargs = campaign_calls[0]
    assert isinstance(provider, FakeProvider)
    assert kwargs["ledger_dir"] == tmp_path
    assert kwargs["runs"] == 2
    assert kwargs["pipeline"] == "v2"
    assert kwargs["corpus_role"] == "calibration"
    assert kwargs["case_ids"] == ["first", "second"]
    assert kwargs["known_error_types"] == (QueryProviderError,)
    assert kwargs["provider_connection_seconds"] >= 0
    assert (
        "single-none-main-entrance-hours · run 1 · PASS · 0.625s"
        in result.output
    )
    assert "CALIBRATION · leave-one-out" in result.output
    assert "Score: 10/10 cases passed" in result.output
    assert "Attempts: exact 20/20 · structurally valid 20/20" in result.output
    assert "mean/median/p95/max" in result.output
    assert "SINGLE" in result.output
    assert "Ledger:" in result.output


def test_failed_cases_return_nonzero_after_rendering_saved_ledger(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: FakeProvider(),
    )
    monkeypatch.setattr(
        command,
        "run_ambiguity_campaign",
        lambda provider, **kwargs: _run_record(
            passed=9,
            failed=1,
            ledger_path=str(tmp_path / "runs" / "failed.json"),
        ),
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "run", "ambiguity", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "Score: 9/10 cases passed" in result.output
    assert "LABEL_MISMATCH 1" in result.output
    assert "Ledger:" in result.output


def test_run_selects_and_labels_the_frozen_holdout(monkeypatch, tmp_path):
    captured: list[dict] = []
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: FakeProvider(),
    )

    def run_campaign(provider, **kwargs):
        captured.append(kwargs)
        return _run_record(
            corpus_role="HOLDOUT",
            ledger_path=str(tmp_path / "runs" / "holdout.json"),
        )

    monkeypatch.setattr(command, "run_ambiguity_campaign", run_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "ambiguity",
            "--corpus",
            "holdout",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured[0]["corpus_role"] == "holdout"
    assert "Corpus: HOLDOUT · independent · fixed calibration" in result.output


def test_run_duplicate_uses_the_host_first_campaign(monkeypatch, tmp_path):
    captured: list[dict] = []
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: FakeProvider(),
    )

    def run_campaign(provider, **kwargs):
        captured.append(kwargs)
        return _run_record(
            operation="find-duplicates",
            selected_case_count=6,
            passed=6,
            ledger_path=str(tmp_path / "runs" / "duplicate.json"),
        )

    monkeypatch.setattr(command, "run_duplicate_campaign", run_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "duplicate",
            "--provider",
            "ollama",
            "--model",
            "qwen3.6:35b-a3b",
            "--thinking",
            "off",
            "--runs",
            "3",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured[0]["runs"] == 3
    assert "Semantic eval · duplicate · classification gate" in result.output
    assert "Relation distribution:" in result.output


class ReadOnlyConfig:
    """Enough Config surface to prove transient selection never writes it."""

    def semantic_provider(self):
        return "ollama"

    def model_for_provider(self, provider):
        return {
            "ollama": "saved-local",
            "openrouter": "saved/remote",
            "codex_chatgpt": None,
        }.get(provider)

    def codex_reasoning_effort(self):
        return None

    def semantic_timeout_seconds(self):
        return 60.0

    def ollama_base_url(self):
        return "http://127.0.0.1:11434"

    def semantic_context_tokens(self):
        return 4096

    def semantic_max_output_tokens(self):
        return 1024

    def openrouter_zdr(self):
        return True


def test_transient_ollama_connection_reads_config_without_updating_it(monkeypatch):
    captured: dict = {}
    sentinel = FakeProvider()
    monkeypatch.setattr(command, "Config", ReadOnlyConfig)

    def connect(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(command.OllamaProvider, "connect", connect)

    provider = command._connect_transient_provider(
        provider_id="ollama",
        model="qwen3.6:35b-a3b",
        preset=None,
        reasoning=None,
        thinking="on",
    )

    assert provider is sentinel
    assert captured == {
        "model": "qwen3.6:35b-a3b",
        "base_url": "http://127.0.0.1:11434",
        "timeout": 60.0,
        "context_tokens": 4096,
        "max_output_tokens": 1024,
        "thinking": True,
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"provider_id": "unknown"}, "--provider must be one of"),
        (
            {"provider_id": "codex_chatgpt", "preset": "luna-low", "model": "x"},
            "--preset cannot be combined",
        ),
        (
            {"provider_id": "codex_chatgpt", "thinking": "on"},
            "applies only to Ollama",
        ),
        (
            {"provider_id": "openrouter", "reasoning": "low"},
            "apply only to Codex",
        ),
    ],
)
def test_transient_provider_options_fail_closed(kwargs, message):
    values = {
        "provider_id": None,
        "model": None,
        "preset": None,
        "reasoning": None,
        "thinking": "auto",
    }
    values.update(kwargs)

    with pytest.raises(typer.BadParameter, match=message):
        command._resolve_transient_selection(ReadOnlyConfig(), **values)


def test_luna_low_preset_is_a_transient_codex_model_selection():
    selection = command._resolve_transient_selection(
        ReadOnlyConfig(),
        provider_id=None,
        model=None,
        preset="luna-low",
        reasoning=None,
        thinking="auto",
    )

    assert selection.provider_id == "codex_chatgpt"
    assert selection.model == "gpt-5.6-luna"
    assert selection.reasoning_effort == "low"


def test_connection_error_never_exposes_environment_credential(
    monkeypatch,
    tmp_path,
):
    secret = "openrouter-secret-that-must-not-appear"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)

    def fail(**kwargs):
        raise QueryProviderError(f"authentication failed for {secret}")

    monkeypatch.setattr(command, "_connect_transient_provider", fail)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "ambiguity",
            "--provider",
            "openrouter",
            "--model",
            "author/model",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert secret not in result.output
    assert secret not in result.stderr
    assert "[redacted]" in result.stderr


def _write_record(root: Path, name: str, value: dict) -> None:
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / name).write_text(json.dumps(value), encoding="utf-8")


def test_status_is_provider_free_and_shows_latest_per_provider_model_pipeline(
    monkeypatch,
    tmp_path,
):
    _write_record(
        tmp_path,
        "001.json",
        _run_record(
            run_id="001",
            passed=7,
            failed=3,
            started_at="2026-08-01T00:00:00Z",
        ),
    )
    _write_record(
        tmp_path,
        "002.json",
        _run_record(
            run_id="002",
            passed=9,
            failed=1,
            started_at="2026-08-02T00:00:00Z",
        ),
    )
    _write_record(
        tmp_path,
        "003.json",
        _run_record(
            run_id="003",
            provider="codex_chatgpt",
            model="gpt-5.6-luna",
            passed=10,
            failed=0,
            started_at="2026-08-03T00:00:00Z",
        ),
    )
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("status must not connect a provider"),
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "ollama:qwen3.6:35b-a3b" in result.output
    assert "CALIBRATION score 9/10" in result.output
    assert "CALIBRATION score 7/10" not in result.output
    assert "codex_chatgpt:gpt-5.6-luna" in result.output
    assert "CALIBRATION score 10/10" in result.output
    assert "attempts exact=10/10 · structurally-valid=10/10" in result.output
    assert "completion(mean/median/p95/max)" in result.output
    assert "Label distribution:" in result.output


def test_scoreboard_separates_thinking_and_prefers_full_corpus_over_newer_subset():
    auto_full = command._validate_run_record(
        _run_record(
            run_id="auto-full",
            started_at="2026-08-01T00:00:00Z",
            thinking=True,
        )
    )
    auto_subset = command._validate_run_record(
        _run_record(
            run_id="auto-subset",
            started_at="2026-08-03T00:00:00Z",
            thinking=True,
            selected_case_count=1,
            passed=1,
            failed=0,
        )
    )
    off_full = command._validate_run_record(
        _run_record(
            run_id="off-full",
            started_at="2026-08-02T00:00:00Z",
            thinking=False,
        )
    )

    latest = command._latest_records([auto_full, auto_subset, off_full])

    assert len(latest) == 2
    assert {record["effective_thinking"] for record in latest} == {True, False}
    selected = {
        record["effective_thinking"]: record["run_id"] for record in latest
    }
    assert selected[True] == "auto-full"


def test_status_with_no_runs_is_a_normal_read_only_state(tmp_path):
    result = runner.invoke(
        command.eval_app,
        ["semantic", "status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "No semantic evaluation campaigns yet" in result.output
    assert "mem eval semantic run ambiguity" in result.output


@pytest.mark.parametrize(
    "raw",
    [
        "{not-json",
        '{"schema_version":1,"schema_version":1}',
        json.dumps(
            {
                "schema_version": 999,
                "kind": "memcommit.semantic-eval.run",
                "run_id": "bad",
                "status": "COMPLETED",
            }
        ),
    ],
)
def test_status_fails_closed_on_corrupt_or_unknown_run_schema(tmp_path, raw):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "bad.json").write_text(raw, encoding="utf-8")

    result = runner.invoke(
        command.eval_app,
        ["semantic", "status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "Semantic eval status error" in result.stderr


def test_runs_option_is_bounded_before_provider_connection(monkeypatch, tmp_path):
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("invalid runs must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "ambiguity",
            "--runs",
            "21",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "20" in result.stderr


def test_task2_v3_rejects_unfrozen_rung_before_provider_connection(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("invalid rung must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-retrieval-v3",
            "--groups",
            "27",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "26, 50, 100, or 138" in result.stderr


@pytest.mark.parametrize(
    ("contract_valid", "exit_code"),
    [(True, 0), (False, 1)],
)
def test_task2_v3_command_renders_retained_result(
    monkeypatch, tmp_path, contract_valid, exit_code
):
    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )
    captured: dict[str, object] = {}

    def fake_campaign(provider, **kwargs):
        captured.update(kwargs)
        return _task2_v3_record(contract_valid=contract_valid)

    monkeypatch.setattr(command, "run_task2_retrieval_v3_campaign", fake_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-retrieval-v3",
            "--provider",
            "ollama",
            "--groups",
            "26",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == exit_code
    assert "Group co-membership: exact 56/56" in result.output
    assert "Reviewed 1:1 subset: exact 48/48" in result.output
    assert "reciprocal 26/26" in result.output
    assert captured["group_count"] == 26
    assert captured["known_error_types"] == (QueryProviderError,)


def test_task2_v4_rejects_unfrozen_rung_before_provider_connection(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("invalid rung must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-retrieval-v4",
            "--groups",
            "27",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "26, 50, 100, or 138" in result.stderr


@pytest.mark.parametrize(
    ("contract_valid", "exit_code"),
    [(True, 0), (False, 1)],
)
def test_task2_v4_command_renders_candidate_and_verifier_results(
    monkeypatch, tmp_path, contract_valid, exit_code
):
    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )
    captured: dict[str, object] = {}

    def fake_campaign(provider, **kwargs):
        captured.update(kwargs)
        return _task2_v4_record(contract_valid=contract_valid)

    monkeypatch.setattr(command, "run_task2_retrieval_v4_campaign", fake_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-retrieval-v4",
            "--provider",
            "ollama",
            "--groups",
            "26",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == exit_code
    assert "Stage A candidate recall@3: 56/56" in result.output
    assert "Stage B group co-membership: exact 56/56" in result.output
    assert "Reviewed 1:1 subset: exact 48/48" in result.output
    assert "Stage A calls 2.000s" in result.output
    assert "Stage B calls 1.500s" in result.output
    assert "Single-run rung gate: " in result.output
    assert captured["group_count"] == 26
    assert captured["known_error_types"] == (QueryProviderError,)


@pytest.mark.parametrize(
    ("contract_valid", "exit_code"),
    [(True, 0), (False, 1)],
)
def test_task2_candidate_v5_command_renders_ablation_result(
    monkeypatch, tmp_path, contract_valid, exit_code
):
    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )
    captured: dict[str, object] = {}

    def fake_campaign(provider, **kwargs):
        captured.update(kwargs)
        return _task2_candidate_v5_record(contract_valid=contract_valid)

    monkeypatch.setattr(
        command, "run_task2_candidate_ablation_v5_campaign", fake_campaign
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-candidate-v5",
            "--provider",
            "ollama",
            "--candidate-count",
            "5",
            "--groups",
            "26",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == exit_code
    assert "Candidate ablation TOP_5: directed co-member recall 63/64" in result.output
    assert "reviewed 1:1 47/48" in result.output
    assert "exact groups 25/26" in result.output
    assert "provider calls 3.500s" in result.output
    assert captured["candidate_count"] == 5
    assert captured["group_count"] == 26
    assert captured["known_error_types"] == (QueryProviderError,)






















@pytest.mark.parametrize("passed", [True, False])
def test_task2_v3_parity_command_uses_co_membership_result(
    monkeypatch, tmp_path, passed
):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "compare_task2_retrieval_v3_records",
        lambda _first, _second: {
            "first_contract_valid": True,
            "second_contract_valid": True,
            "group_co_membership_agreement": {
                "overall": {
                    "exact": 56 if passed else 55,
                    "total": 56,
                    "macro_jaccard": 1.0 if passed else 0.98,
                }
            },
            "reviewed_one_to_one_agreement": {
                "overall": {
                    "both_gold": 48 if passed else 47,
                    "first_only_gold": 0 if passed else 1,
                    "second_only_gold": 0,
                    "both_wrong_same": 0,
                    "both_wrong_different": 0,
                }
            },
            "grouping_agreement": {
                "reciprocal": {"jaccard": 1.0 if passed else 0.9},
                "union": {"jaccard": 1.0 if passed else 0.9},
            },
            "parity_gate_passed": passed,
        },
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-retrieval-v3-parity", str(first), str(second)],
    )

    assert result.exit_code == (0 if passed else 1)
    assert "group co-membership sets" in result.output
    assert "Reviewed 1:1 Gold split" in result.output


@pytest.mark.parametrize("passed", [True, False])
def test_task2_v4_parity_command_separates_candidate_and_final_agreement(
    monkeypatch, tmp_path, passed
):
    first = tmp_path / "first-v4.json"
    second = tmp_path / "second-v4.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "compare_task2_retrieval_v4_records",
        lambda _first, _second: {
            "first_contract_valid": True,
            "second_contract_valid": True,
            "candidate_set_agreement": {
                "overall": {
                    "exact": 56 if passed else 20,
                    "total": 56,
                    "macro_jaccard": 1.0 if passed else 0.6,
                }
            },
            "final_group_co_membership_agreement": {
                "overall": {
                    "exact": 56 if passed else 40,
                    "total": 56,
                    "macro_jaccard": 1.0 if passed else 0.75,
                }
            },
            "reviewed_one_to_one_gold_quadrants": {
                "overall": {
                    "both_gold": 48 if passed else 30,
                    "first_only_gold": 0 if passed else 5,
                    "second_only_gold": 0 if passed else 4,
                    "both_wrong_same": 0 if passed else 6,
                    "both_wrong_different": 0 if passed else 3,
                }
            },
            "grouping_agreement": {
                "reciprocal": {"jaccard": 1.0 if passed else 0.7},
                "union": {"jaccard": 1.0 if passed else 0.3},
            },
            "parity_gate_passed": passed,
        },
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-retrieval-v4-parity", str(first), str(second)],
    )

    assert result.exit_code == (0 if passed else 1)
    assert "candidate sets" in result.output
    assert "final co-membership sets" in result.output
    assert "Reviewed 1:1 Gold split" in result.output
















def test_task2_status_renders_v3_when_no_v1_ledgers_exist(tmp_path):
    directory = tmp_path / "task2-retrieval-v3"
    directory.mkdir()
    record = _task2_v3_record()
    record["lock"] = {"corpus_locked": True}
    (directory / "v3.json").write_text(json.dumps(record), encoding="utf-8")

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "No Task 2 V1 discovery runs found" in result.output
    assert "V3 retrieval · ollama:qwen3.6:35b-a3b" in result.output
    assert "UNVERIFIED" in result.output
    assert "LOCKED" not in result.output
    assert "group co-membership 56/56" in result.output


def test_task2_status_renders_v4_candidate_and_verifier_rows(tmp_path):
    directory = tmp_path / "task2-retrieval-v4"
    directory.mkdir()
    record = _task2_v4_record()
    record["lock"] = {"corpus_locked": True}
    (directory / "v4.json").write_text(json.dumps(record), encoding="utf-8")

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "V4 candidate→verify · ollama:qwen3.6:35b-a3b" in result.output
    assert "UNVERIFIED" in result.output
    assert "candidate recall@3 56/56" in result.output
    assert "final co-membership 56/56" in result.output
    assert "Stage A 2.000s · Stage B 1.500s" in result.output
