"""Replayable semantic-evaluation campaigns for decomposed operations."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import tempfile
import time
import uuid

from memcommit.semantic.classification.ambiguity import (
    AMBIGUITY_PIPELINE_V1,
    AMBIGUITY_PIPELINE_V2,
    AMBIGUITY_PIPELINE_V3,
    AMBIGUITY_PIPELINE_V4,
    AMBIGUITY_PIPELINE_V5,
    AMBIGUITY_PIPELINE_V6,
    AmbiguityPipelineError,
    AmbiguityStageRun,
    classify_ambiguity_case,
    classify_ambiguity_case_v1,
    classify_ambiguity_case_v3,
    classify_ambiguity_case_v4,
    classify_ambiguity_case_v5,
    classify_ambiguity_case_v6,
)
from memcommit.semantic.classification.duplicates import (
    DUPLICATE_PIPELINE_V1,
    DuplicatePipelineError,
    classify_duplicate_case,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity, SemanticProvider
from memcommit.query_provider import QueryProviderError


DEFAULT_AMBIGUITY_FIXTURE = Path(__file__).parent / "fixtures" / "ambiguity.json"
DEFAULT_AMBIGUITY_HOLDOUT_FIXTURE = (
    Path(__file__).parent / "fixtures" / "ambiguity_holdout.json"
)
DEFAULT_AMBIGUITY_HOLDOUT_LOCK = (
    Path(__file__).parent / "fixtures" / "ambiguity_holdout.lock.json"
)
DEFAULT_DUPLICATE_FIXTURE = Path(__file__).parent / "fixtures" / "duplicates.json"
LEDGER_SCHEMA_VERSION = 1
LEDGER_KIND = "memcommit.semantic-eval.run"
PIPELINE_ID = AMBIGUITY_PIPELINE_V2
PIPELINE_CHOICES = ("v1", "v2", "v3", "v4", "v5", "v6")
CORPUS_CHOICES = ("calibration", "holdout")
CALIBRATION_CORPUS_ROLE = "CALIBRATION"
HOLDOUT_CORPUS_ROLE = "HOLDOUT"
CALIBRATION_MODE = "LEAVE_ONE_OUT"
HOLDOUT_CALIBRATION_MODE = "FIXED_CALIBRATION"
_INTERPRETATIONS = ("SINGLE", "DOMINANT", "COMPETING")
_CLARIFICATIONS = ("NONE", "HELPFUL", "REQUIRED")
_DUPLICATE_RELATIONS = (
    "EXACT",
    "SURFACE_EQUIVALENT",
    "SEMANTIC_EQUIVALENT",
    "OVERLAP",
    "UNKNOWN",
    "DISTINCT",
)
_SEMANTIC_DUPLICATE_RELATIONS = set(_DUPLICATE_RELATIONS[2:])


class SemanticCampaignError(RuntimeError):
    """The campaign or its retained ledger cannot be interpreted safely."""


@dataclass(frozen=True)
class AmbiguityCorpus:
    """One fully validated ambiguity fixture snapshot."""

    path: Path
    digest: str
    schema_version: int
    ruleset_version: str
    cases: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class AmbiguityHoldoutLock:
    """The reviewed fixture identities frozen before holdout evaluation."""

    path: Path
    fixture: str
    fixture_digest: str
    case_count: int
    calibration_fixture: str
    calibration_digest: str
    frozen_at: str


@dataclass(frozen=True)
class DuplicateCorpus:
    """One fully validated duplicate-relation fixture snapshot."""

    path: Path
    digest: str
    schema_version: int
    ruleset_version: str
    cases: tuple[dict[str, object], ...]


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticCampaignError(f"Ambiguity fixture {field} must be non-empty.")
    return value


def _validate_case(raw: object, *, index: int) -> dict[str, object]:
    if not isinstance(raw, dict) or set(raw) != {
        "id",
        "scenario",
        "memory",
        "expected",
    }:
        raise SemanticCampaignError(
            f"Ambiguity fixture case {index} has an invalid field set."
        )
    case_id = _nonempty_string(raw["id"], f"case {index} id")
    scenario = _nonempty_string(raw["scenario"], f"case {case_id} scenario")
    memory = raw["memory"]
    if not isinstance(memory, dict) or set(memory) != {"uid", "content"}:
        raise SemanticCampaignError(
            f"Ambiguity fixture case {case_id} requires one uid/content Memory."
        )
    uid = _nonempty_string(memory["uid"], f"case {case_id} Memory uid")
    content = _nonempty_string(
        memory["content"], f"case {case_id} Memory content"
    )
    expected = raw["expected"]
    if not isinstance(expected, dict) or set(expected) != {
        "interpretation",
        "clarification",
        "ordinary_readings",
        "question",
        "rationale",
    }:
        raise SemanticCampaignError(
            f"Ambiguity fixture case {case_id} has an invalid expected contract."
        )
    interpretation = expected["interpretation"]
    clarification = expected["clarification"]
    if interpretation not in _INTERPRETATIONS:
        raise SemanticCampaignError(
            f"Ambiguity fixture case {case_id} has an invalid interpretation."
        )
    if clarification not in _CLARIFICATIONS:
        raise SemanticCampaignError(
            f"Ambiguity fixture case {case_id} has an invalid clarification."
        )
    readings = expected["ordinary_readings"]
    if (
        not isinstance(readings, list)
        or not readings
        or any(not isinstance(item, str) or not item.strip() for item in readings)
    ):
        raise SemanticCampaignError(
            f"Ambiguity fixture case {case_id} has invalid ordinary readings."
        )
    question = expected["question"]
    rationale = expected["rationale"]
    if not isinstance(question, str) or not isinstance(rationale, str) or not rationale:
        raise SemanticCampaignError(
            f"Ambiguity fixture case {case_id} has invalid explanatory text."
        )
    return {
        "id": case_id,
        "scenario": scenario,
        "memory": {"uid": uid, "content": content},
        "expected": {
            "interpretation": interpretation,
            "clarification": clarification,
            "ordinary_readings": list(readings),
            "question": question,
            "rationale": rationale,
        },
    }


def load_ambiguity_corpus(path: Path | None = None) -> AmbiguityCorpus:
    """Load a reviewed ambiguity fixture without accepting partial shapes."""
    fixture_path = path or DEFAULT_AMBIGUITY_FIXTURE
    try:
        raw_bytes = fixture_path.read_bytes()
        decoded = raw_bytes.decode("utf-8")
        data = json.loads(decoded, object_pairs_hook=_strict_json_object)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise SemanticCampaignError(
            "The ambiguity calibration fixture is not valid strict UTF-8 JSON."
        ) from error
    if not isinstance(data, dict) or set(data) != {
        "operation",
        "schema_version",
        "ruleset_version",
        "description",
        "labels",
        "cases",
    }:
        raise SemanticCampaignError(
            "The ambiguity calibration fixture has an invalid top-level contract."
        )
    if (
        data["operation"] != "find-ambiguities"
        or not isinstance(data["schema_version"], int)
        or isinstance(data["schema_version"], bool)
        or data["schema_version"] != 1
    ):
        raise SemanticCampaignError(
            "The ambiguity calibration fixture operation or schema is unsupported."
        )
    ruleset = _nonempty_string(data["ruleset_version"], "ruleset_version")
    _nonempty_string(data["description"], "description")
    if data["labels"] != {
        "interpretation": list(_INTERPRETATIONS),
        "clarification": list(_CLARIFICATIONS),
    }:
        raise SemanticCampaignError(
            "The ambiguity calibration fixture label contract is unsupported."
        )
    raw_cases = data["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise SemanticCampaignError("The ambiguity calibration fixture is empty.")
    cases = tuple(
        _validate_case(case, index=index)
        for index, case in enumerate(raw_cases, start=1)
    )
    ids = [str(case["id"]) for case in cases]
    uids = [str(case["memory"]["uid"]) for case in cases]  # type: ignore[index]
    if len(ids) != len(set(ids)) or len(uids) != len(set(uids)):
        raise SemanticCampaignError(
            "Ambiguity calibration case IDs and Memory UIDs must be unique."
        )
    return AmbiguityCorpus(
        path=fixture_path,
        digest=hashlib.sha256(raw_bytes).hexdigest(),
        schema_version=1,
        ruleset_version=ruleset,
        cases=cases,
    )


def _validate_duplicate_case(raw: object, *, index: int) -> dict[str, object]:
    if not isinstance(raw, dict) or set(raw) != {
        "id",
        "scenario",
        "memories",
        "expected",
    }:
        raise SemanticCampaignError(
            f"Duplicate fixture case {index} has an invalid field set."
        )
    case_id = _nonempty_string(raw["id"], f"duplicate case {index} id")
    scenario = _nonempty_string(
        raw["scenario"],
        f"duplicate case {case_id} scenario",
    )
    memories = raw["memories"]
    if not isinstance(memories, list) or len(memories) != 2:
        raise SemanticCampaignError(
            f"Duplicate fixture case {case_id} requires exactly two Memories."
        )
    projected_memories: list[dict[str, str]] = []
    for memory_index, memory in enumerate(memories, start=1):
        if not isinstance(memory, dict) or set(memory) != {"uid", "content"}:
            raise SemanticCampaignError(
                f"Duplicate fixture case {case_id} Memory {memory_index} is invalid."
            )
        projected_memories.append(
            {
                "uid": _nonempty_string(
                    memory["uid"],
                    f"duplicate case {case_id} Memory uid",
                ),
                "content": _nonempty_string(
                    memory["content"],
                    f"duplicate case {case_id} Memory content",
                ),
            }
        )
    if projected_memories[0]["uid"] == projected_memories[1]["uid"]:
        raise SemanticCampaignError(
            f"Duplicate fixture case {case_id} Memory UIDs must differ."
        )
    expected = raw["expected"]
    if not isinstance(expected, dict) or set(expected) != {"relation", "rationale"}:
        raise SemanticCampaignError(
            f"Duplicate fixture case {case_id} has an invalid expected contract."
        )
    relation = expected["relation"]
    if relation not in _DUPLICATE_RELATIONS:
        raise SemanticCampaignError(
            f"Duplicate fixture case {case_id} has an invalid relation."
        )
    rationale = _nonempty_string(
        expected["rationale"],
        f"duplicate case {case_id} rationale",
    )
    return {
        "id": case_id,
        "scenario": scenario,
        "memories": projected_memories,
        "expected": {"relation": relation, "rationale": rationale},
    }


def load_duplicate_corpus(path: Path | None = None) -> DuplicateCorpus:
    """Load the strict reviewed duplicate-relation calibration fixture."""
    fixture_path = path or DEFAULT_DUPLICATE_FIXTURE
    try:
        raw_bytes = fixture_path.read_bytes()
        value = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_strict_json_object,
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise SemanticCampaignError(
            "The duplicate calibration fixture is not valid strict UTF-8 JSON."
        ) from error
    if not isinstance(value, dict) or set(value) != {
        "operation",
        "schema_version",
        "ruleset_version",
        "description",
        "labels",
        "cases",
    }:
        raise SemanticCampaignError(
            "The duplicate calibration fixture has an invalid top-level contract."
        )
    if (
        value["operation"] != "find-duplicates"
        or not isinstance(value["schema_version"], int)
        or isinstance(value["schema_version"], bool)
        or value["schema_version"] != 1
        or value["labels"] != list(_DUPLICATE_RELATIONS)
    ):
        raise SemanticCampaignError(
            "The duplicate calibration fixture operation, schema, or labels are unsupported."
        )
    ruleset = _nonempty_string(value["ruleset_version"], "ruleset_version")
    _nonempty_string(value["description"], "description")
    raw_cases = value["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise SemanticCampaignError("The duplicate calibration fixture is empty.")
    cases = tuple(
        _validate_duplicate_case(case, index=index)
        for index, case in enumerate(raw_cases, start=1)
    )
    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise SemanticCampaignError("Duplicate calibration case IDs must be unique.")
    return DuplicateCorpus(
        path=fixture_path,
        digest=hashlib.sha256(raw_bytes).hexdigest(),
        schema_version=1,
        ruleset_version=ruleset,
        cases=cases,
    )


def _sha256_text(value: object, field: str) -> str:
    text = _nonempty_string(value, field)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise SemanticCampaignError(f"Ambiguity holdout lock {field} is invalid.")
    return text


def load_ambiguity_holdout_lock(
    path: Path | None = None,
) -> AmbiguityHoldoutLock:
    """Load the strict holdout lock without opening either scored fixture."""
    lock_path = path or DEFAULT_AMBIGUITY_HOLDOUT_LOCK
    try:
        value = json.loads(
            lock_path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_json_object,
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise SemanticCampaignError(
            "The ambiguity holdout lock is not valid strict UTF-8 JSON."
        ) from error
    required = {
        "kind",
        "schema_version",
        "operation",
        "corpus_role",
        "fixture",
        "fixture_sha256",
        "case_count",
        "calibration_fixture",
        "calibration_sha256",
        "frozen_at",
        "first_evaluation_must_use_frozen_pipeline",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise SemanticCampaignError("The ambiguity holdout lock contract is invalid.")
    if (
        value["kind"] != "memcommit.semantic-eval.corpus-lock"
        or value["schema_version"] != 1
        or value["operation"] != "find-ambiguities"
        or value["corpus_role"] != HOLDOUT_CORPUS_ROLE
        or value["first_evaluation_must_use_frozen_pipeline"] is not True
    ):
        raise SemanticCampaignError("The ambiguity holdout lock identity is invalid.")
    case_count = value["case_count"]
    if not isinstance(case_count, int) or isinstance(case_count, bool) or case_count < 1:
        raise SemanticCampaignError("The ambiguity holdout lock case count is invalid.")
    return AmbiguityHoldoutLock(
        path=lock_path,
        fixture=_nonempty_string(value["fixture"], "lock fixture"),
        fixture_digest=_sha256_text(value["fixture_sha256"], "fixture_sha256"),
        case_count=case_count,
        calibration_fixture=_nonempty_string(
            value["calibration_fixture"],
            "lock calibration_fixture",
        ),
        calibration_digest=_sha256_text(
            value["calibration_sha256"],
            "calibration_sha256",
        ),
        frozen_at=_nonempty_string(value["frozen_at"], "lock frozen_at"),
    )


def _validate_frozen_holdout(
    holdout: AmbiguityCorpus,
    calibration: AmbiguityCorpus,
    lock: AmbiguityHoldoutLock,
) -> None:
    if (
        holdout.path.name != lock.fixture
        or holdout.digest != lock.fixture_digest
        or len(holdout.cases) != lock.case_count
        or calibration.path.name != lock.calibration_fixture
        or calibration.digest != lock.calibration_digest
    ):
        raise SemanticCampaignError(
            "The ambiguity holdout or its calibration source no longer matches "
            "the frozen lock."
        )
    holdout_ids = {str(case["id"]) for case in holdout.cases}
    calibration_ids = {str(case["id"]) for case in calibration.cases}
    holdout_uids = {
        str(case["memory"]["uid"])  # type: ignore[index]
        for case in holdout.cases
    }
    calibration_uids = {
        str(case["memory"]["uid"])  # type: ignore[index]
        for case in calibration.cases
    }
    if holdout_ids & calibration_ids or holdout_uids & calibration_uids:
        raise SemanticCampaignError(
            "The frozen ambiguity holdout overlaps its calibration source."
        )


def _calibration_projection(
    case: Mapping[str, object],
    *,
    include_evidence: bool = False,
) -> dict[str, object]:
    expected = case["expected"]
    assert isinstance(expected, Mapping)
    expected_projection: dict[str, object] = {
        "interpretation": expected["interpretation"],
        "clarification": expected["clarification"],
    }
    if include_evidence:
        expected_projection["ordinary_readings"] = expected["ordinary_readings"]
        expected_projection["question"] = expected["question"]
    return {
        "id": case["id"],
        "scenario": case["scenario"],
        "memory": case["memory"],
        "expected": expected_projection,
    }


def _duplicate_calibration_projection(
    case: Mapping[str, object],
) -> dict[str, object]:
    expected = case["expected"]
    assert isinstance(expected, Mapping)
    return {
        "id": case["id"],
        "scenario": case["scenario"],
        "memories": case["memories"],
        "expected": {"relation": expected["relation"]},
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_id(started: datetime) -> str:
    stamp = started.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def _ensure_ledger_directory(ledger_dir: Path) -> Path:
    if ledger_dir.is_symlink():
        raise SemanticCampaignError("Semantic ledger directory cannot be a symlink.")
    ledger_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = ledger_dir / "runs"
    if runs_dir.is_symlink():
        raise SemanticCampaignError("Semantic ledger runs directory cannot be a symlink.")
    runs_dir.mkdir(exist_ok=True)
    if not runs_dir.is_dir():
        raise SemanticCampaignError("Semantic ledger runs path is not a directory.")
    return runs_dir


def _atomic_write_json(path: Path, value: Mapping[str, object]) -> None:
    if path.exists() and path.is_symlink():
        raise SemanticCampaignError("Semantic run ledger cannot be a symlink.")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _identity(provider: SemanticProvider) -> dict[str, object]:
    identity = getattr(provider, "identity", None)
    if isinstance(identity, ProviderIdentity):
        result: dict[str, object] = asdict(identity)
    else:
        result = {
            "provider": "unknown",
            "model": "unknown",
            "model_digest": None,
            "runtime": None,
            "endpoint": None,
            "reasoning_effort": None,
        }
    result["effective_thinking"] = getattr(provider, "thinking", None)
    return result


def _provider_settings(provider: SemanticProvider) -> dict[str, object]:
    return {
        "timeout_seconds": getattr(provider, "timeout", None),
        "context_tokens": getattr(provider, "context_tokens", None),
        "max_output_tokens": getattr(provider, "max_output_tokens", None),
    }


def _completion_metadata(
    provider: SemanticProvider,
    previous: object,
) -> dict[str, object] | None:
    completion = getattr(provider, "last_run", None)
    if completion is previous or not isinstance(completion, CompletionRun):
        return None
    return {
        "operation": completion.operation,
        "prompt_tokens": completion.prompt_tokens,
        "completion_tokens": completion.completion_tokens,
        "upstream_model": completion.upstream_model,
        "upstream_provider": completion.upstream_provider,
    }


def _stage_records(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, AmbiguityStageRun) for item in value
    ):
        raise SemanticCampaignError("Classifier returned invalid stage artifacts.")
    return [asdict(item) for item in value]


def _latency_stats(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    rank = max(1, math.ceil(0.95 * len(ordered)))
    return {
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "p95": ordered[rank - 1],
        "max": ordered[-1],
    }


def _case_results(
    cases: Sequence[Mapping[str, object]],
    attempts: Sequence[Mapping[str, object]],
    runs: int,
) -> list[dict[str, object]]:
    threshold = math.ceil((2 * runs) / 3)
    results: list[dict[str, object]] = []
    for case in cases:
        case_id = case["id"]
        case_attempts = [item for item in attempts if item["case_id"] == case_id]
        structured = [item for item in case_attempts if item["actual"] is not None]
        exact = [item for item in structured if item["failure_category"] is None]
        pairs = Counter(
            (
                str(item["actual"]["interpretation"]),  # type: ignore[index]
                str(item["actual"]["clarification"]),  # type: ignore[index]
            )
            for item in structured
        )
        majority = max(pairs.values(), default=0)
        passed = (
            len(case_attempts) == runs
            and len(structured) == runs
            and len(exact) >= threshold
            and majority >= threshold
        )
        expected = case["expected"]
        assert isinstance(expected, Mapping)
        results.append(
            {
                "case_id": case_id,
                "expected": {
                    "interpretation": expected["interpretation"],
                    "clarification": expected["clarification"],
                },
                "status": "PASS" if passed else "FAIL",
                "attempts": len(case_attempts),
                "structurally_valid": len(structured),
                "exact_matches": len(exact),
                "majority_count": majority,
                "required_count": threshold,
                "stability": majority / runs,
            }
        )
    return results


def _summary(
    cases: Sequence[Mapping[str, object]],
    attempts: Sequence[Mapping[str, object]],
    runs: int,
) -> dict[str, object]:
    case_results = _case_results(cases, attempts, runs)
    failures = Counter(
        str(item["failure_category"])
        for item in attempts
        if item["failure_category"] is not None
    )
    expected_interpretation = Counter()
    expected_clarification = Counter()
    expected_joint = Counter()
    pass_by_interpretation: dict[str, dict[str, int]] = {
        label: {"passed": 0, "total": 0} for label in _INTERPRETATIONS
    }
    pass_by_clarification: dict[str, dict[str, int]] = {
        label: {"passed": 0, "total": 0} for label in _CLARIFICATIONS
    }
    for result in case_results:
        expected = result["expected"]
        assert isinstance(expected, Mapping)
        interpretation = str(expected["interpretation"])
        clarification = str(expected["clarification"])
        expected_interpretation[interpretation] += 1
        expected_clarification[clarification] += 1
        expected_joint[f"{interpretation}/{clarification}"] += 1
        pass_by_interpretation[interpretation]["total"] += 1
        pass_by_clarification[clarification]["total"] += 1
        if result["status"] == "PASS":
            pass_by_interpretation[interpretation]["passed"] += 1
            pass_by_clarification[clarification]["passed"] += 1
    actual_joint = Counter(
        f"{item['actual']['interpretation']}/{item['actual']['clarification']}"  # type: ignore[index]
        for item in attempts
        if item["actual"] is not None
    )
    completion_values = [float(item["completion_seconds"]) for item in attempts]
    stage_values: dict[str, list[float]] = {}
    prompt_tokens = 0
    completion_tokens = 0
    reported_attempts = 0
    reported_calls = 0
    for item in attempts:
        stages = item.get("stage_runs")
        stage_metadata = (
            [stage for stage in stages if isinstance(stage, Mapping)]
            if isinstance(stages, list)
            else []
        )
        if stage_metadata:
            attempt_reported = False
            for stage in stage_metadata:
                stage_name = stage.get("stage")
                stage_seconds = stage.get("completion_seconds")
                if isinstance(stage_name, str) and isinstance(
                    stage_seconds, (int, float)
                ):
                    stage_values.setdefault(stage_name, []).append(
                        float(stage_seconds)
                    )
                stage_reported = False
                if isinstance(stage.get("prompt_tokens"), int):
                    prompt_tokens += int(stage["prompt_tokens"])
                    stage_reported = True
                if isinstance(stage.get("completion_tokens"), int):
                    completion_tokens += int(stage["completion_tokens"])
                    stage_reported = True
                if stage_reported:
                    reported_calls += 1
                    attempt_reported = True
            if attempt_reported:
                reported_attempts += 1
            continue
        metadata = item.get("provider_run")
        if not isinstance(metadata, Mapping):
            continue
        attempt_reported = False
        if isinstance(metadata.get("prompt_tokens"), int):
            prompt_tokens += int(metadata["prompt_tokens"])
            attempt_reported = True
        if isinstance(metadata.get("completion_tokens"), int):
            completion_tokens += int(metadata["completion_tokens"])
            attempt_reported = True
        if attempt_reported:
            reported_attempts += 1
            reported_calls += 1
    passed_cases = sum(item["status"] == "PASS" for item in case_results)
    return {
        "campaign_passed": passed_cases == len(case_results) and bool(case_results),
        "cases": {
            "passed": passed_cases,
            "failed": len(case_results) - passed_cases,
            "total": len(case_results),
        },
        "attempts": {
            "exact_matches": sum(item["failure_category"] is None for item in attempts),
            "structurally_valid": sum(item["actual"] is not None for item in attempts),
            "total": len(attempts),
        },
        "case_results": case_results,
        "failures": dict(sorted(failures.items())),
        "distributions": {
            "expected_interpretation": dict(expected_interpretation),
            "expected_clarification": dict(expected_clarification),
            "expected_joint": dict(expected_joint),
            "actual_joint_attempts": dict(actual_joint),
            "case_pass_by_interpretation": pass_by_interpretation,
            "case_pass_by_clarification": pass_by_clarification,
        },
        "completion_seconds": _latency_stats(completion_values),
        "stage_completion_seconds": {
            stage: _latency_stats(values)
            for stage, values in sorted(stage_values.items())
        },
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "reported_attempts": reported_attempts,
            "reported_calls": reported_calls,
        },
    }


def _duplicate_case_results(
    cases: Sequence[Mapping[str, object]],
    attempts: Sequence[Mapping[str, object]],
    runs: int,
) -> list[dict[str, object]]:
    threshold = math.ceil((2 * runs) / 3)
    results: list[dict[str, object]] = []
    for case in cases:
        case_id = case["id"]
        case_attempts = [item for item in attempts if item["case_id"] == case_id]
        structured = [item for item in case_attempts if item["actual"] is not None]
        exact = [item for item in structured if item["failure_category"] is None]
        relations = Counter(
            str(item["actual"]["relation"])  # type: ignore[index]
            for item in structured
        )
        majority = max(relations.values(), default=0)
        expected = case["expected"]
        assert isinstance(expected, Mapping)
        passed = (
            len(case_attempts) == runs
            and len(structured) == runs
            and len(exact) >= threshold
            and majority >= threshold
        )
        results.append(
            {
                "case_id": case_id,
                "expected": {"relation": expected["relation"]},
                "status": "PASS" if passed else "FAIL",
                "attempts": len(case_attempts),
                "structurally_valid": len(structured),
                "exact_matches": len(exact),
                "majority_count": majority,
                "required_count": threshold,
                "stability": majority / runs,
            }
        )
    return results


def _duplicate_summary(
    cases: Sequence[Mapping[str, object]],
    attempts: Sequence[Mapping[str, object]],
    runs: int,
) -> dict[str, object]:
    case_results = _duplicate_case_results(cases, attempts, runs)
    failures = Counter(
        str(item["failure_category"])
        for item in attempts
        if item["failure_category"] is not None
    )
    expected_relations = Counter()
    for case in cases:
        expected = case["expected"]
        assert isinstance(expected, Mapping)
        expected_relations[str(expected["relation"])] += 1
    actual_relations = Counter(
        str(item["actual"]["relation"])  # type: ignore[index]
        for item in attempts
        if item["actual"] is not None
    )
    completion_values = [float(item["completion_seconds"]) for item in attempts]
    stage_values: dict[str, list[float]] = {}
    prompt_tokens = 0
    completion_tokens = 0
    reported_attempts = 0
    for item in attempts:
        stage = item.get("stage")
        seconds = item.get("completion_seconds")
        if isinstance(stage, str) and isinstance(seconds, (int, float)):
            stage_values.setdefault(stage, []).append(float(seconds))
        metadata = item.get("provider_run")
        if not isinstance(metadata, Mapping):
            continue
        reported = False
        if isinstance(metadata.get("prompt_tokens"), int):
            prompt_tokens += int(metadata["prompt_tokens"])
            reported = True
        if isinstance(metadata.get("completion_tokens"), int):
            completion_tokens += int(metadata["completion_tokens"])
            reported = True
        if reported:
            reported_attempts += 1
    passed_cases = sum(item["status"] == "PASS" for item in case_results)
    return {
        "campaign_passed": passed_cases == len(case_results) and bool(case_results),
        "cases": {
            "passed": passed_cases,
            "failed": len(case_results) - passed_cases,
            "total": len(case_results),
        },
        "attempts": {
            "exact_matches": sum(item["failure_category"] is None for item in attempts),
            "structurally_valid": sum(item["actual"] is not None for item in attempts),
            "total": len(attempts),
        },
        "case_results": case_results,
        "failures": dict(sorted(failures.items())),
        "distributions": {
            "expected_relation": dict(expected_relations),
            "actual_relation_attempts": dict(actual_relations),
        },
        "completion_seconds": _latency_stats(completion_values),
        "stage_completion_seconds": {
            stage: _latency_stats(values)
            for stage, values in sorted(stage_values.items())
        },
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "reported_attempts": reported_attempts,
            "reported_calls": reported_attempts,
        },
    }


def _safe_diagnostic(error: BaseException) -> str:
    if isinstance(
        error,
        (AmbiguityPipelineError, DuplicatePipelineError, QueryProviderError),
    ):
        return str(error)
    return "A configured campaign dependency returned a known failure."


def _provider_failure_category(error: QueryProviderError) -> str:
    message = str(error).lower()
    if "timed out" in message:
        return "TIMEOUT"
    if "returned no answer" in message or "exhausted its output budget" in message:
        return "EMPTY_OR_TRUNCATED"
    return "PROVIDER"


def run_ambiguity_campaign(
    provider: SemanticProvider,
    *,
    ledger_dir: Path,
    provider_connection_seconds: float,
    runs: int = 3,
    pipeline: str = "v2",
    corpus_role: str = "calibration",
    fixture_path: Path | None = None,
    calibration_fixture_path: Path | None = None,
    holdout_lock_path: Path | None = None,
    classifier: Callable[..., object] | None = None,
    known_error_types: tuple[type[BaseException], ...] = (),
    case_ids: Sequence[str] | None = None,
    progress_fn: Callable[[dict[str, object]], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
    utcnow: Callable[[], datetime] = _utc_now,
) -> dict[str, object]:
    """Run one frozen ambiguity corpus and persist after every attempt."""
    if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
        raise SemanticCampaignError("Campaign runs must be a positive integer.")
    selected_pipeline = pipeline.strip().lower() if isinstance(pipeline, str) else ""
    if selected_pipeline not in PIPELINE_CHOICES:
        raise SemanticCampaignError(
            "Ambiguity pipeline must be one of: " + ", ".join(PIPELINE_CHOICES)
        )
    selected_corpus_role = (
        corpus_role.strip().lower() if isinstance(corpus_role, str) else ""
    )
    if selected_corpus_role not in CORPUS_CHOICES:
        raise SemanticCampaignError(
            "Ambiguity corpus must be one of: " + ", ".join(CORPUS_CHOICES)
        )
    pipeline_id = {
        "v1": AMBIGUITY_PIPELINE_V1,
        "v2": AMBIGUITY_PIPELINE_V2,
        "v3": AMBIGUITY_PIPELINE_V3,
        "v4": AMBIGUITY_PIPELINE_V4,
        "v5": AMBIGUITY_PIPELINE_V5,
        "v6": AMBIGUITY_PIPELINE_V6,
    }[selected_pipeline]
    pipeline_version = {
        "v1": 1,
        "v2": 2,
        "v3": 3,
        "v4": 4,
        "v5": 5,
        "v6": 6,
    }[
        selected_pipeline
    ]
    if (
        not isinstance(provider_connection_seconds, (int, float))
        or isinstance(provider_connection_seconds, bool)
        or provider_connection_seconds < 0
        or not math.isfinite(provider_connection_seconds)
    ):
        raise SemanticCampaignError("Provider connection time must be finite and nonnegative.")
    if any(not isinstance(item, type) or not issubclass(item, BaseException) for item in known_error_types):
        raise SemanticCampaignError("Known campaign error types are invalid.")
    campaign_started = clock()
    if selected_corpus_role == "holdout":
        corpus = load_ambiguity_corpus(
            fixture_path or DEFAULT_AMBIGUITY_HOLDOUT_FIXTURE
        )
        calibration_corpus = load_ambiguity_corpus(
            calibration_fixture_path or DEFAULT_AMBIGUITY_FIXTURE
        )
        holdout_lock = load_ambiguity_holdout_lock(holdout_lock_path)
        _validate_frozen_holdout(corpus, calibration_corpus, holdout_lock)
        retained_role = HOLDOUT_CORPUS_ROLE
        calibration_mode = HOLDOUT_CALIBRATION_MODE
        independent_holdout = True
    else:
        corpus = load_ambiguity_corpus(fixture_path)
        calibration_corpus = corpus
        holdout_lock = None
        retained_role = CALIBRATION_CORPUS_ROLE
        calibration_mode = CALIBRATION_MODE
        independent_holdout = False
    available = {str(case["id"]): case for case in corpus.cases}
    if case_ids is None:
        selected = list(corpus.cases)
    else:
        requested = list(case_ids)
        if any(not isinstance(case_id, str) or not case_id for case_id in requested):
            raise SemanticCampaignError("Campaign case IDs must be non-empty strings.")
        if len(requested) != len(set(requested)):
            raise SemanticCampaignError("Campaign case IDs cannot be repeated.")
        unknown = [case_id for case_id in requested if case_id not in available]
        if unknown:
            raise SemanticCampaignError(
                "Unknown ambiguity campaign case(s): " + ", ".join(unknown)
            )
        requested_set = set(requested)
        selected = [case for case in corpus.cases if case["id"] in requested_set]
        if not selected:
            raise SemanticCampaignError("At least one ambiguity case is required.")

    runs_dir = _ensure_ledger_directory(ledger_dir)
    started = utcnow()
    campaign_id = _run_id(started)
    ledger_path = runs_dir / f"{campaign_id}.json"
    runner = classifier or {
        "v1": classify_ambiguity_case_v1,
        "v2": classify_ambiguity_case,
        "v3": classify_ambiguity_case_v3,
        "v4": classify_ambiguity_case_v4,
        "v5": classify_ambiguity_case_v5,
        "v6": classify_ambiguity_case_v6,
    }[selected_pipeline]
    ledger: dict[str, object] = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "kind": LEDGER_KIND,
        "run_id": campaign_id,
        "status": "RUNNING",
        "started_at": _timestamp(started),
        "completed_at": None,
        "ledger_path": str(ledger_path),
        "corpus": {
            "operation": "find-ambiguities",
            "role": retained_role,
            "calibration_mode": calibration_mode,
            "independent_holdout": independent_holdout,
            "fixture": corpus.path.name,
            "fixture_digest": corpus.digest,
            "schema_version": corpus.schema_version,
            "ruleset_version": corpus.ruleset_version,
            "fixture_case_count": len(corpus.cases),
            "selected_case_ids": [case["id"] for case in selected],
            "calibration_fixture": calibration_corpus.path.name,
            "calibration_fixture_digest": calibration_corpus.digest,
            "calibration_case_count": len(calibration_corpus.cases),
            "holdout_lock": (
                holdout_lock.path.name if holdout_lock is not None else None
            ),
            "holdout_frozen_at": (
                holdout_lock.frozen_at if holdout_lock is not None else None
            ),
        },
        "pipeline": {
            "id": pipeline_id,
            "version": pipeline_version,
            "stages": (
                [
                    "MULTIPLE_READINGS",
                    "CLEAR_LEADER",
                    "PRACTICAL_IMPROVEMENT",
                    "CAN_PROCEED",
                    "PROJECT_LABELS",
                ]
                if selected_pipeline == "v3"
                else (
                    ["READING_CENSUS", "CLARIFICATION_CENSUS", "PROJECT_LABELS"]
                    if selected_pipeline in {"v4", "v5", "v6"}
                    else ["CLASSIFY"]
                )
            ),
            "gate": "exact two-label contract with repeated stability",
        },
        "provider": _identity(provider),
        "settings": {
            "runs_per_case": runs,
            "provider": _provider_settings(provider),
            "temperature": 0,
            "ttft": "NOT_AVAILABLE_NONSTREAMING",
        },
        "timing": {
            "provider_connection_seconds": provider_connection_seconds,
            "campaign_seconds": None,
            "total_seconds": None,
        },
        "attempts": [],
        "summary": _summary(selected, [], runs),
    }
    _atomic_write_json(ledger_path, ledger)

    attempts = ledger["attempts"]
    assert isinstance(attempts, list)
    try:
        for case in selected:
            calibration_items = (
                [
                    item
                    for item in calibration_corpus.cases
                    if item["id"] != case["id"]
                ]
                if retained_role == CALIBRATION_CORPUS_ROLE
                else list(calibration_corpus.cases)
            )
            calibration = [
                _calibration_projection(
                    item,
                    include_evidence=selected_pipeline in {"v4", "v5", "v6"},
                )
                for item in calibration_items
            ]
            expected_contract = case["expected"]
            assert isinstance(expected_contract, Mapping)
            expected = {
                "interpretation": expected_contract["interpretation"],
                "clarification": expected_contract["clarification"],
            }
            for repetition in range(1, runs + 1):
                attempt_started = clock()
                previous_run = getattr(provider, "last_run", None)
                actual: dict[str, object] | None = None
                raw_response: str | None = None
                prompt_digest: str | None = None
                schema_digest: str | None = None
                response_digest: str | None = None
                stage_runs: list[dict[str, object]] = []
                failure_category: str | None = None
                diagnostic: str | None = None
                error_type: str | None = None
                unexpected: BaseException | None = None
                try:
                    result = runner(
                        case,
                        provider,
                        calibration_examples=calibration,
                    )
                    observed_pipeline = getattr(result, "pipeline_id", pipeline_id)
                    observed_version = getattr(
                        result,
                        "pipeline_version",
                        pipeline_version,
                    )
                    if (
                        observed_pipeline != pipeline_id
                        or observed_version != pipeline_version
                    ):
                        raise SemanticCampaignError(
                            "Classifier result does not match the frozen pipeline."
                        )
                    classification = getattr(result, "classification")
                    actual = {
                        "interpretation": getattr(classification, "interpretation"),
                        "clarification": getattr(classification, "clarification"),
                    }
                    raw_response = getattr(result, "raw_response")
                    prompt_digest = getattr(result, "prompt_digest")
                    schema_digest = getattr(result, "schema_digest")
                    response_digest = getattr(result, "response_digest")
                    stage_runs = _stage_records(getattr(result, "stage_runs", ()))
                    if actual != expected:
                        failure_category = "LABEL_MISMATCH"
                        diagnostic = (
                            "Both labels must exactly match the reviewed corpus contract."
                        )
                except AmbiguityPipelineError as error:
                    failure_category = error.category
                    diagnostic = _safe_diagnostic(error)
                    error_type = type(error).__name__
                    raw_response = error.raw_response
                    prompt_digest = error.prompt_digest
                    schema_digest = error.schema_digest
                    response_digest = error.response_digest
                    stage_runs = _stage_records(error.stage_runs)
                except QueryProviderError as error:
                    failure_category = _provider_failure_category(error)
                    diagnostic = _safe_diagnostic(error)
                    error_type = type(error).__name__
                except known_error_types as error:
                    failure_category = "PROVIDER"
                    diagnostic = _safe_diagnostic(error)
                    error_type = type(error).__name__
                except BaseException as error:
                    failure_category = "INTERNAL"
                    diagnostic = "The host campaign aborted on an unexpected internal failure."
                    error_type = type(error).__name__
                    unexpected = error
                completion_seconds = max(0.0, clock() - attempt_started)
                attempt = {
                    "ordinal": len(attempts) + 1,
                    "case_id": case["id"],
                    "repetition": repetition,
                    "stage": "CLASSIFY",
                    "status": "PASS" if failure_category is None else "FAIL",
                    "failure_category": failure_category,
                    "diagnostic": diagnostic,
                    "error_type": error_type,
                    "expected": expected,
                    "actual": actual,
                    "completion_seconds": completion_seconds,
                    "prompt_digest": prompt_digest,
                    "schema_digest": schema_digest,
                    "response_digest": response_digest,
                    "stage_runs": stage_runs,
                    # Both current corpora contain public repository fixtures.
                    # Future user-data campaigns must choose a stricter retention
                    # policy before reusing raw responses.
                    "raw_response": raw_response,
                    "response_bytes": (
                        len(raw_response.encode("utf-8"))
                        if raw_response is not None
                        else None
                    ),
                    "provider_run": _completion_metadata(provider, previous_run),
                }
                attempts.append(attempt)
                ledger["summary"] = _summary(selected, attempts, runs)
                _atomic_write_json(ledger_path, ledger)
                if progress_fn is not None:
                    progress_event = dict(attempt)
                    progress_event["index"] = attempt["ordinal"]
                    progress_event["total"] = len(selected) * runs
                    progress_fn(progress_event)
                if unexpected is not None:
                    raise unexpected
    except BaseException:
        campaign_seconds = max(0.0, clock() - campaign_started)
        ledger["status"] = "ABORTED"
        ledger["completed_at"] = _timestamp(utcnow())
        ledger["timing"] = {
            "provider_connection_seconds": provider_connection_seconds,
            "campaign_seconds": campaign_seconds,
            "total_seconds": provider_connection_seconds + campaign_seconds,
        }
        ledger["summary"] = _summary(selected, attempts, runs)
        _atomic_write_json(ledger_path, ledger)
        raise

    campaign_seconds = max(0.0, clock() - campaign_started)
    ledger["status"] = "COMPLETED"
    ledger["completed_at"] = _timestamp(utcnow())
    ledger["timing"] = {
        "provider_connection_seconds": provider_connection_seconds,
        "campaign_seconds": campaign_seconds,
        "total_seconds": provider_connection_seconds + campaign_seconds,
    }
    ledger["summary"] = _summary(selected, attempts, runs)
    _atomic_write_json(ledger_path, ledger)
    return ledger


def run_duplicate_campaign(
    provider: SemanticProvider,
    *,
    ledger_dir: Path,
    provider_connection_seconds: float,
    runs: int = 3,
    fixture_path: Path | None = None,
    classifier: Callable[..., object] | None = None,
    known_error_types: tuple[type[BaseException], ...] = (),
    case_ids: Sequence[str] | None = None,
    progress_fn: Callable[[dict[str, object]], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
    utcnow: Callable[[], datetime] = _utc_now,
) -> dict[str, object]:
    """Run the host-first duplicate relation calibration campaign."""
    if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
        raise SemanticCampaignError("Campaign runs must be a positive integer.")
    if (
        not isinstance(provider_connection_seconds, (int, float))
        or isinstance(provider_connection_seconds, bool)
        or provider_connection_seconds < 0
        or not math.isfinite(provider_connection_seconds)
    ):
        raise SemanticCampaignError(
            "Provider connection time must be finite and nonnegative."
        )
    if any(
        not isinstance(item, type) or not issubclass(item, BaseException)
        for item in known_error_types
    ):
        raise SemanticCampaignError("Known campaign error types are invalid.")
    campaign_started = clock()
    corpus = load_duplicate_corpus(fixture_path)
    available = {str(case["id"]): case for case in corpus.cases}
    if case_ids is None:
        selected = list(corpus.cases)
    else:
        requested = list(case_ids)
        if any(not isinstance(case_id, str) or not case_id for case_id in requested):
            raise SemanticCampaignError("Campaign case IDs must be non-empty strings.")
        if len(requested) != len(set(requested)):
            raise SemanticCampaignError("Campaign case IDs cannot be repeated.")
        unknown = [case_id for case_id in requested if case_id not in available]
        if unknown:
            raise SemanticCampaignError(
                "Unknown duplicate campaign case(s): " + ", ".join(unknown)
            )
        requested_set = set(requested)
        selected = [case for case in corpus.cases if case["id"] in requested_set]
        if not selected:
            raise SemanticCampaignError("At least one duplicate case is required.")

    runs_dir = _ensure_ledger_directory(ledger_dir)
    started = utcnow()
    campaign_id = _run_id(started)
    ledger_path = runs_dir / f"{campaign_id}.json"
    runner = classifier or classify_duplicate_case
    ledger: dict[str, object] = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "kind": LEDGER_KIND,
        "run_id": campaign_id,
        "status": "RUNNING",
        "started_at": _timestamp(started),
        "completed_at": None,
        "ledger_path": str(ledger_path),
        "corpus": {
            "operation": "find-duplicates",
            "role": CALIBRATION_CORPUS_ROLE,
            "calibration_mode": CALIBRATION_MODE,
            "independent_holdout": False,
            "fixture": corpus.path.name,
            "fixture_digest": corpus.digest,
            "schema_version": corpus.schema_version,
            "ruleset_version": corpus.ruleset_version,
            "fixture_case_count": len(corpus.cases),
            "selected_case_ids": [case["id"] for case in selected],
        },
        "pipeline": {
            "id": DUPLICATE_PIPELINE_V1,
            "version": 1,
            "stages": [
                "HOST_EXACT",
                "HOST_SURFACE_EQUIVALENT",
                "SEMANTIC_RELATION",
            ],
            "gate": "exact relation contract with repeated stability",
        },
        "provider": _identity(provider),
        "settings": {
            "runs_per_case": runs,
            "provider": _provider_settings(provider),
            "temperature": 0,
            "ttft": "NOT_AVAILABLE_NONSTREAMING",
        },
        "timing": {
            "provider_connection_seconds": provider_connection_seconds,
            "campaign_seconds": None,
            "total_seconds": None,
        },
        "attempts": [],
        "summary": _duplicate_summary(selected, [], runs),
    }
    _atomic_write_json(ledger_path, ledger)

    attempts = ledger["attempts"]
    assert isinstance(attempts, list)
    try:
        for case in selected:
            calibration = [
                _duplicate_calibration_projection(item)
                for item in corpus.cases
                if item["id"] != case["id"]
                and isinstance(item["expected"], Mapping)
                and item["expected"]["relation"] in _SEMANTIC_DUPLICATE_RELATIONS
            ]
            expected_contract = case["expected"]
            assert isinstance(expected_contract, Mapping)
            expected = {"relation": expected_contract["relation"]}
            for repetition in range(1, runs + 1):
                attempt_started = clock()
                previous_run = getattr(provider, "last_run", None)
                actual: dict[str, object] | None = None
                raw_response: str | None = None
                prompt_digest: str | None = None
                schema_digest: str | None = None
                response_digest: str | None = None
                failure_category: str | None = None
                diagnostic: str | None = None
                error_type: str | None = None
                stage = "SEMANTIC_RELATION"
                unexpected: BaseException | None = None
                try:
                    result = runner(
                        case,
                        provider,
                        calibration_examples=calibration,
                    )
                    if (
                        getattr(result, "pipeline_id", DUPLICATE_PIPELINE_V1)
                        != DUPLICATE_PIPELINE_V1
                        or getattr(result, "pipeline_version", 1) != 1
                    ):
                        raise SemanticCampaignError(
                            "Classifier result does not match the frozen pipeline."
                        )
                    classification = getattr(result, "classification")
                    actual = {"relation": getattr(classification, "relation")}
                    raw_response = getattr(result, "raw_response")
                    prompt_digest = getattr(result, "prompt_digest")
                    schema_digest = getattr(result, "schema_digest")
                    response_digest = getattr(result, "response_digest")
                    stage = getattr(result, "stage", stage)
                    if actual != expected:
                        failure_category = "LABEL_MISMATCH"
                        diagnostic = (
                            "The relation must exactly match the reviewed corpus contract."
                        )
                except DuplicatePipelineError as error:
                    failure_category = error.category
                    diagnostic = _safe_diagnostic(error)
                    error_type = type(error).__name__
                    raw_response = error.raw_response
                    prompt_digest = error.prompt_digest
                    schema_digest = error.schema_digest
                    response_digest = error.response_digest
                    stage = error.stage or stage
                except QueryProviderError as error:
                    failure_category = _provider_failure_category(error)
                    diagnostic = _safe_diagnostic(error)
                    error_type = type(error).__name__
                except known_error_types as error:
                    failure_category = "PROVIDER"
                    diagnostic = _safe_diagnostic(error)
                    error_type = type(error).__name__
                except BaseException as error:
                    failure_category = "INTERNAL"
                    diagnostic = (
                        "The host campaign aborted on an unexpected internal failure."
                    )
                    error_type = type(error).__name__
                    unexpected = error
                completion_seconds = max(0.0, clock() - attempt_started)
                attempt = {
                    "ordinal": len(attempts) + 1,
                    "case_id": case["id"],
                    "repetition": repetition,
                    "stage": stage,
                    "status": "PASS" if failure_category is None else "FAIL",
                    "failure_category": failure_category,
                    "diagnostic": diagnostic,
                    "error_type": error_type,
                    "expected": expected,
                    "actual": actual,
                    "completion_seconds": completion_seconds,
                    "prompt_digest": prompt_digest,
                    "schema_digest": schema_digest,
                    "response_digest": response_digest,
                    "stage_runs": [],
                    "raw_response": raw_response,
                    "response_bytes": (
                        len(raw_response.encode("utf-8"))
                        if raw_response is not None
                        else None
                    ),
                    "provider_run": _completion_metadata(provider, previous_run),
                }
                attempts.append(attempt)
                ledger["summary"] = _duplicate_summary(selected, attempts, runs)
                _atomic_write_json(ledger_path, ledger)
                if progress_fn is not None:
                    progress_event = dict(attempt)
                    progress_event["index"] = attempt["ordinal"]
                    progress_event["total"] = len(selected) * runs
                    progress_fn(progress_event)
                if unexpected is not None:
                    raise unexpected
    except BaseException:
        campaign_seconds = max(0.0, clock() - campaign_started)
        ledger["status"] = "ABORTED"
        ledger["completed_at"] = _timestamp(utcnow())
        ledger["timing"] = {
            "provider_connection_seconds": provider_connection_seconds,
            "campaign_seconds": campaign_seconds,
            "total_seconds": provider_connection_seconds + campaign_seconds,
        }
        ledger["summary"] = _duplicate_summary(selected, attempts, runs)
        _atomic_write_json(ledger_path, ledger)
        raise

    campaign_seconds = max(0.0, clock() - campaign_started)
    ledger["status"] = "COMPLETED"
    ledger["completed_at"] = _timestamp(utcnow())
    ledger["timing"] = {
        "provider_connection_seconds": provider_connection_seconds,
        "campaign_seconds": campaign_seconds,
        "total_seconds": provider_connection_seconds + campaign_seconds,
    }
    ledger["summary"] = _duplicate_summary(selected, attempts, runs)
    _atomic_write_json(ledger_path, ledger)
    return ledger


def load_campaign_ledgers(ledger_dir: Path) -> list[dict[str, object]]:
    """Read completed or partial run snapshots without contacting a provider."""
    runs_dir = ledger_dir / "runs"
    if not runs_dir.exists():
        return []
    if runs_dir.is_symlink() or not runs_dir.is_dir():
        raise SemanticCampaignError("Semantic ledger runs path is invalid.")
    ledgers: list[dict[str, object]] = []
    for path in sorted(runs_dir.iterdir()):
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            raise SemanticCampaignError(
                f"Unexpected semantic ledger entry: {path.name}"
            )
        try:
            value = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_strict_json_object,
            )
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
            raise SemanticCampaignError(
                f"Semantic ledger {path.name} is invalid strict JSON."
            ) from error
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != LEDGER_SCHEMA_VERSION
            or value.get("kind") != LEDGER_KIND
            or value.get("run_id") != path.stem
            or value.get("status") not in {"RUNNING", "COMPLETED", "ABORTED"}
        ):
            raise SemanticCampaignError(
                f"Semantic ledger {path.name} has an unsupported contract."
            )
        value["ledger_path"] = str(path)
        ledgers.append(value)
    return ledgers
