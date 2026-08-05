"""Run and inspect provider-neutral semantic evaluation campaigns."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
import os
from pathlib import Path
import time
from typing import Annotated, Optional

import typer

from memcommit.commands.tui_primitives import display_escape_text
from memcommit.config import Config
from memcommit.eval.semantic_campaign import (
    LEDGER_KIND,
    PIPELINE_CHOICES,
    SemanticCampaignError,
    load_campaign_ledgers,
    run_ambiguity_campaign,
)
from memcommit.provider_types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_LUNA_LOW_PRESET,
    CODEX_LUNA_MODEL,
    CODEX_PROVIDER_PRESETS,
    CODEX_REASONING_EFFORTS,
    OLLAMA_PROVIDER,
    OPENROUTER_PROVIDER,
    SEMANTIC_PROVIDER_IDS,
    ProviderIdentity,
    SemanticProvider,
)
from memcommit.query_provider import CodexChatGPTProvider, QueryProviderError
from memcommit.semantic_provider import OllamaProvider, OpenRouterProvider


DEFAULT_SEMANTIC_EVAL_LEDGER = Path.home() / ".mem" / "eval" / "semantic"
_STATUS_VALUES = {"RUNNING", "COMPLETED", "ABORTED"}
_INTERPRETATIONS = ("SINGLE", "DOMINANT", "COMPETING")
_CLARIFICATIONS = ("NONE", "HELPFUL", "REQUIRED")
_BINARY_STAGES = (
    "MULTIPLE_READINGS",
    "CLEAR_LEADER",
    "PRACTICAL_IMPROVEMENT",
    "CAN_PROCEED",
    "READING_CENSUS",
    "CLARIFICATION_CENSUS",
)
_SECRET_ENV_NAMES = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "CODEX_ACCESS_TOKEN",
)


eval_app = typer.Typer(
    no_args_is_help=True,
    help="Run and inspect reproducible semantic evaluation campaigns.",
)
semantic_app = typer.Typer(
    no_args_is_help=True,
    help="Evaluate staged semantic-operation contracts.",
)
run_app = typer.Typer(
    no_args_is_help=True,
    help="Run one frozen semantic evaluation campaign.",
)
eval_app.add_typer(semantic_app, name="semantic")
semantic_app.add_typer(run_app, name="run")


@dataclass(frozen=True)
class _TransientSelection:
    provider_id: str
    model: str | None
    reasoning_effort: str | None
    thinking: bool | None


class _RunRecordError(ValueError):
    """A persisted campaign cannot be rendered without guessing."""


def _redacted_error(error: BaseException) -> str:
    """Render a safe diagnostic even if a dependency echoed a credential."""
    message = str(error)
    for name in _SECRET_ENV_NAMES:
        secret = os.environ.get(name)
        if secret:
            message = message.replace(secret, "[redacted]")
    return display_escape_text(message)


def _normalized_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _resolve_transient_selection(
    config: Config,
    *,
    provider_id: str | None,
    model: str | None,
    preset: str | None,
    reasoning: str | None,
    thinking: str,
) -> _TransientSelection:
    selected_provider = _normalized_optional(provider_id)
    selected_preset = _normalized_optional(preset)
    selected_reasoning = _normalized_optional(reasoning)
    selected_thinking = thinking.strip().lower()

    if selected_preset is not None and selected_provider is None:
        # A Codex-only preset is an unambiguous transient provider request. It
        # must not rewrite the configured default merely to run one campaign.
        selected_provider = CODEX_CHATGPT_PROVIDER
    if selected_provider is None:
        selected_provider = config.semantic_provider()
    if selected_provider not in SEMANTIC_PROVIDER_IDS:
        raise typer.BadParameter(
            "--provider must be one of: " + ", ".join(SEMANTIC_PROVIDER_IDS)
        )
    if selected_thinking not in {"auto", "on", "off"}:
        raise typer.BadParameter("--thinking must be auto, on, or off")
    if selected_preset is not None and selected_preset not in CODEX_PROVIDER_PRESETS:
        raise typer.BadParameter(
            "--preset must be one of: " + ", ".join(CODEX_PROVIDER_PRESETS)
        )
    if (
        selected_reasoning is not None
        and selected_reasoning not in CODEX_REASONING_EFFORTS
    ):
        raise typer.BadParameter(
            "--reasoning must be one of: "
            + ", ".join(CODEX_REASONING_EFFORTS)
        )
    if selected_preset is not None and (model is not None or reasoning is not None):
        raise typer.BadParameter(
            "--preset cannot be combined with --model or --reasoning"
        )
    if selected_provider != CODEX_CHATGPT_PROVIDER and (
        selected_preset is not None or selected_reasoning is not None
    ):
        raise typer.BadParameter("--preset and --reasoning apply only to Codex")
    if selected_provider != OLLAMA_PROVIDER and selected_thinking != "auto":
        raise typer.BadParameter("--thinking on/off applies only to Ollama")

    if selected_preset == CODEX_LUNA_LOW_PRESET:
        selected_model = CODEX_LUNA_MODEL
        selected_reasoning = "low"
    else:
        selected_model = model or config.model_for_provider(selected_provider)
        if (
            selected_provider == CODEX_CHATGPT_PROVIDER
            and model is None
            and reasoning is None
        ):
            selected_reasoning = config.codex_reasoning_effort()

    if selected_provider != CODEX_CHATGPT_PROVIDER and not selected_model:
        raise typer.BadParameter(
            "--model is required when the selected provider has no saved model"
        )
    if (
        selected_provider == CODEX_CHATGPT_PROVIDER
        and selected_reasoning is not None
        and not selected_model
    ):
        raise typer.BadParameter("--reasoning requires a Codex model or --preset")

    thinking_value = {
        "auto": None,
        "on": True,
        "off": False,
    }[selected_thinking]
    return _TransientSelection(
        provider_id=selected_provider,
        model=selected_model,
        reasoning_effort=selected_reasoning,
        thinking=thinking_value,
    )


def _connect_transient_provider(
    *,
    provider_id: str | None,
    model: str | None,
    preset: str | None,
    reasoning: str | None,
    thinking: str,
) -> SemanticProvider:
    """Connect one campaign provider without updating global configuration."""
    config = Config()
    selection = _resolve_transient_selection(
        config,
        provider_id=provider_id,
        model=model,
        preset=preset,
        reasoning=reasoning,
        thinking=thinking,
    )
    timeout = config.semantic_timeout_seconds()
    if selection.provider_id == CODEX_CHATGPT_PROVIDER:
        return CodexChatGPTProvider.connect(
            env=dict(os.environ),
            timeout=timeout,
            model=selection.model,
            reasoning_effort=selection.reasoning_effort,
        )
    if selection.provider_id == OLLAMA_PROVIDER:
        assert selection.model is not None
        return OllamaProvider.connect(
            model=selection.model,
            base_url=config.ollama_base_url(),
            timeout=timeout,
            context_tokens=config.semantic_context_tokens(),
            max_output_tokens=config.semantic_max_output_tokens(),
            thinking=selection.thinking,
        )
    if selection.provider_id == OPENROUTER_PROVIDER:
        assert selection.model is not None
        return OpenRouterProvider.connect(
            model=selection.model,
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            timeout=timeout,
            max_output_tokens=config.semantic_max_output_tokens(),
            zdr=config.openrouter_zdr(),
        )
    raise AssertionError("validated semantic provider was not connected")


def _progress_line(event: object) -> str | None:
    if not isinstance(event, Mapping):
        return None
    case_id = event.get("case_id")
    status = event.get("status")
    if not isinstance(case_id, str) or not isinstance(status, str):
        return None
    index = event.get("index")
    total = event.get("total")
    prefix = ""
    if (
        isinstance(index, int)
        and not isinstance(index, bool)
        and isinstance(total, int)
        and not isinstance(total, bool)
    ):
        prefix = f"[{index:02d}/{total:02d}] "
    repetition = event.get("repetition")
    repetition_text = (
        f" · run {repetition}"
        if isinstance(repetition, int) and not isinstance(repetition, bool)
        else ""
    )
    return (
        prefix
        + display_escape_text(case_id)
        + repetition_text
        + " · "
        + display_escape_text(status.upper())
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _RunRecordError(f"{label} must be an object")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _RunRecordError(f"{label} must be a non-negative integer")
    return value


def _number(value: object, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise _RunRecordError(f"{label} must be a non-negative finite number")
    return float(value)


def _optional_number(value: object, label: str) -> float | None:
    if value is None:
        return None
    return _number(value, label)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _RunRecordError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _optional_bool(value: object, label: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise _RunRecordError(f"{label} must be boolean or null")


def _validate_distribution(value: object) -> dict[str, dict[str, int]]:
    joint = _mapping(value, "summary.distributions.expected_joint")
    allowed = {
        f"{interpretation}/{clarification}"
        for interpretation in _INTERPRETATIONS
        for clarification in _CLARIFICATIONS
    }
    if not set(joint) <= allowed:
        raise _RunRecordError("expected_joint contains an unknown label pair")
    return {
        interpretation: {
            clarification: _integer(
                joint.get(f"{interpretation}/{clarification}", 0),
                f"expected_joint.{interpretation}/{clarification}",
            )
            for clarification in _CLARIFICATIONS
        }
        for interpretation in _INTERPRETATIONS
    }


def _validate_stats(value: object, label: str) -> dict[str, float | None]:
    stats = _mapping(value, label)
    required = {"mean", "median", "p95", "max"}
    if set(stats) != required:
        raise _RunRecordError(f"{label} must contain mean, median, p95, and max")
    return {
        name: _optional_number(stats[name], f"{label}.{name}")
        for name in required
    }


def _validate_run_record(value: object, *, source: Path | None = None) -> dict:
    record = _mapping(value, "run record")
    required = {
        "schema_version",
        "kind",
        "run_id",
        "status",
        "started_at",
        "completed_at",
        "ledger_path",
        "provider",
        "pipeline",
        "corpus",
        "settings",
        "attempts",
        "summary",
        "timing",
    }
    missing = required - set(record)
    if missing:
        raise _RunRecordError("missing keys: " + ", ".join(sorted(missing)))
    if record["schema_version"] != 1:
        raise _RunRecordError("unsupported schema_version")
    if record["kind"] != LEDGER_KIND:
        raise _RunRecordError("unsupported run ledger kind")
    run_id = _text(record["run_id"], "run_id")
    status = _text(record["status"], "status").upper()
    if status not in _STATUS_VALUES:
        raise _RunRecordError("unsupported campaign status")

    provider = _mapping(record["provider"], "provider")
    provider_id = _text(provider.get("provider"), "provider.provider")
    model = _text(provider.get("model"), "provider.model")
    model_digest = _optional_text(
        provider.get("model_digest"),
        "provider.model_digest",
    )
    reasoning_effort = _optional_text(
        provider.get("reasoning_effort"),
        "provider.reasoning_effort",
    )
    effective_thinking = _optional_bool(
        provider.get("effective_thinking"),
        "provider.effective_thinking",
    )
    pipeline = _mapping(record["pipeline"], "pipeline")
    pipeline_id = _text(pipeline.get("id"), "pipeline.id")
    pipeline_version = _integer(pipeline.get("version"), "pipeline.version")

    corpus = _mapping(record["corpus"], "corpus")
    if corpus.get("role") != "CALIBRATION":
        raise _RunRecordError("V1 corpus.role must be CALIBRATION")
    if corpus.get("operation") != "find-ambiguities":
        raise _RunRecordError("V1 corpus.operation must be find-ambiguities")
    if corpus.get("calibration_mode") != "LEAVE_ONE_OUT":
        raise _RunRecordError("V1 corpus.calibration_mode must be LEAVE_ONE_OUT")
    fixture_digest = _text(
        corpus.get("fixture_digest"),
        "corpus.fixture_digest",
    )
    fixture_case_count = _integer(
        corpus.get("fixture_case_count"),
        "corpus.fixture_case_count",
    )
    selected_case_ids = corpus.get("selected_case_ids")
    if (
        not isinstance(selected_case_ids, list)
        or any(not isinstance(item, str) or not item for item in selected_case_ids)
        or len(selected_case_ids) != len(set(selected_case_ids))
        or len(selected_case_ids) > fixture_case_count
    ):
        raise _RunRecordError("corpus.selected_case_ids is invalid")
    settings = _mapping(record["settings"], "settings")
    runs_per_case = _integer(
        settings.get("runs_per_case"),
        "settings.runs_per_case",
    )
    if runs_per_case < 1:
        raise _RunRecordError("settings.runs_per_case must be positive")

    summary = _mapping(record["summary"], "summary")
    cases = _mapping(summary.get("cases"), "summary.cases")
    cases_total = _integer(cases.get("total"), "summary.cases.total")
    cases_passed = _integer(cases.get("passed"), "summary.cases.passed")
    cases_failed = _integer(cases.get("failed"), "summary.cases.failed")
    if cases_passed + cases_failed != cases_total:
        raise _RunRecordError("case counts do not add up")
    if cases_total != len(selected_case_ids):
        raise _RunRecordError("case total does not match selected case IDs")
    campaign_passed = summary.get("campaign_passed")
    if not isinstance(campaign_passed, bool):
        raise _RunRecordError("summary.campaign_passed must be boolean")
    if campaign_passed != (cases_total > 0 and cases_failed == 0):
        raise _RunRecordError("campaign_passed is inconsistent with case counts")
    failure_counts_value = _mapping(
        summary.get("failures"),
        "summary.failures",
    )
    failure_counts = {
        _text(name, "failure category"): _integer(
            count,
            f"summary.failure_counts.{name}",
        )
        for name, count in failure_counts_value.items()
    }
    distributions = _mapping(summary.get("distributions"), "summary.distributions")
    distribution = _validate_distribution(distributions.get("expected_joint"))
    if sum(sum(row.values()) for row in distribution.values()) != cases_total:
        raise _RunRecordError("expected label distribution does not match case total")

    timing = _mapping(record["timing"], "timing")
    connection_seconds = _number(
        timing.get("provider_connection_seconds"),
        "timing.provider_connection_seconds",
    )
    completion_stats = _validate_stats(
        summary.get("completion_seconds"),
        "summary.completion_seconds",
    )
    stage_stats_value = summary.get("stage_completion_seconds", {})
    stage_stats_mapping = _mapping(
        stage_stats_value,
        "summary.stage_completion_seconds",
    )
    if not set(stage_stats_mapping) <= set(_BINARY_STAGES):
        raise _RunRecordError("stage timing contains an unknown stage")
    stage_stats = {
        stage: _validate_stats(
            value,
            f"summary.stage_completion_seconds.{stage}",
        )
        for stage, value in stage_stats_mapping.items()
    }
    campaign_seconds = _optional_number(
        timing.get("campaign_seconds"),
        "timing.campaign_seconds",
    )
    total_seconds = _optional_number(
        timing.get("total_seconds"),
        "timing.total_seconds",
    )

    started_at = _text(record.get("started_at"), "started_at")
    ledger_path = _text(record.get("ledger_path"), "ledger_path")
    attempts = record.get("attempts")
    if not isinstance(attempts, list):
        raise _RunRecordError("attempts must be an array")
    return {
        "source": source or Path(ledger_path),
        "run_id": run_id,
        "started_at": started_at,
        "status": status,
        "provider": provider_id,
        "model": model,
        "model_digest": model_digest,
        "reasoning_effort": reasoning_effort,
        "effective_thinking": effective_thinking,
        "pipeline_id": pipeline_id,
        "pipeline_version": pipeline_version,
        "fixture_digest": fixture_digest,
        "fixture_case_count": fixture_case_count,
        "selected_case_count": len(selected_case_ids),
        "runs_per_case": runs_per_case,
        "cases_total": cases_total,
        "cases_passed": cases_passed,
        "cases_failed": cases_failed,
        "failure_counts": failure_counts,
        "distribution": distribution,
        "connection_seconds": connection_seconds,
        "completion_seconds": completion_stats,
        "stage_completion_seconds": stage_stats,
        "campaign_seconds": campaign_seconds,
        "total_seconds": total_seconds,
    }


def _read_run_records(ledger_dir: Path) -> list[dict]:
    records = []
    for value in load_campaign_ledgers(ledger_dir):
        ledger_path = value.get("ledger_path")
        source = Path(ledger_path) if isinstance(ledger_path, str) else None
        records.append(_validate_run_record(value, source=source))
    return records


def _latest_records(records: list[dict]) -> list[dict]:
    latest: dict[tuple[object, ...], dict] = {}
    for record in records:
        key = (
            record["provider"],
            record["model"],
            record["model_digest"],
            record["reasoning_effort"],
            record["effective_thinking"],
            record["pipeline_id"],
            record["pipeline_version"],
            record["fixture_digest"],
            record["runs_per_case"],
        )
        existing = latest.get(key)
        record_is_full = (
            record["selected_case_count"] == record["fixture_case_count"]
        )
        existing_is_full = (
            existing is not None
            and existing["selected_case_count"] == existing["fixture_case_count"]
        )
        if (
            existing is None
            or (record_is_full and not existing_is_full)
            or (
                record_is_full == existing_is_full
                and (record["started_at"], record["run_id"])
                > (existing["started_at"], existing["run_id"])
            )
        ):
            latest[key] = record
    return sorted(
        latest.values(),
        key=lambda item: (
            item["provider"],
            item["model"],
            str(item["reasoning_effort"]),
            str(item["effective_thinking"]),
            item["runs_per_case"],
        ),
    )


def _condition_suffix(record: Mapping[str, object]) -> str:
    parts = []
    reasoning = record.get("reasoning_effort")
    if isinstance(reasoning, str):
        parts.append(f"reasoning={display_escape_text(reasoning)}")
    thinking = record.get("effective_thinking")
    if isinstance(thinking, bool):
        parts.append(f"thinking={str(thinking).lower()}")
    parts.append(f"runs={record['runs_per_case']}")
    parts.append(
        f"cases={record['selected_case_count']}/{record['fixture_case_count']}"
    )
    return " · " + " · ".join(parts)


def _format_seconds(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}s"


def _render_distribution(distribution: dict[str, dict[str, int]]) -> None:
    typer.echo("Label distribution:")
    typer.echo("  interpretation   NONE  HELPFUL  REQUIRED")
    for interpretation in _INTERPRETATIONS:
        row = distribution[interpretation]
        typer.echo(
            f"  {interpretation:<14}"
            f" {row['NONE']:>4}  {row['HELPFUL']:>7}  {row['REQUIRED']:>8}"
        )


def _render_stage_timing(stage_stats: Mapping[str, object]) -> None:
    if not stage_stats:
        return
    typer.echo("Stage timing (mean/p95):")
    for stage in _BINARY_STAGES:
        stats = stage_stats.get(stage)
        if not isinstance(stats, Mapping):
            continue
        typer.echo(
            f"  {stage:<24}"
            + _format_seconds(stats.get("mean"))  # type: ignore[arg-type]
            + "/"
            + _format_seconds(stats.get("p95"))  # type: ignore[arg-type]
        )


def _render_campaign_result(value: object) -> dict:
    result = _validate_run_record(value)
    typer.secho("Semantic eval · ambiguity · classification gate", bold=True)
    typer.echo(
        "Provider: "
        + display_escape_text(f"{result['provider']}:{result['model']}")
        + _condition_suffix(result)
    )
    typer.echo("Corpus: CALIBRATION · leave-one-out · not an independent holdout")
    typer.echo(
        f"Pipeline: {display_escape_text(result['pipeline_id'])}"
        f" · schema v{result['pipeline_version']}"
    )
    typer.echo(
        f"Score: {result['cases_passed']}/{result['cases_total']} cases passed"
    )
    failures = result["failure_counts"]
    if failures:
        typer.echo(
            "Failures: "
            + " · ".join(
                f"{display_escape_text(name)} {count}"
                for name, count in sorted(failures.items())
            )
        )
    timing = result["completion_seconds"]
    typer.echo(
        "Timing: connection "
        + _format_seconds(result["connection_seconds"])
        + " · completion mean/median/p95/max "
        + "/".join(
            _format_seconds(timing[name])
            for name in ("mean", "median", "p95", "max")
        )
        + " · campaign "
        + _format_seconds(result["campaign_seconds"])
        + " · total "
        + _format_seconds(result["total_seconds"])
    )
    _render_distribution(result["distribution"])
    _render_stage_timing(result["stage_completion_seconds"])
    ledger_path = result.get("source")
    if ledger_path is not None:
        typer.echo(f"Ledger: {display_escape_text(str(ledger_path))}")
    return result


@run_app.command("ambiguity")
def run_ambiguity(
    provider_id: Annotated[
        Optional[str],
        typer.Option(
            "--provider",
            help="Transient provider; defaults to the configured selection",
        ),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Transient model name or slug"),
    ] = None,
    preset: Annotated[
        Optional[str],
        typer.Option("--preset", help="Codex preset; currently: luna-low"),
    ] = None,
    reasoning: Annotated[
        Optional[str],
        typer.Option("--reasoning", help="Codex reasoning effort"),
    ] = None,
    thinking: Annotated[
        str,
        typer.Option("--thinking", help="Ollama thinking: auto, on, or off"),
    ] = "auto",
    pipeline: Annotated[
        str,
        typer.Option(
            "--pipeline",
            help="Ambiguity pipeline: v1 replay through evidence-census v4",
        ),
    ] = "v2",
    runs: Annotated[
        int,
        typer.Option("--runs", "-n", min=1, max=20, help="Attempts per case"),
    ] = 3,
    case_ids: Annotated[
        Optional[list[str]],
        typer.Option("--case", help="Run only this case ID; repeatable"),
    ] = None,
    ledger_dir: Annotated[
        Path,
        typer.Option(
            "--ledger-dir",
            file_okay=False,
            dir_okay=True,
            help="Profile-independent semantic evaluation ledger",
        ),
    ] = DEFAULT_SEMANTIC_EVAL_LEDGER,
) -> None:
    """Run the V1 leave-one-out ambiguity classification calibration."""
    selected_pipeline = pipeline.strip().lower()
    if selected_pipeline not in PIPELINE_CHOICES:
        raise typer.BadParameter(
            "--pipeline must be one of: " + ", ".join(PIPELINE_CHOICES)
        )
    connection_started = time.monotonic()
    try:
        provider = _connect_transient_provider(
            provider_id=provider_id,
            model=model,
            preset=preset,
            reasoning=reasoning,
            thinking=thinking,
        )
    except (
        QueryProviderError,
        SemanticCampaignError,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Semantic eval connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    provider_label = (
        identity.display_name()
        if isinstance(identity, ProviderIdentity)
        else "configured semantic provider"
    )
    typer.echo(
        "Connected: "
        + display_escape_text(provider_label)
        + " · "
        + _format_seconds(connection_seconds)
    )

    def report_progress(event: object) -> None:
        line = _progress_line(event)
        if line is not None:
            typer.echo(line)

    try:
        result = run_ambiguity_campaign(
            provider,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            runs=runs,
            pipeline=selected_pipeline,
            known_error_types=(QueryProviderError,),
            case_ids=case_ids,
            progress_fn=report_progress,
        )
        rendered = _render_campaign_result(result)
    except (
        QueryProviderError,
        SemanticCampaignError,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        typer.secho(
            "Semantic eval error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if rendered["cases_failed"]:
        raise typer.Exit(1)


@semantic_app.command("status")
def semantic_status(
    ledger_dir: Annotated[
        Path,
        typer.Option(
            "--ledger-dir",
            file_okay=False,
            dir_okay=True,
            help="Profile-independent semantic evaluation ledger",
        ),
    ] = DEFAULT_SEMANTIC_EVAL_LEDGER,
) -> None:
    """Show the latest campaign per provider/model without connecting it."""
    try:
        records = _read_run_records(ledger_dir)
        latest = _latest_records(records)
    except (OSError, SemanticCampaignError, _RunRecordError) as error:
        typer.secho(
            "Semantic eval status error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if not latest:
        typer.echo("No semantic evaluation campaigns yet.")
        typer.echo("Run: mem eval semantic run ambiguity")
        return

    typer.secho("Semantic eval scoreboard · latest comparable campaigns", bold=True)
    for record in latest:
        typer.echo()
        typer.echo(
            display_escape_text(f"{record['provider']}:{record['model']}")
            + f" · {display_escape_text(record['pipeline_id'])}"
            + f" · schema v{record['pipeline_version']} · {record['status']}"
            + _condition_suffix(record)
        )
        typer.echo(
            f"  CALIBRATION score {record['cases_passed']}/"
            f"{record['cases_total']} · failed {record['cases_failed']}"
        )
        failures = record["failure_counts"]
        typer.echo(
            "  failures "
            + (
                ", ".join(
                    f"{display_escape_text(name)}={count}"
                    for name, count in sorted(failures.items())
                )
                if failures
                else "none"
            )
        )
        timing = record["completion_seconds"]
        typer.echo(
            "  time connection="
            + _format_seconds(record["connection_seconds"])
            + " completion(mean/median/p95/max)="
            + "/".join(
                _format_seconds(timing[name])
                for name in ("mean", "median", "p95", "max")
            )
            + " campaign="
            + _format_seconds(record["campaign_seconds"])
            + " total="
            + _format_seconds(record["total_seconds"])
        )
        _render_distribution(record["distribution"])
        _render_stage_timing(record["stage_completion_seconds"])
