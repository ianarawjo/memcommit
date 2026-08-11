"""Replay the provider-free Task 3 mixed-authority rule Meld."""

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


LEFT = "task-3/local/guardrails"
RIGHT = (
    "task-3/remote/government/healthcare-agent/info-request/transmission-guidance"
)
TARGET = "task-3/participant/rule-meld-replay-result"
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
    from memcommit.profile_config import load_profile_registry
    from memcommit.store import MemoryStore
    from memcommit.study_action_log import StudyActionLedger

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
    sys.path.insert(0, str(ROOT))
    from memcommit.profile_config import load_profile_registry
    from memcommit.store import MemoryStore

    if load_profile_registry().active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")
    store = MemoryStore(create=False)
    if store.context_exists(TARGET):
        raise RuntimeError(f"Task 3 rule Meld target {TARGET!r} already exists.")
    current_before = store.current_context_name()
    provider_events_before = _provider_event_count()

    child, recorder = _spawn(*CREATE_ARGV)
    started = time.monotonic()
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            _pump(child, recorder, seconds=0.05)
            visible = _visible_text(recorder)
            if "SYMMETRIC PEERS" in visible and "RELATIONS 57" in visible:
                break
        else:
            raise RuntimeError("Timed out waiting for Task 3 rule Meld.")
        elapsed_to_review = time.monotonic() - started
        _pump(child, recorder, seconds=0.5)
        visible = _visible_text(recorder)
        for value in ("MEMORIES 75 + 25", "RELATIONS 57", TARGET):
            if value not in visible:
                raise RuntimeError(f"Task 3 rule Meld missed {value!r}.")
        _snapshot(recorder, "95-task3-rule-meld-exact-entry")

        child.send("\t\x1b[B\r")
        _pump(child, recorder, seconds=0.8)
        visible = _visible_text(recorder)
        if "SOURCE CLAIMS" not in visible or "CLASSIFICATION" not in visible:
            raise RuntimeError("Task 3 rule Meld issue detail did not open.")
        _snapshot(recorder, "96-task3-rule-meld-issue-detail")

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
        or session.current_assessment is None
        or len(session.current_assessment.issues) != 16
        or len(tuple(target.iter_items())) != 0
    ):
        raise RuntimeError("Initial Task 3 rule Meld contract is incomplete.")

    _capture_command(
        ("switch", TARGET),
        stem="97-task3-rule-meld-target-switch",
        expected=(TARGET,),
    )
    preserve_seconds = _capture_command(
        (*RESUME_ARGV, "--preserve-all"),
        stem="98-task3-rule-meld-preserve-all",
        expected=("READY_TO_APPLY", "100/100", "57/57", "--accept"),
    )
    session = store.load_meld_session(target.uid)
    assessment = session.current_assessment if session is not None else None
    if (
        session is None
        or session.state != "READY_TO_APPLY"
        or assessment is None
        or len(assessment.proposals) != 100
    ):
        raise RuntimeError("Task 3 rule preservation is not 100 Memories.")

    accept_seconds = _capture_command(
        (*RESUME_ARGV, "--accept"),
        stem="99-task3-rule-meld-accept-receipt",
        expected=("APPLIED", "Applied 100 meld results", TARGET),
    )
    result = store.load_direct(TARGET)
    session = store.load_meld_session(result.uid)
    if (
        session is None
        or session.state != "APPLIED"
        or len(tuple(result.iter_items())) != 100
    ):
        raise RuntimeError("Task 3 rule Meld result is not 100 Memories.")
    _capture_read_only(
        ("show", "--context", TARGET),
        stem="100-task3-rule-meld-result-verification",
        expected=(TARGET, "Memories 100"),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "25"),
        stem="101-task3-rule-meld-action-log",
        expected=("operation=meld", "COMMAND_FINISHED"),
    )
    _capture_command(
        ("switch", current_before),
        stem="102-task3-rule-meld-current-restored",
        expected=(current_before,),
    )

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Task 3 rule Meld contacted a provider.")
    (OUT / "task3-rule-meld-replay-metrics.json").write_text(
        json.dumps(
            {
                "result_creation_command": "mem " + " ".join(CREATE_ARGV),
                "profile": PROFILE_NAME,
                "elapsed_to_review_seconds": elapsed_to_review,
                "preserve_all_seconds": preserve_seconds,
                "accept_seconds": accept_seconds,
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
                "input_memories": [75, 25],
                "relations": 57,
                "issues": 16,
                "result_memories": 100,
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
