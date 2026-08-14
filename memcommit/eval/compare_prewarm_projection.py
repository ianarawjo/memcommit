"""Evaluate exact Compare reuse, deletion projection, and a fresh audit.

This runner deliberately leaves production Compare unchanged.  It replays a
retained exhaustive 150+150 response to seed the existing exact ordered-pair
cache, measures foreground cache reuse, projects that primary relation ledger
onto a deterministic 75+150 subset, and spends one new provider call on the
same complete surviving frames.  The fresh result audits the projection; it is
not hidden work required by the foreground cache-hit condition.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
from typing import Protocol
import uuid

import memcommit.store as store_module
from memcommit.commands.comparison_execution import ensure_comparison_analysis
from memcommit.authority.access import ContextAccess
from memcommit.comparison import ComparisonAnalysis, ComparisonInput
from memcommit.comparison_provider import analyze_comparison
from memcommit.comparison_store import save_comparison_analysis
from memcommit.config import Config
from memcommit.context import Context, Memory
from memcommit.eval.compare_latency_ab import build_task2_comparison_input
from memcommit.provider_types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
    CompletionRun,
    ProviderIdentity,
)
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.store import MemoryStore


KIND = "COMPARE_PREWARM_PROJECTION_AUDIT"
SCHEMA_VERSION = 1
BASELINE_CONDITION = "BASELINE_EXHAUSTIVE"
DEFAULT_BASELINE_LEDGER = Path(
    "outputs/compare-latency-ab/"
    "20260810-gpt-5.6-sol-medium-a-then-b.json"
)
DELETION_POLICY = "KEEP_ODD_ONE_BASED_REFERENCE_POSITIONS"
DEFAULT_TIMEOUT_SECONDS = 900.0


class ComparePrewarmProjectionError(RuntimeError):
    """Safe evaluation-only benchmark failure."""


class _Provider(Protocol):
    identity: ProviderIdentity
    last_run: CompletionRun | None

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str: ...


def _json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=pretty,
    )


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_ledger(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ComparePrewarmProjectionError(
            f"Cannot read retained baseline ledger: {path}"
        ) from error
    if not isinstance(value, dict):
        raise ComparePrewarmProjectionError("Retained baseline ledger is invalid.")
    return value


def _retained_baseline_call(ledger: Mapping[str, object]) -> dict[str, object]:
    calls = ledger.get("calls")
    if not isinstance(calls, list):
        raise ComparePrewarmProjectionError("Baseline ledger has no calls.")
    matches = [
        call
        for call in calls
        if isinstance(call, dict)
        and call.get("condition") == BASELINE_CONDITION
        and call.get("contract_valid") is True
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("raw_response"), str):
        raise ComparePrewarmProjectionError(
            "Baseline ledger must contain one valid exhaustive raw response."
        )
    return matches[0]


class _ReplayProvider:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        if operation != "compare_contexts":
            raise ComparePrewarmProjectionError("Unexpected replay operation.")
        self.calls += 1
        return self.response


def replay_retained_baseline(
    ledger: Mapping[str, object],
    comparison_input: ComparisonInput,
) -> tuple[ComparisonAnalysis, dict[str, object]]:
    """Decode retained provider evidence without issuing a provider call."""

    call = _retained_baseline_call(ledger)
    response = call["raw_response"]
    assert isinstance(response, str)
    replay = _ReplayProvider(response)
    started = time.monotonic()
    analysis = analyze_comparison(comparison_input, replay)
    decode_seconds = max(0.0, time.monotonic() - started)
    if replay.calls != 1:
        raise ComparePrewarmProjectionError("Retained response replay was not exact.")
    return analysis, {
        "retained_provider_seconds": call.get("provider_seconds"),
        "retained_response_chars": len(response),
        "retained_response_digest": _sha(response),
        "host_replay_decode_seconds": decode_seconds,
    }


def _context_from_frame(frame) -> Context:
    context = Context(uid=frame.context_uid, name=frame.context_name)
    for memory in frame.memories:
        context.add(Memory(uid=memory.uid, content=memory.content))
    return context


def contexts_from_input(comparison_input: ComparisonInput) -> tuple[Context, Context]:
    return tuple(_context_from_frame(frame) for frame in comparison_input.frames)  # type: ignore[return-value]


def build_deletion_input(
    full_input: ComparisonInput,
) -> ComparisonInput:
    """Keep odd one-based reference rows and the complete compared frame."""

    reference_frame, compared_frame = full_input.frames
    reference = Context(
        uid=reference_frame.context_uid,
        name=reference_frame.context_name,
    )
    for ordinal, memory in enumerate(reference_frame.memories, start=1):
        if ordinal % 2 == 1:
            reference.add(Memory(uid=memory.uid, content=memory.content))
    compared = _context_from_frame(compared_frame)
    result = ComparisonInput.from_contexts(reference, compared)
    expected_reference = (len(reference_frame.memories) + 1) // 2
    if tuple(len(frame.memories) for frame in result.frames) != (
        expected_reference,
        len(compared_frame.memories),
    ):
        raise ComparePrewarmProjectionError("Deletion fixture has the wrong size.")
    return result


def _stable_aliases(
    full_input: ComparisonInput,
) -> dict[tuple[str, str], str]:
    aliases: dict[tuple[str, str], str] = {}
    for side, frame in zip(("a", "b"), full_input.frames, strict=True):
        for ordinal, memory in enumerate(frame.memories, start=1):
            aliases[(frame.context_uid, memory.uid)] = f"{side}{ordinal:03d}"
    return aliases


def _relation_members(
    analysis: ComparisonAnalysis,
    relation,
) -> tuple[tuple[str, str], ...]:
    context_by_frame = {
        frame.uid: frame.context_uid for frame in analysis.frames
    }
    return tuple(
        (context_by_frame[member.frame_uid], member.memory_uid)
        for member in relation.members
    )


def _shape(
    members: Sequence[tuple[str, str]],
    reference_context_uid: str,
) -> tuple[int, int]:
    left = sum(context_uid == reference_context_uid for context_uid, _ in members)
    return left, len(members) - left


def _shape_text(shape: tuple[int, int]) -> str:
    return f"{shape[0]}:{shape[1]}"


def _valid_side_shape(kind: str, shape: tuple[int, int]) -> bool:
    left, right = shape
    if kind == "DISTINCT":
        return (left > 0) != (right > 0)
    return left > 0 and right > 0


def project_primary_relations(
    baseline: ComparisonAnalysis,
    surviving_input: ComparisonInput,
    full_input: ComparisonInput,
) -> dict[str, object]:
    """Project the retained primary partition without claiming completeness."""

    aliases = _stable_aliases(full_input)
    survivors = {
        (frame.context_uid, memory.uid)
        for frame in surviving_input.frames
        for memory in frame.memories
    }
    reference_uid = full_input.frames[0].context_uid
    relations: list[dict[str, object]] = []
    repaired_relations: list[dict[str, object]] = []
    cut_count = 0
    empty_count = 0
    invalid_count = 0
    touched_nm_count = 0
    touched_nm_memberships = 0
    covered: list[str] = []

    for ordinal, relation in enumerate(baseline.relations, start=1):
        original_members = _relation_members(baseline, relation)
        surviving_members = tuple(
            member for member in original_members if member in survivors
        )
        original_shape = _shape(original_members, reference_uid)
        surviving_shape = _shape(surviving_members, reference_uid)
        cut = len(surviving_members) != len(original_members)
        original_nm = original_shape[0] > 1 and original_shape[1] > 1
        if cut:
            cut_count += 1
        if cut and original_nm:
            touched_nm_count += 1
            touched_nm_memberships += len(original_members)
        if not surviving_members:
            empty_count += 1
            continue
        valid = _valid_side_shape(relation.kind, surviving_shape)
        if not valid:
            invalid_count += 1
        member_aliases = sorted(aliases[member] for member in surviving_members)
        covered.extend(member_aliases)
        record = {
            "baseline_relation_ordinal": ordinal,
            "kind": relation.kind,
            "status": relation.status,
            "members": member_aliases,
            "original_shape": _shape_text(original_shape),
            "projected_shape": _shape_text(surviving_shape),
            "cut": cut,
            "original_true_n_m": original_nm,
            "side_shape_valid": valid,
        }
        relations.append(record)
        repaired = {
            "kind": relation.kind if valid else "DISTINCT",
            "members": member_aliases,
        }
        repaired_relations.append(repaired)

    expected_aliases = {aliases[member] for member in survivors}
    duplicates = len(covered) - len(set(covered))
    missing = sorted(expected_aliases - set(covered))
    unknown = sorted(set(covered) - expected_aliases)
    projection_valid = not invalid_count and not duplicates and not missing and not unknown
    return {
        "deletion_policy": DELETION_POLICY,
        "source_count": len(expected_aliases),
        "original_relation_count": len(baseline.relations),
        "projected_relation_count": len(relations),
        "empty_relation_count": empty_count,
        "untouched_relation_count": len(baseline.relations) - cut_count,
        "cut_relation_count": cut_count,
        "invalid_side_shape_count": invalid_count,
        "touched_true_n_m_count": touched_nm_count,
        "touched_true_n_m_original_memberships": touched_nm_memberships,
        "coverage": {
            "expected": len(expected_aliases),
            "observed_unique": len(set(covered)),
            "duplicate_count": duplicates,
            "missing": missing,
            "unknown": unknown,
        },
        "raw_projection_structurally_valid": projection_valid,
        "relations": relations,
        # This makes the partition structurally decodable only.  Turning a
        # one-sided remnant into DISTINCT cannot recover a secondary relation
        # hidden by the old primary partition, so the fresh audit remains
        # semantically necessary.
        "shape_repaired_relations": repaired_relations,
    }


def _timed_repetitions(
    operation: Callable[[], object],
    repetitions: int,
) -> tuple[object, dict[str, object]]:
    if repetitions < 1:
        raise ComparePrewarmProjectionError("Repetitions must be positive.")
    durations: list[float] = []
    result: object = None
    for _ in range(repetitions):
        started = time.monotonic()
        result = operation()
        durations.append(max(0.0, time.monotonic() - started))
    return result, {
        "repetitions": repetitions,
        "seconds": durations,
        "minimum_seconds": min(durations),
        "median_seconds": statistics.median(durations),
        "maximum_seconds": max(durations),
    }


def measure_exact_warm_cache(
    baseline: ComparisonAnalysis,
    full_input: ComparisonInput,
    *,
    repetitions: int = 3,
) -> dict[str, object]:
    """Seed and exercise the production exact ordered-pair cache in isolation."""

    reference, compared = contexts_from_input(full_input)
    old_store_dir = store_module.STORE_DIR
    with tempfile.TemporaryDirectory(prefix="memcommit-compare-warm-") as temporary:
        root = Path(temporary) / ".mem"
        store_module.STORE_DIR = root
        try:
            store = MemoryStore(root=root)
            store.create_context(reference)
            store.create_context(compared)
            seed_started = time.monotonic()
            save_comparison_analysis(
                store,
                baseline,
                expected_analysis_uid=None,
            )
            seed_seconds = max(0.0, time.monotonic() - seed_started)
            reference_access = ContextAccess(
                store=store,
                context_name=reference.name,
                display_name=reference.name,
                attachment_name=None,
                permission="READ",
            )
            compared_access = ContextAccess(
                store=store,
                context_name=compared.name,
                display_name=compared.name,
                attachment_name=None,
                permission="READ",
            )
            analyze_calls = 0

            def forbidden_analyze(_: ComparisonInput) -> ComparisonAnalysis:
                nonlocal analyze_calls
                analyze_calls += 1
                raise AssertionError("Warm exact comparison called the analyzer.")

            def reuse_once():
                result = ensure_comparison_analysis(
                    store=store,
                    reference_access=reference_access,
                    compared_access=compared_access,
                    reference=reference,
                    compared=compared,
                    current_name=reference.name,
                    analyze=forbidden_analyze,
                )
                if not result.reused or result.analysis.uid != baseline.uid:
                    raise ComparePrewarmProjectionError(
                        "Exact warm comparison did not reuse the seeded artifact."
                    )
                return result

            _, timings = _timed_repetitions(reuse_once, repetitions)
        finally:
            store_module.STORE_DIR = old_store_dir
    return {
        "condition": "W0_EXACT_WARM_150_TO_150",
        "source_counts": [
            len(full_input.frames[0].memories),
            len(full_input.frames[1].memories),
        ],
        "seed_host_seconds": seed_seconds,
        "provider_calls": analyze_calls,
        "reused": analyze_calls == 0,
        "analysis_uid": baseline.uid,
        "timing": timings,
    }


class _CaptureProvider:
    def __init__(self, provider: _Provider):
        self._provider = provider
        self.identity = provider.identity
        self.last_run: CompletionRun | None = None
        self.prompt = ""
        self.output_schema: dict[str, object] | None = None
        self.response = ""
        self.provider_seconds = 0.0
        self.calls = 0

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        self.calls += 1
        self.prompt = prompt
        self.output_schema = output_schema
        started = time.monotonic()
        self.response = self._provider.complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )
        self.provider_seconds = max(0.0, time.monotonic() - started)
        self.last_run = self._provider.last_run
        return self.response


def _normalized_analysis(
    analysis: ComparisonAnalysis,
    aliases: Mapping[tuple[str, str], str],
) -> dict[str, object]:
    relations: list[dict[str, object]] = []
    for relation in analysis.relations:
        members = sorted(aliases[member] for member in _relation_members(analysis, relation))
        relations.append({"kind": relation.kind, "members": members})
    relations.sort(key=lambda relation: relation["members"][0])
    return {
        "source_count": sum(len(frame.memories) for frame in analysis.frames),
        "relation_count": len(relations),
        "issue_count": len(analysis.issues),
        "required_issue_count": sum(
            issue.priority == "REQUIRED" for issue in analysis.issues
        ),
        "kind_counts": dict(
            sorted(Counter(relation["kind"] for relation in relations).items())
        ),
        "relations": relations,
        "analysis_digest": _sha(_json(analysis.to_dict())),
    }


def _relation_maps(
    relations: Sequence[Mapping[str, object]],
) -> tuple[dict[str, tuple[str, frozenset[str]]], set[tuple[str, frozenset[str]]]]:
    by_source: dict[str, tuple[str, frozenset[str]]] = {}
    signatures: set[tuple[str, frozenset[str]]] = set()
    for relation in relations:
        kind = relation.get("kind")
        members = relation.get("members")
        if not isinstance(kind, str) or not isinstance(members, list):
            raise ComparePrewarmProjectionError("Invalid normalized relation.")
        member_set = frozenset(str(member) for member in members)
        signature = (kind, member_set)
        signatures.add(signature)
        for member in member_set:
            if member in by_source:
                raise ComparePrewarmProjectionError(
                    "Normalized relation ledger duplicates a source."
                )
            by_source[member] = signature
    return by_source, signatures


def _same_group_pairs(
    by_source: Mapping[str, tuple[str, frozenset[str]]],
) -> set[tuple[str, str]]:
    groups = {signature[1] for signature in by_source.values()}
    return {
        tuple(sorted(pair))
        for members in groups
        for pair in itertools.combinations(members, 2)
    }


def compare_relation_ledgers(
    projected: Sequence[Mapping[str, object]],
    fresh: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    projected_by_source, projected_signatures = _relation_maps(projected)
    fresh_by_source, fresh_signatures = _relation_maps(fresh)
    sources = set(projected_by_source)
    if sources != set(fresh_by_source):
        raise ComparePrewarmProjectionError(
            "Projection and fresh audit do not cover the same sources."
        )
    exact_source = sum(
        projected_by_source[source] == fresh_by_source[source]
        for source in sources
    )
    kind_source = sum(
        projected_by_source[source][0] == fresh_by_source[source][0]
        for source in sources
    )
    projected_pairs = _same_group_pairs(projected_by_source)
    fresh_pairs = _same_group_pairs(fresh_by_source)
    true_positive = len(projected_pairs & fresh_pairs)
    false_positive = len(projected_pairs - fresh_pairs)
    false_negative = len(fresh_pairs - projected_pairs)
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 1.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 1.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "source_count": len(sources),
        "source_kind_agreement": kind_source / len(sources) if sources else 1.0,
        "exact_source_group_and_kind_agreement": (
            exact_source / len(sources) if sources else 1.0
        ),
        "exact_relation_signature_overlap": len(
            projected_signatures & fresh_signatures
        ),
        "projected_relation_signatures": len(projected_signatures),
        "fresh_relation_signatures": len(fresh_signatures),
        "pairwise_same_group": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
    }


def run_fresh_audit(
    provider: _Provider,
    surviving_input: ComparisonInput,
    full_input: ComparisonInput,
) -> tuple[ComparisonAnalysis, dict[str, object]]:
    capture = _CaptureProvider(provider)
    started = time.monotonic()
    analysis = analyze_comparison(surviving_input, capture)
    elapsed = max(0.0, time.monotonic() - started)
    if capture.calls != 1:
        raise ComparePrewarmProjectionError("Fresh audit was not one provider call.")
    aliases = _stable_aliases(full_input)
    normalized = _normalized_analysis(analysis, aliases)
    provider_run = capture.last_run
    return analysis, {
        "condition": "W2_FRESH_WHOLE_CONTEXT_75_TO_150",
        "source_counts": [
            len(surviving_input.frames[0].memories),
            len(surviving_input.frames[1].memories),
        ],
        "provider_calls": capture.calls,
        "provider_seconds": capture.provider_seconds,
        "validation_and_host_seconds": max(0.0, elapsed - capture.provider_seconds),
        "elapsed_seconds": elapsed,
        "prompt_chars": len(capture.prompt),
        "prompt_digest": _sha(capture.prompt),
        "schema_chars": len(_json(capture.output_schema)),
        "schema_digest": _sha(_json(capture.output_schema)),
        "response_chars": len(capture.response),
        "response_digest": _sha(capture.response),
        "raw_response": capture.response,
        "provider_run": asdict(provider_run) if provider_run is not None else None,
        "normalized_analysis": normalized,
    }


def run_experiment(
    provider: _Provider,
    baseline_ledger: Mapping[str, object],
    *,
    warm_repetitions: int = 3,
    projection_repetitions: int = 3,
) -> dict[str, object]:
    full_input = build_task2_comparison_input(language="en")
    baseline, retained = replay_retained_baseline(baseline_ledger, full_input)
    warm = measure_exact_warm_cache(
        baseline,
        full_input,
        repetitions=warm_repetitions,
    )
    surviving_input = build_deletion_input(full_input)
    projected, projection_timing = _timed_repetitions(
        lambda: project_primary_relations(baseline, surviving_input, full_input),
        projection_repetitions,
    )
    assert isinstance(projected, dict)
    projected["condition"] = "W1_PRIMARY_LEDGER_PROJECTION_75_TO_150"
    projected["timing"] = projection_timing
    _, fresh = run_fresh_audit(provider, surviving_input, full_input)
    normalized_fresh = fresh["normalized_analysis"]
    assert isinstance(normalized_fresh, dict)
    fresh_relations = normalized_fresh["relations"]
    assert isinstance(fresh_relations, list)
    raw_relations = [
        {"kind": relation["kind"], "members": relation["members"]}
        for relation in projected["relations"]
    ]
    repaired_relations = projected["shape_repaired_relations"]
    assert isinstance(repaired_relations, list)
    agreement = {
        "raw_projection_vs_fresh": compare_relation_ledgers(
            raw_relations,
            fresh_relations,
        ),
        "shape_repaired_projection_vs_fresh": compare_relation_ledgers(
            repaired_relations,
            fresh_relations,
        ),
    }
    started_at = datetime.now(timezone.utc)
    return {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "run_id": (
            started_at.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
        ),
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "status": "VALID",
        "corpus": {
            "language": "en",
            "full_source_counts": [
                len(full_input.frames[0].memories),
                len(full_input.frames[1].memories),
            ],
            "full_context_uids": [frame.context_uid for frame in full_input.frames],
            "full_context_digests": [
                frame.context_digest for frame in full_input.frames
            ],
            "surviving_source_counts": [
                len(surviving_input.frames[0].memories),
                len(surviving_input.frames[1].memories),
            ],
            "surviving_context_digests": [
                frame.context_digest for frame in surviving_input.frames
            ],
        },
        "experiment": {
            "production_behavior_changed": False,
            "reasoning_axis_changed": False,
            "reasoning_effort": provider.identity.reasoning_effort,
            "full_fixture": "task2-advisor1-vs-task2-advisor2-150-to-150",
            "deletion_policy": DELETION_POLICY,
            "fresh_audit_calls": 1,
            "foreground_and_hidden_work_reported_separately": True,
        },
        "provider": asdict(provider.identity),
        "retained_baseline": retained,
        "conditions": [warm, projected, fresh],
        "agreement": agreement,
    }


def write_ledger(path: Path, record: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as file:
            file.write(_json(record, pretty=True))
            file.write("\n")
    except FileExistsError as error:
        raise ComparePrewarmProjectionError(
            f"Refusing to overwrite existing benchmark ledger: {path}"
        ) from error


def _default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("outputs/compare-latency-ab") / f"{stamp}-medium-prewarm-projection.json"


def _summary(record: Mapping[str, object], output: Path) -> dict[str, object]:
    conditions = record["conditions"]
    assert isinstance(conditions, list)
    warm, projected, fresh = conditions
    assert isinstance(warm, dict) and isinstance(projected, dict) and isinstance(fresh, dict)
    warm_timing = warm["timing"]
    projection_timing = projected["timing"]
    assert isinstance(warm_timing, dict) and isinstance(projection_timing, dict)
    agreement = record["agreement"]
    assert isinstance(agreement, dict)
    repaired = agreement["shape_repaired_projection_vs_fresh"]
    assert isinstance(repaired, dict)
    return {
        "status": record["status"],
        "output": str(output),
        "warm_max_seconds": warm_timing["maximum_seconds"],
        "warm_provider_calls": warm["provider_calls"],
        "projection_max_seconds": projection_timing["maximum_seconds"],
        "projection_invalid_side_shapes": projected["invalid_side_shape_count"],
        "fresh_provider_seconds": fresh["provider_seconds"],
        "fresh_response_chars": fresh["response_chars"],
        "repaired_source_kind_agreement": repaired["source_kind_agreement"],
        "repaired_exact_group_kind_agreement": repaired[
            "exact_source_group_and_kind_agreement"
        ],
        "repaired_pairwise_f1": repaired["pairwise_same_group"]["f1"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure exact warm Compare reuse, a deterministic 75+150 deletion "
            "projection, and one fresh medium whole-Context audit."
        )
    )
    parser.add_argument("--baseline-ledger", type=Path, default=DEFAULT_BASELINE_LEDGER)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--reasoning",
        choices=CODEX_REASONING_EFFORTS,
        default="medium",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--warm-repetitions", type=int, default=3)
    parser.add_argument("--projection-repetitions", type=int, default=3)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.timeout <= 0 or args.warm_repetitions < 1 or args.projection_repetitions < 1:
        print("Timeout and repetition counts must be positive.", file=sys.stderr)
        return 2
    config = Config()
    model = args.model or config.model_for_provider(CODEX_CHATGPT_PROVIDER)
    if not model:
        print("No Codex model configured; pass --model explicitly.", file=sys.stderr)
        return 2
    output = args.output or _default_output_path()
    try:
        baseline_ledger = _read_ledger(args.baseline_ledger)
        provider = CodexChatGPTProvider.connect(
            timeout=args.timeout,
            model=model,
            reasoning_effort=args.reasoning,
        )
        print("START W0 exact warm 150:150", flush=True)
        print("START W1 deletion projection 75:150", flush=True)
        print("START W2 fresh whole-Context audit 75:150", flush=True)
        record = run_experiment(
            provider,
            baseline_ledger,
            warm_repetitions=args.warm_repetitions,
            projection_repetitions=args.projection_repetitions,
        )
        write_ledger(output, record)
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(_json(_summary(record, output), pretty=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
