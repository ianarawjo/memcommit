"""Run and inspect provider-neutral semantic evaluation campaigns."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import time
from typing import Annotated, Optional

import typer

from memcommit.interfaces.console.text import display_escape_text
from memcommit.config import Config
from memcommit.eval.semantic_campaign import (
    CORPUS_CHOICES,
    LEDGER_KIND,
    PIPELINE_CHOICES,
    SemanticCampaignError,
    load_campaign_ledgers,
    run_ambiguity_campaign,
    run_duplicate_campaign,
)
from memcommit.eval.operation_gate_campaign import run_operation_gate_campaign
from memcommit.eval.task2_adjudication_queue_v5 import (
    Task2AdjudicationQueueV5Error,
    build_task2_judge_adjudication_queue_v5,
    render_task2_judge_adjudication_queue_v5,
)
from memcommit.eval.task2_classification import (
    Task2ClassificationError,
    compare_task2_classification_records,
    run_task2_classification_campaign,
)
from memcommit.eval.task2_candidate_ablation_v5 import (
    Task2CandidateAblationV5Error,
    run_task2_candidate_ablation_v5_campaign,
)
from memcommit.eval.task2_discovery import (
    Task2DiscoveryError,
    compare_task2_discovery_records,
    run_task2_discovery_campaign,
)
from memcommit.eval.task2_discovery_v2 import (
    Task2DiscoveryV2Error,
    run_task2_discovery_v2_campaign,
)
from memcommit.eval.task2_retrieval_v3 import (
    Task2RetrievalV3Error,
    compare_task2_retrieval_v3_records,
    evaluate_task2_retrieval_v3_promotion,
    run_task2_retrieval_v3_campaign,
)
from memcommit.eval.task2_retrieval_v4 import (
    Task2RetrievalV4Error,
    compare_task2_retrieval_v4_records,
    evaluate_task2_retrieval_v4_rung_gate,
    run_task2_retrieval_v4_campaign,
)
from memcommit.eval.task2_judge_replay_v5 import (
    Task2JudgeReplayV5Error,
    compare_task2_judge_replay_v5_records,
    run_task2_judge_replay_v5_campaign,
)
from memcommit.eval.task2_judge_replay_v6 import (
    Task2JudgeReplayV6Error,
    compare_task2_judge_replay_v6_records,
    run_task2_judge_replay_v6_campaign,
)
from memcommit.eval.task2_judge_replay_v7 import (
    Task2JudgeReplayV7Error,
    run_task2_judge_replay_v7_campaign,
    validate_task2_judge_replay_v7_record,
)
from memcommit.eval.task2_judge_replay_v8 import (
    Task2JudgeReplayV8Error,
    run_task2_judge_replay_v8_campaign,
    validate_task2_judge_replay_v8_record,
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
_STAGE_ORDER = (
    "MULTIPLE_READINGS",
    "CLEAR_LEADER",
    "PRACTICAL_IMPROVEMENT",
    "CAN_PROCEED",
    "READING_CENSUS",
    "CLARIFICATION_CENSUS",
    "HOST_EXACT",
    "HOST_SURFACE_EQUIVALENT",
    "SEMANTIC_RELATION",
    "SEMANTIC_GATE",
)
_DUPLICATE_RELATIONS = (
    "EXACT",
    "SURFACE_EQUIVALENT",
    "SEMANTIC_EQUIVALENT",
    "OVERLAP",
    "UNKNOWN",
    "DISTINCT",
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
    completion_seconds = event.get("completion_seconds")
    timing_text = (
        " · " + _format_seconds(float(completion_seconds))
        if isinstance(completion_seconds, (int, float))
        and not isinstance(completion_seconds, bool)
        and completion_seconds >= 0
        else ""
    )
    return (
        prefix
        + display_escape_text(case_id)
        + repetition_text
        + " · "
        + display_escape_text(status.upper())
        + timing_text
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _RunRecordError(f"{label} must be an object")
    return value


def _task2_scorer_provenance(
    record: Mapping[str, object],
) -> tuple[object, str]:
    raw = record.get("scorer_version")
    if raw is None:
        return 1, "legacy-v1"
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1:
        return raw, f"v{raw}"
    return "invalid", "INVALID"


def _task2_lock_provenance(
    record: Mapping[str, object],
) -> tuple[str, str]:
    lock = record.get("lock")
    if isinstance(lock, Mapping) and lock.get("corpus_locked") is True:
        return "locked", "LOCKED"
    if lock is None:
        return "pre-lock", "PRE-LOCK"
    return "unverified", "UNVERIFIED"


def _task2_v3_lock_provenance(
    record: Mapping[str, object],
) -> tuple[str, str]:
    lock = record.get("lock")
    corpus = record.get("corpus")
    selected = lock.get("selected_slice") if isinstance(lock, Mapping) else None
    if (
        isinstance(lock, Mapping)
        and isinstance(corpus, Mapping)
        and isinstance(selected, Mapping)
        and lock.get("corpus_locked") is True
        and lock.get("slice_locked") is True
        and lock.get("corpus_digest") == corpus.get("digest")
        and selected.get("input_digest") == corpus.get("input_digest")
        and selected.get("alias_mapping_digest")
        == corpus.get("alias_mapping_digest")
        and selected.get("group_count") == corpus.get("selected_group_count")
        and selected.get("selected_left_count")
        == corpus.get("selected_left_count")
        and selected.get("selected_right_count")
        == corpus.get("selected_right_count")
    ):
        return "locked", "LOCKED"
    return "unverified", "UNVERIFIED"


def _task2_v4_lock_provenance(
    record: Mapping[str, object],
) -> tuple[str, str]:
    lock = record.get("lock")
    corpus = record.get("corpus")
    selected = lock.get("selected_rung") if isinstance(lock, Mapping) else None
    if (
        isinstance(lock, Mapping)
        and isinstance(corpus, Mapping)
        and isinstance(selected, Mapping)
        and lock.get("corpus_locked") is True
        and lock.get("rung_locked") is True
        and lock.get("corpus_digest") == corpus.get("digest")
        and selected.get("input_digest") == corpus.get("input_digest")
        and selected.get("alias_mapping_digest")
        == corpus.get("source_alias_mapping_digest")
        and selected.get("group_count") == corpus.get("selected_group_count")
        and selected.get("selected_left_count")
        == corpus.get("selected_left_count")
        and selected.get("selected_right_count")
        == corpus.get("selected_right_count")
    ):
        return "locked", "LOCKED"
    return "unverified", "UNVERIFIED"


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
    corpus_role = _text(corpus.get("role"), "corpus.role").upper()
    calibration_mode = _text(
        corpus.get("calibration_mode"),
        "corpus.calibration_mode",
    ).upper()
    independent_holdout = corpus.get("independent_holdout")
    if not isinstance(independent_holdout, bool):
        raise _RunRecordError("corpus.independent_holdout must be boolean")
    operation = _text(corpus.get("operation"), "corpus.operation")
    if operation not in {"find-ambiguities", "find-duplicates", "operation-gates"}:
        raise _RunRecordError("corpus.operation is unsupported")
    if operation in {"find-duplicates", "operation-gates"} and corpus_role != "CALIBRATION":
        raise _RunRecordError("this evaluation currently requires CALIBRATION")
    if (
        corpus_role == "CALIBRATION"
        and calibration_mode == "LEAVE_ONE_OUT"
        and not independent_holdout
    ):
        pass
    elif (
        corpus_role == "HOLDOUT"
        and calibration_mode == "FIXED_CALIBRATION"
        and independent_holdout
    ):
        pass
    else:
        raise _RunRecordError("corpus role and calibration mode are inconsistent")
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
    selection_scope: tuple[object, ...] | None = None
    selected_length_tiers: tuple[str, ...] = ()
    selected_tasks: tuple[int, ...] = ()
    selected_operations: tuple[str, ...] = ()
    selected_layer: str | None = None
    if operation == "operation-gates":
        tiers_value = corpus.get("selected_length_tiers")
        tasks_value = corpus.get("selected_tasks")
        operations_value = corpus.get("selected_operations")
        layer_value = corpus.get("selected_layer", "ALL")
        if (
            not isinstance(tiers_value, list)
            or not tiers_value
            or not set(tiers_value) <= {"SHORT", "LONG"}
            or not isinstance(tasks_value, list)
            or not tasks_value
            or not set(tasks_value) <= {1, 2, 3}
            or not isinstance(operations_value, list)
            or not operations_value
            or any(not isinstance(item, str) or not item for item in operations_value)
            or layer_value not in {"ALL", "BASE", "ADDITIONS"}
        ):
            raise _RunRecordError("operation gate selection scope is invalid")
        selected_length_tiers = tuple(sorted(tiers_value))
        selected_tasks = tuple(sorted(tasks_value))
        selected_operations = tuple(sorted(operations_value))
        selected_layer = str(layer_value)
        selection_scope = (
            selected_layer,
            selected_length_tiers,
            selected_tasks,
            selected_operations,
            tuple(selected_case_ids),
        )
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
    attempt_counts = _mapping(summary.get("attempts"), "summary.attempts")
    attempts_total = _integer(
        attempt_counts.get("total"),
        "summary.attempts.total",
    )
    attempts_structurally_valid = _integer(
        attempt_counts.get("structurally_valid"),
        "summary.attempts.structurally_valid",
    )
    attempts_exact = _integer(
        attempt_counts.get("exact_matches"),
        "summary.attempts.exact_matches",
    )
    if not 0 <= attempts_exact <= attempts_structurally_valid <= attempts_total:
        raise _RunRecordError("attempt counts are inconsistent")
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
    distribution: dict[str, dict[str, int]] | None = None
    relation_distribution: dict[str, int] | None = None
    label_distribution: dict[str, int] | None = None
    if operation == "find-ambiguities":
        distribution = _validate_distribution(distributions.get("expected_joint"))
        if sum(sum(row.values()) for row in distribution.values()) != cases_total:
            raise _RunRecordError(
                "expected label distribution does not match case total"
            )
    elif operation == "find-duplicates":
        relation_value = _mapping(
            distributions.get("expected_relation"),
            "summary.distributions.expected_relation",
        )
        if not set(relation_value) <= set(_DUPLICATE_RELATIONS):
            raise _RunRecordError("duplicate relation distribution is invalid")
        relation_distribution = {
            relation: _integer(count, f"expected_relation.{relation}")
            for relation, count in relation_value.items()
        }
        if sum(relation_distribution.values()) != cases_total:
            raise _RunRecordError(
                "expected relation distribution does not match case total"
            )
    else:
        label_value = _mapping(
            distributions.get("expected_label"),
            "summary.distributions.expected_label",
        )
        label_distribution = {
            _text(label, "expected label"): _integer(count, f"expected_label.{label}")
            for label, count in label_value.items()
        }
        if sum(label_distribution.values()) != cases_total:
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
    if not set(stage_stats_mapping) <= set(_STAGE_ORDER):
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
        "operation": operation,
        "corpus_role": corpus_role,
        "calibration_mode": calibration_mode,
        "independent_holdout": independent_holdout,
        "fixture_digest": fixture_digest,
        "fixture_case_count": fixture_case_count,
        "selected_case_count": len(selected_case_ids),
        "selection_scope": selection_scope,
        "selected_length_tiers": selected_length_tiers,
        "selected_tasks": selected_tasks,
        "selected_operations": selected_operations,
        "selected_layer": selected_layer,
        "runs_per_case": runs_per_case,
        "cases_total": cases_total,
        "cases_passed": cases_passed,
        "cases_failed": cases_failed,
        "attempts_total": attempts_total,
        "attempts_structurally_valid": attempts_structurally_valid,
        "attempts_exact": attempts_exact,
        "failure_counts": failure_counts,
        "distribution": distribution,
        "relation_distribution": relation_distribution,
        "label_distribution": label_distribution,
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
            record["operation"],
            record["provider"],
            record["model"],
            record["model_digest"],
            record["reasoning_effort"],
            record["effective_thinking"],
            record["pipeline_id"],
            record["pipeline_version"],
            record["corpus_role"],
            record["fixture_digest"],
            record["runs_per_case"],
            record["selection_scope"],
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
            item["operation"],
            item["provider"],
            item["model"],
            item["corpus_role"],
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
    tiers = record.get("selected_length_tiers")
    tasks = record.get("selected_tasks")
    layer = record.get("selected_layer")
    if isinstance(layer, str):
        parts.append("layer=" + layer.lower())
    if isinstance(tiers, tuple) and tiers:
        parts.append("tiers=" + ",".join(tier.lower() for tier in tiers))
    if isinstance(tasks, tuple) and tasks:
        parts.append("tasks=" + ",".join(str(task) for task in tasks))
    return " · " + " · ".join(parts)


def _format_seconds(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}s"


def _render_task2_judge_v7_record(
    record: Mapping[str, object],
    *,
    self_validation: Mapping[str, object],
) -> None:
    """Render one strictly self-validated Qwen-only V7 ablation record."""
    provider = _mapping(record.get("provider"), "task2 v7 provider")
    protocol = _mapping(record.get("evidence_protocol"), "task2 v7 protocol")
    boundary = _mapping(record.get("evaluation_boundary"), "task2 v7 boundary")
    directed_bundle = _mapping(
        record.get("candidate_bundle"), "task2 v7 directed bundle"
    )
    canonical_bundle = _mapping(
        record.get("canonical_bundle"), "task2 v7 canonical bundle"
    )
    score = _mapping(record.get("score"), "task2 v7 score")
    canonical = _mapping(score.get("canonical_judge"), "task2 v7 canonical score")
    binary = _mapping(
        canonical.get("binary_same_hypergroup"), "task2 v7 canonical binary"
    )
    multi = _mapping(
        canonical.get("multi_member_binary"), "task2 v7 canonical multi"
    )
    enum_score = _mapping(
        canonical.get("group_induced_enum"), "task2 v7 canonical enum"
    )
    direct = _mapping(
        canonical.get("reviewed_one_to_one_direct_subset"),
        "task2 v7 canonical reviewed direct",
    )
    evidence = _mapping(
        score.get("canonical_evidence"), "task2 v7 canonical evidence"
    )
    projected = _mapping(
        score.get("projected_directed_v5"), "task2 v7 directed projection"
    )
    projected_sources = _mapping(
        projected.get("source_accepted_set"), "task2 v7 projected source sets"
    )
    invariance = _mapping(
        score.get("direction_invariance"), "task2 v7 direction invariance"
    )
    timing = _mapping(record.get("timing"), "task2 v7 timing")
    label = str(provider.get("provider")) + ":" + str(provider.get("model"))
    typer.echo(
        "V7 canonical evidence judge · "
        + display_escape_text(label)
        + " · strict self-validation "
        + ("VALID" if self_validation.get("valid") is True else "UNAVAILABLE")
        + " · thinking="
        + str(record.get("effective_thinking")).lower()
    )
    typer.echo(
        "  canonicalization "
        + str(directed_bundle.get("directed_pair_count"))
        + "→"
        + str(canonical_bundle.get("pair_count"))
        + " canonical pairs · calls "
        + str(record.get("provider_call_count"))
        + "/"
        + str(record.get("expected_provider_call_count"))
    )
    typer.echo(
        "  protocols "
        + display_escape_text(str(protocol.get("prompt_revision")))
        + " · prompt "
        + str(protocol.get("prompt_protocol_digest"))[:12]
        + " · projection "
        + str(protocol.get("projection_protocol_digest"))[:12]
        + " · schema "
        + str(protocol.get("schema_protocol_digest"))[:12]
        + " · freeze "
        + str(protocol.get("evidence_freeze_digest"))[:12]
    )
    typer.echo(
        "  canonical evidence resolved/abstain/missing "
        + "/".join(
            str(evidence.get(field))
            for field in (
                "resolved",
                "explicit_abstain",
                "missing_due_invalid_call",
            )
        )
        + " · returned "
        + str(evidence.get("evidence_returned"))
        + "/"
        + str(evidence.get("canonical_pair_count"))
    )
    typer.echo(
        "  canonical partition-induced binary proxy TP/FP/TN/FN "
        + "/".join(
            str(binary.get(field))
            for field in (
                "true_positive",
                "false_positive",
                "true_negative",
                "false_negative",
            )
        )
        + " · precision "
        + f"{float(binary.get('precision', 0.0)):.3f}"
        + " · recall "
        + f"{float(binary.get('recall', 0.0)):.3f}"
        + " · FP/TN are not independently reviewed semantic-pair accuracy"
    )
    typer.echo(
        "  canonical enum "
        + str(enum_score.get("exact"))
        + "/"
        + str(enum_score.get("total"))
        + " · reviewed 1:1 direct "
        + str(direct.get("exact"))
        + "/"
        + str(direct.get("total"))
        + " · multi TP/FP/TN/FN "
        + "/".join(
            str(multi.get(field))
            for field in (
                "true_positive",
                "false_positive",
                "true_negative",
                "false_negative",
            )
        )
        + " · multi recall "
        + f"{float(multi.get('recall', 0.0)):.3f}"
    )
    typer.echo(
        "  projected directed source sets "
        + str(projected_sources.get("exact"))
        + "/"
        + str(projected_sources.get("total"))
        + " · direction invariance "
        + str(invariance.get("invariant_resolved_bidirectional_pairs"))
        + "/"
        + str(invariance.get("comparable_resolved_bidirectional_pairs"))
        + " · rate "
        + f"{float(invariance.get('invariance_rate', 0.0)):.3f}"
        + " · resolved bidirectional coverage "
        + f"{float(invariance.get('resolved_bidirectional_coverage', 0.0)):.3f}"
    )
    typer.echo(
        "  timing connection "
        + _format_seconds(float(timing.get("provider_connection_seconds", 0.0)))
        + " · input "
        + _format_seconds(float(timing.get("input_preparation_seconds", 0.0)))
        + " · pipeline "
        + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    typer.echo(
        "  evaluation "
        + display_escape_text(str(boundary.get("role")))
        + " · no scale promotion"
        + " · eligible="
        + str(boundary.get("scale_promotion_eligible")).lower()
    )
    typer.echo("  ledger " + display_escape_text(str(record.get("ledger_path"))))


def _render_task2_judge_v8_record(
    record: Mapping[str, object],
    *,
    self_validation: Mapping[str, object],
) -> None:
    """Render one integrity-valid and contract-valid Qwen-only V8 record."""
    provider = _mapping(record.get("provider"), "task2 v8 provider")
    protocol = _mapping(record.get("staged_protocol"), "task2 v8 protocol")
    boundary = _mapping(record.get("evaluation_boundary"), "task2 v8 boundary")
    directed_bundle = _mapping(
        record.get("candidate_bundle"), "task2 v8 directed bundle"
    )
    canonical_bundle = _mapping(
        record.get("canonical_bundle"), "task2 v8 canonical bundle"
    )
    schedules = _mapping(record.get("stage_schedules"), "task2 v8 schedules")
    stage_a = _mapping(schedules.get("stage_a"), "task2 v8 stage A schedule")
    stage_b = _mapping(schedules.get("stage_b"), "task2 v8 stage B schedule")
    stage_c_claim = _mapping(
        schedules.get("stage_c_claim"), "task2 v8 stage C claim schedule"
    )
    stage_c_primary = _mapping(
        schedules.get("stage_c_primary"), "task2 v8 stage C primary schedule"
    )
    calls = _mapping(record.get("calls"), "task2 v8 calls")
    score = _mapping(record.get("score"), "task2 v8 score")
    staged = _mapping(score.get("staged_pipeline"), "task2 v8 staged score")
    outcomes = _mapping(staged.get("outcome_counts"), "task2 v8 outcomes")
    anomalies = _mapping(staged.get("call_anomalies"), "task2 v8 anomalies")
    canonical = _mapping(score.get("canonical_judge"), "task2 v8 canonical score")
    binary = _mapping(
        canonical.get("binary_same_hypergroup"), "task2 v8 canonical binary"
    )
    multi = _mapping(
        canonical.get("multi_member_binary"), "task2 v8 canonical multi"
    )
    enum_score = _mapping(
        canonical.get("group_induced_enum"), "task2 v8 canonical enum"
    )
    direct = _mapping(
        canonical.get("reviewed_one_to_one_direct_subset"),
        "task2 v8 canonical reviewed direct",
    )
    projected = _mapping(
        score.get("projected_directed_v5"), "task2 v8 directed projection"
    )
    projected_sources = _mapping(
        projected.get("source_accepted_set"), "task2 v8 projected source sets"
    )
    invariance = _mapping(
        score.get("direction_invariance"), "task2 v8 direction invariance"
    )
    prompt_digests = _mapping(
        protocol.get("prompt_protocol_digests"), "task2 v8 prompt digests"
    )
    schema_digests = _mapping(
        protocol.get("schema_protocol_digests"), "task2 v8 schema digests"
    )
    timing = _mapping(record.get("timing"), "task2 v8 timing")

    def call_count(stage: str) -> int:
        value = calls.get(stage)
        return len(value) if isinstance(value, list) else 0

    label = str(provider.get("provider")) + ":" + str(provider.get("model"))
    stage_c_pairs = int(stage_c_claim.get("pair_count", 0)) + int(
        stage_c_primary.get("pair_count", 0)
    )
    stage_c_calls = call_count("stage_c_claim") + call_count("stage_c_primary")
    typer.echo(
        "V8 staged canonical judge · "
        + display_escape_text(label)
        + " · strict integrity VALID · contract VALID · thinking="
        + str(record.get("effective_thinking")).lower()
    )
    typer.echo(
        "  canonicalization "
        + str(directed_bundle.get("directed_pair_count"))
        + "→"
        + str(canonical_bundle.get("pair_count"))
        + " canonical pairs"
    )
    typer.echo(
        "  stage pairs A/B/C "
        + str(stage_a.get("pair_count"))
        + "/"
        + str(stage_b.get("pair_count"))
        + "/"
        + str(stage_c_pairs)
        + " · C claim/primary "
        + str(stage_c_claim.get("pair_count"))
        + "/"
        + str(stage_c_primary.get("pair_count"))
    )
    typer.echo(
        "  stage calls A/B/C "
        + str(call_count("stage_a"))
        + "/"
        + str(call_count("stage_b"))
        + "/"
        + str(stage_c_calls)
        + " · C claim/primary "
        + str(call_count("stage_c_claim"))
        + "/"
        + str(call_count("stage_c_primary"))
        + " · total "
        + str(record.get("provider_call_count"))
        + "/"
        + str(record.get("expected_provider_call_count"))
    )
    typer.echo(
        "  protocol "
        + display_escape_text(str(protocol.get("protocol_revision")))
        + " · projection "
        + str(protocol.get("projection_digest"))[:12]
        + " · input freeze "
        + str(protocol.get("input_freeze_digest"))[:12]
        + " · A schedule "
        + str(protocol.get("stage_a_schedule_digest"))[:12]
    )
    typer.echo(
        "  prompt digests A/B/C-claim/C-primary "
        + "/".join(
            str(prompt_digests.get(stage))[:12]
            for stage in (
                "STAGE_A_SCOPE_GATE",
                "STAGE_B_UNIT_KIND",
                "STAGE_C_CLAIM_OR_RULE",
                "STAGE_C_PRIMARY_OR_JOINT_UNIT",
            )
        )
    )
    typer.echo(
        "  schema digests A/B/C-claim/C-primary "
        + "/".join(
            str(schema_digests.get(stage))[:12]
            for stage in (
                "STAGE_A_SCOPE_GATE",
                "STAGE_B_UNIT_KIND",
                "STAGE_C_CLAIM_OR_RULE",
                "STAGE_C_PRIMARY_OR_JOINT_UNIT",
            )
        )
        + " · dynamic freezes B/C-claim/C-primary "
        + "/".join(
            str(schedule.get("freeze_digest"))[:12]
            for schedule in (stage_b, stage_c_claim, stage_c_primary)
        )
    )
    typer.echo(
        "  outcomes FINAL/ABSTAIN/INVALID_EVIDENCE/MISSING_DUE_CALL "
        + "/".join(
            str(outcomes.get(status))
            for status in (
                "FINAL",
                "ABSTAIN",
                "INVALID_EVIDENCE",
                "MISSING_DUE_CALL",
            )
        )
    )
    typer.echo(
        "  call anomalies invalid-items/invalid-pairs/unattributable/missing/"
        "response-mismatch "
        + "/".join(
            str(anomalies.get(field))
            for field in (
                "attributable_invalid_item_count",
                "invalid_pair_count",
                "unattributable_item_count",
                "missing_pair_count",
                "response_count_mismatch_calls",
            )
        )
    )
    typer.echo(
        "  canonical partition-induced binary proxy TP/FP/TN/FN "
        + "/".join(
            str(binary.get(field))
            for field in (
                "true_positive",
                "false_positive",
                "true_negative",
                "false_negative",
            )
        )
        + " · precision "
        + f"{float(binary.get('precision', 0.0)):.3f}"
        + " · recall "
        + f"{float(binary.get('recall', 0.0)):.3f}"
        + " · FP/TN are partition-induced negative proxies"
    )
    typer.echo(
        "  canonical enum "
        + str(enum_score.get("exact"))
        + "/"
        + str(enum_score.get("total"))
        + " · reviewed 1:1 direct "
        + str(direct.get("exact"))
        + "/"
        + str(direct.get("total"))
        + " · multi TP/FP/TN/FN "
        + "/".join(
            str(multi.get(field))
            for field in (
                "true_positive",
                "false_positive",
                "true_negative",
                "false_negative",
            )
        )
        + " · multi recall "
        + f"{float(multi.get('recall', 0.0)):.3f}"
    )
    typer.echo(
        "  projected directed source sets "
        + str(projected_sources.get("exact"))
        + "/"
        + str(projected_sources.get("total"))
        + " · direction invariance "
        + str(invariance.get("invariant_resolved_bidirectional_pairs"))
        + "/"
        + str(invariance.get("comparable_resolved_bidirectional_pairs"))
        + " · rate "
        + f"{float(invariance.get('invariance_rate', 0.0)):.3f}"
    )
    typer.echo(
        "  stage time A/B/C-claim/C-primary "
        + "/".join(
            _format_seconds(float(timing.get(field, 0.0)))
            for field in (
                "stage_a_seconds",
                "stage_b_seconds",
                "stage_c_claim_seconds",
                "stage_c_primary_seconds",
            )
        )
        + " · pipeline "
        + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    typer.echo(
        "  evaluation "
        + display_escape_text(str(boundary.get("role")))
        + " · no scale promotion · eligible="
        + str(boundary.get("scale_promotion_eligible")).lower()
        + " · validator contract="
        + str(self_validation.get("contract_valid")).lower()
    )
    typer.echo("  ledger " + display_escape_text(str(record.get("ledger_path"))))


def _render_distribution(distribution: dict[str, dict[str, int]]) -> None:
    typer.echo("Label distribution:")
    typer.echo("  interpretation   NONE  HELPFUL  REQUIRED")
    for interpretation in _INTERPRETATIONS:
        row = distribution[interpretation]
        typer.echo(
            f"  {interpretation:<14}"
            f" {row['NONE']:>4}  {row['HELPFUL']:>7}  {row['REQUIRED']:>8}"
        )


def _render_relation_distribution(distribution: Mapping[str, int]) -> None:
    typer.echo("Relation distribution:")
    for relation in _DUPLICATE_RELATIONS:
        typer.echo(f"  {relation:<24}{distribution.get(relation, 0):>4}")


def _render_label_distribution(distribution: Mapping[str, int]) -> None:
    typer.echo("Gate label distribution:")
    for label, count in sorted(distribution.items()):
        typer.echo(f"  {display_escape_text(label):<24}{count:>4}")


def _render_stage_timing(stage_stats: Mapping[str, object]) -> None:
    if not stage_stats:
        return
    typer.echo("Stage timing (mean/p95):")
    for stage in _STAGE_ORDER:
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
    operation_label = {
        "find-ambiguities": "ambiguity",
        "find-duplicates": "duplicate",
        "operation-gates": "operation suite",
    }[result["operation"]]
    typer.secho(
        f"Semantic eval · {operation_label} · classification gate",
        bold=True,
    )
    typer.echo(
        "Provider: "
        + display_escape_text(f"{result['provider']}:{result['model']}")
        + _condition_suffix(result)
    )
    if result["corpus_role"] == "HOLDOUT":
        typer.echo(
            "Corpus: HOLDOUT · independent · fixed calibration · digest "
            + result["fixture_digest"][:12]
        )
    else:
        typer.echo(
            "Corpus: CALIBRATION · leave-one-out · not an independent holdout"
            " · digest "
            + result["fixture_digest"][:12]
        )
    typer.echo(
        f"Pipeline: {display_escape_text(result['pipeline_id'])}"
        f" · schema v{result['pipeline_version']}"
    )
    typer.echo(
        f"Score: {result['cases_passed']}/{result['cases_total']} cases passed"
    )
    typer.echo(
        f"Attempts: exact {result['attempts_exact']}/{result['attempts_total']}"
        f" · structurally valid {result['attempts_structurally_valid']}/"
        f"{result['attempts_total']}"
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
    if result["distribution"] is not None:
        _render_distribution(result["distribution"])
    elif result["relation_distribution"] is not None:
        _render_relation_distribution(result["relation_distribution"])
    elif result["label_distribution"] is not None:
        _render_label_distribution(result["label_distribution"])
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
            help="Ambiguity pipeline: v1 replay through compiled-rules v6",
        ),
    ] = "v2",
    corpus: Annotated[
        str,
        typer.Option(
            "--corpus",
            help="Scored corpus: calibration or frozen independent holdout",
        ),
    ] = "calibration",
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
    """Run a versioned ambiguity calibration or frozen holdout campaign."""
    selected_pipeline = pipeline.strip().lower()
    if selected_pipeline not in PIPELINE_CHOICES:
        raise typer.BadParameter(
            "--pipeline must be one of: " + ", ".join(PIPELINE_CHOICES)
        )
    selected_corpus = corpus.strip().lower()
    if selected_corpus not in CORPUS_CHOICES:
        raise typer.BadParameter(
            "--corpus must be one of: " + ", ".join(CORPUS_CHOICES)
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
            corpus_role=selected_corpus,
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


@run_app.command("duplicate")
def run_duplicate(
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
    """Run the host-first duplicate relation calibration campaign."""
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
        result = run_duplicate_campaign(
            provider,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            runs=runs,
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


@run_app.command("gates")
def run_gates(
    provider_id: Annotated[
        Optional[str],
        typer.Option("--provider", help="Transient provider; defaults to configured selection"),
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
    runs: Annotated[
        int,
        typer.Option("--runs", "-n", min=1, max=20, help="Attempts per case"),
    ] = 1,
    operations: Annotated[
        Optional[list[str]],
        typer.Option("--operation", help="Operation gate to include; repeatable"),
    ] = None,
    length_tiers: Annotated[
        Optional[list[str]],
        typer.Option("--tier", help="SHORT or LONG; repeatable"),
    ] = None,
    tasks: Annotated[
        Optional[list[int]],
        typer.Option("--task", min=1, max=3, help="Task fixture scope; repeatable"),
    ] = None,
    case_ids: Annotated[
        Optional[list[str]],
        typer.Option("--case", help="Run only this case ID; repeatable"),
    ] = None,
    fixture: Annotated[
        Optional[Path],
        typer.Option("--fixture", exists=True, dir_okay=False, help="Gate corpus or extension fixture"),
    ] = None,
    layer: Annotated[
        str,
        typer.Option("--layer", help="Composite corpus layer: all, base, or additions"),
    ] = "all",
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
    """Run bounded gates for the remaining semantic operations."""
    connection_started = time.monotonic()
    try:
        provider = _connect_transient_provider(
            provider_id=provider_id,
            model=model,
            preset=preset,
            reasoning=reasoning,
            thinking=thinking,
        )
    except (QueryProviderError, SemanticCampaignError, RuntimeError, ValueError, OSError) as error:
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
    label = identity.display_name() if isinstance(identity, ProviderIdentity) else "configured semantic provider"
    typer.echo("Connected: " + display_escape_text(label) + " · " + _format_seconds(connection_seconds))

    def report_progress(event: object) -> None:
        line = _progress_line(event)
        if line is not None:
            typer.echo(line)

    try:
        result = run_operation_gate_campaign(
            provider,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            runs=runs,
            operations=operations,
            length_tiers=[tier.upper() for tier in length_tiers] if length_tiers else None,
            tasks=tasks,
            case_ids=case_ids,
            fixture_path=fixture,
            layer=layer,
            known_error_types=(QueryProviderError,),
            progress_fn=report_progress,
        )
        rendered = _render_campaign_result(result)
    except (QueryProviderError, SemanticCampaignError, RuntimeError, ValueError, OSError) as error:
        typer.secho("Semantic eval error: " + _redacted_error(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if rendered["cases_failed"]:
        raise typer.Exit(1)


@run_app.command("task2-discovery")
def run_task2_discovery(
    provider_id: Annotated[
        Optional[str],
        typer.Option("--provider", help="Transient provider; defaults to configured selection"),
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
    groups: Annotated[
        int,
        typer.Option(
            "--groups",
            min=1,
            max=138,
            help="Complete reviewed relation groups in the calibration slice",
        ),
    ] = 26,
    language: Annotated[
        str,
        typer.Option("--language", help="Fixture language: en or ko"),
    ] = "en",
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
    """Discover Task 2 relation groups and bands from two unordered sets."""
    selected_language = language.strip().lower()
    if selected_language != "en":
        raise typer.BadParameter(
            "--language must be en for scored campaigns; ko is unreviewed robustness data"
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
    except (QueryProviderError, Task2DiscoveryError, RuntimeError, ValueError, OSError) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 discovery connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    label = (
        identity.display_name()
        if isinstance(identity, ProviderIdentity)
        else "configured semantic provider"
    )
    typer.echo(
        "Connected: "
        + display_escape_text(label)
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_discovery_campaign(
            provider,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            language=selected_language,
            group_count=groups,
            known_error_types=(QueryProviderError,),
        )
    except (QueryProviderError, Task2DiscoveryError, RuntimeError, ValueError, OSError) as error:
        typer.secho(
            "Task 2 discovery error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    corpus = _mapping(record.get("corpus"), "task2 corpus")
    score = _mapping(record.get("score"), "task2 score")
    timing = _mapping(record.get("timing"), "task2 timing")
    if record.get("contract_valid") is False:
        typer.secho(
            "Contract: INVALID_OUTPUT · "
            + display_escape_text(str(record.get("validation_error"))),
            fg=typer.colors.RED,
        )
    typer.echo(
        "Slice: "
        + str(corpus.get("selected_left_count"))
        + " left × "
        + str(corpus.get("selected_right_count"))
        + " right · "
        + str(corpus.get("selected_group_count"))
        + "/"
        + str(corpus.get("full_group_count"))
        + " reviewed groups"
    )
    typer.echo(
        "Discovery: exact groups "
        + str(score.get("exact_structure_groups"))
        + "/"
        + str(score.get("expected_groups"))
        + " · group-induced co-membership "
        + str(score.get("member_counterpart_exact"))
        + "/"
        + str(score.get("member_counterpart_total"))
        + " · co-membership Jaccard "
        + f"{float(score.get('member_counterpart_macro_jaccard', 0.0)):.3f}"
    )
    typer.echo(
        "Classification: exact structure+band "
        + str(score.get("exact_band_groups"))
        + "/"
        + str(score.get("expected_groups"))
        + " · conditional band accuracy "
        + (
            f"{float(score['band_accuracy_on_exact_structures']):.3f}"
            if isinstance(score.get("band_accuracy_on_exact_structures"), (int, float))
            and not isinstance(score.get("band_accuracy_on_exact_structures"), bool)
            else "N/A"
        )
    )
    typer.echo(
        "Timing: connection "
        + _format_seconds(float(timing.get("provider_connection_seconds", 0.0)))
        + " · corpus "
        + _format_seconds(float(timing.get("corpus_preparation_seconds", 0.0)))
        + " · prompt "
        + _format_seconds(float(timing.get("prompt_preparation_seconds", 0.0)))
        + " · provider "
        + _format_seconds(float(timing.get("provider_completion_seconds", 0.0)))
        + " · validate "
        + _format_seconds(float(timing.get("response_validation_seconds", 0.0)))
        + " · score "
        + _format_seconds(float(timing.get("scoring_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    typer.echo("Ledger: " + display_escape_text(str(record.get("ledger_path"))))
    if record.get("contract_valid") is not True or not score.get("exact_complete_match"):
        raise typer.Exit(1)


@run_app.command("task2-classification")
def run_task2_classification(
    provider_id: Annotated[
        Optional[str],
        typer.Option("--provider", help="Transient provider; defaults to configured selection"),
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
    groups: Annotated[
        int,
        typer.Option("--groups", min=1, max=138, help="Reviewed oracle groups to classify"),
    ] = 26,
    language: Annotated[
        str,
        typer.Option("--language", help="Fixture language: en or ko"),
    ] = "en",
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
    """Classify hidden bands for supplied reviewed Task 2 group structures."""
    selected_language = language.strip().lower()
    if selected_language != "en":
        raise typer.BadParameter(
            "--language must be en for scored campaigns; ko is unreviewed robustness data"
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
    except (QueryProviderError, Task2ClassificationError, RuntimeError, ValueError, OSError) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 classification connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    label = (
        identity.display_name()
        if isinstance(identity, ProviderIdentity)
        else "configured semantic provider"
    )
    typer.echo(
        "Connected: "
        + display_escape_text(label)
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_classification_campaign(
            provider,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            language=selected_language,
            group_count=groups,
        )
    except (QueryProviderError, Task2ClassificationError, RuntimeError, ValueError, OSError) as error:
        typer.secho(
            "Task 2 classification error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    score = _mapping(record.get("score"), "task2 classification score")
    timing = _mapping(record.get("timing"), "task2 classification timing")
    if record.get("contract_valid") is False:
        typer.secho(
            "Contract: INVALID_OUTPUT · "
            + display_escape_text(str(record.get("validation_error"))),
            fg=typer.colors.RED,
        )
    typer.echo(
        "Oracle classification: "
        + str(score.get("correct_projected_band_groups"))
        + "/"
        + str(score.get("expected_groups"))
        + " projected bands · accuracy "
        + f"{float(score.get('projected_band_accuracy', 0.0)):.3f}"
    )
    typer.echo(
        "Evidence: "
        + " · ".join(
            display_escape_text(str(name)) + "=" + str(count)
            for name, count in sorted(
                _mapping(score.get("evidence_distribution"), "task2 evidence").items()
            )
        )
    )
    typer.echo(
        "Timing: connection "
        + _format_seconds(float(timing.get("provider_connection_seconds", 0.0)))
        + " · provider "
        + _format_seconds(float(timing.get("provider_completion_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    typer.echo("Ledger: " + display_escape_text(str(record.get("ledger_path"))))
    if record.get("contract_valid") is not True or not score.get("exact_complete_match"):
        raise typer.Exit(1)


@run_app.command("task2-discovery-v2")
def run_task2_discovery_v2(
    provider_id: Annotated[
        Optional[str],
        typer.Option("--provider", help="Transient provider; defaults to configured selection"),
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
    groups: Annotated[
        int,
        typer.Option("--groups", min=1, max=138, help="Complete reviewed groups in the frozen slice"),
    ] = 26,
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
    """Run fixed candidate-grouping and global-reconciliation calls without bands."""
    connection_started = time.monotonic()
    try:
        provider = _connect_transient_provider(
            provider_id=provider_id,
            model=model,
            preset=preset,
            reasoning=reasoning,
            thinking=thinking,
        )
    except (QueryProviderError, Task2DiscoveryV2Error, RuntimeError, ValueError, OSError) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 discovery v2 connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    label = (
        identity.display_name()
        if isinstance(identity, ProviderIdentity)
        else "configured semantic provider"
    )
    typer.echo(
        "Connected: "
        + display_escape_text(label)
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_discovery_v2_campaign(
            provider,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            group_count=groups,
        )
    except (QueryProviderError, Task2DiscoveryV2Error, RuntimeError, ValueError, OSError) as error:
        typer.secho(
            "Task 2 discovery v2 error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    corpus = _mapping(record.get("corpus"), "task2 v2 corpus")
    stage1 = _mapping(record.get("stage1"), "task2 v2 stage1")
    stage2 = _mapping(record.get("stage2"), "task2 v2 stage2")
    score = _mapping(record.get("score"), "task2 v2 score")
    timing = _mapping(record.get("timing"), "task2 v2 timing")
    if record.get("contract_valid") is False:
        typer.secho(
            "Contract: INVALID_OUTPUT · "
            + display_escape_text(str(record.get("validation_error"))),
            fg=typer.colors.RED,
        )
    typer.echo(
        "Slice: "
        + str(corpus.get("selected_left_count"))
        + " left × "
        + str(corpus.get("selected_right_count"))
        + " right · two fixed calls"
    )
    typer.echo(
        "Stages: candidate "
        + ("VALID" if stage1.get("contract_valid") else "INVALID")
        + " ("
        + str(len(stage1.get("groups", [])))
        + " draft groups, "
        + _format_seconds(float(stage1.get("provider_completion_seconds", 0.0)))
        + ") · reconciliation "
        + ("VALID" if stage2.get("contract_valid") else "INVALID")
        + " ("
        + str(len(stage2.get("groups", [])))
        + " groups, "
        + _format_seconds(float(stage2.get("provider_completion_seconds", 0.0)))
        + ")"
    )
    typer.echo(
        "Discovery: exact groups "
        + str(score.get("exact_structure_groups"))
        + "/"
        + str(score.get("expected_groups"))
        + " · group-induced co-membership "
        + str(score.get("member_counterpart_exact"))
        + "/"
        + str(score.get("member_counterpart_total"))
        + " · co-membership Jaccard "
        + f"{float(score.get('member_counterpart_macro_jaccard', 0.0)):.3f}"
    )
    typer.echo(
        "Timing: connection "
        + _format_seconds(float(timing.get("provider_connection_seconds", 0.0)))
        + " · pipeline "
        + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    typer.echo("Ledger: " + display_escape_text(str(record.get("ledger_path"))))
    if not record.get("contract_valid") or not score.get("exact_complete_match"):
        raise typer.Exit(1)


@run_app.command("task2-retrieval-v3")
def run_task2_retrieval_v3(
    provider_id: Annotated[
        Optional[str],
        typer.Option("--provider", help="Transient provider; defaults to configured selection"),
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
    groups: Annotated[
        int,
        typer.Option(
            "--groups",
            min=1,
            max=138,
            help="Frozen scale rung: 26, 50, 100, or 138 groups",
        ),
    ] = 26,
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
    """Retrieve opposite-side group co-members in fixed source microbatches."""
    if groups not in (26, 50, 100, 138):
        raise typer.BadParameter("--groups must be one of 26, 50, 100, or 138")
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
        Task2RetrievalV3Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 retrieval v3 connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    label = (
        identity.display_name()
        if isinstance(identity, ProviderIdentity)
        else "configured semantic provider"
    )
    typer.echo(
        "Connected: "
        + display_escape_text(label)
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_retrieval_v3_campaign(
            provider,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            group_count=groups,
            known_error_types=(QueryProviderError,),
        )
    except (
        QueryProviderError,
        Task2RetrievalV3Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        typer.secho(
            "Task 2 retrieval v3 error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    corpus = _mapping(record.get("corpus"), "task2 v3 corpus")
    score = _mapping(record.get("score"), "task2 v3 score")
    direct = _mapping(
        score.get("group_co_membership_retrieval"), "task2 v3 co-membership score"
    )
    reviewed = _mapping(
        direct.get("reviewed_one_to_one_subset"), "task2 v3 reviewed 1:1 subset"
    )
    reviewed_overall = _mapping(
        reviewed.get("overall"), "task2 v3 reviewed direct score"
    )
    co_membership = _mapping(
        direct.get("group_co_membership"), "task2 v3 group co-membership"
    )
    co_membership_overall = _mapping(
        co_membership.get("overall"), "task2 v3 group co-membership score"
    )
    diagnostics = _mapping(
        score.get("grouping_diagnostics"), "task2 v3 grouping diagnostics"
    )
    reciprocal = _mapping(
        _mapping(diagnostics.get("reciprocal"), "task2 v3 reciprocal").get("score"),
        "task2 v3 reciprocal score",
    )
    union = _mapping(
        _mapping(diagnostics.get("union"), "task2 v3 union").get("score"),
        "task2 v3 union score",
    )
    timing = _mapping(record.get("timing"), "task2 v3 timing")
    promotion = evaluate_task2_retrieval_v3_promotion(record)
    promotion_criteria = _mapping(
        promotion.get("criteria"), "task2 v3 promotion criteria"
    )
    if record.get("contract_valid") is not True:
        typer.secho(
            "Contract: "
            + display_escape_text(str(record.get("status")))
            + " · "
            + display_escape_text(str(record.get("validation_error"))),
            fg=typer.colors.RED,
        )
    typer.echo(
        "Slice: "
        + str(corpus.get("selected_left_count"))
        + " left × "
        + str(corpus.get("selected_right_count"))
        + " right · "
        + str(record.get("provider_call_count"))
        + "/"
        + str(record.get("expected_provider_call_count"))
        + " fixed calls"
    )
    typer.echo(
        "Group co-membership: exact "
        + str(co_membership_overall.get("exact"))
        + "/"
        + str(co_membership_overall.get("total"))
        + " · macro Jaccard "
        + f"{float(co_membership_overall.get('macro_jaccard', 0.0)):.3f}"
        + " · not atomic-pair accuracy"
    )
    typer.echo(
        "Reviewed 1:1 subset: exact "
        + str(reviewed_overall.get("exact"))
        + "/"
        + str(reviewed_overall.get("total"))
    )
    typer.echo(
        "Grouping diagnostics: reciprocal "
        + str(reciprocal.get("exact_groups"))
        + "/"
        + str(reciprocal.get("expected_groups"))
        + " · union "
        + str(union.get("exact_groups"))
        + "/"
        + str(union.get("expected_groups"))
        + " · no Gold-selected grouping"
    )
    typer.echo(
        "Timing: connection "
        + _format_seconds(float(timing.get("provider_connection_seconds", 0.0)))
        + " · pipeline "
        + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    retrieval_recall_gate = _mapping(
        promotion_criteria.get("co_membership_micro_recall"),
        "task2 v3 co-membership micro-recall gate",
    )
    exact_gate = _mapping(
        promotion_criteria.get("co_membership_exact_accuracy"),
        "task2 v3 co-membership exact gate",
    )
    group_gate = _mapping(
        promotion_criteria.get("reciprocal_group_f1"), "task2 v3 group gate"
    )
    multi_gate = _mapping(
        promotion_criteria.get("multi_member_group_recall"),
        "task2 v3 multi-group gate",
    )
    typer.echo(
        "Single-run rung gate: "
        + ("PASS" if promotion.get("passed") else "FAIL")
        + " · co-membership micro recall "
        + f"{float(retrieval_recall_gate.get('actual', 0.0)):.3f}"
        + " · exact accuracy "
        + f"{float(exact_gate.get('actual', 0.0)):.3f}"
        + " · reciprocal group F1 "
        + f"{float(group_gate.get('actual', 0.0)):.3f}"
        + " · multi-group recall "
        + f"{float(multi_gate.get('actual', 0.0)):.3f}"
    )
    typer.echo("Ledger: " + display_escape_text(str(record.get("ledger_path"))))
    if promotion.get("passed") is not True:
        raise typer.Exit(1)


@run_app.command("task2-retrieval-v4")
def run_task2_retrieval_v4(
    provider_id: Annotated[
        Optional[str],
        typer.Option("--provider", help="Transient provider; defaults to configured selection"),
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
    groups: Annotated[
        int,
        typer.Option(
            "--groups",
            min=1,
            max=138,
            help="Frozen scale rung: 26, 50, 100, or 138 groups",
        ),
    ] = 26,
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
    """Run fixed Stage-A candidate retrieval and Stage-B verification."""
    if groups not in (26, 50, 100, 138):
        raise typer.BadParameter("--groups must be one of 26, 50, 100, or 138")
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
        Task2RetrievalV4Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 retrieval v4 connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    label = (
        identity.display_name()
        if isinstance(identity, ProviderIdentity)
        else "configured semantic provider"
    )
    typer.echo(
        "Connected: "
        + display_escape_text(label)
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_retrieval_v4_campaign(
            provider,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            group_count=groups,
            known_error_types=(QueryProviderError,),
        )
    except (
        QueryProviderError,
        Task2RetrievalV4Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        typer.secho(
            "Task 2 retrieval v4 error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    corpus = _mapping(record.get("corpus"), "task2 v4 corpus")
    score = _mapping(record.get("score"), "task2 v4 score")
    candidates = _mapping(
        score.get("candidate_retrieval"), "task2 v4 candidate score"
    )
    final = _mapping(
        score.get("final_group_co_membership"), "task2 v4 final score"
    )
    reviewed = _mapping(
        final.get("reviewed_one_to_one_subset"), "task2 v4 reviewed subset"
    )
    reviewed_overall = _mapping(
        reviewed.get("overall"), "task2 v4 reviewed subset overall"
    )
    all_reviewed = _mapping(
        final.get("all_reviewed_groups"), "task2 v4 all-reviewed score"
    )
    all_reviewed_overall = _mapping(
        all_reviewed.get("overall"), "task2 v4 all-reviewed overall"
    )
    diagnostics = _mapping(
        score.get("grouping_diagnostics"), "task2 v4 grouping diagnostics"
    )
    reciprocal = _mapping(
        _mapping(diagnostics.get("reciprocal"), "task2 v4 reciprocal").get(
            "score"
        ),
        "task2 v4 reciprocal score",
    )
    union = _mapping(
        _mapping(diagnostics.get("union"), "task2 v4 union").get("score"),
        "task2 v4 union score",
    )
    timing = _mapping(record.get("timing"), "task2 v4 timing")
    rung_gate = evaluate_task2_retrieval_v4_rung_gate(record)
    gate_criteria = _mapping(rung_gate.get("criteria"), "task2 v4 rung criteria")
    if record.get("contract_valid") is not True:
        typer.secho(
            "Contract: "
            + display_escape_text(str(record.get("status")))
            + " · "
            + display_escape_text(str(record.get("validation_error"))),
            fg=typer.colors.RED,
        )
    typer.echo(
        "Slice: "
        + str(corpus.get("selected_left_count"))
        + " left × "
        + str(corpus.get("selected_right_count"))
        + " right · "
        + str(record.get("provider_call_count"))
        + "/"
        + str(record.get("expected_provider_call_count"))
        + " fixed calls"
    )
    typer.echo(
        "Stage A candidate recall@3: "
        + str(candidates.get("recalled"))
        + "/"
        + str(candidates.get("expected"))
        + " · micro "
        + f"{float(candidates.get('recall_at_3', 0.0)):.3f}"
        + " · macro-source "
        + f"{float(candidates.get('macro_source_recall_at_3', 0.0)):.3f}"
    )
    typer.echo(
        "Stage B group co-membership: exact "
        + str(all_reviewed_overall.get("exact"))
        + "/"
        + str(all_reviewed_overall.get("total"))
        + " · macro Jaccard "
        + f"{float(all_reviewed_overall.get('macro_jaccard', 0.0)):.3f}"
        + " · not atomic-pair accuracy"
    )
    typer.echo(
        "Reviewed 1:1 subset: exact "
        + str(reviewed_overall.get("exact"))
        + "/"
        + str(reviewed_overall.get("total"))
    )
    typer.echo(
        "Grouping diagnostics: reciprocal "
        + str(reciprocal.get("exact_groups"))
        + "/"
        + str(reciprocal.get("expected_groups"))
        + " · union "
        + str(union.get("exact_groups"))
        + "/"
        + str(union.get("expected_groups"))
        + " · no Gold-selected grouping"
    )
    typer.echo(
        "Timing: connection "
        + _format_seconds(float(timing.get("provider_connection_seconds", 0.0)))
        + " · Stage A calls "
        + _format_seconds(float(timing.get("candidate_stage_call_seconds", 0.0)))
        + " · Stage B calls "
        + _format_seconds(float(timing.get("verifier_stage_call_seconds", 0.0)))
        + " · pipeline "
        + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    candidate_gate = _mapping(
        gate_criteria.get("candidate_recall_at_3"), "task2 v4 candidate gate"
    )
    final_gate = _mapping(
        gate_criteria.get("final_co_membership_exact_accuracy"),
        "task2 v4 final co-membership gate",
    )
    group_gate = _mapping(
        gate_criteria.get("reciprocal_group_f1"), "task2 v4 group gate"
    )
    multi_gate = _mapping(
        gate_criteria.get("multi_member_group_recall"), "task2 v4 multi gate"
    )
    typer.echo(
        "Single-run rung gate: "
        + ("PASS" if rung_gate.get("passed") else "FAIL")
        + " · candidate recall@3 "
        + f"{float(candidate_gate.get('actual', 0.0)):.3f}"
        + " · final exact "
        + f"{float(final_gate.get('actual', 0.0)):.3f}"
        + " · reciprocal group F1 "
        + f"{float(group_gate.get('actual', 0.0)):.3f}"
        + " · multi-group recall "
        + f"{float(multi_gate.get('actual', 0.0)):.3f}"
        + " · scale promotion still requires 3/3 repeats"
    )
    typer.echo("Ledger: " + display_escape_text(str(record.get("ledger_path"))))
    if rung_gate.get("passed") is not True:
        raise typer.Exit(1)


@run_app.command("task2-judge-replay-v5")
def run_task2_judge_replay_v5(
    candidate_ledgers: Annotated[
        Optional[list[Path]],
        typer.Option(
            "--candidate-ledger",
            exists=True,
            dir_okay=False,
            help="Contract-valid V4 parent; repeat at least twice",
        ),
    ] = None,
    provider_id: Annotated[
        Optional[str],
        typer.Option("--provider", help="Transient provider; defaults to configured selection"),
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
    """Judge one frozen Gold-blind union of identical V4 candidate pairs."""
    parents = list(candidate_ledgers or [])
    if len(parents) < 2:
        raise typer.BadParameter(
            "--candidate-ledger must be repeated for at least two V4 parents"
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
        Task2JudgeReplayV5Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 judge replay v5 connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    label = (
        identity.display_name()
        if isinstance(identity, ProviderIdentity)
        else "configured semantic provider"
    )
    typer.echo(
        "Connected: "
        + display_escape_text(label)
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_judge_replay_v5_campaign(
            provider,
            parent_ledgers=parents,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            known_error_types=(QueryProviderError,),
        )
    except (
        QueryProviderError,
        Task2JudgeReplayV5Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        typer.secho(
            "Task 2 judge replay v5 error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    bundle = _mapping(record.get("candidate_bundle"), "task2 v5 candidate bundle")
    score = _mapping(record.get("score"), "task2 v5 score")
    ceiling = _mapping(score.get("candidate_ceiling"), "task2 v5 candidate ceiling")
    binary = _mapping(
        score.get("binary_same_hypergroup"), "task2 v5 binary score"
    )
    enum_score = _mapping(score.get("group_induced_enum"), "task2 v5 enum score")
    direct = _mapping(
        score.get("reviewed_one_to_one_direct_subset"),
        "task2 v5 reviewed direct score",
    )
    sources = _mapping(
        score.get("source_accepted_set"), "task2 v5 accepted source sets"
    )
    timing = _mapping(record.get("timing"), "task2 v5 timing")
    if record.get("contract_valid") is not True:
        typer.secho(
            "Contract: "
            + display_escape_text(str(record.get("status")))
            + " · "
            + display_escape_text(str(record.get("validation_error"))),
            fg=typer.colors.RED,
        )
    typer.echo(
        "Fixed judge bundle: "
        + str(bundle.get("pair_count"))
        + " directed candidate pairs · "
        + str(record.get("provider_call_count"))
        + "/"
        + str(record.get("expected_provider_call_count"))
        + " fixed calls · digest "
        + str(bundle.get("digest"))[:12]
    )
    typer.echo(
        "Candidate ceiling: directed Gold co-members "
        + str(ceiling.get("recovered_directed_group_edges"))
        + "/"
        + str(ceiling.get("expected_directed_group_edges"))
        + " · recoverable groups "
        + str(ceiling.get("recoverable_groups"))
        + "/"
        + str(ceiling.get("group_total"))
    )
    typer.echo(
        "Partition-induced binary proxy: TP/FP/TN/FN "
        + "/".join(
            str(binary.get(field))
            for field in (
                "true_positive",
                "false_positive",
                "true_negative",
                "false_negative",
            )
        )
        + " · precision "
        + f"{float(binary.get('precision', 0.0)):.3f}"
        + " · recall "
        + f"{float(binary.get('recall', 0.0)):.3f}"
        + " · F1 "
        + f"{float(binary.get('f1', 0.0)):.3f}"
        + " · not independently reviewed negative-pair accuracy"
    )
    typer.echo(
        "Group-induced enum: exact "
        + str(enum_score.get("exact"))
        + "/"
        + str(enum_score.get("total"))
        + " · reviewed 1:1 direct enum "
        + str(direct.get("exact"))
        + "/"
        + str(direct.get("total"))
        + " · accepted source sets "
        + str(sources.get("exact"))
        + "/"
        + str(sources.get("total"))
    )
    typer.echo(
        "Timing: connection "
        + _format_seconds(float(timing.get("provider_connection_seconds", 0.0)))
        + " · input "
        + _format_seconds(float(timing.get("input_preparation_seconds", 0.0)))
        + " · judge pipeline "
        + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    typer.echo("Ledger: " + display_escape_text(str(record.get("ledger_path"))))
    if record.get("contract_valid") is not True:
        raise typer.Exit(1)


@run_app.command("task2-judge-replay-v6")
def run_task2_judge_replay_v6(
    candidate_ledgers: Annotated[
        Optional[list[Path]],
        typer.Option(
            "--candidate-ledger",
            exists=True,
            dir_okay=False,
            help="Contract-valid V4 parent; repeat at least twice",
        ),
    ] = None,
    provider_id: Annotated[
        Optional[str],
        typer.Option("--provider", help="Transient provider; defaults to configured selection"),
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
    """Replay the V5 candidate freeze with the V6 strict-boundary prompt."""
    parents = list(candidate_ledgers or [])
    if len(parents) < 2:
        raise typer.BadParameter(
            "--candidate-ledger must be repeated for at least two V4 parents"
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
        Task2JudgeReplayV6Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 judge replay v6 connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    label = (
        identity.display_name()
        if isinstance(identity, ProviderIdentity)
        else "configured semantic provider"
    )
    typer.echo(
        "Connected: "
        + display_escape_text(label)
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_judge_replay_v6_campaign(
            provider,
            parent_ledgers=parents,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            known_error_types=(QueryProviderError,),
        )
    except (
        QueryProviderError,
        Task2JudgeReplayV6Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        typer.secho(
            "Task 2 judge replay v6 error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    prompt = _mapping(record.get("prompt_ablation"), "task2 v6 prompt ablation")
    bundle = _mapping(record.get("candidate_bundle"), "task2 v6 candidate bundle")
    score = _mapping(record.get("score"), "task2 v6 score")
    ceiling = _mapping(score.get("candidate_ceiling"), "task2 v6 candidate ceiling")
    binary = _mapping(
        score.get("binary_same_hypergroup"), "task2 v6 binary proxy score"
    )
    multi = _mapping(score.get("multi_member_binary"), "task2 v6 multi score")
    enum_score = _mapping(score.get("group_induced_enum"), "task2 v6 enum score")
    direct = _mapping(
        score.get("reviewed_one_to_one_direct_subset"),
        "task2 v6 reviewed direct score",
    )
    sources = _mapping(
        score.get("source_accepted_set"), "task2 v6 accepted source sets"
    )
    timing = _mapping(record.get("timing"), "task2 v6 timing")
    if record.get("contract_valid") is not True:
        typer.secho(
            "Contract: "
            + display_escape_text(str(record.get("status")))
            + " · "
            + display_escape_text(str(record.get("validation_error"))),
            fg=typer.colors.RED,
        )
    typer.echo(
        "Fixed judge bundle: "
        + str(bundle.get("pair_count"))
        + " directed candidate pairs · "
        + str(record.get("provider_call_count"))
        + "/"
        + str(record.get("expected_provider_call_count"))
        + " fixed calls · replay "
        + str(bundle.get("replay_freeze_digest"))[:12]
    )
    typer.echo(
        "Strict prompt: revision "
        + display_escape_text(str(prompt.get("prompt_revision")))
        + " · protocol "
        + str(prompt.get("prompt_protocol_digest"))[:12]
        + " · ablation "
        + str(prompt.get("ablation_freeze_digest"))[:12]
    )
    typer.echo(
        "Candidate ceiling: directed Gold co-members "
        + str(ceiling.get("recovered_directed_group_edges"))
        + "/"
        + str(ceiling.get("expected_directed_group_edges"))
        + " · recoverable groups "
        + str(ceiling.get("recoverable_groups"))
        + "/"
        + str(ceiling.get("group_total"))
    )
    typer.echo(
        "Partition-induced binary proxy: TP/FP/TN/FN "
        + "/".join(
            str(binary.get(field))
            for field in (
                "true_positive",
                "false_positive",
                "true_negative",
                "false_negative",
            )
        )
        + " · precision "
        + f"{float(binary.get('precision', 0.0)):.3f}"
        + " · recall "
        + f"{float(binary.get('recall', 0.0)):.3f}"
        + " · F1 "
        + f"{float(binary.get('f1', 0.0)):.3f}"
        + " · not independently reviewed negative-pair accuracy"
    )
    typer.echo(
        "Group-induced enum: exact "
        + str(enum_score.get("exact"))
        + "/"
        + str(enum_score.get("total"))
        + " · reviewed 1:1 direct enum "
        + str(direct.get("exact"))
        + "/"
        + str(direct.get("total"))
        + " · accepted source sets "
        + str(sources.get("exact"))
        + "/"
        + str(sources.get("total"))
        + " · multi-member recall "
        + f"{float(multi.get('recall', 0.0)):.3f}"
    )
    typer.echo(
        "Timing: connection "
        + _format_seconds(float(timing.get("provider_connection_seconds", 0.0)))
        + " · input "
        + _format_seconds(float(timing.get("input_preparation_seconds", 0.0)))
        + " · judge pipeline "
        + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    typer.echo("Ledger: " + display_escape_text(str(record.get("ledger_path"))))
    if record.get("contract_valid") is not True:
        raise typer.Exit(1)


@run_app.command("task2-judge-replay-v7")
def run_task2_judge_replay_v7(
    candidate_ledgers: Annotated[
        Optional[list[Path]],
        typer.Option(
            "--candidate-ledger",
            exists=True,
            dir_okay=False,
            help="Contract-valid V4 parent; repeat at least twice",
        ),
    ] = None,
    provider_id: Annotated[
        Optional[str],
        typer.Option(
            "--provider",
            help="Qwen-only V7: use an Ollama or OpenRouter Qwen provider",
        ),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Qwen model name or slug"),
    ] = None,
    preset: Annotated[
        Optional[str],
        typer.Option("--preset", help="Unavailable for the Qwen-only V7 policy"),
    ] = None,
    reasoning: Annotated[
        Optional[str],
        typer.Option("--reasoning", help="Unavailable for the Qwen-only V7 policy"),
    ] = None,
    thinking: Annotated[
        str,
        typer.Option("--thinking", help="Qwen thinking: auto, on, or off"),
    ] = "auto",
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
    """Run the Qwen-only V7 judge ablation; never call Sol or Luna."""
    parents = list(candidate_ledgers or [])
    if len(parents) < 2:
        raise typer.BadParameter(
            "--candidate-ledger must be repeated for at least two V4 parents"
        )
    if provider_id == CODEX_CHATGPT_PROVIDER or preset is not None or reasoning is not None:
        raise typer.BadParameter(
            "task2-judge-replay-v7 is Qwen-only; Codex, Sol, and Luna are not allowed"
        )
    if model is not None and "qwen" not in model.lower():
        raise typer.BadParameter("--model must select a Qwen model for V7")
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
        Task2JudgeReplayV7Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 judge replay v7 connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    if (
        not isinstance(identity, ProviderIdentity)
        or "qwen" not in identity.model.lower()
        or identity.provider == CODEX_CHATGPT_PROVIDER
    ):
        typer.secho(
            "Task 2 judge replay v7 policy error: connected provider must be Qwen; "
            "Sol and Luna are not called.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(
        "Connected Qwen-only V7: "
        + display_escape_text(identity.display_name())
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_judge_replay_v7_campaign(
            provider,
            parent_ledgers=parents,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            known_error_types=(QueryProviderError,),
        )
        self_validation = validate_task2_judge_replay_v7_record(record)
    except (
        QueryProviderError,
        Task2JudgeReplayV7Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        typer.secho(
            "Task 2 judge replay v7 error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    _render_task2_judge_v7_record(record, self_validation=self_validation)


@run_app.command("task2-judge-replay-v8")
def run_task2_judge_replay_v8(
    candidate_ledgers: Annotated[
        Optional[list[Path]],
        typer.Option(
            "--candidate-ledger",
            exists=True,
            dir_okay=False,
            help="Contract-valid V4 parent; repeat at least twice",
        ),
    ] = None,
    provider_id: Annotated[
        Optional[str],
        typer.Option(
            "--provider",
            help="Qwen-only V8: use an Ollama or OpenRouter Qwen provider",
        ),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Qwen model name or slug"),
    ] = None,
    preset: Annotated[
        Optional[str],
        typer.Option("--preset", help="Unavailable for the Qwen-only V8 policy"),
    ] = None,
    reasoning: Annotated[
        Optional[str],
        typer.Option("--reasoning", help="Unavailable for the Qwen-only V8 policy"),
    ] = None,
    thinking: Annotated[
        str,
        typer.Option("--thinking", help="Qwen thinking: auto, on, or off"),
    ] = "auto",
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
    """Run the Qwen-only staged V8 judge ablation; never call Sol or Luna."""
    parents = list(candidate_ledgers or [])
    if len(parents) < 2:
        raise typer.BadParameter(
            "--candidate-ledger must be repeated for at least two V4 parents"
        )
    if provider_id == CODEX_CHATGPT_PROVIDER or preset is not None or reasoning is not None:
        raise typer.BadParameter(
            "task2-judge-replay-v8 is Qwen-only; Codex, Sol, and Luna are not allowed"
        )
    if model is not None and "qwen" not in model.lower():
        raise typer.BadParameter("--model must select a Qwen model for V8")
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
        Task2JudgeReplayV8Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 judge replay v8 connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    if (
        not isinstance(identity, ProviderIdentity)
        or "qwen" not in identity.model.lower()
        or identity.provider == CODEX_CHATGPT_PROVIDER
    ):
        typer.secho(
            "Task 2 judge replay v8 policy error: connected provider must be Qwen; "
            "Sol and Luna are not called.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(
        "Connected Qwen-only V8: "
        + display_escape_text(identity.display_name())
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_judge_replay_v8_campaign(
            provider,
            parent_ledgers=parents,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            known_error_types=(QueryProviderError,),
        )
        self_validation = validate_task2_judge_replay_v8_record(record)
    except (
        QueryProviderError,
        Task2JudgeReplayV8Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        typer.secho(
            "Task 2 judge replay v8 error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if (
        self_validation.get("integrity_valid") is not True
        or self_validation.get("contract_valid") is not True
        or record.get("contract_valid") is not True
    ):
        typer.secho(
            "V8 staged canonical judge · strict integrity "
            + ("VALID" if self_validation.get("integrity_valid") else "UNAVAILABLE")
            + " · contract INVALID · metrics UNAVAILABLE",
            fg=typer.colors.RED,
            err=True,
        )
        typer.secho(
            "Provider schedule completed "
            + str(record.get("provider_call_count"))
            + "/"
            + str(record.get("expected_provider_call_count"))
            + " calls; retained status "
            + display_escape_text(str(self_validation.get("status")))
            + ".",
            fg=typer.colors.RED,
            err=True,
        )
        score = _mapping(record.get("score"), "task2 v8 invalid score")
        staged = _mapping(
            score.get("staged_pipeline"), "task2 v8 invalid staged score"
        )
        outcomes = _mapping(
            staged.get("outcome_counts"), "task2 v8 invalid outcomes"
        )
        anomalies = _mapping(
            staged.get("call_anomalies"), "task2 v8 invalid anomalies"
        )
        timing = _mapping(record.get("timing"), "task2 v8 invalid timing")
        typer.secho(
            "Retained non-performance outcomes FINAL/ABSTAIN/INVALID_EVIDENCE/"
            "MISSING_DUE_CALL "
            + "/".join(
                str(outcomes.get(status))
                for status in (
                    "FINAL",
                    "ABSTAIN",
                    "INVALID_EVIDENCE",
                    "MISSING_DUE_CALL",
                )
            ),
            fg=typer.colors.RED,
            err=True,
        )
        typer.secho(
            "Retained call anomalies invalid-items/invalid-pairs/unattributable/"
            "missing/response-mismatch "
            + "/".join(
                str(anomalies.get(field))
                for field in (
                    "attributable_invalid_item_count",
                    "invalid_pair_count",
                    "unattributable_item_count",
                    "missing_pair_count",
                    "response_count_mismatch_calls",
                )
            ),
            fg=typer.colors.RED,
            err=True,
        )
        typer.secho(
            "Retained stage time A/B/C-claim/C-primary "
            + "/".join(
                _format_seconds(float(timing.get(field, 0.0)))
                for field in (
                    "stage_a_seconds",
                    "stage_b_seconds",
                    "stage_c_claim_seconds",
                    "stage_c_primary_seconds",
                )
            )
            + " · pipeline "
            + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
            + " · total "
            + _format_seconds(float(timing.get("total_seconds", 0.0))),
            fg=typer.colors.RED,
            err=True,
        )
        typer.secho(
            "Validation error: "
            + display_escape_text(str(record.get("validation_error")))
            + " · JUDGE_ABLATION_ONLY · no scale promotion",
            fg=typer.colors.RED,
            err=True,
        )
        typer.secho(
            "Ledger: " + display_escape_text(str(record.get("ledger_path"))),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    _render_task2_judge_v8_record(record, self_validation=self_validation)


@run_app.command("task2-candidate-v5")
def run_task2_candidate_v5(
    candidate_count: Annotated[
        int,
        typer.Option("--candidate-count", "-k", help="Ablation condition: 4 or 5"),
    ] = 4,
    provider_id: Annotated[
        Optional[str],
        typer.Option("--provider", help="Transient provider; defaults to configured selection"),
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
    groups: Annotated[
        int,
        typer.Option(
            "--groups",
            min=1,
            max=138,
            help="Frozen scale rung: 26, 50, 100, or 138 groups",
        ),
    ] = 26,
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
    """Measure top-4 or top-5 candidate recall without a verifier."""
    if candidate_count not in (4, 5):
        raise typer.BadParameter("--candidate-count must be 4 or 5")
    if groups not in (26, 50, 100, 138):
        raise typer.BadParameter("--groups must be one of 26, 50, 100, or 138")
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
        Task2CandidateAblationV5Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        connection_seconds = time.monotonic() - connection_started
        typer.secho(
            "Task 2 candidate v5 connection error after "
            + _format_seconds(connection_seconds)
            + ": "
            + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    connection_seconds = time.monotonic() - connection_started
    identity = getattr(provider, "identity", None)
    label = (
        identity.display_name()
        if isinstance(identity, ProviderIdentity)
        else "configured semantic provider"
    )
    typer.echo(
        "Connected: "
        + display_escape_text(label)
        + " · "
        + _format_seconds(connection_seconds)
    )
    try:
        record = run_task2_candidate_ablation_v5_campaign(
            provider,
            ledger_dir=ledger_dir,
            provider_connection_seconds=connection_seconds,
            candidate_count=candidate_count,
            group_count=groups,
            known_error_types=(QueryProviderError,),
        )
    except (
        QueryProviderError,
        Task2CandidateAblationV5Error,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        typer.secho(
            "Task 2 candidate v5 error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    condition = _mapping(record.get("condition"), "task2 candidate condition")
    score = _mapping(record.get("score"), "task2 candidate score")
    overall = _mapping(score.get("overall"), "task2 candidate overall")
    one_to_one = _mapping(overall.get("one_to_one"), "task2 candidate 1:1")
    multi = _mapping(
        overall.get("multi_member_groups"), "task2 candidate multi-member"
    )
    distribution = _mapping(
        overall.get("source_hit_distribution"), "task2 candidate hit distribution"
    )
    unique_edges = _mapping(
        score.get("unique_undirected_gold_edge_recoverability"),
        "task2 candidate unique-edge recoverability",
    )
    groups_score = _mapping(
        score.get("exact_group_recoverability"),
        "task2 candidate group recoverability",
    )
    multi_groups = _mapping(
        groups_score.get("multi_member"), "task2 candidate multi-group score"
    )
    timing = _mapping(record.get("timing"), "task2 candidate timing")
    if record.get("contract_valid") is not True:
        typer.secho(
            "Contract: "
            + display_escape_text(str(record.get("status")))
            + " · "
            + display_escape_text(str(record.get("validation_error"))),
            fg=typer.colors.RED,
        )
    typer.echo(
        "Candidate ablation "
        + str(condition.get("id"))
        + ": directed co-member recall "
        + str(overall.get("recovered_directed_edges"))
        + "/"
        + str(overall.get("expected_directed_edges"))
        + " · micro "
        + f"{float(overall.get('micro_recall_at_k', 0.0)):.3f}"
        + " · macro-source "
        + f"{float(overall.get('macro_source_recall_at_k', 0.0)):.3f}"
    )
    typer.echo(
        "Partitions: reviewed 1:1 "
        + str(one_to_one.get("recovered"))
        + "/"
        + str(one_to_one.get("expected"))
        + " · multi directed "
        + str(multi.get("recovered"))
        + "/"
        + str(multi.get("expected"))
        + " · sources complete/partial/zero "
        + "/".join(
            str(distribution.get(field))
            for field in ("complete", "partial", "zero_hit")
        )
    )
    typer.echo(
        "Recoverability: unique Gold edges "
        + str(unique_edges.get("recovered"))
        + "/"
        + str(unique_edges.get("expected"))
        + " · exact groups "
        + str(groups_score.get("recoverable"))
        + "/"
        + str(groups_score.get("expected"))
        + " · multi groups "
        + str(multi_groups.get("recoverable"))
        + "/"
        + str(multi_groups.get("expected"))
    )
    typer.echo(
        "Timing: connection "
        + _format_seconds(float(timing.get("provider_connection_seconds", 0.0)))
        + " · provider calls "
        + _format_seconds(float(timing.get("provider_call_seconds", 0.0)))
        + " · pipeline "
        + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
        + " · total "
        + _format_seconds(float(timing.get("total_seconds", 0.0)))
    )
    typer.echo("Ledger: " + display_escape_text(str(record.get("ledger_path"))))
    if record.get("contract_valid") is not True:
        raise typer.Exit(1)


@semantic_app.command("task2-parity")
def task2_parity(
    first: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    second: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Compare two retained Task 2 provider discoveries on one frozen slice."""
    try:
        first_record = json.loads(first.read_text(encoding="utf-8"))
        second_record = json.loads(second.read_text(encoding="utf-8"))
        result = compare_task2_discovery_records(first_record, second_record)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, Task2DiscoveryError) as error:
        typer.secho(
            "Task 2 parity error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(
        "Parity: contracts "
        + str(result["first_contract_valid"]).lower()
        + "/"
        + str(result["second_contract_valid"]).lower()
        + " · exact structure "
        + str(result["exact_structure_agreement"]).lower()
        + " · exact structure+band "
        + str(result["exact_relation_agreement"]).lower()
    )
    typer.echo(
        "Agreement: structure groups "
        + str(result["agreed_structure_groups"])
        + " · banded groups "
        + str(result["agreed_groups"])
        + " · structure Jaccard "
        + f"{float(result['structure_group_jaccard']):.3f}"
        + " · banded Jaccard "
        + f"{float(result['banded_group_jaccard']):.3f}"
        + " · coassignment Jaccard "
        + f"{float(result['coassignment_jaccard']):.3f}"
    )
    if not result["parity_gate_passed"]:
        raise typer.Exit(1)


@semantic_app.command("task2-retrieval-v3-parity")
def task2_retrieval_v3_parity(
    first: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    second: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Compare group co-membership sets from two fixed V3 schedules."""
    try:
        first_record = json.loads(first.read_text(encoding="utf-8"))
        second_record = json.loads(second.read_text(encoding="utf-8"))
        result = compare_task2_retrieval_v3_records(first_record, second_record)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        Task2RetrievalV3Error,
    ) as error:
        typer.secho(
            "Task 2 retrieval v3 parity error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    agreement = _mapping(
        result.get("group_co_membership_agreement"), "task2 v3 parity agreement"
    )
    overall = _mapping(agreement.get("overall"), "task2 v3 parity overall")
    reviewed = _mapping(
        result.get("reviewed_one_to_one_agreement"),
        "task2 v3 reviewed parity agreement",
    )
    reviewed_overall = _mapping(
        reviewed.get("overall"), "task2 v3 reviewed parity overall"
    )
    groupings = _mapping(
        result.get("grouping_agreement"), "task2 v3 parity groupings"
    )
    reciprocal = _mapping(
        groupings.get("reciprocal"), "task2 v3 parity reciprocal"
    )
    union = _mapping(groupings.get("union"), "task2 v3 parity union")
    typer.echo(
        "V3 parity: contracts "
        + str(result.get("first_contract_valid")).lower()
        + "/"
        + str(result.get("second_contract_valid")).lower()
        + " · group co-membership sets "
        + str(overall.get("exact"))
        + "/"
        + str(overall.get("total"))
        + " · macro Jaccard "
        + f"{float(overall.get('macro_jaccard', 0.0)):.3f}"
    )
    typer.echo(
        "Reviewed 1:1 Gold split: both "
        + str(reviewed_overall.get("both_gold"))
        + " · first only "
        + str(reviewed_overall.get("first_only_gold"))
        + " · second only "
        + str(reviewed_overall.get("second_only_gold"))
        + " · both wrong same "
        + str(reviewed_overall.get("both_wrong_same"))
        + " · both wrong different "
        + str(reviewed_overall.get("both_wrong_different"))
    )
    typer.echo(
        "Grouping agreement: reciprocal Jaccard "
        + f"{float(reciprocal.get('jaccard', 0.0)):.3f}"
        + " · union Jaccard "
        + f"{float(union.get('jaccard', 0.0)):.3f}"
    )
    if result.get("parity_gate_passed") is not True:
        raise typer.Exit(1)


@semantic_app.command("task2-retrieval-v4-parity")
def task2_retrieval_v4_parity(
    first: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    second: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Compare candidate and final sets from two fixed V4 schedules."""
    try:
        first_record = json.loads(first.read_text(encoding="utf-8"))
        second_record = json.loads(second.read_text(encoding="utf-8"))
        result = compare_task2_retrieval_v4_records(first_record, second_record)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        Task2RetrievalV4Error,
    ) as error:
        typer.secho(
            "Task 2 retrieval v4 parity error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    candidate = _mapping(
        result.get("candidate_set_agreement"), "task2 v4 candidate agreement"
    )
    candidate_overall = _mapping(
        candidate.get("overall"), "task2 v4 candidate overall"
    )
    final = _mapping(
        result.get("final_group_co_membership_agreement"),
        "task2 v4 final agreement",
    )
    final_overall = _mapping(final.get("overall"), "task2 v4 final overall")
    reviewed = _mapping(
        result.get("reviewed_one_to_one_gold_quadrants"),
        "task2 v4 reviewed quadrants",
    )
    reviewed_overall = _mapping(
        reviewed.get("overall"), "task2 v4 reviewed quadrant overall"
    )
    groupings = _mapping(
        result.get("grouping_agreement"), "task2 v4 grouping agreement"
    )
    reciprocal = _mapping(
        groupings.get("reciprocal"), "task2 v4 reciprocal agreement"
    )
    union = _mapping(groupings.get("union"), "task2 v4 union agreement")
    typer.echo(
        "V4 parity: contracts "
        + str(result.get("first_contract_valid")).lower()
        + "/"
        + str(result.get("second_contract_valid")).lower()
        + " · candidate sets "
        + str(candidate_overall.get("exact"))
        + "/"
        + str(candidate_overall.get("total"))
        + " · final co-membership sets "
        + str(final_overall.get("exact"))
        + "/"
        + str(final_overall.get("total"))
        + " · final Jaccard "
        + f"{float(final_overall.get('macro_jaccard', 0.0)):.3f}"
    )
    typer.echo(
        "Reviewed 1:1 Gold split: both "
        + str(reviewed_overall.get("both_gold"))
        + " · first only "
        + str(reviewed_overall.get("first_only_gold"))
        + " · second only "
        + str(reviewed_overall.get("second_only_gold"))
        + " · both wrong same "
        + str(reviewed_overall.get("both_wrong_same"))
        + " · both wrong different "
        + str(reviewed_overall.get("both_wrong_different"))
    )
    typer.echo(
        "Grouping agreement: reciprocal Jaccard "
        + f"{float(reciprocal.get('jaccard', 0.0)):.3f}"
        + " · union Jaccard "
        + f"{float(union.get('jaccard', 0.0)):.3f}"
    )
    if result.get("parity_gate_passed") is not True:
        raise typer.Exit(1)


@semantic_app.command("task2-classification-parity")
def task2_classification_parity(
    first: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    second: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Compare oracle-group evidence and projected bands for two providers."""
    try:
        first_record = json.loads(first.read_text(encoding="utf-8"))
        second_record = json.loads(second.read_text(encoding="utf-8"))
        result = compare_task2_classification_records(first_record, second_record)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        Task2ClassificationError,
    ) as error:
        typer.secho(
            "Task 2 classification parity error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(
        "Oracle-group parity: projected bands "
        + str(result["projected_band_agreement"])
        + "/"
        + str(result["expected_groups"])
        + " · evidence "
        + str(result["evidence_agreement"])
        + "/"
        + str(result["expected_groups"])
    )
    typer.echo(
        "Gold split: both "
        + str(result["both_gold"])
        + " · first only "
        + str(result["first_only_gold"])
        + " · second only "
        + str(result["second_only_gold"])
        + " · both wrong same "
        + str(result["both_wrong_same"])
        + " · both wrong different "
        + str(result["both_wrong_different"])
    )
    if not result["parity_gate_passed"]:
        raise typer.Exit(1)


@semantic_app.command("task2-judge-v5-parity")
def task2_judge_v5_parity(
    first: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    second: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Compare two providers on one identical frozen V5 judge replay."""
    try:
        first_record = json.loads(first.read_text(encoding="utf-8"))
        second_record = json.loads(second.read_text(encoding="utf-8"))
        result = compare_task2_judge_replay_v5_records(
            first_record, second_record
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        Task2JudgeReplayV5Error,
    ) as error:
        typer.secho(
            "Task 2 judge v5 parity error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    binary = _mapping(
        result.get("binary_accept_reject_agreement"),
        "task2 judge v5 binary parity",
    )
    enum_score = _mapping(
        result.get("exact_enum_agreement"), "task2 judge v5 enum parity"
    )
    sources = _mapping(
        result.get("source_accepted_set_agreement"),
        "task2 judge v5 source parity",
    )
    multi = _mapping(
        result.get("multi_member_agreement"),
        "task2 judge v5 multi-member parity",
    )
    multi_binary = _mapping(
        multi.get("pair_binary_accept_reject"),
        "task2 judge v5 multi-member binary parity",
    )
    multi_enum = _mapping(
        multi.get("pair_enum"), "task2 judge v5 multi-member enum parity"
    )
    multi_sources = _mapping(
        multi.get("source_accepted_set"),
        "task2 judge v5 multi-member source parity",
    )
    reviewed = _mapping(
        result.get("reviewed_one_to_one_direct_enum_quadrants"),
        "task2 judge v5 reviewed direct quadrants",
    )
    gate = _mapping(result.get("parity_gate"), "task2 judge v5 parity gate")
    typer.echo(
        "V5 judge parity: fixed common call inputs "
        + str(result.get("fixed_call_inputs_identical")).lower()
        + " · binary accept/reject "
        + str(binary.get("exact"))
        + "/"
        + str(binary.get("total"))
        + " · exact relation enum "
        + str(enum_score.get("exact"))
        + "/"
        + str(enum_score.get("total"))
    )
    typer.echo(
        "Accepted source sets: exact "
        + str(sources.get("exact"))
        + "/"
        + str(sources.get("total"))
        + " · macro Jaccard "
        + f"{float(sources.get('macro_jaccard', 0.0)):.3f}"
    )
    typer.echo(
        "Multi-member agreement: binary "
        + str(multi_binary.get("exact"))
        + "/"
        + str(multi_binary.get("total"))
        + " · enum "
        + str(multi_enum.get("exact"))
        + "/"
        + str(multi_enum.get("total"))
        + " · accepted source sets "
        + str(multi_sources.get("exact"))
        + "/"
        + str(multi_sources.get("total"))
    )
    typer.echo(
        "Reviewed 1:1 direct Gold split: recovered "
        + str(reviewed.get("recovered_directed_sources"))
        + "/"
        + str(reviewed.get("expected_directed_sources"))
        + " · both "
        + str(reviewed.get("both_gold"))
        + " · first only "
        + str(reviewed.get("first_only_gold"))
        + " · second only "
        + str(reviewed.get("second_only_gold"))
        + " · both wrong same "
        + str(reviewed.get("both_wrong_same"))
        + " · both wrong different "
        + str(reviewed.get("both_wrong_different"))
    )
    typer.echo("Parity gate: " + ("PASS" if gate.get("passed") else "FAIL"))
    if gate.get("passed") is not True:
        raise typer.Exit(1)


@semantic_app.command("task2-judge-v6-parity")
def task2_judge_v6_parity(
    first: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    second: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Compare two providers on one identical frozen V6 prompt ablation."""
    try:
        first_record = json.loads(first.read_text(encoding="utf-8"))
        second_record = json.loads(second.read_text(encoding="utf-8"))
        result = compare_task2_judge_replay_v6_records(
            first_record, second_record
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        Task2JudgeReplayV6Error,
    ) as error:
        typer.secho(
            "Task 2 judge v6 parity error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    binary = _mapping(
        result.get("binary_accept_reject_agreement"),
        "task2 judge v6 binary parity",
    )
    enum_score = _mapping(
        result.get("exact_enum_agreement"), "task2 judge v6 enum parity"
    )
    sources = _mapping(
        result.get("source_accepted_set_agreement"),
        "task2 judge v6 source parity",
    )
    multi = _mapping(
        result.get("multi_member_agreement"),
        "task2 judge v6 multi-member parity",
    )
    multi_binary = _mapping(
        multi.get("pair_binary_accept_reject"),
        "task2 judge v6 multi-member binary parity",
    )
    multi_enum = _mapping(
        multi.get("pair_enum"), "task2 judge v6 multi-member enum parity"
    )
    multi_sources = _mapping(
        multi.get("source_accepted_set"),
        "task2 judge v6 multi-member source parity",
    )
    reviewed = _mapping(
        result.get("reviewed_one_to_one_direct_enum_quadrants"),
        "task2 judge v6 reviewed direct quadrants",
    )
    gate = _mapping(result.get("parity_gate"), "task2 judge v6 parity gate")
    typer.echo(
        "V6 judge parity: strict prompt "
        + display_escape_text(str(result.get("prompt_revision")))
        + " · ablation "
        + str(result.get("ablation_freeze_digest"))[:12]
        + " · fixed common call inputs "
        + str(result.get("fixed_call_inputs_identical")).lower()
        + " · binary accept/reject "
        + str(binary.get("exact"))
        + "/"
        + str(binary.get("total"))
        + " · exact relation enum "
        + str(enum_score.get("exact"))
        + "/"
        + str(enum_score.get("total"))
    )
    typer.echo(
        "Accepted source sets: exact "
        + str(sources.get("exact"))
        + "/"
        + str(sources.get("total"))
        + " · macro Jaccard "
        + f"{float(sources.get('macro_jaccard', 0.0)):.3f}"
    )
    typer.echo(
        "Multi-member agreement: binary "
        + str(multi_binary.get("exact"))
        + "/"
        + str(multi_binary.get("total"))
        + " · enum "
        + str(multi_enum.get("exact"))
        + "/"
        + str(multi_enum.get("total"))
        + " · accepted source sets "
        + str(multi_sources.get("exact"))
        + "/"
        + str(multi_sources.get("total"))
    )
    typer.echo(
        "Reviewed 1:1 direct Gold split: recovered "
        + str(reviewed.get("recovered_directed_sources"))
        + "/"
        + str(reviewed.get("expected_directed_sources"))
        + " · both "
        + str(reviewed.get("both_gold"))
        + " · first only "
        + str(reviewed.get("first_only_gold"))
        + " · second only "
        + str(reviewed.get("second_only_gold"))
        + " · both wrong same "
        + str(reviewed.get("both_wrong_same"))
        + " · both wrong different "
        + str(reviewed.get("both_wrong_different"))
    )
    typer.echo("Parity gate: " + ("PASS" if gate.get("passed") else "FAIL"))
    if gate.get("passed") is not True:
        raise typer.Exit(1)


@semantic_app.command("task2-judge-v5-adjudication")
def task2_judge_v5_adjudication(
    teacher_run_id: Annotated[
        str,
        typer.Option(
            "--teacher-run-id",
            help="Run ID used only as the reference teacher, never as Gold",
        ),
    ],
    judge_ledgers: Annotated[
        Optional[list[Path]],
        typer.Option(
            "--judge-ledger",
            exists=True,
            dir_okay=False,
            help="Strictly valid V5 judge ledger; repeat at least twice",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the deterministic full report as JSON"),
    ] = False,
) -> None:
    """Build a deterministic read-only V5 adjudication queue in memory."""
    ledgers = list(judge_ledgers or [])
    if len(ledgers) < 2:
        raise typer.BadParameter(
            "--judge-ledger must be repeated for at least two V5 judge ledgers"
        )
    try:
        report = build_task2_judge_adjudication_queue_v5(
            ledgers,
            teacher_run_id=teacher_run_id,
        )
        boundary = _mapping(
            report.get("expected_boundary_notes"),
            "task2 v5 adjudication boundary",
        )
        if (
            report.get("mode") != "READ_ONLY_NO_RELABELING"
            or boundary.get("teacher_is_gold") is not False
            or boundary.get("queue_can_relabel") is not False
        ):
            raise Task2AdjudicationQueueV5Error(
                "Task 2 adjudication report violates its read-only boundary."
            )
        if json_output:
            typer.echo(
                render_task2_judge_adjudication_queue_v5(report),
                nl=False,
            )
            return
        summary = _mapping(report.get("summary"), "task2 v5 adjudication summary")

        def render_distribution(field: str, label: str) -> None:
            distribution = _mapping(
                summary.get(field), f"task2 v5 adjudication {field}"
            )
            values = [
                display_escape_text(str(key)) + "=" + str(distribution[key])
                for key in sorted(distribution, key=str)
            ]
            typer.echo(label + ": " + (" · ".join(values) if values else "(none)"))

        typer.echo(
            "Adjudication queue: total "
            + str(summary.get("queue_item_count"))
            + " · "
            + str(summary.get("ledger_count"))
            + " judge ledgers · "
            + str(summary.get("candidate_pair_count"))
            + " candidate pairs · replay "
            + str(report.get("replay_freeze_digest"))[:12]
        )
        render_distribution("counts_by_priority", "Priorities")
        render_distribution("counts_by_reason", "Reasons")
        render_distribution("counts_by_existing_boundary", "Existing boundaries")
        typer.echo(
            "Boundary: teacher is a reference only, not Gold · read-only report "
            "· no relabeling · existing labels remain unchanged"
        )
    except Task2AdjudicationQueueV5Error as error:
        typer.secho(
            "Task 2 judge v5 adjudication error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


@semantic_app.command("task2-status")
def task2_status(
    ledger_dir: Annotated[
        Path,
        typer.Option(
            "--ledger-dir",
            file_okay=False,
            dir_okay=True,
            help="Profile-independent semantic evaluation ledger",
        ),
    ] = DEFAULT_SEMANTIC_EVAL_LEDGER,
    all_runs: Annotated[
        bool,
        typer.Option("--all", help="Show every retained run instead of latest comparable rows"),
    ] = False,
) -> None:
    """Show Task 2 discovery coverage, label score, failures, and elapsed time."""
    runs_dir = ledger_dir / "task2-discovery"
    try:
        paths = sorted(runs_dir.glob("*.json")) if runs_dir.is_dir() else []
        records = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in paths
            if path.is_file() and not path.is_symlink()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        typer.secho(
            "Task 2 status error: " + _redacted_error(error),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    records = [
        record
        for record in records
        if isinstance(record, dict)
        and record.get("kind") == "memcommit.semantic-eval.task2-discovery"
    ]
    if not records:
        typer.echo("No Task 2 V1 discovery runs found.")
    if not all_runs:
        latest: dict[tuple[object, ...], dict[str, object]] = {}
        for record in records:
            provider = record.get("provider")
            corpus = record.get("corpus")
            if not isinstance(provider, Mapping) or not isinstance(corpus, Mapping):
                continue
            key = (
                provider.get("provider"),
                provider.get("model"),
                provider.get("model_digest"),
                provider.get("reasoning_effort"),
                record.get("effective_thinking"),
                record.get("pipeline"),
                corpus.get("input_digest"),
                _task2_scorer_provenance(record)[0],
                _task2_lock_provenance(record)[0],
            )
            prior = latest.get(key)
            if prior is None or str(record.get("started_at")) > str(prior.get("started_at")):
                latest[key] = record
        records = list(latest.values())
    records.sort(
        key=lambda record: (
            int(_mapping(record.get("corpus"), "task2 corpus").get("selected_group_count", 0)),
            str(_mapping(record.get("provider"), "task2 provider").get("provider")),
            str(record.get("started_at")),
        )
    )
    for record in records:
        provider = _mapping(record.get("provider"), "task2 provider")
        corpus = _mapping(record.get("corpus"), "task2 corpus")
        score = _mapping(record.get("score"), "task2 score")
        timing = _mapping(record.get("timing"), "task2 timing")
        _scorer_key, scorer_label = _task2_scorer_provenance(record)
        _lock_key, lock_label = _task2_lock_provenance(record)
        label = str(provider.get("provider")) + ":" + str(provider.get("model"))
        condition = []
        if provider.get("reasoning_effort"):
            condition.append("reasoning=" + str(provider.get("reasoning_effort")))
        if isinstance(record.get("effective_thinking"), bool):
            condition.append("thinking=" + str(record.get("effective_thinking")).lower())
        typer.echo(
            display_escape_text(label)
            + ((" · " + " · ".join(condition)) if condition else "")
            + " · "
            + str(corpus.get("selected_left_count"))
            + "×"
            + str(corpus.get("selected_right_count"))
            + " ("
            + str(corpus.get("selected_group_count"))
            + " groups)"
            + " · scorer "
            + scorer_label
            + " · "
            + lock_label
        )
        typer.echo(
            "  contract "
            + ("VALID" if record.get("contract_valid") else "INVALID")
            + " · structure "
            + str(score.get("exact_structure_groups"))
            + "/"
            + str(score.get("expected_groups"))
            + " · band "
            + str(score.get("exact_band_groups"))
            + "/"
            + str(score.get("expected_groups"))
            + " · group-induced "
            + str(score.get("member_counterpart_exact"))
            + "/"
            + str(score.get("member_counterpart_total"))
        )
        typer.echo(
            "  time provider "
            + _format_seconds(float(timing.get("provider_completion_seconds", 0.0)))
            + " · total "
            + _format_seconds(float(timing.get("total_seconds", 0.0)))
            + " · ledger "
            + display_escape_text(str(record.get("ledger_path")))
        )
        if record.get("contract_valid") is False:
            typer.echo(
                "  failure "
                + display_escape_text(str(record.get("validation_error")))
            )

    def load_extra(subdir: str, kind: str) -> list[dict[str, object]]:
        directory = ledger_dir / subdir
        loaded: list[dict[str, object]] = []
        for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
            if not path.is_file() or path.is_symlink():
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and value.get("kind") == kind:
                loaded.append(value)
        if all_runs:
            return loaded
        latest_extra: dict[tuple[object, ...], dict[str, object]] = {}
        for value in loaded:
            provider = value.get("provider")
            corpus = value.get("corpus")
            if not isinstance(provider, Mapping) or not isinstance(corpus, Mapping):
                continue
            key = (
                provider.get("provider"),
                provider.get("model"),
                provider.get("model_digest"),
                provider.get("reasoning_effort"),
                value.get("effective_thinking"),
                value.get("pipeline"),
                corpus.get("input_digest"),
            )
            if kind == "memcommit.semantic-eval.task2-discovery-v2":
                key += (
                    _task2_scorer_provenance(value)[0],
                    _task2_lock_provenance(value)[0],
                )
            elif kind == "memcommit.semantic-eval.task2-retrieval-v3":
                key += (
                    value.get("schema_version"),
                    _task2_v3_lock_provenance(value)[0],
                )
            elif kind == "memcommit.semantic-eval.task2-retrieval-v4":
                key += (
                    value.get("schema_version"),
                    _task2_v4_lock_provenance(value)[0],
                )
            elif kind == "memcommit.semantic-eval.task2-candidate-ablation-v5":
                condition = value.get("condition")
                key += (
                    value.get("schema_version"),
                    condition.get("id") if isinstance(condition, Mapping) else None,
                    _task2_v4_lock_provenance(value)[0],
                )
            elif kind == "memcommit.semantic-eval.task2-judge-replay-v5":
                bundle = value.get("candidate_bundle")
                key += (
                    value.get("schema_version"),
                    (
                        bundle.get("replay_freeze_digest")
                        if isinstance(bundle, Mapping)
                        else None
                    ),
                )
            elif kind == "memcommit.semantic-eval.task2-judge-replay-v6":
                bundle = value.get("candidate_bundle")
                prompt = value.get("prompt_ablation")
                key += (
                    value.get("schema_version"),
                    (
                        bundle.get("replay_freeze_digest")
                        if isinstance(bundle, Mapping)
                        else None
                    ),
                    (
                        prompt.get("ablation_freeze_digest")
                        if isinstance(prompt, Mapping)
                        else None
                    ),
                )
            elif kind == "memcommit.semantic-eval.task2-judge-replay-v7":
                canonical = value.get("canonical_bundle")
                key += (
                    value.get("schema_version"),
                    (
                        canonical.get("evidence_freeze_digest")
                        if isinstance(canonical, Mapping)
                        else None
                    ),
                )
            elif kind == "memcommit.semantic-eval.task2-judge-replay-v8":
                protocol = value.get("staged_protocol")
                key += (
                    value.get("schema_version"),
                    (
                        protocol.get("input_freeze_digest")
                        if isinstance(protocol, Mapping)
                        else None
                    ),
                )
            prior = latest_extra.get(key)
            if prior is None or str(value.get("started_at")) > str(prior.get("started_at")):
                latest_extra[key] = value
        return list(latest_extra.values())

    for record in sorted(
        load_extra(
            "task2-discovery-v2",
            "memcommit.semantic-eval.task2-discovery-v2",
        ),
        key=lambda value: str(value.get("started_at")),
    ):
        provider = _mapping(record.get("provider"), "task2 v2 provider")
        corpus = _mapping(record.get("corpus"), "task2 v2 corpus")
        score = _mapping(record.get("score"), "task2 v2 score")
        timing = _mapping(record.get("timing"), "task2 v2 timing")
        _scorer_key, scorer_label = _task2_scorer_provenance(record)
        _lock_key, lock_label = _task2_lock_provenance(record)
        typer.echo(
            "V2 structure · "
            + display_escape_text(str(provider.get("provider")) + ":" + str(provider.get("model")))
            + " · "
            + str(corpus.get("selected_left_count"))
            + "×"
            + str(corpus.get("selected_right_count"))
            + " · contract "
            + ("VALID" if record.get("contract_valid") else "INVALID")
            + " · scorer "
            + scorer_label
            + " · "
            + lock_label
        )
        typer.echo(
            "  structure "
            + str(score.get("exact_structure_groups"))
            + "/"
            + str(score.get("expected_groups"))
            + " · group-induced "
            + str(score.get("member_counterpart_exact"))
            + "/"
            + str(score.get("member_counterpart_total"))
            + " · pipeline "
            + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
            + " · ledger "
            + display_escape_text(str(record.get("ledger_path")))
        )

    v3_records = sorted(
        load_extra(
            "task2-retrieval-v3",
            "memcommit.semantic-eval.task2-retrieval-v3",
        ),
        key=lambda value: str(value.get("started_at")),
    )
    for record in v3_records:
        provider = _mapping(record.get("provider"), "task2 v3 provider")
        corpus = _mapping(record.get("corpus"), "task2 v3 corpus")
        score = _mapping(record.get("score"), "task2 v3 score")
        direct = _mapping(
            score.get("group_co_membership_retrieval"), "task2 v3 retrieval score"
        )
        reviewed = _mapping(
            direct.get("reviewed_one_to_one_subset"), "task2 v3 reviewed subset"
        )
        reviewed_overall = _mapping(
            reviewed.get("overall"), "task2 v3 reviewed score"
        )
        co_membership = _mapping(
            direct.get("group_co_membership"), "task2 v3 co-membership"
        )
        co_membership_overall = _mapping(
            co_membership.get("overall"), "task2 v3 co-membership score"
        )
        diagnostics = _mapping(
            score.get("grouping_diagnostics"), "task2 v3 diagnostics"
        )
        reciprocal = _mapping(
            _mapping(diagnostics.get("reciprocal"), "task2 v3 reciprocal").get(
                "score"
            ),
            "task2 v3 reciprocal score",
        )
        union = _mapping(
            _mapping(diagnostics.get("union"), "task2 v3 union").get("score"),
            "task2 v3 union score",
        )
        timing = _mapping(record.get("timing"), "task2 v3 timing")
        promotion = evaluate_task2_retrieval_v3_promotion(record)
        _lock_key, lock_label = _task2_v3_lock_provenance(record)
        typer.echo(
            "V3 retrieval · "
            + display_escape_text(
                str(provider.get("provider")) + ":" + str(provider.get("model"))
            )
            + " · "
            + str(corpus.get("selected_left_count"))
            + "×"
            + str(corpus.get("selected_right_count"))
            + " · contract "
            + ("VALID" if record.get("contract_valid") else "INVALID")
            + " · "
            + lock_label
        )
        typer.echo(
            "  group co-membership "
            + str(co_membership_overall.get("exact"))
            + "/"
            + str(co_membership_overall.get("total"))
            + " · Jaccard "
            + f"{float(co_membership_overall.get('macro_jaccard', 0.0)):.3f}"
            + " · reviewed 1:1 "
            + str(reviewed_overall.get("exact"))
            + "/"
            + str(reviewed_overall.get("total"))
            + " · groups reciprocal "
            + str(reciprocal.get("exact_groups"))
            + "/"
            + str(reciprocal.get("expected_groups"))
            + " union "
            + str(union.get("exact_groups"))
            + "/"
            + str(union.get("expected_groups"))
        )
        typer.echo(
            "  calls "
            + str(record.get("provider_call_count"))
            + "/"
            + str(record.get("expected_provider_call_count"))
            + " · pipeline "
            + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
            + " · ledger "
            + display_escape_text(str(record.get("ledger_path")))
        )
        typer.echo(
            "  single-run rung gate "
            + ("PASS" if promotion.get("passed") else "FAIL")
            + " · consumed calibration · scale promotion requires 3/3 repeats"
        )

    v4_records = sorted(
        load_extra(
            "task2-retrieval-v4",
            "memcommit.semantic-eval.task2-retrieval-v4",
        ),
        key=lambda value: str(value.get("started_at")),
    )
    for record in v4_records:
        provider = _mapping(record.get("provider"), "task2 v4 provider")
        corpus = _mapping(record.get("corpus"), "task2 v4 corpus")
        score = _mapping(record.get("score"), "task2 v4 score")
        candidates = _mapping(
            score.get("candidate_retrieval"), "task2 v4 candidate score"
        )
        final = _mapping(
            score.get("final_group_co_membership"), "task2 v4 final score"
        )
        all_reviewed = _mapping(
            final.get("all_reviewed_groups"), "task2 v4 all-reviewed score"
        )
        all_overall = _mapping(
            all_reviewed.get("overall"), "task2 v4 all-reviewed overall"
        )
        reviewed = _mapping(
            final.get("reviewed_one_to_one_subset"), "task2 v4 reviewed subset"
        )
        reviewed_overall = _mapping(
            reviewed.get("overall"), "task2 v4 reviewed subset overall"
        )
        diagnostics = _mapping(
            score.get("grouping_diagnostics"), "task2 v4 diagnostics"
        )
        reciprocal = _mapping(
            _mapping(diagnostics.get("reciprocal"), "task2 v4 reciprocal").get(
                "score"
            ),
            "task2 v4 reciprocal score",
        )
        union = _mapping(
            _mapping(diagnostics.get("union"), "task2 v4 union").get("score"),
            "task2 v4 union score",
        )
        timing = _mapping(record.get("timing"), "task2 v4 timing")
        rung_gate = evaluate_task2_retrieval_v4_rung_gate(record)
        _lock_key, lock_label = _task2_v4_lock_provenance(record)
        typer.echo(
            "V4 candidate→verify · "
            + display_escape_text(
                str(provider.get("provider")) + ":" + str(provider.get("model"))
            )
            + " · "
            + str(corpus.get("selected_left_count"))
            + "×"
            + str(corpus.get("selected_right_count"))
            + " · contract "
            + ("VALID" if record.get("contract_valid") else "INVALID")
            + " · "
            + lock_label
        )
        typer.echo(
            "  candidate recall@3 "
            + str(candidates.get("recalled"))
            + "/"
            + str(candidates.get("expected"))
            + " · final co-membership "
            + str(all_overall.get("exact"))
            + "/"
            + str(all_overall.get("total"))
            + " · reviewed 1:1 "
            + str(reviewed_overall.get("exact"))
            + "/"
            + str(reviewed_overall.get("total"))
            + " · groups reciprocal "
            + str(reciprocal.get("exact_groups"))
            + "/"
            + str(reciprocal.get("expected_groups"))
            + " union "
            + str(union.get("exact_groups"))
            + "/"
            + str(union.get("expected_groups"))
        )
        typer.echo(
            "  calls "
            + str(record.get("provider_call_count"))
            + "/"
            + str(record.get("expected_provider_call_count"))
            + " · Stage A "
            + _format_seconds(
                float(timing.get("candidate_stage_call_seconds", 0.0))
            )
            + " · Stage B "
            + _format_seconds(
                float(timing.get("verifier_stage_call_seconds", 0.0))
            )
            + " · pipeline "
            + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
            + " · ledger "
            + display_escape_text(str(record.get("ledger_path")))
        )
        typer.echo(
            "  single-run rung gate "
            + ("PASS" if rung_gate.get("passed") else "FAIL")
            + " · scale promotion requires 3/3 repeats"
        )

    candidate_v5_records = sorted(
        load_extra(
            "task2-candidate-ablation-v5",
            "memcommit.semantic-eval.task2-candidate-ablation-v5",
        ),
        key=lambda value: str(value.get("started_at")),
    )
    for record in candidate_v5_records:
        provider = _mapping(record.get("provider"), "task2 candidate v5 provider")
        condition = _mapping(
            record.get("condition"), "task2 candidate v5 condition"
        )
        corpus = _mapping(record.get("corpus"), "task2 candidate v5 corpus")
        score = _mapping(record.get("score"), "task2 candidate v5 score")
        overall = _mapping(score.get("overall"), "task2 candidate v5 overall")
        one_to_one = _mapping(
            overall.get("one_to_one"), "task2 candidate v5 1:1"
        )
        multi = _mapping(
            overall.get("multi_member_groups"), "task2 candidate v5 multi"
        )
        groups_score = _mapping(
            score.get("exact_group_recoverability"),
            "task2 candidate v5 group recoverability",
        )
        multi_groups = _mapping(
            groups_score.get("multi_member"), "task2 candidate v5 multi groups"
        )
        timing = _mapping(record.get("timing"), "task2 candidate v5 timing")
        _lock_key, lock_label = _task2_v4_lock_provenance(record)
        typer.echo(
            "V5 candidate-only "
            + display_escape_text(str(condition.get("id")))
            + " · "
            + display_escape_text(
                str(provider.get("provider")) + ":" + str(provider.get("model"))
            )
            + " · "
            + str(corpus.get("selected_left_count"))
            + "×"
            + str(corpus.get("selected_right_count"))
            + " · contract "
            + ("VALID" if record.get("contract_valid") else "INVALID")
            + " · "
            + lock_label
        )
        typer.echo(
            "  directed recall "
            + str(overall.get("recovered_directed_edges"))
            + "/"
            + str(overall.get("expected_directed_edges"))
            + " · reviewed 1:1 "
            + str(one_to_one.get("recovered"))
            + "/"
            + str(one_to_one.get("expected"))
            + " · multi directed "
            + str(multi.get("recovered"))
            + "/"
            + str(multi.get("expected"))
            + " · exact groups "
            + str(groups_score.get("recoverable"))
            + "/"
            + str(groups_score.get("expected"))
            + " · multi groups "
            + str(multi_groups.get("recoverable"))
            + "/"
            + str(multi_groups.get("expected"))
        )
        typer.echo(
            "  calls "
            + str(record.get("provider_call_count"))
            + "/"
            + str(record.get("expected_provider_call_count"))
            + " · pipeline "
            + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
            + " · measurement only · ledger "
            + display_escape_text(str(record.get("ledger_path")))
        )

    judge_v5_records = sorted(
        load_extra(
            "task2-judge-replay-v5",
            "memcommit.semantic-eval.task2-judge-replay-v5",
        ),
        key=lambda value: str(value.get("started_at")),
    )
    for record in judge_v5_records:
        provider = _mapping(record.get("provider"), "task2 judge v5 provider")
        corpus = _mapping(record.get("corpus"), "task2 judge v5 corpus")
        bundle = _mapping(
            record.get("candidate_bundle"), "task2 judge v5 candidate bundle"
        )
        score = _mapping(record.get("score"), "task2 judge v5 score")
        binary = _mapping(
            score.get("binary_same_hypergroup"), "task2 judge v5 binary score"
        )
        multi = _mapping(
            score.get("multi_member_binary"), "task2 judge v5 multi score"
        )
        enum_score = _mapping(
            score.get("group_induced_enum"), "task2 judge v5 enum score"
        )
        direct = _mapping(
            score.get("reviewed_one_to_one_direct_subset"),
            "task2 judge v5 reviewed direct score",
        )
        sources = _mapping(
            score.get("source_accepted_set"), "task2 judge v5 source score"
        )
        timing = _mapping(record.get("timing"), "task2 judge v5 timing")
        label = str(provider.get("provider")) + ":" + str(provider.get("model"))
        typer.echo(
            "V5 common-candidate judge · "
            + display_escape_text(label)
            + " · "
            + str(corpus.get("group_count"))
            + " groups · "
            + str(bundle.get("pair_count"))
            + " pairs · contract "
            + ("VALID" if record.get("contract_valid") else "INVALID")
            + " · replay "
            + str(bundle.get("replay_freeze_digest"))[:12]
        )
        typer.echo(
            "  partition-induced binary proxy TP/FP/TN/FN "
            + "/".join(
                str(binary.get(field))
                for field in (
                    "true_positive",
                    "false_positive",
                    "true_negative",
                    "false_negative",
                )
            )
            + " · precision "
            + f"{float(binary.get('precision', 0.0)):.3f}"
            + " recall "
            + f"{float(binary.get('recall', 0.0)):.3f}"
            + " · multi recall "
            + f"{float(multi.get('recall', 0.0)):.3f}"
            + " · not independently reviewed negative-pair accuracy"
        )
        typer.echo(
            "  group-induced enum "
            + str(enum_score.get("exact"))
            + "/"
            + str(enum_score.get("total"))
            + " · reviewed 1:1 direct "
            + str(direct.get("exact"))
            + "/"
            + str(direct.get("total"))
            + " · accepted source sets "
            + str(sources.get("exact"))
            + "/"
            + str(sources.get("total"))
        )
        typer.echo(
            "  calls "
            + str(record.get("provider_call_count"))
            + "/"
            + str(record.get("expected_provider_call_count"))
            + " · input "
            + _format_seconds(float(timing.get("input_preparation_seconds", 0.0)))
            + " · pipeline "
            + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
            + " · ledger "
            + display_escape_text(str(record.get("ledger_path")))
        )
        if record.get("contract_valid") is False:
            typer.echo(
                "  failure "
                + display_escape_text(str(record.get("validation_error")))
            )

    judge_v6_records = sorted(
        load_extra(
            "task2-judge-replay-v6",
            "memcommit.semantic-eval.task2-judge-replay-v6",
        ),
        key=lambda value: str(value.get("started_at")),
    )
    for record in judge_v6_records:
        provider = _mapping(record.get("provider"), "task2 judge v6 provider")
        corpus = _mapping(record.get("corpus"), "task2 judge v6 corpus")
        bundle = _mapping(
            record.get("candidate_bundle"), "task2 judge v6 candidate bundle"
        )
        prompt = _mapping(
            record.get("prompt_ablation"), "task2 judge v6 prompt ablation"
        )
        score = _mapping(record.get("score"), "task2 judge v6 score")
        binary = _mapping(
            score.get("binary_same_hypergroup"), "task2 judge v6 binary proxy"
        )
        multi = _mapping(
            score.get("multi_member_binary"), "task2 judge v6 multi proxy"
        )
        enum_score = _mapping(
            score.get("group_induced_enum"), "task2 judge v6 enum score"
        )
        direct = _mapping(
            score.get("reviewed_one_to_one_direct_subset"),
            "task2 judge v6 reviewed direct score",
        )
        sources = _mapping(
            score.get("source_accepted_set"), "task2 judge v6 source score"
        )
        timing = _mapping(record.get("timing"), "task2 judge v6 timing")
        label = str(provider.get("provider")) + ":" + str(provider.get("model"))
        typer.echo(
            "V6 strict-boundary judge · "
            + display_escape_text(label)
            + " · "
            + str(corpus.get("group_count"))
            + " groups · "
            + str(bundle.get("pair_count"))
            + " pairs · contract "
            + ("VALID" if record.get("contract_valid") else "INVALID")
            + " · replay "
            + str(bundle.get("replay_freeze_digest"))[:12]
        )
        typer.echo(
            "  prompt "
            + display_escape_text(str(prompt.get("prompt_revision")))
            + " · protocol "
            + str(prompt.get("prompt_protocol_digest"))[:12]
            + " · ablation "
            + str(prompt.get("ablation_freeze_digest"))[:12]
        )
        typer.echo(
            "  partition-induced binary proxy TP/FP/TN/FN "
            + "/".join(
                str(binary.get(field))
                for field in (
                    "true_positive",
                    "false_positive",
                    "true_negative",
                    "false_negative",
                )
            )
            + " · precision "
            + f"{float(binary.get('precision', 0.0)):.3f}"
            + " recall "
            + f"{float(binary.get('recall', 0.0)):.3f}"
            + " · multi recall "
            + f"{float(multi.get('recall', 0.0)):.3f}"
        )
        typer.echo(
            "  group-induced enum "
            + str(enum_score.get("exact"))
            + "/"
            + str(enum_score.get("total"))
            + " · reviewed 1:1 direct "
            + str(direct.get("exact"))
            + "/"
            + str(direct.get("total"))
            + " · accepted source sets "
            + str(sources.get("exact"))
            + "/"
            + str(sources.get("total"))
        )
        typer.echo(
            "  calls "
            + str(record.get("provider_call_count"))
            + "/"
            + str(record.get("expected_provider_call_count"))
            + " · input "
            + _format_seconds(float(timing.get("input_preparation_seconds", 0.0)))
            + " · pipeline "
            + _format_seconds(float(timing.get("pipeline_seconds", 0.0)))
            + " · ledger "
            + display_escape_text(str(record.get("ledger_path")))
        )
        if record.get("contract_valid") is False:
            typer.echo(
                "  failure "
                + display_escape_text(str(record.get("validation_error")))
            )

    def judge_provider_condition(value: Mapping[str, object]) -> tuple[object, ...] | None:
        provider = value.get("provider")
        if not isinstance(provider, Mapping):
            return None
        return (
            provider.get("provider"),
            provider.get("model"),
            provider.get("model_digest"),
            provider.get("reasoning_effort"),
            provider.get("runtime"),
            provider.get("endpoint"),
            value.get("effective_thinking"),
        )

    for v6_record in judge_v6_records:
        if v6_record.get("contract_valid") is not True:
            continue
        v6_bundle = v6_record.get("candidate_bundle")
        v6_condition = judge_provider_condition(v6_record)
        if not isinstance(v6_bundle, Mapping) or v6_condition is None:
            continue
        matching_v5 = [
            record
            for record in judge_v5_records
            if record.get("contract_valid") is True
            and judge_provider_condition(record) == v6_condition
            and isinstance(record.get("candidate_bundle"), Mapping)
            and record["candidate_bundle"].get("replay_freeze_digest")
            == v6_bundle.get("replay_freeze_digest")
        ]
        if not matching_v5:
            continue
        v5_record = max(matching_v5, key=lambda value: str(value.get("started_at")))
        v5_provider = _mapping(v5_record.get("provider"), "task2 v5 ablation provider")
        v5_score = _mapping(v5_record.get("score"), "task2 v5 ablation score")
        v6_score = _mapping(v6_record.get("score"), "task2 v6 ablation score")
        v5_binary = _mapping(
            v5_score.get("binary_same_hypergroup"), "task2 v5 ablation binary"
        )
        v6_binary = _mapping(
            v6_score.get("binary_same_hypergroup"), "task2 v6 ablation binary"
        )
        v5_enum = _mapping(
            v5_score.get("group_induced_enum"), "task2 v5 ablation enum"
        )
        v6_enum = _mapping(
            v6_score.get("group_induced_enum"), "task2 v6 ablation enum"
        )
        v5_sources = _mapping(
            v5_score.get("source_accepted_set"), "task2 v5 ablation sources"
        )
        v6_sources = _mapping(
            v6_score.get("source_accepted_set"), "task2 v6 ablation sources"
        )
        v5_multi = _mapping(
            v5_score.get("multi_member_binary"), "task2 v5 ablation multi"
        )
        v6_multi = _mapping(
            v6_score.get("multi_member_binary"), "task2 v6 ablation multi"
        )
        v5_timing = _mapping(v5_record.get("timing"), "task2 v5 ablation timing")
        v6_timing = _mapping(v6_record.get("timing"), "task2 v6 ablation timing")

        def count_delta(
            newer: Mapping[str, object], older: Mapping[str, object], field: str
        ) -> int:
            return int(newer.get(field, 0)) - int(older.get(field, 0))

        v5_pipeline_seconds = float(v5_timing.get("pipeline_seconds", 0.0))
        v6_pipeline_seconds = float(v6_timing.get("pipeline_seconds", 0.0))
        timing_ratio = (
            f"×{v6_pipeline_seconds / v5_pipeline_seconds:.3f}"
            if v5_pipeline_seconds > 0.0
            else "N/A"
        )
        provider_label = str(v5_provider.get("provider")) + ":" + str(
            v5_provider.get("model")
        )
        typer.echo(
            "V5→V6 prompt ablation · "
            + display_escape_text(provider_label)
            + " · identical replay "
            + str(v6_bundle.get("replay_freeze_digest"))[:12]
        )
        typer.echo(
            "  partition-induced binary proxy ΔTP/FP/TN/FN "
            + "/".join(
                f"{count_delta(v6_binary, v5_binary, field):+d}"
                for field in (
                    "true_positive",
                    "false_positive",
                    "true_negative",
                    "false_negative",
                )
            )
            + " · FP/TN are not independently reviewed semantic-pair accuracy"
        )
        typer.echo(
            "  Δenum exact "
            + f"{count_delta(v6_enum, v5_enum, 'exact'):+d}"
            + " · Δsource-set exact "
            + f"{count_delta(v6_sources, v5_sources, 'exact'):+d}"
            + " · multi ΔTP/FP/TN/FN "
            + "/".join(
                f"{count_delta(v6_multi, v5_multi, field):+d}"
                for field in (
                    "true_positive",
                    "false_positive",
                    "true_negative",
                    "false_negative",
                )
            )
            + " · Δrecall "
            + f"{float(v6_multi.get('recall', 0.0)) - float(v5_multi.get('recall', 0.0)):+.3f}"
            + " · pipeline "
            + timing_ratio
            + " (V6/V5)"
        )

    judge_v7_records = sorted(
        load_extra(
            "task2-judge-replay-v7",
            "memcommit.semantic-eval.task2-judge-replay-v7",
        ),
        key=lambda value: str(value.get("started_at")),
    )
    for record in judge_v7_records:
        provider = record.get("provider")
        provider_label = "unknown:unknown"
        qwen_policy_valid = False
        if isinstance(provider, Mapping):
            provider_label = str(provider.get("provider")) + ":" + str(
                provider.get("model")
            )
            qwen_policy_valid = (
                "qwen" in str(provider.get("model", "")).lower()
                and provider.get("provider") != CODEX_CHATGPT_PROVIDER
            )
        try:
            if not qwen_policy_valid:
                raise Task2JudgeReplayV7Error(
                    "retained V7 record violates the CLI Qwen-only policy"
                )
            self_validation = validate_task2_judge_replay_v7_record(record)
        except Task2JudgeReplayV7Error as error:
            typer.echo(
                "V7 canonical evidence judge · "
                + display_escape_text(provider_label)
                + " · strict self-validation UNAVAILABLE"
                + " · contract "
                + ("VALID" if record.get("contract_valid") else "INVALID")
            )
            typer.echo(
                "  unavailable "
                + display_escape_text(_redacted_error(error))
                + " · ledger "
                + display_escape_text(str(record.get("ledger_path")))
            )
            continue
        _render_task2_judge_v7_record(
            record,
            self_validation=self_validation,
        )

    judge_v8_records = sorted(
        load_extra(
            "task2-judge-replay-v8",
            "memcommit.semantic-eval.task2-judge-replay-v8",
        ),
        key=lambda value: str(value.get("started_at")),
    )
    for record in judge_v8_records:
        provider = record.get("provider")
        provider_label = "unknown:unknown"
        qwen_policy_valid = False
        if isinstance(provider, Mapping):
            provider_label = str(provider.get("provider")) + ":" + str(
                provider.get("model")
            )
            qwen_policy_valid = (
                "qwen" in str(provider.get("model", "")).lower()
                and provider.get("provider") != CODEX_CHATGPT_PROVIDER
            )
        try:
            if not qwen_policy_valid:
                raise Task2JudgeReplayV8Error(
                    "retained V8 record violates the CLI Qwen-only policy"
                )
            self_validation = validate_task2_judge_replay_v8_record(record)
        except Task2JudgeReplayV8Error as error:
            typer.echo(
                "V8 staged canonical judge · "
                + display_escape_text(provider_label)
                + " · strict integrity UNAVAILABLE · metrics UNAVAILABLE"
            )
            typer.echo(
                "  unavailable "
                + display_escape_text(_redacted_error(error))
                + " · ledger "
                + display_escape_text(str(record.get("ledger_path")))
            )
            continue
        if (
            self_validation.get("integrity_valid") is not True
            or self_validation.get("contract_valid") is not True
            or record.get("contract_valid") is not True
        ):
            typer.echo(
                "V8 staged canonical judge · "
                + display_escape_text(provider_label)
                + " · strict integrity "
                + (
                    "VALID"
                    if self_validation.get("integrity_valid") is True
                    else "UNAVAILABLE"
                )
                + " · contract INVALID · metrics UNAVAILABLE"
            )
            typer.echo(
                "  retained status "
                + display_escape_text(str(self_validation.get("status")))
                + " · calls "
                + str(record.get("provider_call_count"))
                + "/"
                + str(record.get("expected_provider_call_count"))
                + " · failure "
                + display_escape_text(str(record.get("validation_error")))
                + " · ledger "
                + display_escape_text(str(record.get("ledger_path")))
            )
            continue
        _render_task2_judge_v8_record(
            record,
            self_validation=self_validation,
        )

    for first_index, first_record in enumerate(v3_records):
        first_corpus = first_record.get("corpus")
        if not isinstance(first_corpus, Mapping):
            continue
        for second_record in v3_records[first_index + 1 :]:
            second_corpus = second_record.get("corpus")
            if (
                not isinstance(second_corpus, Mapping)
                or first_record.get("pipeline") != second_record.get("pipeline")
                or first_corpus.get("input_digest")
                != second_corpus.get("input_digest")
            ):
                continue
            try:
                parity = compare_task2_retrieval_v3_records(
                    first_record, second_record
                )
            except Task2RetrievalV3Error as error:
                typer.echo(
                    "V3 parity unavailable · "
                    + display_escape_text(_redacted_error(error))
                )
                continue
            first_provider = _mapping(
                first_record.get("provider"), "task2 v3 first parity provider"
            )
            second_provider = _mapping(
                second_record.get("provider"), "task2 v3 second parity provider"
            )
            agreement = _mapping(
                parity.get("group_co_membership_agreement"),
                "task2 v3 status parity agreement",
            )
            overall = _mapping(
                agreement.get("overall"), "task2 v3 status parity overall"
            )
            reviewed = _mapping(
                parity.get("reviewed_one_to_one_agreement"),
                "task2 v3 status reviewed parity",
            )
            reviewed_overall = _mapping(
                reviewed.get("overall"), "task2 v3 status reviewed parity overall"
            )
            first_label = str(first_provider.get("provider")) + ":" + str(
                first_provider.get("model")
            )
            second_label = str(second_provider.get("provider")) + ":" + str(
                second_provider.get("model")
            )
            typer.echo(
                "V3 parity · "
                + display_escape_text(first_label)
                + " ↔ "
                + display_escape_text(second_label)
                + " · contracts "
                + str(parity.get("first_contract_valid")).lower()
                + "/"
                + str(parity.get("second_contract_valid")).lower()
            )
            typer.echo(
                "  co-membership agreement "
                + str(overall.get("exact"))
                + "/"
                + str(overall.get("total"))
                + " · Jaccard "
                + f"{float(overall.get('macro_jaccard', 0.0)):.3f}"
                + " · reviewed 1:1 both Gold "
                + str(reviewed_overall.get("both_gold"))
                + "/"
                + str(reviewed_overall.get("total"))
            )

    for first_index, first_record in enumerate(v4_records):
        first_corpus = first_record.get("corpus")
        if not isinstance(first_corpus, Mapping):
            continue
        for second_record in v4_records[first_index + 1 :]:
            second_corpus = second_record.get("corpus")
            if (
                not isinstance(second_corpus, Mapping)
                or first_record.get("pipeline") != second_record.get("pipeline")
                or first_corpus.get("input_digest")
                != second_corpus.get("input_digest")
            ):
                continue
            try:
                parity = compare_task2_retrieval_v4_records(
                    first_record, second_record
                )
            except Task2RetrievalV4Error as error:
                typer.echo(
                    "V4 parity unavailable · "
                    + display_escape_text(_redacted_error(error))
                )
                continue
            first_provider = _mapping(
                first_record.get("provider"), "task2 v4 first parity provider"
            )
            second_provider = _mapping(
                second_record.get("provider"), "task2 v4 second parity provider"
            )
            candidate = _mapping(
                parity.get("candidate_set_agreement"),
                "task2 v4 status candidate parity",
            )
            candidate_overall = _mapping(
                candidate.get("overall"), "task2 v4 status candidate overall"
            )
            final = _mapping(
                parity.get("final_group_co_membership_agreement"),
                "task2 v4 status final parity",
            )
            final_overall = _mapping(
                final.get("overall"), "task2 v4 status final overall"
            )
            reviewed = _mapping(
                parity.get("reviewed_one_to_one_gold_quadrants"),
                "task2 v4 status reviewed parity",
            )
            reviewed_overall = _mapping(
                reviewed.get("overall"), "task2 v4 status reviewed overall"
            )
            first_label = str(first_provider.get("provider")) + ":" + str(
                first_provider.get("model")
            )
            second_label = str(second_provider.get("provider")) + ":" + str(
                second_provider.get("model")
            )
            typer.echo(
                "V4 parity · "
                + display_escape_text(first_label)
                + " ↔ "
                + display_escape_text(second_label)
                + " · contracts "
                + str(parity.get("first_contract_valid")).lower()
                + "/"
                + str(parity.get("second_contract_valid")).lower()
            )
            typer.echo(
                "  candidate sets "
                + str(candidate_overall.get("exact"))
                + "/"
                + str(candidate_overall.get("total"))
                + " · final co-membership "
                + str(final_overall.get("exact"))
                + "/"
                + str(final_overall.get("total"))
                + " · Jaccard "
                + f"{float(final_overall.get('macro_jaccard', 0.0)):.3f}"
                + " · reviewed 1:1 both Gold "
                + str(reviewed_overall.get("both_gold"))
                + "/"
                + str(reviewed_overall.get("total"))
                + " · provider-specific candidate inputs"
            )

    for first_index, first_record in enumerate(judge_v5_records):
        first_bundle = first_record.get("candidate_bundle")
        if not isinstance(first_bundle, Mapping):
            continue
        for second_record in judge_v5_records[first_index + 1 :]:
            second_bundle = second_record.get("candidate_bundle")
            if (
                not isinstance(second_bundle, Mapping)
                or first_record.get("pipeline") != second_record.get("pipeline")
                or first_bundle.get("replay_freeze_digest")
                != second_bundle.get("replay_freeze_digest")
            ):
                continue
            try:
                parity = compare_task2_judge_replay_v5_records(
                    first_record, second_record
                )
            except Task2JudgeReplayV5Error as error:
                typer.echo(
                    "V5 judge parity unavailable · "
                    + display_escape_text(_redacted_error(error))
                )
                continue
            first_provider = _mapping(
                first_record.get("provider"), "task2 judge v5 first provider"
            )
            second_provider = _mapping(
                second_record.get("provider"), "task2 judge v5 second provider"
            )
            binary = _mapping(
                parity.get("binary_accept_reject_agreement"),
                "task2 judge v5 status binary parity",
            )
            enum_score = _mapping(
                parity.get("exact_enum_agreement"),
                "task2 judge v5 status enum parity",
            )
            sources = _mapping(
                parity.get("source_accepted_set_agreement"),
                "task2 judge v5 status source parity",
            )
            multi = _mapping(
                parity.get("multi_member_agreement"),
                "task2 judge v5 status multi-member parity",
            )
            multi_binary = _mapping(
                multi.get("pair_binary_accept_reject"),
                "task2 judge v5 status multi-member binary parity",
            )
            multi_enum = _mapping(
                multi.get("pair_enum"),
                "task2 judge v5 status multi-member enum parity",
            )
            multi_sources = _mapping(
                multi.get("source_accepted_set"),
                "task2 judge v5 status multi-member source parity",
            )
            reviewed = _mapping(
                parity.get("reviewed_one_to_one_direct_enum_quadrants"),
                "task2 judge v5 status reviewed parity",
            )
            gate = _mapping(
                parity.get("parity_gate"), "task2 judge v5 status gate"
            )
            first_label = str(first_provider.get("provider")) + ":" + str(
                first_provider.get("model")
            )
            second_label = str(second_provider.get("provider")) + ":" + str(
                second_provider.get("model")
            )
            typer.echo(
                "V5 judge parity · "
                + display_escape_text(first_label)
                + " ↔ "
                + display_escape_text(second_label)
                + " · fixed common inputs "
                + str(parity.get("fixed_call_inputs_identical")).lower()
                + " · gate "
                + ("PASS" if gate.get("passed") else "FAIL")
            )
            typer.echo(
                "  binary accept/reject "
                + str(binary.get("exact"))
                + "/"
                + str(binary.get("total"))
                + " · exact enum "
                + str(enum_score.get("exact"))
                + "/"
                + str(enum_score.get("total"))
                + " · accepted source sets "
                + str(sources.get("exact"))
                + "/"
                + str(sources.get("total"))
                + " · Jaccard "
                + f"{float(sources.get('macro_jaccard', 0.0)):.3f}"
                + " · reviewed 1:1 both Gold "
                + str(reviewed.get("both_gold"))
                + "/"
                + str(reviewed.get("recovered_directed_sources"))
            )
            typer.echo(
                "  multi-member binary "
                + str(multi_binary.get("exact"))
                + "/"
                + str(multi_binary.get("total"))
                + " · enum "
                + str(multi_enum.get("exact"))
                + "/"
                + str(multi_enum.get("total"))
                + " · accepted source sets "
                + str(multi_sources.get("exact"))
                + "/"
                + str(multi_sources.get("total"))
            )

    for first_index, first_record in enumerate(judge_v6_records):
        first_prompt = first_record.get("prompt_ablation")
        if not isinstance(first_prompt, Mapping):
            continue
        for second_record in judge_v6_records[first_index + 1 :]:
            second_prompt = second_record.get("prompt_ablation")
            if (
                not isinstance(second_prompt, Mapping)
                or first_record.get("pipeline") != second_record.get("pipeline")
                or first_prompt.get("ablation_freeze_digest")
                != second_prompt.get("ablation_freeze_digest")
            ):
                continue
            try:
                parity = compare_task2_judge_replay_v6_records(
                    first_record, second_record
                )
            except Task2JudgeReplayV6Error as error:
                typer.echo(
                    "V6 judge parity unavailable · "
                    + display_escape_text(_redacted_error(error))
                )
                continue
            first_provider = _mapping(
                first_record.get("provider"), "task2 judge v6 first provider"
            )
            second_provider = _mapping(
                second_record.get("provider"), "task2 judge v6 second provider"
            )
            binary = _mapping(
                parity.get("binary_accept_reject_agreement"),
                "task2 judge v6 status binary parity",
            )
            enum_score = _mapping(
                parity.get("exact_enum_agreement"),
                "task2 judge v6 status enum parity",
            )
            sources = _mapping(
                parity.get("source_accepted_set_agreement"),
                "task2 judge v6 status source parity",
            )
            multi = _mapping(
                parity.get("multi_member_agreement"),
                "task2 judge v6 status multi-member parity",
            )
            multi_binary = _mapping(
                multi.get("pair_binary_accept_reject"),
                "task2 judge v6 status multi-member binary parity",
            )
            multi_enum = _mapping(
                multi.get("pair_enum"),
                "task2 judge v6 status multi-member enum parity",
            )
            multi_sources = _mapping(
                multi.get("source_accepted_set"),
                "task2 judge v6 status multi-member source parity",
            )
            reviewed = _mapping(
                parity.get("reviewed_one_to_one_direct_enum_quadrants"),
                "task2 judge v6 status reviewed parity",
            )
            gate = _mapping(
                parity.get("parity_gate"), "task2 judge v6 status gate"
            )
            first_label = str(first_provider.get("provider")) + ":" + str(
                first_provider.get("model")
            )
            second_label = str(second_provider.get("provider")) + ":" + str(
                second_provider.get("model")
            )
            typer.echo(
                "V6 judge parity · "
                + display_escape_text(first_label)
                + " ↔ "
                + display_escape_text(second_label)
                + " · ablation "
                + str(parity.get("ablation_freeze_digest"))[:12]
                + " · fixed common inputs "
                + str(parity.get("fixed_call_inputs_identical")).lower()
                + " · gate "
                + ("PASS" if gate.get("passed") else "FAIL")
            )
            typer.echo(
                "  binary accept/reject "
                + str(binary.get("exact"))
                + "/"
                + str(binary.get("total"))
                + " · exact enum "
                + str(enum_score.get("exact"))
                + "/"
                + str(enum_score.get("total"))
                + " · accepted source sets "
                + str(sources.get("exact"))
                + "/"
                + str(sources.get("total"))
                + " · Jaccard "
                + f"{float(sources.get('macro_jaccard', 0.0)):.3f}"
                + " · reviewed 1:1 both Gold "
                + str(reviewed.get("both_gold"))
                + "/"
                + str(reviewed.get("recovered_directed_sources"))
            )
            typer.echo(
                "  multi-member binary "
                + str(multi_binary.get("exact"))
                + "/"
                + str(multi_binary.get("total"))
                + " · enum "
                + str(multi_enum.get("exact"))
                + "/"
                + str(multi_enum.get("total"))
                + " · accepted source sets "
                + str(multi_sources.get("exact"))
                + "/"
                + str(multi_sources.get("total"))
            )

    for record in sorted(
        load_extra(
            "task2-classification",
            "memcommit.semantic-eval.task2-classification",
        ),
        key=lambda value: str(value.get("started_at")),
    ):
        provider = _mapping(record.get("provider"), "task2 classification provider")
        corpus = _mapping(record.get("corpus"), "task2 classification corpus")
        score = _mapping(record.get("score"), "task2 classification score")
        timing = _mapping(record.get("timing"), "task2 classification timing")
        typer.echo(
            "Oracle bands · "
            + display_escape_text(str(provider.get("provider")) + ":" + str(provider.get("model")))
            + " · "
            + str(corpus.get("selected_group_count"))
            + " groups · contract "
            + ("VALID" if record.get("contract_valid") else "INVALID")
        )
        typer.echo(
            "  projected band "
            + str(score.get("correct_projected_band_groups"))
            + "/"
            + str(score.get("expected_groups"))
            + " · provider "
            + _format_seconds(float(timing.get("provider_completion_seconds", 0.0)))
            + " · ledger "
            + display_escape_text(str(record.get("ledger_path")))
        )


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
            display_escape_text(record["operation"])
            + " · "
            + display_escape_text(f"{record['provider']}:{record['model']}")
            + f" · {display_escape_text(record['pipeline_id'])}"
            + f" · schema v{record['pipeline_version']} · {record['status']}"
            + f" · {record['corpus_role']}@{record['fixture_digest'][:12]}"
            + _condition_suffix(record)
        )
        typer.echo(
            f"  {record['corpus_role']} score {record['cases_passed']}/"
            f"{record['cases_total']} · failed {record['cases_failed']}"
        )
        typer.echo(
            f"  attempts exact={record['attempts_exact']}/"
            f"{record['attempts_total']} · structurally-valid="
            f"{record['attempts_structurally_valid']}/{record['attempts_total']}"
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
        if record["distribution"] is not None:
            _render_distribution(record["distribution"])
        elif record["relation_distribution"] is not None:
            _render_relation_distribution(record["relation_distribution"])
        elif record["label_distribution"] is not None:
            _render_label_distribution(record["label_distribution"])
        _render_stage_timing(record["stage_completion_seconds"])
