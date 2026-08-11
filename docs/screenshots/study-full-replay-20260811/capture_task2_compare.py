"""Capture the exact Task 2 advisor Compare in the fresh Study replay."""

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


REFERENCE = "task-2/advisor1"
COMPARED = "task-2/advisor2"
ARGV = (
    "compare",
    "--from",
    REFERENCE,
    "--to",
    COMPARED,
    "--reference-descendants",
    "--compared-descendants",
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


def main() -> None:
    sys.path.insert(0, str(ROOT))
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
                and "MEMORIES 150 + 150" in visible
                and "RELATIONS 98" in visible
            ):
                break
        else:
            raise RuntimeError("Timed out waiting for the exact Task 2 report.")
        elapsed_to_report = time.monotonic() - started
        _pump(child, recorder, seconds=0.4)
        visible = _visible_text(recorder)
        for value in (
            "MEM COMPARE · SYMMETRIC PEERS",
            "EXACT PREWARM · SAVED · RETAINED",
            "MEMORIES 150 + 150",
            "RELATIONS 98",
        ):
            if value not in visible:
                raise RuntimeError(f"Task 2 Compare screen missed {value!r}.")
        _snapshot(recorder, "44-task2-compare-exact-entry")

        child.send("\t")
        _pump(child, recorder, seconds=0.3)
        child.send("\x1b[F")
        _pump(child, recorder, seconds=0.3)
        child.send("\x1b[A" * 97)
        _pump(child, recorder, seconds=0.7)
        child.send("\r")
        _pump(child, recorder, seconds=0.7)
        visible = _visible_text(recorder)
        if "RELATION ·" not in visible or "task-2/" not in visible:
            raise RuntimeError("Task 2 relation detail did not open.")
        _snapshot(recorder, "45-task2-compare-relation-detail")

        child.send("q")
        _pump(child, recorder, seconds=10, require_eof=True)
        if "Compare view closed." not in recorder.getvalue():
            raise RuntimeError("Task 2 Compare did not emit its close receipt.")
        _snapshot(recorder, "46-task2-compare-close-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Exact Task 2 Compare unexpectedly contacted a provider.")
    _capture_read_only(
        (*ARGV, "--snapshot"),
        stem="47-task2-compare-snapshot-verification",
        expected=(
            "EXACT PREWARM · SAVED · RETAINED",
            "MEMORIES 150 + 150",
            "RELATIONS 98",
        ),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "20"),
        stem="48-task2-compare-action-log",
        expected=("operation=compare", "status=COMPLETED"),
    )
    (OUT / "task2-compare-replay-metrics.json").write_text(
        json.dumps(
            {
                "command": "mem " + " ".join(ARGV),
                "profile": PROFILE_NAME,
                "elapsed_to_report_seconds": elapsed_to_report,
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
                "input_memories": [150, 150],
                "relations": 98,
                "origin": "EXACT_PREWARM",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
