"""CLI contracts for staged semantic evaluation campaigns."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import memcommit.adapters.console.commands.eval.command as command
from memcommit.providers.types import ProviderIdentity
from memcommit.providers.subscription import QueryProviderError


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


def test_nested_cli_exposes_run_and_status_options():
    run_help = runner.invoke(command.app, ["semantic", "run", "--help"])
    assert run_help.exit_code == 0, run_help.output
    for name in ("ambiguity", "duplicate", "gates"):
        assert name in run_help.output
    assert "task2-" not in run_help.output

    semantic_help = runner.invoke(command.app, ["semantic", "--help"])
    assert semantic_help.exit_code == 0, semantic_help.output
    assert "task2-" not in semantic_help.output

    result = runner.invoke(
        command.app,
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

    status = runner.invoke(command.app, ["semantic", "status", "--help"])
    assert status.exit_code == 0, status.output
    assert "--ledger-dir" in status.output

    duplicate = runner.invoke(
        command.app,
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
        command.app,
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
        command.app,
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
        command.app,
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
        command.app,
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
        command.app,
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
        command.app,
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
        command.app,
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
        command.app,
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
        command.app,
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
