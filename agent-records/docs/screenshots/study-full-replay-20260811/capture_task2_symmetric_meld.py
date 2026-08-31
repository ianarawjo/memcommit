"""Replay the provider-free Task 2 symmetric Meld from its exact Compare basis."""

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


LEFT = "task-2/advisor1"
RIGHT = "task-2/advisor2"
TARGET = "task-2/participant/symmetric-replay-result"
CREATE_ARGV = (
    "meld",
    LEFT,
    RIGHT,
    "--left-descendants",
    "--right-descendants",
    "--to",
    TARGET,
)
RESUME_ARGV = (
    "meld",
    LEFT,
    RIGHT,
    "--left-descendants",
    "--right-descendants",
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


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.application.operations.profiles.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore

    if load_profile_registry().active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")
    store = MemoryStore(create=False)
    if store.context_exists(TARGET):
        raise RuntimeError(f"Task 2 replay target {TARGET!r} already exists.")
    current_before = store.current_context_name()
    provider_events_before = _provider_event_count()

    child, recorder = _spawn(*CREATE_ARGV)
    started = time.monotonic()
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            _pump(child, recorder, seconds=0.05)
            visible = _visible_text(recorder)
            if "SYMMETRIC PEERS" in visible and "RELATIONS 98" in visible:
                break
        else:
            raise RuntimeError("Timed out waiting for Task 2 symmetric Meld.")
        elapsed_to_review = time.monotonic() - started
        _pump(child, recorder, seconds=0.5)
        visible = _visible_text(recorder)
        for value in (
            "SYMMETRIC PEERS",
            "MEMORIES 150 + 150",
            "RELATIONS 98",
            TARGET,
        ):
            if value not in visible:
                raise RuntimeError(f"Task 2 symmetric Meld missed {value!r}.")
        _snapshot(recorder, "49-task2-symmetric-meld-exact-entry")

        child.send("\t\x1b[B\r")
        _pump(child, recorder, seconds=0.8)
        visible = _visible_text(recorder)
        if "SOURCE CLAIMS" not in visible or "CLASSIFICATION" not in visible:
            raise RuntimeError("Task 2 Meld issue detail did not open.")
        _snapshot(recorder, "50-task2-symmetric-meld-conflict-detail")

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
        or session.comparison_seed is None
        or len(session.comparison_seed.analysis.relations) != 98
        or len(tuple(target.iter_items())) != 0
    ):
        raise RuntimeError("Initial Task 2 symmetric Meld contract is incomplete.")

    _capture_command(
        ("switch", TARGET),
        stem="51-task2-symmetric-meld-target-switch",
        expected=(TARGET,),
    )
    preserve_seconds = _capture_command(
        (*RESUME_ARGV, "--preserve-all"),
        stem="52-task2-symmetric-meld-preserve-all",
        expected=("READY_TO_APPLY", "300/300", "98/98", "--accept"),
    )
    session = store.load_meld_session(target.uid)
    assessment = session.current_assessment if session is not None else None
    if (
        session is None
        or session.state != "READY_TO_APPLY"
        or assessment is None
        or len(assessment.proposals) != 249
    ):
        raise RuntimeError("Task 2 preserve-all did not produce 249 results.")

    accept_seconds = _capture_command(
        (*RESUME_ARGV, "--accept"),
        stem="53-task2-symmetric-meld-accept-receipt",
        expected=("APPLIED", "Applied 249 meld results", TARGET),
    )
    result = store.load_direct(TARGET)
    session = store.load_meld_session(result.uid)
    if (
        session is None
        or session.state != "APPLIED"
        or len(tuple(result.iter_items())) != 249
    ):
        raise RuntimeError("Task 2 symmetric Meld result is not 249 Memories.")

    _capture_read_only(
        ("show", "--context", TARGET),
        stem="54-task2-symmetric-meld-result-verification",
        expected=(TARGET, "Memories 249"),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "25"),
        stem="55-task2-symmetric-meld-action-log",
        expected=("operation=meld", "COMMAND_FINISHED"),
    )
    _capture_command(
        ("switch", current_before),
        stem="56-task2-symmetric-meld-current-restored",
        expected=(current_before,),
    )

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Task 2 symmetric Meld unexpectedly contacted a provider.")
    (OUT / "task2-symmetric-meld-replay-metrics.json").write_text(
        json.dumps(
            {
                "result_creation_command": "mem " + " ".join(CREATE_ARGV),
                "profile": PROFILE_NAME,
                "elapsed_to_review_seconds": elapsed_to_review,
                "preserve_all_seconds": preserve_seconds,
                "accept_seconds": accept_seconds,
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
                "input_memories": [150, 150],
                "relations": 98,
                "issues": 45,
                "required_conflicts": 5,
                "result_memories": 249,
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
