"""Replay all three provider-free Task 3 year-pair symmetric Melds."""

from __future__ import annotations

import json
import sys
import time

from capture_init_study import (
    OUT,
    PROFILE_NAME,
    ROOT,
    _capture_read_only,
    _pump,
    _snapshot,
    _spawn,
    _visible_text,
)


YEAR_ROOT = "task-3/local/personal-memory"
RESULT_ROOT = "task-3/participant"
PAIRS = (
    ("2024", "2025", 120, 120, 119, 7, 70),
    ("2024", "2026", 120, 60, 96, 10, 76),
    ("2025", "2026", 120, 60, 102, 2, 82),
)


def _study_ledger():
    from memcommit.application.operations.profiles.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore
    from memcommit.persistence.command_ledger.study_actions import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    return StudyActionLedger(profile, store_dir=store.store_dir)


def _provider_event_count() -> int:
    return sum(
        event.action.startswith("PROVIDER_") for event in _study_ledger().list()
    )


def _capture_command(
    args: tuple[str, ...], *, stem: str, expected: tuple[str, ...]
) -> float:
    child, recorder = _spawn(*args)
    started = time.monotonic()
    try:
        _pump(child, recorder, seconds=30, require_eof=True)
        elapsed = time.monotonic() - started
        raw = recorder.getvalue()
        missing = [value for value in expected if value not in raw]
        if missing:
            raise RuntimeError(f"Command capture {stem} missed {missing!r}.")
        _snapshot(recorder, stem)
        return elapsed
    finally:
        if child.isalive():
            child.close(force=True)


def _create_argv(left: str, right: str, target: str) -> tuple[str, ...]:
    return (
        "meld",
        f"{YEAR_ROOT}/{left}",
        f"{YEAR_ROOT}/{right}",
        "--left-descendants",
        "--right-descendants",
        "--to",
        target,
    )


def _resume_argv(left: str, right: str) -> tuple[str, ...]:
    return (
        "meld",
        f"{YEAR_ROOT}/{left}",
        f"{YEAR_ROOT}/{right}",
        "--left-descendants",
        "--right-descendants",
    )


def _capture_pair(
    *,
    store,
    left: str,
    right: str,
    left_count: int,
    right_count: int,
    relations: int,
    issues: int,
    first_number: int,
) -> dict[str, object]:
    target_name = f"{RESULT_ROOT}/year-meld-{left}-{right}"
    if store.context_exists(target_name):
        raise RuntimeError(f"Task 3 year Meld target {target_name!r} already exists.")
    create_argv = _create_argv(left, right, target_name)
    resume_argv = _resume_argv(left, right)
    slug = f"task3-{left}-{right}-meld"

    child, recorder = _spawn(*create_argv)
    started = time.monotonic()
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            _pump(child, recorder, seconds=0.05)
            visible = _visible_text(recorder)
            if "SYMMETRIC PEERS" in visible and f"RELATIONS {relations}" in visible:
                break
        else:
            raise RuntimeError(f"Timed out waiting for {left}-{right} Meld.")
        open_seconds = time.monotonic() - started
        _pump(child, recorder, seconds=0.5)
        visible = _visible_text(recorder)
        for value in (
            f"MEMORIES {left_count} + {right_count}",
            f"RELATIONS {relations}",
            target_name,
        ):
            if value not in visible:
                raise RuntimeError(f"{left}-{right} Meld missed {value!r}.")
        _snapshot(recorder, f"{first_number:02d}-{slug}-exact-entry")

        child.send("\t\x1b[B\r")
        _pump(child, recorder, seconds=0.8)
        visible = _visible_text(recorder)
        if "SOURCE CLAIMS" not in visible or "CLASSIFICATION" not in visible:
            raise RuntimeError(f"{left}-{right} Meld issue did not open.")
        _snapshot(recorder, f"{first_number + 1:02d}-{slug}-issue-detail")

        child.send("q")
        _pump(child, recorder, seconds=30, require_eof=True)
    finally:
        if child.isalive():
            child.close(force=True)

    target = store.load_direct(target_name)
    session = store.load_meld_session(target.uid)
    if (
        session is None
        or session.state != "AWAITING_REPLY"
        or session.current_assessment is None
        or len(session.current_assessment.issues) != issues
        or len(tuple(target.iter_items())) != 0
    ):
        raise RuntimeError(f"{left}-{right} initial Meld contract is incomplete.")

    _capture_command(
        ("switch", target_name),
        stem=f"{first_number + 2:02d}-{slug}-target-switch",
        expected=(target_name,),
    )
    preserve_seconds = _capture_command(
        (*resume_argv, "--preserve-all"),
        stem=f"{first_number + 3:02d}-{slug}-preserve-all",
        expected=(
            "READY_TO_APPLY",
            f"{left_count + right_count}/{left_count + right_count}",
            f"{relations}/{relations}",
            "--accept",
        ),
    )
    session = store.load_meld_session(target.uid)
    assessment = session.current_assessment if session is not None else None
    if session is None or session.state != "READY_TO_APPLY" or assessment is None:
        raise RuntimeError(f"{left}-{right} preservation was not ready.")
    result_count = len(assessment.proposals)

    accept_seconds = _capture_command(
        (*resume_argv, "--accept"),
        stem=f"{first_number + 4:02d}-{slug}-accept-receipt",
        expected=("APPLIED", f"Applied {result_count} meld results", target_name),
    )
    result = store.load_direct(target_name)
    session = store.load_meld_session(result.uid)
    if (
        session is None
        or session.state != "APPLIED"
        or len(tuple(result.iter_items())) != result_count
    ):
        raise RuntimeError(f"{left}-{right} result count is inconsistent.")
    _capture_read_only(
        ("show", "--context", target_name),
        stem=f"{first_number + 5:02d}-{slug}-result-verification",
        expected=(target_name, f"Memories {result_count}"),
    )
    return {
        "years": [left, right],
        "input_memories": [left_count, right_count],
        "relations": relations,
        "issues": issues,
        "result_memories": result_count,
        "elapsed_to_review_seconds": open_seconds,
        "preserve_all_seconds": preserve_seconds,
        "accept_seconds": accept_seconds,
        "target": target_name,
    }


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.application.operations.profiles.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore

    if load_profile_registry().active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")
    store = MemoryStore(create=False)
    current_before = store.current_context_name()
    provider_events_before = _provider_event_count()
    results = [
        _capture_pair(
            store=store,
            left=left,
            right=right,
            left_count=left_count,
            right_count=right_count,
            relations=relations,
            issues=issues,
            first_number=first_number,
        )
        for (
            left,
            right,
            left_count,
            right_count,
            relations,
            issues,
            first_number,
        ) in PAIRS
    ]
    _capture_command(
        ("switch", current_before),
        stem="88-task3-year-melds-current-restored",
        expected=(current_before,),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "60"),
        stem="89-task3-year-melds-action-log",
        expected=("operation=meld", "COMMAND_FINISHED"),
    )

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Task 3 year Meld replay contacted a provider.")
    (OUT / "task3-year-melds-replay-metrics.json").write_text(
        json.dumps(
            {
                "profile": PROFILE_NAME,
                "pairs": results,
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
                "origin": "EXACT_PREWARM_COMPARE_BASES",
                "current_before": current_before,
                "current_after": store.current_context_name(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
