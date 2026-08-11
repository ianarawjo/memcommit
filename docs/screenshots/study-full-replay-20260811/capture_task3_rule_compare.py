"""Capture the exact Task 3 local-to-granted rule comparison."""

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


REFERENCE = "task-3/local/guardrails"
COMPARED = (
    "task-3/remote/government/healthcare-agent/info-request/transmission-guidance"
)
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
                and "MEMORIES 75 + 25" in visible
                and "RELATIONS 57" in visible
            ):
                break
        else:
            raise RuntimeError("Timed out waiting for Task 3 rule Compare.")
        elapsed_to_report = time.monotonic() - started
        _pump(child, recorder, seconds=0.4)
        _snapshot(recorder, "90-task3-rule-compare-exact-entry")

        child.send("\t")
        _pump(child, recorder, seconds=0.3)
        child.send("\x1b[F")
        _pump(child, recorder, seconds=0.3)
        child.send("\x1b[A" * 56)
        _pump(child, recorder, seconds=0.6)
        child.send("\r")
        _pump(child, recorder, seconds=0.7)
        visible = _visible_text(recorder)
        if "RELATION ·" not in visible or "task-3/" not in visible:
            raise RuntimeError("Task 3 rule relation detail did not open.")
        _snapshot(recorder, "91-task3-rule-compare-relation-detail")

        child.send("q")
        _pump(child, recorder, seconds=10, require_eof=True)
        if "Compare view closed." not in recorder.getvalue():
            raise RuntimeError("Task 3 rule Compare did not close cleanly.")
        _snapshot(recorder, "92-task3-rule-compare-close-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Task 3 rule Compare contacted a provider.")
    _capture_read_only(
        (*ARGV, "--snapshot"),
        stem="93-task3-rule-compare-snapshot-verification",
        expected=(
            "EXACT PREWARM · SAVED · RETAINED",
            "MEMORIES 75 + 25",
            "RELATIONS 57",
        ),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "20"),
        stem="94-task3-rule-compare-action-log",
        expected=("operation=compare", "COMMAND_FINISHED"),
    )
    (OUT / "task3-rule-compare-replay-metrics.json").write_text(
        json.dumps(
            {
                "command": "mem " + " ".join(ARGV),
                "profile": PROFILE_NAME,
                "elapsed_to_report_seconds": elapsed_to_report,
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
                "input_memories": [75, 25],
                "relations": 57,
                "origin": "EXACT_PREWARM",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
