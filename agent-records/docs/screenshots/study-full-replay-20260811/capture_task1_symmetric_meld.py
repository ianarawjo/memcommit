"""Replay the provider-free Task 1 symmetric Meld from its exact Compare basis."""

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


LEFT = "task-1/participant/construction-updates"
RIGHT = "task-1/campus-wiki"
TARGET = "task-1/participant/symmetric-replay-result"
LEFT_COUNT = 75
RIGHT_COUNT = 300


def _provider_event_count() -> int:
    from memcommit.application.operations.profiles.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore
    from memcommit.persistence.command_ledger.study_actions import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    ledger = StudyActionLedger(profile, store_dir=store.store_dir)
    return sum(event.action.startswith("PROVIDER_") for event in ledger.list())


def _latest_completed_meld_seconds() -> tuple[float, float, float]:
    from memcommit.application.operations.profiles.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore
    from memcommit.persistence.command_ledger.study_actions import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    ledger = StudyActionLedger(profile, store_dir=store.store_dir)
    durations: list[float] = []
    for event in ledger.list():
        if (
            event.action != "COMMAND_STARTED"
            or event.data.get("operation") != "meld"
        ):
            continue
        finished = next(
            (
                item
                for item in ledger.events_for_attempt(event.attempt_uid)
                if item.action == "COMMAND_FINISHED"
            ),
            None,
        )
        if finished is not None and finished.elapsed_seconds is not None:
            durations.append(finished.elapsed_seconds)
        if len(durations) == 3:
            break
    if len(durations) != 3:
        raise RuntimeError("Could not recover the three completed Meld timings.")
    accept_seconds, preserve_seconds, review_attempt_seconds = durations
    return review_attempt_seconds, preserve_seconds, accept_seconds


def _capture_command(
    args: tuple[str, ...], *, stem: str, expected: tuple[str, ...]
) -> tuple[str, float]:
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
        return raw, elapsed
    finally:
        if child.isalive():
            child.close(force=True)


def _relation_count(session) -> int:
    seed = session.comparison_seed
    if seed is None:
        raise RuntimeError("Symmetric Meld did not retain a Compare seed.")
    return len(seed.analysis.relations)


def _finish_applied_replay(
    *,
    store,
    current_before: str,
    provider_events_before: int,
    review_attempt_seconds: float,
    preserve_seconds: float,
    accept_seconds: float,
    creation_argv: tuple[str, ...],
    captured_argv: tuple[str, ...],
) -> None:
    result = store.load_direct(TARGET)
    session = store.load_meld_session(result.uid)
    if (
        session is None
        or session.state != "APPLIED"
        or len(tuple(result.iter_items())) != LEFT_COUNT + RIGHT_COUNT
    ):
        raise RuntimeError("Exact Task 1 Meld acceptance was not materialized.")

    _capture_read_only(
        ("show", "--context", TARGET),
        stem="33-task1-symmetric-meld-result-verification",
        expected=(TARGET, "Memories 375"),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "30"),
        stem="34-task1-symmetric-meld-action-log",
        expected=("operation=meld", "COMMAND_FINISHED"),
    )
    _capture_command(
        ("switch", current_before),
        stem="35-task1-symmetric-meld-current-restored",
        expected=(current_before,),
    )

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Task 1 symmetric Meld unexpectedly contacted a provider.")
    (OUT / "task1-symmetric-meld-replay-metrics.json").write_text(
        json.dumps(
            {
                "result_creation_command": "mem " + " ".join(creation_argv),
                "captured_resume_command": "mem " + " ".join(captured_argv),
                "profile": PROFILE_NAME,
                "review_attempt_seconds": review_attempt_seconds,
                "preserve_all_seconds": preserve_seconds,
                "accept_seconds": accept_seconds,
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
                "left_memories": LEFT_COUNT,
                "right_memories": RIGHT_COUNT,
                "relations": 51,
                "result_memories": LEFT_COUNT + RIGHT_COUNT,
                "origin": "EXACT_PREWARM_COMPARE_BASIS",
                "current_before": current_before,
                "current_after": store.current_context_name(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.application.operations.profiles.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore

    if load_profile_registry().active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")

    store = MemoryStore(create=False)
    current_before = store.current_context_name()
    provider_events_before = _provider_event_count()

    creation_argv = (
        "meld",
        LEFT,
        RIGHT,
        "--left-descendants",
        "--right-descendants",
        "--to",
        TARGET,
    )
    captured_argv = (
        "meld",
        LEFT,
        RIGHT,
        "--left-descendants",
        "--right-descendants",
    )
    if store.context_exists(TARGET):
        target = store.load_direct(TARGET)
        resumed = store.load_meld_session(target.uid)
        if resumed is not None and resumed.state == "APPLIED":
            review, preserve, accept = _latest_completed_meld_seconds()
            _finish_applied_replay(
                store=store,
                current_before=current_before,
                provider_events_before=provider_events_before,
                review_attempt_seconds=review,
                preserve_seconds=preserve,
                accept_seconds=accept,
                creation_argv=creation_argv,
                captured_argv=captured_argv,
            )
            return
        if (
            resumed is None
            or resumed.state != "AWAITING_REPLY"
            or len(tuple(target.iter_items())) != 0
            or _relation_count(resumed) != 51
        ):
            raise RuntimeError(f"Replay target {TARGET!r} is not resumable.")
    else:
        raise RuntimeError(
            "The exact result/session creation step is missing; rerun init-study replay setup."
        )

    _capture_command(
        ("switch", TARGET),
        stem="28-task1-symmetric-meld-target-switch",
        expected=(TARGET,),
    )
    argv = captured_argv
    child, recorder = _spawn(*argv)
    started = time.monotonic()
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            _pump(child, recorder, seconds=0.05)
            visible = _visible_text(recorder)
            if "RELATIONS 51" in visible and "SYMMETRIC PEERS" in visible:
                break
        else:
            raise RuntimeError("Timed out waiting for Task 1 symmetric Meld.")
        elapsed_to_review = time.monotonic() - started
        _pump(child, recorder, seconds=0.5)
        visible = _visible_text(recorder)
        for value in ("SYMMETRIC PEERS", "RELATIONS 51", TARGET):
            if value not in visible:
                raise RuntimeError(f"Initial Meld screen missed {value!r}.")
        _snapshot(recorder, "29-task1-symmetric-meld-exact-entry")

        child.send("\t\x1b[B\r")
        _pump(child, recorder, seconds=0.8)
        visible = _visible_text(recorder)
        if "RELATION" not in visible or "SOURCE" not in visible:
            raise RuntimeError("Meld relation detail did not open.")
        _snapshot(recorder, "30-task1-symmetric-meld-relation-detail")

        child.send("q")
        _pump(child, recorder, seconds=30, require_eof=True)
    finally:
        if child.isalive():
            child.close(force=True)

    target = store.load_direct(TARGET)
    session = store.load_meld_session(target.uid)
    if (
        session is None
        or session.state != "AWAITING_REPLY"
        or _relation_count(session) != 51
        or len(tuple(target.iter_items())) != 0
    ):
        raise RuntimeError("Initial Task 1 symmetric Meld contract is incomplete.")

    _, preserve_seconds = _capture_command(
        (
            "meld",
            LEFT,
            RIGHT,
            "--left-descendants",
            "--right-descendants",
            "--preserve-all",
        ),
        stem="31-task1-symmetric-meld-preserve-all",
        expected=("READY_TO_APPLY", "375/375", "51/51", "--accept"),
    )

    session = store.load_meld_session(target.uid)
    assessment = session.current_assessment if session is not None else None
    if (
        session is None
        or session.state != "READY_TO_APPLY"
        or assessment is None
        or len(assessment.proposals) != LEFT_COUNT + RIGHT_COUNT
    ):
        raise RuntimeError("Deterministic preserve-all did not cover all inputs.")

    _, accept_seconds = _capture_command(
        (
            "meld",
            LEFT,
            RIGHT,
            "--left-descendants",
            "--right-descendants",
            "--accept",
        ),
        stem="32-task1-symmetric-meld-accept-receipt",
        expected=("APPLIED", "Applied 375 meld results", TARGET),
    )
    result = store.load_direct(TARGET)
    session = store.load_meld_session(result.uid)
    if (
        session is None
        or session.state != "APPLIED"
        or len(tuple(result.iter_items())) != LEFT_COUNT + RIGHT_COUNT
    ):
        raise RuntimeError("Exact Task 1 Meld acceptance was not materialized.")

    _capture_read_only(
        ("show", "--context", TARGET),
        stem="33-task1-symmetric-meld-result-verification",
        expected=(TARGET, "Memories 375"),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "30"),
        stem="34-task1-symmetric-meld-action-log",
        expected=("operation=meld", "COMMAND_FINISHED"),
    )
    _capture_command(
        ("switch", current_before),
        stem="35-task1-symmetric-meld-current-restored",
        expected=(current_before,),
    )

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Task 1 symmetric Meld unexpectedly contacted a provider.")
    (OUT / "task1-symmetric-meld-replay-metrics.json").write_text(
        json.dumps(
            {
                "result_creation_command": "mem " + " ".join(creation_argv),
                "captured_resume_command": "mem " + " ".join(argv),
                "profile": PROFILE_NAME,
                "elapsed_to_review_seconds": elapsed_to_review,
                "preserve_all_seconds": preserve_seconds,
                "accept_seconds": accept_seconds,
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
                "left_memories": LEFT_COUNT,
                "right_memories": RIGHT_COUNT,
                "relations": 51,
                "result_memories": LEFT_COUNT + RIGHT_COUNT,
                "origin": "EXACT_PREWARM_COMPARE_BASIS",
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
