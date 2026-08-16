"""Prepare every declared Study Compare pair through the ordinary contract.

This replaces participant-facing parent projection.  The frozen pair set is
derived once from the Study's declared parent regions, but every selected row
is then analyzed independently by production ``analyze_comparison``.  Pair
outputs are resumable; baseline publication happens only after all rows are
available and validated.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

from memcommit.authority.access import resolve_context_access
from memcommit.commands.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.comparison import ComparisonAnalysis, ComparisonInput
from memcommit.comparison_provider import analyze_comparison
from memcommit.config import Config
from memcommit.eval.study_compare_graph_prewarm import (
    GraphPair,
    TaskGraphPlan,
    build_graph_plan,
)
from memcommit.profile_config import (
    load_profile_registry,
    profile_store_dir,
    study_run_identity,
)
from memcommit.provider_types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
)
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.store import MemoryStore
from memcommit.study_prewarm.compare import (
    _exact_input_matches,
    _projection_orientation,
    _validate_artifact,
    build_compare_prewarm_artifact,
)
from memcommit.study_prewarm.registry import (
    canonical_json,
    load_artifact,
    load_registry,
    publish_artifact,
)


KIND = "STUDY_COMPARE_EXACT_MATRIX"
SCHEMA_VERSION = 1
PAIR_KIND = "STUDY_COMPARE_EXACT_MATRIX_PAIR"
PAIR_SCHEMA_VERSION = 1
DEFAULT_TIMEOUT_SECONDS = 900.0
DEFAULT_WORKERS = 16
DEFAULT_RETRIES = 1
TASKS = ("task-1", "task-2", "task-3")


class StudyCompareExactMatrixError(RuntimeError):
    """The exact matrix plan, provider result, or publication is unsafe."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.write-{threading.get_ident()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _pair_plan_key(pair: GraphPair, *, model: str, reasoning: str) -> str:
    return _sha(
        {
            "kind": PAIR_KIND,
            "schema_version": PAIR_SCHEMA_VERSION,
            "task": pair.task,
            "description_digest": pair.description_digest,
            "left": {"name": pair.left.name, "digest": pair.left.context_digest},
            "right": {
                "name": pair.right.name,
                "digest": pair.right.context_digest,
            },
            "include_descendants": [True, True],
            "provider": CODEX_CHATGPT_PROVIDER,
            "model": model,
            "reasoning": reasoning,
        }
    )


def _comparison_input(pair: GraphPair) -> ComparisonInput:
    return ComparisonInput.from_contexts(
        pair.left.context,
        pair.right.context,
        reference_descendants=True,
        compared_descendants=True,
    )


def declared_exact_plans(
    plans: Sequence[TaskGraphPlan],
    *,
    parents: Sequence[ComparisonAnalysis],
) -> tuple[GraphPair, ...]:
    """Freeze the old declared regions as a finite exact-pair manifest."""

    selected: list[GraphPair] = []
    for plan in plans:
        task_parents = tuple(
            parent
            for parent in parents
            if all(frame.context_name.split("/", 1)[0] == plan.task for frame in parent.frames)
        )
        for pair in plan.pairs:
            # Ordinary Compare rejects an empty side before provider
            # connection. Such graph coordinates are not executable requests
            # and therefore cannot be declared exact prewarm rows.
            if not pair.left.memory_uids or not pair.right.memory_uids:
                continue
            requested = _comparison_input(pair)
            if any(
                _projection_orientation(requested, parent) is not None
                for parent in task_parents
            ):
                selected.append(pair)
    return tuple(selected)


def _existing_exact_artifacts(
    store: MemoryStore,
) -> tuple[tuple[ComparisonAnalysis, dict[str, object]], ...]:
    registry = load_registry(store.store_dir)
    if registry is None:
        return ()
    result: list[tuple[ComparisonAnalysis, dict[str, object]]] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != "COMPARE":
            continue
        artifact = load_artifact(store.store_dir, entry)
        analysis, _ = _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
        result.append((analysis, artifact))
    return tuple(result)


def _pair_output_path(root: Path, pair: GraphPair, *, model: str, reasoning: str) -> Path:
    return root / pair.task / "pairs" / f"{_pair_plan_key(pair, model=model, reasoning=reasoning)}.json"


def _validate_pair_output(
    value: object,
    *,
    pair: GraphPair,
    model: str,
    reasoning: str,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise StudyCompareExactMatrixError("Exact matrix pair output is invalid.")
    key = _pair_plan_key(pair, model=model, reasoning=reasoning)
    if (
        value.get("kind") != PAIR_KIND
        or value.get("schema_version") != PAIR_SCHEMA_VERSION
        or value.get("pair_key") != key
        or value.get("task") != pair.task
        or value.get("state") != "EXACT_PREWARM"
        or not isinstance(value.get("artifact"), dict)
    ):
        raise StudyCompareExactMatrixError("Exact matrix pair output is stale.")
    artifact = value["artifact"]
    analysis, _ = _validate_artifact(
        artifact,
        entry_key=str(artifact.get("key")),
        entry_task=pair.task,
    )
    if not _exact_input_matches(analysis, _comparison_input(pair)):
        raise StudyCompareExactMatrixError(
            "Exact matrix pair does not match its frozen inputs."
        )
    return value


def _run_pair(
    pair: GraphPair,
    *,
    description,
    model: str,
    reasoning: str,
    timeout: float,
) -> dict[str, object]:
    provider = CodexChatGPTProvider.connect(
        timeout=timeout,
        model=model,
        reasoning_effort=reasoning,
    )
    started = time.monotonic()
    analysis = analyze_comparison(_comparison_input(pair), provider)
    provider_seconds = max(0.0, time.monotonic() - started)
    key, artifact = build_compare_prewarm_artifact(
        task=pair.task,
        task_description=description,
        analysis=analysis,
        provider=CODEX_CHATGPT_PROVIDER,
        model=model,
        reasoning=reasoning,
        offline_provider_seconds=provider_seconds,
    )
    return {
        "kind": PAIR_KIND,
        "schema_version": PAIR_SCHEMA_VERSION,
        "pair_key": _pair_plan_key(pair, model=model, reasoning=reasoning),
        "created_at": _utc_now(),
        "task": pair.task,
        "state": "EXACT_PREWARM",
        "left": pair.left.name,
        "right": pair.right.name,
        "provider_seconds": provider_seconds,
        "artifact_key": key,
        "artifact": artifact,
    }


def run_exact_matrix(
    *,
    store: MemoryStore,
    plans: Sequence[TaskGraphPlan],
    output_root: Path,
    baseline_profile_name: str,
    model: str,
    reasoning: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    workers: int = DEFAULT_WORKERS,
    retries: int = DEFAULT_RETRIES,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if workers < 1 or retries < 0 or timeout <= 0:
        raise StudyCompareExactMatrixError("Invalid matrix execution settings.")
    profile_registry = load_profile_registry()
    identity = study_run_identity(profile_registry.active)
    if identity is None or identity.role != "PARTICIPANT":
        raise StudyCompareExactMatrixError("Active Profile is not a Study participant.")
    baseline = profile_registry.by_name(baseline_profile_name)
    if baseline is None or baseline.uid != identity.baseline_profile_uid:
        raise StudyCompareExactMatrixError("Study baseline does not match the active run.")
    existing = _existing_exact_artifacts(store)
    parents = tuple(analysis for analysis, _ in existing)
    pairs = declared_exact_plans(plans, parents=parents)
    if len(pairs) != 718:
        raise StudyCompareExactMatrixError(
            f"Frozen exact Compare matrix has {len(pairs)} pairs instead of 718."
        )
    descriptions = {
        plan.task: next(view.context for view in plan.views if view.name == plan.description_name)
        for plan in plans
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _atomic_write(
        output_root / "manifest.json",
        {
            "kind": KIND,
            "schema_version": SCHEMA_VERSION,
            "created_at": _utc_now(),
            "profile_name": profile_registry.active.name,
            "profile_uid": profile_registry.active.uid,
            "baseline_profile_uid": baseline.uid,
            "provider": CODEX_CHATGPT_PROVIDER,
            "model": model,
            "reasoning": reasoning,
            "pair_count": len(pairs),
            "tasks": {
                task: sum(pair.task == task for pair in pairs) for task in TASKS
            },
            "pairs": [
                {
                    "pair_key": _pair_plan_key(pair, model=model, reasoning=reasoning),
                    "task": pair.task,
                    "left": pair.left.name,
                    "right": pair.right.name,
                    "left_count": len(pair.left.memory_uids),
                    "right_count": len(pair.right.memory_uids),
                }
                for pair in pairs
            ],
        },
    )

    outputs: dict[str, dict[str, object]] = {}
    pending: list[GraphPair] = []
    for pair in pairs:
        plan_key = _pair_plan_key(pair, model=model, reasoning=reasoning)
        exact = next(
            (
                artifact
                for analysis, artifact in existing
                if _exact_input_matches(analysis, _comparison_input(pair))
                and artifact.get("provider") == CODEX_CHATGPT_PROVIDER
                and artifact.get("model") == model
                and artifact.get("reasoning") == reasoning
                and isinstance(artifact.get("task_description"), dict)
                and artifact["task_description"].get("context_digest")
                == pair.description_digest
            ),
            None,
        )
        if exact is not None:
            outputs[plan_key] = {
                "kind": PAIR_KIND,
                "schema_version": PAIR_SCHEMA_VERSION,
                "pair_key": plan_key,
                "created_at": _utc_now(),
                "task": pair.task,
                "state": "EXACT_PREWARM",
                "left": pair.left.name,
                "right": pair.right.name,
                "provider_seconds": exact.get("offline_provider_seconds", 0.0),
                "artifact_key": exact["key"],
                "artifact": exact,
                "reused_existing": True,
            }
            continue
        path = _pair_output_path(output_root, pair, model=model, reasoning=reasoning)
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            outputs[plan_key] = _validate_pair_output(
                value,
                pair=pair,
                model=model,
                reasoning=reasoning,
            )
        else:
            pending.append(pair)

    attempts: dict[str, int] = {}
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        running: dict[Future[dict[str, object]], GraphPair] = {}

        def submit(pair: GraphPair) -> None:
            key = _pair_plan_key(pair, model=model, reasoning=reasoning)
            attempts[key] = attempts.get(key, 0) + 1
            running[
                executor.submit(
                    _run_pair,
                    pair,
                    description=descriptions[pair.task],
                    model=model,
                    reasoning=reasoning,
                    timeout=timeout,
                )
            ] = pair

        while pending and len(running) < workers:
            submit(pending.pop(0))
        while running:
            done, _ = wait(tuple(running), return_when=FIRST_COMPLETED)
            for future in done:
                pair = running.pop(future)
                key = _pair_plan_key(pair, model=model, reasoning=reasoning)
                try:
                    value = _validate_pair_output(
                        future.result(),
                        pair=pair,
                        model=model,
                        reasoning=reasoning,
                    )
                    _atomic_write(
                        _pair_output_path(
                            output_root, pair, model=model, reasoning=reasoning
                        ),
                        value,
                    )
                    outputs[key] = value
                    if progress is not None:
                        progress(f"COMPLETE {len(outputs)}/{len(pairs)} {pair.left.name} <> {pair.right.name}")
                except Exception as error:
                    if attempts[key] <= retries:
                        submit(pair)
                    else:
                        failures.append(
                            {
                                "pair_key": key,
                                "left": pair.left.name,
                                "right": pair.right.name,
                                "error": f"{type(error).__name__}: {error}",
                            }
                        )
                while pending and len(running) < workers:
                    submit(pending.pop(0))

    if failures or len(outputs) != len(pairs):
        summary = {
            "kind": KIND + "_SUMMARY",
            "schema_version": SCHEMA_VERSION,
            "created_at": _utc_now(),
            "pair_count": len(pairs),
            "completed_count": len(outputs),
            "failures": failures,
            "published": False,
        }
        _atomic_write(output_root / "summary.json", summary)
        raise StudyCompareExactMatrixError(
            f"Exact Compare matrix has {len(failures)} failed pairs."
        )

    published = 0
    baseline_root = profile_store_dir(baseline)
    existing_keys = {
        entry.key
        for entry in (load_registry(baseline_root).entries if load_registry(baseline_root) else ())
    }
    for value in outputs.values():
        artifact = value["artifact"]
        artifact_key = str(artifact["key"])
        if artifact_key in existing_keys:
            continue
        publish_artifact(
            baseline_root,
            baseline_profile_uid=baseline.uid,
            operation="COMPARE",
            task=str(value["task"]),
            key=artifact_key,
            artifact=artifact,
        )
        existing_keys.add(artifact_key)
        published += 1
    summary = {
        "kind": KIND + "_SUMMARY",
        "schema_version": SCHEMA_VERSION,
        "created_at": _utc_now(),
        "pair_count": len(pairs),
        "completed_count": len(outputs),
        "reused_existing_count": sum(
            bool(value.get("reused_existing")) for value in outputs.values()
        ),
        "published_count": published,
        "provider_seconds": sum(
            float(value.get("provider_seconds", 0.0))
            for value in outputs.values()
            if not value.get("reused_existing")
        ),
        "failures": [],
        "published": True,
    }
    _atomic_write(output_root / "summary.json", summary)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-profile", default="study-baseline")
    parser.add_argument("--model", default=None)
    parser.add_argument("--reasoning", choices=CODEX_REASONING_EFFORTS, default="medium")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--output-root", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = Config()
    model = args.model or config.model_for_provider(CODEX_CHATGPT_PROVIDER)
    if not model:
        print("No Codex model configured; pass --model.", file=sys.stderr)
        return 2
    try:
        registry = load_profile_registry()
        store = MemoryStore(create=False)
        current = store.current_context_name()
        if current is None:
            raise StudyCompareExactMatrixError("Active Study has no current Context.")
        selected = resolve_context_access(
            store,
            current,
            current_name=current,
            required_permission="READ",
            registry=registry,
        )
        catalog = freeze_profile_readable_context_catalog(
            store,
            selected,
            include_query_routes=False,
        )
        plans = build_graph_plan(
            catalog,
            model=model,
            reasoning=args.reasoning,
            tasks=TASKS,
        )
        root = args.output_root or Path("outputs/study-compare-exact-matrix") / (
            f"{registry.active.name}-{model}-{args.reasoning}"
        )
        summary = run_exact_matrix(
            store=store,
            plans=plans,
            output_root=root,
            baseline_profile_name=args.baseline_profile,
            model=model,
            reasoning=args.reasoning,
            timeout=args.timeout,
            workers=args.workers,
            retries=args.retries,
            progress=lambda message: print(message, flush=True),
        )
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"output_root": str(root), **summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
