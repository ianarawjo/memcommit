"""Capture the exact Task 1 peer Compare in the fresh Study replay."""

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


REFERENCE = "task-1/participant/construction-updates"
COMPARED = "task-1/campus-wiki"
ARGV = (
    "compare",
    "--from",
    REFERENCE,
    "--to",
    COMPARED,
    "--reference-descendants",
    "--compared-descendants",
)


def _require_visible(recorder, *expected: str) -> None:
    visible = _visible_text(recorder)
    missing = [value for value in expected if value not in visible]
    if missing:
        raise RuntimeError(f"Task 1 Compare screen missed expected text: {missing!r}")


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


def _verify_latest_compare_attempt() -> None:
    ledger = _study_ledger()
    start = next(
        event
        for event in ledger.list()
        if event.action == "COMMAND_STARTED"
        and event.data.get("operation") == "compare"
    )
    attempt = ledger.events_for_attempt(start.attempt_uid)
    if any(event.action.startswith("PROVIDER_") for event in attempt):
        raise RuntimeError("Exact Task 1 Compare contacted a provider.")
    if not any(event.action == "COMMAND_FINISHED" for event in attempt):
        raise RuntimeError("Exact Task 1 Compare did not complete cleanly.")


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.profile_config import load_profile_registry

    if load_profile_registry().active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")
    provider_events_before = _provider_event_count()

    child, recorder = _spawn(*ARGV)
    started = time.monotonic()
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            _pump(child, recorder, seconds=0.05)
            visible = _visible_text(recorder)
            if (
                "EXACT PREWARM · SAVED · RETAINED" in visible
                and "MEMORIES 75 + 300" in visible
                and "RELATIONS 51" in visible
            ):
                break
        else:
            raise RuntimeError("Timed out waiting for the exact Task 1 report.")
        elapsed_to_report = time.monotonic() - started
        _pump(child, recorder, seconds=0.4)
        _require_visible(
            recorder,
            "MEM COMPARE · SYMMETRIC PEERS",
            "EXACT PREWARM · SAVED · RETAINED",
            "MEMORIES 75 + 300",
            "RELATIONS 51",
            "FOCUS VIEWER",
        )
        _snapshot(recorder, "14-task1-compare-exact-entry")

        # Items owns semantic navigation. End finds R51 without depending on
        # report/issue row counts, then 50 Up keys select the first relation.
        child.send("\t")
        _pump(child, recorder, seconds=0.3)
        child.send("\x1b[F")
        _pump(child, recorder, seconds=0.3)
        child.send("\x1b[A" * 50)
        _pump(child, recorder, seconds=0.5)
        child.send("\r")
        _pump(child, recorder, seconds=0.7)
        _require_visible(recorder, "RELATION ·", "task-1/")
        _snapshot(recorder, "15-task1-compare-relation-detail")

        child.send("q")
        _pump(child, recorder, seconds=10, require_eof=True)
        if "Compare view closed." not in recorder.getvalue():
            raise RuntimeError("Task 1 Compare did not emit its close receipt.")
        _snapshot(recorder, "16-task1-compare-close-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    if _provider_event_count() != provider_events_before:
        raise RuntimeError("Exact Task 1 Compare unexpectedly contacted a provider.")
    _verify_latest_compare_attempt()

    _capture_read_only(
        (*ARGV, "--snapshot"),
        stem="17-task1-compare-snapshot-verification",
        expected=(
            "EXACT PREWARM · SAVED · RETAINED",
            "MEMORIES 75 + 300",
            "RELATIONS 51",
        ),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "20"),
        stem="18-task1-compare-action-log",
        expected=("operation=compare", "status=COMPLETED"),
    )

    (OUT / "task1-compare-replay-metrics.json").write_text(
        json.dumps(
            {
                "command": "mem " + " ".join(ARGV),
                "profile": PROFILE_NAME,
                "elapsed_to_report_seconds": elapsed_to_report,
                "provider_events_before": provider_events_before,
                "provider_events_after": _provider_event_count(),
                "input_memories": [75, 300],
                "relations": 51,
                "origin": "EXACT_PREWARM",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
