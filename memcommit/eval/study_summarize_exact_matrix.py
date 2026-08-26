"""Prepare exact direct and recursive Summarize results for every Study Context.

Every nonempty row executes production ``summarize_frame`` once.  Empty rows
are recorded as deterministic coverage and never call a provider.  Per-row
outputs make the run resumable, while baseline publication waits until the
entire frozen manifest validates.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time

from memcommit.authority.access import resolve_context_access
from memcommit.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.config import Config
from memcommit.infrastructure.providers.policy import (
    resolve_codex_evaluation_policy,
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
from memcommit.study_prewarm.registry import (
    load_artifact,
    load_registry,
    publish_artifact,
)
from memcommit.study_prewarm.summarize import (
    _validate_artifact,
    build_summarize_prewarm_artifact,
    summarize_prewarm_key,
)
from memcommit.operations.summarize.model import SummaryFrame, summarize_frame
from memcommit.operations.summarize.application import SummarizeRequest
from memcommit.operations.summarize.runtime import MemoryStoreSummarySourcePort


KIND = "STUDY_SUMMARIZE_EXACT_MATRIX"
SCHEMA_VERSION = 1
ROW_KIND = "STUDY_SUMMARIZE_EXACT_MATRIX_ROW"
ROW_SCHEMA_VERSION = 1
DEFAULT_TIMEOUT_SECONDS = 900.0
DEFAULT_WORKERS = 16
DEFAULT_RETRIES = 1


class StudySummarizeExactMatrixError(RuntimeError):
    """The frozen matrix, provider result, or publication is unsafe."""


@dataclass(frozen=True)
class SummaryPlan:
    task: str
    frame: SummaryFrame


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _task_root(name: str) -> str:
    root = name.split("/", 1)[0]
    if root == "practice":
        return "tutorial"
    if root in {"task-1", "task-2", "task-3"}:
        return root
    raise StudySummarizeExactMatrixError(
        f"Readable Context {name!r} is outside the Study task roots."
    )


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.write-{threading.get_ident()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def collect_exact_plans(
    *,
    store: MemoryStore,
    context_names: Sequence[str],
    current_context_name: str | None,
) -> tuple[SummaryPlan, ...]:
    """Freeze both public command forms against one readable-name snapshot."""

    source_port = MemoryStoreSummarySourcePort(
        store,
        current_name=current_context_name,
    )
    plans: list[SummaryPlan] = []
    for name in context_names:
        for recursive in (False, True):
            frame = source_port.freeze(
                SummarizeRequest(
                    context_locator=name,
                    include_descendants=recursive,
                    follow_embeds=recursive,
                )
            ).frame
            plans.append(SummaryPlan(task=_task_root(name), frame=frame))
    keys = {
        (
            plan.frame.context_name,
            plan.frame.include_descendants,
            plan.frame.follow_embeds,
        )
        for plan in plans
    }
    if len(keys) != len(plans):
        raise StudySummarizeExactMatrixError(
            "Summarize matrix contains duplicate command forms."
        )
    return tuple(plans)


def _row_key(plan: SummaryPlan, *, model: str, reasoning: str) -> str:
    return summarize_prewarm_key(
        task=plan.task,
        frame=plan.frame,
        provider=CODEX_CHATGPT_PROVIDER,
        model=model,
        reasoning=reasoning,
    )


def _row_path(
    output_root: Path,
    plan: SummaryPlan,
    *,
    model: str,
    reasoning: str,
) -> Path:
    return output_root / plan.task / "rows" / f"{_row_key(plan, model=model, reasoning=reasoning)}.json"


def _validate_row(
    value: object,
    *,
    plan: SummaryPlan,
    model: str,
    reasoning: str,
) -> dict[str, object]:
    key = _row_key(plan, model=model, reasoning=reasoning)
    if (
        not isinstance(value, dict)
        or value.get("kind") != ROW_KIND
        or value.get("schema_version") != ROW_SCHEMA_VERSION
        or value.get("row_key") != key
        or value.get("task") != plan.task
        or value.get("context_name") != plan.frame.context_name
        or value.get("include_descendants") != plan.frame.include_descendants
        or value.get("follow_embeds") != plan.frame.follow_embeds
        or value.get("frame_digest") != plan.frame.digest
        or value.get("state") != "EXACT_PREWARM"
        or not isinstance(value.get("artifact"), dict)
    ):
        raise StudySummarizeExactMatrixError("Summarize row output is stale.")
    _validate_artifact(
        value["artifact"],  # type: ignore[arg-type]
        entry_key=key,
        entry_task=plan.task,
    )
    return value


def _run_plan(
    plan: SummaryPlan,
    *,
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
    understanding = summarize_frame(plan.frame, provider)
    provider_seconds = max(0.0, time.monotonic() - started)
    key, artifact = build_summarize_prewarm_artifact(
        task=plan.task,
        frame=plan.frame,
        understanding=understanding,
        provider=CODEX_CHATGPT_PROVIDER,
        model=model,
        reasoning=reasoning,
        offline_provider_seconds=provider_seconds,
    )
    return {
        "kind": ROW_KIND,
        "schema_version": ROW_SCHEMA_VERSION,
        "row_key": key,
        "created_at": _utc_now(),
        "task": plan.task,
        "state": "EXACT_PREWARM",
        "context_name": plan.frame.context_name,
        "include_descendants": plan.frame.include_descendants,
        "follow_embeds": plan.frame.follow_embeds,
        "frame_digest": plan.frame.digest,
        "source_count": len(plan.frame.sources),
        "provider_seconds": provider_seconds,
        "artifact": artifact,
    }


def run_exact_matrix(
    *,
    store: MemoryStore,
    plans: Sequence[SummaryPlan],
    output_root: Path,
    baseline_profile_name: str,
    model: str,
    reasoning: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    workers: int = DEFAULT_WORKERS,
    retries: int = DEFAULT_RETRIES,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if workers < 1 or workers > 64 or retries < 0 or timeout <= 0:
        raise StudySummarizeExactMatrixError("Invalid matrix execution settings.")
    profile_registry = load_profile_registry()
    identity = study_run_identity(profile_registry.active)
    if identity is None or identity.role != "PARTICIPANT":
        raise StudySummarizeExactMatrixError("Active Profile is not a Study participant.")
    baseline = profile_registry.by_name(baseline_profile_name)
    if baseline is None or baseline.uid != identity.baseline_profile_uid:
        raise StudySummarizeExactMatrixError("Study baseline does not match the active run.")
    if len(plans) != 218:
        raise StudySummarizeExactMatrixError(
            f"Frozen Summarize matrix has {len(plans)} rows instead of 218."
        )
    nonempty = tuple(plan for plan in plans if plan.frame.sources)
    empty = tuple(plan for plan in plans if not plan.frame.sources)
    if len(nonempty) != 198 or len(empty) != 20:
        raise StudySummarizeExactMatrixError(
            "Frozen Summarize matrix does not match the audited 198 call / 20 empty split."
        )

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
            "row_count": len(plans),
            "provider_row_count": len(nonempty),
            "deterministic_empty_count": len(empty),
            "rows": [
                {
                    "row_key": _row_key(plan, model=model, reasoning=reasoning),
                    "task": plan.task,
                    "context_name": plan.frame.context_name,
                    "include_descendants": plan.frame.include_descendants,
                    "follow_embeds": plan.frame.follow_embeds,
                    "frame_digest": plan.frame.digest,
                    "source_count": len(plan.frame.sources),
                    "state": "CALL" if plan.frame.sources else "DETERMINISTIC_EMPTY",
                }
                for plan in plans
            ],
        },
    )

    existing_by_key: dict[str, dict[str, object]] = {}
    current_registry = load_registry(store.store_dir)
    if current_registry is not None:
        for entry in current_registry.entries:
            if not entry.enabled or entry.operation != "SUMMARIZE":
                continue
            artifact = load_artifact(store.store_dir, entry)
            _validate_artifact(
                artifact,
                entry_key=entry.key,
                entry_task=entry.task,
            )
            existing_by_key[entry.key] = artifact

    outputs: dict[str, dict[str, object]] = {}
    pending: list[SummaryPlan] = []
    resumed_output_count = 0
    provider_keys_this_run: set[str] = set()
    for plan in nonempty:
        key = _row_key(plan, model=model, reasoning=reasoning)
        existing = existing_by_key.get(key)
        if existing is not None:
            outputs[key] = {
                "kind": ROW_KIND,
                "schema_version": ROW_SCHEMA_VERSION,
                "row_key": key,
                "created_at": _utc_now(),
                "task": plan.task,
                "state": "EXACT_PREWARM",
                "context_name": plan.frame.context_name,
                "include_descendants": plan.frame.include_descendants,
                "follow_embeds": plan.frame.follow_embeds,
                "frame_digest": plan.frame.digest,
                "source_count": len(plan.frame.sources),
                "provider_seconds": existing.get("offline_provider_seconds", 0.0),
                "artifact": existing,
                "reused_existing": True,
            }
            continue
        path = _row_path(output_root, plan, model=model, reasoning=reasoning)
        if path.exists():
            outputs[key] = _validate_row(
                json.loads(path.read_text(encoding="utf-8")),
                plan=plan,
                model=model,
                reasoning=reasoning,
            )
            resumed_output_count += 1
        else:
            pending.append(plan)

    attempts: dict[str, int] = {}
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        running: dict[Future[dict[str, object]], SummaryPlan] = {}

        def submit(plan: SummaryPlan) -> None:
            key = _row_key(plan, model=model, reasoning=reasoning)
            attempts[key] = attempts.get(key, 0) + 1
            running[
                executor.submit(
                    _run_plan,
                    plan,
                    model=model,
                    reasoning=reasoning,
                    timeout=timeout,
                )
            ] = plan

        while pending and len(running) < workers:
            submit(pending.pop(0))
        while running:
            done, _ = wait(tuple(running), return_when=FIRST_COMPLETED)
            for future in done:
                plan = running.pop(future)
                key = _row_key(plan, model=model, reasoning=reasoning)
                try:
                    value = _validate_row(
                        future.result(),
                        plan=plan,
                        model=model,
                        reasoning=reasoning,
                    )
                    _atomic_write(
                        _row_path(output_root, plan, model=model, reasoning=reasoning),
                        value,
                    )
                    outputs[key] = value
                    provider_keys_this_run.add(key)
                    if progress is not None:
                        reach = "recursive" if plan.frame.include_descendants else "direct"
                        progress(
                            f"COMPLETE {len(outputs)}/{len(nonempty)} "
                            f"{plan.frame.context_name} [{reach}]"
                        )
                except Exception as error:
                    if attempts[key] <= retries:
                        submit(plan)
                    else:
                        failures.append(
                            {
                                "row_key": key,
                                "context_name": plan.frame.context_name,
                                "error": f"{type(error).__name__}: {error}",
                            }
                        )
                while pending and len(running) < workers:
                    submit(pending.pop(0))

    if failures or len(outputs) != len(nonempty):
        summary = {
            "kind": KIND + "_SUMMARY",
            "schema_version": SCHEMA_VERSION,
            "created_at": _utc_now(),
            "row_count": len(plans),
            "completed_provider_rows": len(outputs),
            "deterministic_empty_count": len(empty),
            "failures": failures,
            "published": False,
        }
        _atomic_write(output_root / "summary.json", summary)
        raise StudySummarizeExactMatrixError(
            f"Exact Summarize matrix has {len(failures)} failed rows."
        )

    baseline_root = profile_store_dir(baseline)
    baseline_registry = load_registry(baseline_root)
    existing_keys = {
        entry.key for entry in (baseline_registry.entries if baseline_registry else ())
    }
    already_published_count = sum(key in existing_keys for key in outputs)
    published = 0
    for value in outputs.values():
        artifact = value["artifact"]
        key = str(value["row_key"])
        if key in existing_keys:
            continue
        publish_artifact(
            baseline_root,
            baseline_profile_uid=baseline.uid,
            operation="SUMMARIZE",
            task=str(value["task"]),
            key=key,
            artifact=artifact,  # type: ignore[arg-type]
        )
        existing_keys.add(key)
        published += 1
    summary = {
        "kind": KIND + "_SUMMARY",
        "schema_version": SCHEMA_VERSION,
        "created_at": _utc_now(),
        "row_count": len(plans),
        "completed_provider_rows": len(outputs),
        "deterministic_empty_count": len(empty),
        "provider_call_count": len(provider_keys_this_run),
        "resumed_output_count": resumed_output_count,
        "reused_existing_count": sum(
            bool(value.get("reused_existing")) for value in outputs.values()
        ),
        "already_published_count": already_published_count,
        "published_count": published,
        "provider_seconds": sum(
            float(value.get("provider_seconds", 0.0))
            for key, value in outputs.items()
            if key in provider_keys_this_run
        ),
        "artifact_provider_seconds": sum(
            float(value.get("provider_seconds", 0.0))
            for value in outputs.values()
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
    parser.add_argument(
        "--reasoning",
        choices=CODEX_REASONING_EFFORTS,
        default=None,
    )
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--output-root", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = Config()
    policy = resolve_codex_evaluation_policy(
        "summarize_context",
        config=config,
        model=args.model,
        reasoning_effort=args.reasoning,
        timeout_seconds=args.timeout,
    )
    model = policy.model
    reasoning = policy.reasoning_effort
    if not model:
        print("No Codex model configured; pass --model.", file=sys.stderr)
        return 2
    assert reasoning is not None
    try:
        registry = load_profile_registry()
        store = MemoryStore(create=False)
        current = store.current_context_name()
        if current is None:
            raise StudySummarizeExactMatrixError("Active Study has no current Context.")
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
        plans = collect_exact_plans(
            store=store,
            context_names=tuple(catalog.list_context_names()),
            current_context_name=current,
        )
        root = args.output_root or Path("outputs/study-summarize-exact-matrix") / (
            f"{registry.active.name}-{model}-{reasoning}"
        )
        summary = run_exact_matrix(
            store=store,
            plans=plans,
            output_root=root,
            baseline_profile_name=args.baseline_profile,
            model=model,
            reasoning=reasoning,
            timeout=policy.timeout_seconds,
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
