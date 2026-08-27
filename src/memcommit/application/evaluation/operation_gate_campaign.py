"""Replayable campaigns for the shared first-stage operation gates."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from memcommit.application.evaluation.semantic_campaign import (
    CALIBRATION_CORPUS_ROLE,
    CALIBRATION_MODE,
    LEDGER_KIND,
    LEDGER_SCHEMA_VERSION,
    SemanticCampaignError,
    _atomic_write_json,
    _completion_metadata,
    _ensure_ledger_directory,
    _identity,
    _provider_failure_category,
    _provider_settings,
    _run_id,
    _safe_diagnostic,
    _timestamp,
    _utc_now,
)
from memcommit.application.semantic.classification.gates import (
    OPERATION_GATE_PIPELINE_V1,
    OperationGateError,
    classify_operation_gate,
)
from memcommit.providers.types import SemanticProvider
from memcommit.providers.subscription import QueryProviderError


DEFAULT_OPERATION_GATE_FIXTURE = Path(__file__).parent / "fixtures" / "operation_gates.json"
DEFAULT_OPERATION_GATE_V2_FIXTURE = Path(__file__).parent / "fixtures" / "operation_gates_v2.json"
DEFAULT_OPERATION_GATE_V2_LOCK = Path(__file__).parent / "fixtures" / "operation_gates_v2.lock.json"
DEFAULT_OPERATION_GATE_LOCK = Path(__file__).parent / "fixtures" / "operation_gates.lock.json"
MAX_OPERATION_GATE_CASES = 200


@dataclass(frozen=True)
class OperationGateDefinition:
    labels: tuple[str, ...]
    instruction: str


@dataclass(frozen=True)
class OperationGateCorpus:
    path: Path
    digest: str
    schema_version: int
    ruleset_version: str
    case_limit: int
    definitions: Mapping[str, OperationGateDefinition]
    cases: tuple[dict[str, object], ...]
    base_case_count: int = 0


@dataclass(frozen=True)
class OperationGateLock:
    fixture: str
    digest: str
    case_count: int
    case_limit: int
    frozen_at: str


@dataclass(frozen=True)
class OperationGateCompositeLock:
    base_fixture: str
    base_digest: str
    extension_fixture: str
    extension_digest: str
    composite_digest: str
    case_count: int
    base_case_count: int
    case_limit: int
    frozen_at: str


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticCampaignError(f"Operation gate fixture {field} must be non-empty.")
    return value


def load_operation_gate_lock(path: Path | None = None) -> OperationGateLock:
    """Load the frozen, explicitly consumed calibration baseline identity."""
    lock_path = path or DEFAULT_OPERATION_GATE_LOCK
    try:
        value = json.loads(
            lock_path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise SemanticCampaignError("The operation gate lock is invalid JSON.") from error
    required = {
        "kind", "schema_version", "operation", "corpus_role", "fixture",
        "fixture_sha256", "case_count", "case_limit", "frozen_at",
        "independent_holdout", "consumed_during_optimization",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value["kind"] != "memcommit.semantic-eval.corpus-lock"
        or value["schema_version"] != 1
        or value["operation"] != "operation-gates"
        or value["corpus_role"] != "CALIBRATION"
        or value["independent_holdout"] is not False
        or value["consumed_during_optimization"] is not True
    ):
        raise SemanticCampaignError("The operation gate lock contract is invalid.")
    digest = _text(value["fixture_sha256"], "lock fixture_sha256")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise SemanticCampaignError("The operation gate lock digest is invalid.")
    count = value["case_count"]
    limit = value["case_limit"]
    if (
        not isinstance(count, int) or isinstance(count, bool) or count < 1
        or not isinstance(limit, int) or isinstance(limit, bool)
        or not count <= limit <= MAX_OPERATION_GATE_CASES
    ):
        raise SemanticCampaignError("The operation gate lock counts are invalid.")
    return OperationGateLock(
        fixture=_text(value["fixture"], "lock fixture"),
        digest=digest,
        case_count=count,
        case_limit=limit,
        frozen_at=_text(value["frozen_at"], "lock frozen_at"),
    )


def load_operation_gate_composite_lock(
    path: Path | None = None,
) -> OperationGateCompositeLock:
    """Load the frozen identity of the consumed 75-case composite."""
    lock_path = path or DEFAULT_OPERATION_GATE_V2_LOCK
    try:
        value = json.loads(
            lock_path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise SemanticCampaignError("The operation gate composite lock is invalid JSON.") from error
    required = {
        "kind", "schema_version", "operation", "corpus_role", "base_fixture",
        "base_fixture_sha256", "extension_fixture", "extension_fixture_sha256",
        "composite_sha256", "case_count", "base_case_count", "case_limit",
        "frozen_at", "independent_holdout", "consumed_during_optimization",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value["kind"] != "memcommit.semantic-eval.composite-corpus-lock"
        or value["schema_version"] != 1
        or value["operation"] != "operation-gates"
        or value["corpus_role"] != "CALIBRATION"
        or value["independent_holdout"] is not False
        or value["consumed_during_optimization"] is not True
    ):
        raise SemanticCampaignError("The operation gate composite lock contract is invalid.")
    digests = [
        _text(value[field], f"composite lock {field}")
        for field in (
            "base_fixture_sha256", "extension_fixture_sha256", "composite_sha256"
        )
    ]
    if any(
        len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        for digest in digests
    ):
        raise SemanticCampaignError("The operation gate composite lock digest is invalid.")
    count = value["case_count"]
    base_count = value["base_case_count"]
    limit = value["case_limit"]
    if (
        not isinstance(count, int) or isinstance(count, bool)
        or not isinstance(base_count, int) or isinstance(base_count, bool)
        or not isinstance(limit, int) or isinstance(limit, bool)
        or not 1 <= base_count < count <= limit <= MAX_OPERATION_GATE_CASES
    ):
        raise SemanticCampaignError("The operation gate composite lock counts are invalid.")
    return OperationGateCompositeLock(
        base_fixture=_text(value["base_fixture"], "composite lock base fixture"),
        base_digest=digests[0],
        extension_fixture=_text(value["extension_fixture"], "composite lock extension fixture"),
        extension_digest=digests[1],
        composite_digest=digests[2],
        case_count=count,
        base_case_count=base_count,
        case_limit=limit,
        frozen_at=_text(value["frozen_at"], "composite lock frozen_at"),
    )


def load_operation_gate_corpus(
    path: Path | None = None,
    *,
    lock_path: Path | None = None,
    verify_lock: bool | None = None,
) -> OperationGateCorpus:
    """Load a strict reviewed gate corpus capped for one bounded campaign."""
    fixture_path = path or DEFAULT_OPERATION_GATE_FIXTURE
    composite_base_case_count = 0
    composite_extension_digest: str | None = None
    composite_base_digest: str | None = None
    is_composite_extension = False
    try:
        raw = fixture_path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise SemanticCampaignError(
            "The operation gate fixture is not valid strict UTF-8 JSON."
        ) from error
    if isinstance(value, dict) and value.get("operation") == "operation-gates-extension":
        is_composite_extension = True
        extension_required = {
            "operation", "schema_version", "ruleset_version", "description",
            "case_limit", "base", "cases",
        }
        if set(value) != extension_required or value["schema_version"] != 1:
            raise SemanticCampaignError("The operation gate extension contract is invalid.")
        base_ref = value["base"]
        if not isinstance(base_ref, dict) or set(base_ref) != {"fixture", "fixture_sha256"}:
            raise SemanticCampaignError("The operation gate extension base reference is invalid.")
        base = load_operation_gate_corpus()
        if base_ref != {"fixture": base.path.name, "fixture_sha256": base.digest}:
            raise SemanticCampaignError("The operation gate extension does not reference the frozen base.")
        extension_cases = value["cases"]
        if not isinstance(extension_cases, list) or not extension_cases:
            raise SemanticCampaignError("The operation gate extension has no cases.")
        extension_digest = hashlib.sha256(raw).hexdigest()
        composite_extension_digest = extension_digest
        composite_base_digest = base.digest
        composite_base_case_count = len(base.cases)
        # The composite digest binds both immutable layers even though the v2
        # file stores only additions. This avoids copying or silently editing
        # the consumed 37-case baseline.
        raw = f"{base.digest}:{extension_digest}".encode("ascii")
        value = {
            "operation": "operation-gates",
            "schema_version": 1,
            "ruleset_version": value["ruleset_version"],
            "description": value["description"],
            "case_limit": value["case_limit"],
            "definitions": {
                name: {
                    "labels": list(definition.labels),
                    "instruction": definition.instruction,
                }
                for name, definition in base.definitions.items()
            },
            "cases": [*base.cases, *extension_cases],
        }
    required = {
        "operation", "schema_version", "ruleset_version", "description",
        "case_limit", "definitions", "cases",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise SemanticCampaignError("The operation gate fixture contract is invalid.")
    if value["operation"] != "operation-gates" or value["schema_version"] != 1:
        raise SemanticCampaignError("The operation gate fixture identity is unsupported.")
    case_limit = value["case_limit"]
    if (
        not isinstance(case_limit, int)
        or isinstance(case_limit, bool)
        or not 1 <= case_limit <= MAX_OPERATION_GATE_CASES
    ):
        raise SemanticCampaignError("Operation gate case_limit must be between 1 and 200.")
    raw_definitions = value["definitions"]
    if not isinstance(raw_definitions, dict) or not raw_definitions:
        raise SemanticCampaignError("Operation gate definitions are empty.")
    definitions: dict[str, OperationGateDefinition] = {}
    for name, raw_definition in raw_definitions.items():
        operation = _text(name, "definition name")
        if not isinstance(raw_definition, dict) or set(raw_definition) != {"labels", "instruction"}:
            raise SemanticCampaignError(f"Operation gate definition {operation} is invalid.")
        labels = raw_definition["labels"]
        if (
            not isinstance(labels, list)
            or len(labels) < 2
            or any(not isinstance(label, str) or not label for label in labels)
            or len(labels) != len(set(labels))
        ):
            raise SemanticCampaignError(f"Operation gate {operation} labels are invalid.")
        definitions[operation] = OperationGateDefinition(
            labels=tuple(labels),
            instruction=_text(raw_definition["instruction"], f"{operation} instruction"),
        )
    raw_cases = value["cases"]
    if not isinstance(raw_cases, list) or not raw_cases or len(raw_cases) > case_limit:
        raise SemanticCampaignError("Operation gate case count exceeds its bounded contract.")
    cases: list[dict[str, object]] = []
    for index, raw_case in enumerate(raw_cases, start=1):
        case_fields = {"id", "operation", "task", "length_tier", "scenario", "input", "expected"}
        if not isinstance(raw_case, dict) or set(raw_case) != case_fields:
            raise SemanticCampaignError(f"Operation gate case {index} has an invalid field set.")
        case_id = _text(raw_case["id"], f"case {index} id")
        operation = _text(raw_case["operation"], f"case {case_id} operation")
        if operation not in definitions:
            raise SemanticCampaignError(f"Operation gate case {case_id} uses an unknown operation.")
        task = raw_case["task"]
        if not isinstance(task, int) or isinstance(task, bool) or task not in {1, 2, 3}:
            raise SemanticCampaignError(f"Operation gate case {case_id} task is invalid.")
        tier = raw_case["length_tier"]
        if tier not in {"SHORT", "LONG"}:
            raise SemanticCampaignError(f"Operation gate case {case_id} length tier is invalid.")
        inputs = raw_case["input"]
        if not isinstance(inputs, dict) or not inputs:
            raise SemanticCampaignError(f"Operation gate case {case_id} input is invalid.")
        expected = raw_case["expected"]
        if not isinstance(expected, dict) or set(expected) != {"label", "rationale"}:
            raise SemanticCampaignError(f"Operation gate case {case_id} expected value is invalid.")
        label = expected["label"]
        if label not in definitions[operation].labels:
            raise SemanticCampaignError(f"Operation gate case {case_id} label is invalid.")
        cases.append({
            "id": case_id,
            "operation": operation,
            "task": task,
            "length_tier": tier,
            "scenario": _text(raw_case["scenario"], f"case {case_id} scenario"),
            "input": dict(inputs),
            "expected": {"label": label, "rationale": _text(expected["rationale"], f"case {case_id} rationale")},
        })
    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise SemanticCampaignError("Operation gate case IDs must be unique.")
    covered = {str(case["operation"]) for case in cases}
    if covered != set(definitions):
        raise SemanticCampaignError("Every operation gate definition requires a case.")
    corpus = OperationGateCorpus(
        path=fixture_path,
        digest=hashlib.sha256(raw).hexdigest(),
        schema_version=1,
        ruleset_version=_text(value["ruleset_version"], "ruleset_version"),
        case_limit=case_limit,
        definitions=definitions,
        cases=tuple(cases),
        base_case_count=composite_base_case_count,
    )
    should_verify = (
        (path is None if verify_lock is None else verify_lock)
        and not is_composite_extension
    )
    if should_verify:
        lock = load_operation_gate_lock(lock_path)
        if (
            corpus.path.name != lock.fixture
            or corpus.digest != lock.digest
            or len(corpus.cases) != lock.case_count
            or corpus.case_limit != lock.case_limit
        ):
            raise SemanticCampaignError(
                "The operation gate fixture no longer matches its frozen calibration lock."
            )
    is_default_composite = fixture_path.resolve() == DEFAULT_OPERATION_GATE_V2_FIXTURE.resolve()
    if is_composite_extension and (is_default_composite or verify_lock is True):
        lock = load_operation_gate_composite_lock(lock_path)
        if (
            lock.base_fixture != DEFAULT_OPERATION_GATE_FIXTURE.name
            or lock.base_digest != composite_base_digest
            or lock.extension_fixture != fixture_path.name
            or lock.extension_digest != composite_extension_digest
            or lock.composite_digest != corpus.digest
            or lock.case_count != len(corpus.cases)
            or lock.base_case_count != corpus.base_case_count
            or lock.case_limit != corpus.case_limit
        ):
            raise SemanticCampaignError(
                "The operation gate composite no longer matches its frozen calibration lock."
            )
    return corpus


def _stats(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "p95": ordered[max(1, math.ceil(.95 * len(ordered))) - 1],
        "max": ordered[-1],
    }


def _summary(cases: Sequence[Mapping[str, object]], attempts: Sequence[Mapping[str, object]], runs: int) -> dict[str, object]:
    threshold = math.ceil((2 * runs) / 3)
    case_results: list[dict[str, object]] = []
    for case in cases:
        selected = [attempt for attempt in attempts if attempt["case_id"] == case["id"]]
        valid = [attempt for attempt in selected if attempt["actual"] is not None]
        exact = [attempt for attempt in selected if attempt["failure_category"] is None]
        labels = Counter(str(attempt["actual"]["label"]) for attempt in valid)  # type: ignore[index]
        majority = max(labels.values(), default=0)
        passed = len(selected) == runs and len(valid) == runs and len(exact) >= threshold and majority >= threshold
        case_results.append({"case_id": case["id"], "status": "PASS" if passed else "FAIL", "exact_matches": len(exact), "majority_count": majority, "required_count": threshold})
    passed_count = sum(result["status"] == "PASS" for result in case_results)
    failures = Counter(str(attempt["failure_category"]) for attempt in attempts if attempt["failure_category"] is not None)
    by_operation: dict[str, dict[str, int]] = {}
    by_task: dict[str, dict[str, int]] = {}
    by_tier: dict[str, dict[str, int]] = {}
    result_by_id = {result["case_id"]: result for result in case_results}
    for case in cases:
        passed = result_by_id[case["id"]]["status"] == "PASS"
        for bucket, key in ((by_operation, str(case["operation"])), (by_task, f"task-{case['task']}"), (by_tier, str(case["length_tier"]))):
            row = bucket.setdefault(key, {"passed": 0, "total": 0})
            row["total"] += 1
            row["passed"] += int(passed)
    durations = [float(attempt["completion_seconds"]) for attempt in attempts]
    operation_durations = {
        operation: _stats([float(attempt["completion_seconds"]) for attempt in attempts if attempt["operation"] == operation])
        for operation in sorted(by_operation)
    }
    return {
        "campaign_passed": bool(case_results) and passed_count == len(case_results),
        "cases": {"passed": passed_count, "failed": len(case_results) - passed_count, "total": len(case_results)},
        "attempts": {"exact_matches": sum(attempt["failure_category"] is None for attempt in attempts), "structurally_valid": sum(attempt["actual"] is not None for attempt in attempts), "total": len(attempts)},
        "case_results": case_results,
        "failures": dict(sorted(failures.items())),
        "distributions": {
            "expected_label": dict(sorted(Counter(str(case["expected"]["label"]) for case in cases).items())),  # type: ignore[index]
            "by_operation": by_operation,
            "by_task": by_task,
            "by_length_tier": by_tier,
        },
        "completion_seconds": _stats(durations),
        "stage_completion_seconds": {"SEMANTIC_GATE": _stats(durations)},
        "operation_completion_seconds": operation_durations,
    }


def _projection(case: Mapping[str, object]) -> dict[str, object]:
    expected = case["expected"]
    assert isinstance(expected, Mapping)
    return {"id": case["id"], "scenario": case["scenario"], "input": case["input"], "expected": {"label": expected["label"]}}


def run_operation_gate_campaign(
    provider: SemanticProvider,
    *,
    ledger_dir: Path,
    provider_connection_seconds: float,
    runs: int = 1,
    fixture_path: Path | None = None,
    operations: Sequence[str] | None = None,
    length_tiers: Sequence[str] | None = None,
    tasks: Sequence[int] | None = None,
    case_ids: Sequence[str] | None = None,
    layer: str = "all",
    classifier: Callable[..., object] | None = None,
    known_error_types: tuple[type[BaseException], ...] = (),
    progress_fn: Callable[[dict[str, object]], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
    utcnow: Callable[[], datetime] = _utc_now,
) -> dict[str, object]:
    """Run a frozen, filterable, at-most-200-case gate campaign."""
    if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
        raise SemanticCampaignError("Campaign runs must be a positive integer.")
    # New campaigns default to the latest frozen composite; callers can still
    # replay the 37-case baseline by passing its exact fixture explicitly.
    corpus = load_operation_gate_corpus(
        fixture_path or DEFAULT_OPERATION_GATE_V2_FIXTURE
    )
    normalized_layer = layer.strip().lower()
    if normalized_layer not in {"all", "base", "additions"}:
        raise SemanticCampaignError("Operation gate layer must be all, base, or additions.")
    operation_filter = set(operations or corpus.definitions)
    tier_filter = set(length_tiers or {"SHORT", "LONG"})
    task_filter = set(tasks or {1, 2, 3})
    if not operation_filter <= set(corpus.definitions):
        raise SemanticCampaignError("Unknown operation gate filter.")
    if not tier_filter <= {"SHORT", "LONG"} or not task_filter <= {1, 2, 3}:
        raise SemanticCampaignError("Operation gate tier or task filter is invalid.")
    indexed_cases = list(enumerate(corpus.cases))
    if normalized_layer == "base":
        indexed_cases = indexed_cases[: corpus.base_case_count or len(indexed_cases)]
    elif normalized_layer == "additions":
        if corpus.base_case_count == 0:
            raise SemanticCampaignError("This operation gate corpus has no additions layer.")
        indexed_cases = indexed_cases[corpus.base_case_count :]
    selected = [case for _, case in indexed_cases if case["operation"] in operation_filter and case["length_tier"] in tier_filter and case["task"] in task_filter]
    if case_ids is not None:
        requested = list(case_ids)
        if (
            any(not isinstance(case_id, str) or not case_id for case_id in requested)
            or len(requested) != len(set(requested))
        ):
            raise SemanticCampaignError("Operation gate case IDs must be unique non-empty strings.")
        available = {str(case["id"]) for case in corpus.cases}
        unknown = [case_id for case_id in requested if case_id not in available]
        if unknown:
            raise SemanticCampaignError("Unknown operation gate case(s): " + ", ".join(unknown))
        requested_set = set(requested)
        selected = [case for case in selected if case["id"] in requested_set]
    if not selected or len(selected) > corpus.case_limit:
        raise SemanticCampaignError("Operation gate campaign selection is empty or too large.")
    if provider_connection_seconds < 0 or not math.isfinite(provider_connection_seconds):
        raise SemanticCampaignError("Provider connection time must be finite and nonnegative.")
    campaign_started = clock()
    started = utcnow()
    run_id = _run_id(started)
    runs_dir = _ensure_ledger_directory(ledger_dir)
    ledger_path = runs_dir / f"{run_id}.json"
    ledger: dict[str, object] = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "kind": LEDGER_KIND,
        "run_id": run_id,
        "status": "RUNNING",
        "started_at": _timestamp(started),
        "completed_at": None,
        "ledger_path": str(ledger_path),
        "corpus": {"operation": "operation-gates", "role": CALIBRATION_CORPUS_ROLE, "calibration_mode": CALIBRATION_MODE, "independent_holdout": False, "fixture": corpus.path.name, "fixture_digest": corpus.digest, "schema_version": corpus.schema_version, "ruleset_version": corpus.ruleset_version, "fixture_case_count": len(corpus.cases), "base_case_count": corpus.base_case_count, "case_limit": corpus.case_limit, "selected_layer": normalized_layer.upper(), "selected_case_ids": [case["id"] for case in selected], "selected_operations": sorted(operation_filter), "selected_length_tiers": sorted(tier_filter), "selected_tasks": sorted(task_filter)},
        "pipeline": {"id": OPERATION_GATE_PIPELINE_V1, "version": 1, "stages": ["SEMANTIC_GATE"], "gate": "exact operation label with leave-one-out calibration"},
        "provider": _identity(provider),
        "settings": {"runs_per_case": runs, "provider": _provider_settings(provider), "temperature": 0, "ttft": "NOT_AVAILABLE_NONSTREAMING"},
        "timing": {"provider_connection_seconds": provider_connection_seconds, "campaign_seconds": None, "total_seconds": None},
        "attempts": [],
        "summary": _summary(selected, [], runs),
    }
    _atomic_write_json(ledger_path, ledger)
    attempts = ledger["attempts"]
    assert isinstance(attempts, list)
    runner = classifier or classify_operation_gate
    try:
        for case in selected:
            operation = str(case["operation"])
            definition = corpus.definitions[operation]
            calibration = [_projection(item) for item in corpus.cases if item["operation"] == operation and item["id"] != case["id"]]
            expected = {"label": case["expected"]["label"]}  # type: ignore[index]
            for repetition in range(1, runs + 1):
                attempt_started = clock()
                previous = getattr(provider, "last_run", None)
                actual = None
                raw_response = prompt_digest = schema_digest = response_digest = None
                failure_category = diagnostic = error_type = None
                unexpected = None
                try:
                    result = runner(case, provider, operation=operation, instruction=definition.instruction, labels=definition.labels, calibration_examples=calibration)
                    actual = {"label": result.classification.label}
                    raw_response = result.raw_response
                    prompt_digest = result.prompt_digest
                    schema_digest = result.schema_digest
                    response_digest = result.response_digest
                    if actual != expected:
                        failure_category = "LABEL_MISMATCH"
                        diagnostic = "The label must exactly match the reviewed gate contract."
                except OperationGateError as error:
                    failure_category, diagnostic, error_type = error.category, _safe_diagnostic(error), type(error).__name__
                    raw_response, prompt_digest, schema_digest, response_digest = error.raw_response, error.prompt_digest, error.schema_digest, error.response_digest
                except QueryProviderError as error:
                    failure_category, diagnostic, error_type = _provider_failure_category(error), _safe_diagnostic(error), type(error).__name__
                except known_error_types as error:
                    failure_category, diagnostic, error_type = "PROVIDER", _safe_diagnostic(error), type(error).__name__
                except BaseException as error:
                    failure_category, diagnostic, error_type, unexpected = "INTERNAL", "The host campaign aborted on an unexpected internal failure.", type(error).__name__, error
                duration = max(0.0, clock() - attempt_started)
                attempt = {"ordinal": len(attempts) + 1, "case_id": case["id"], "operation": operation, "task": case["task"], "length_tier": case["length_tier"], "repetition": repetition, "stage": "SEMANTIC_GATE", "status": "PASS" if failure_category is None else "FAIL", "failure_category": failure_category, "diagnostic": diagnostic, "error_type": error_type, "expected": expected, "actual": actual, "completion_seconds": duration, "prompt_digest": prompt_digest, "schema_digest": schema_digest, "response_digest": response_digest, "stage_runs": [], "raw_response": raw_response, "response_bytes": len(raw_response.encode("utf-8")) if raw_response is not None else None, "provider_run": _completion_metadata(provider, previous)}
                attempts.append(attempt)
                ledger["summary"] = _summary(selected, attempts, runs)
                _atomic_write_json(ledger_path, ledger)
                if progress_fn is not None:
                    progress_fn({**attempt, "index": attempt["ordinal"], "total": len(selected) * runs})
                if unexpected is not None:
                    raise unexpected
    except BaseException:
        status = "ABORTED"
        raise
    else:
        status = "COMPLETED"
    finally:
        campaign_seconds = max(0.0, clock() - campaign_started)
        ledger["status"] = status
        ledger["completed_at"] = _timestamp(utcnow())
        ledger["timing"] = {"provider_connection_seconds": provider_connection_seconds, "campaign_seconds": campaign_seconds, "total_seconds": provider_connection_seconds + campaign_seconds}
        ledger["summary"] = _summary(selected, attempts, runs)
        _atomic_write_json(ledger_path, ledger)
    return ledger
