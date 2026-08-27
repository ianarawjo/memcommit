"""Capture and apply the Tutorial Atomize exact prewarm in the replay run."""

from __future__ import annotations

import sys

from capture_init_study import (
    PROFILE_NAME,
    ROOT,
    _capture_read_only,
    _pump,
    _snapshot,
    _spawn,
    _visible_text,
)


SOURCE = "practice/source"
OUTPUT = "practice/source-atomized"


def _require_visible(recorder, *expected: str) -> None:
    visible = _visible_text(recorder)
    missing = [value for value in expected if value not in visible]
    if missing:
        raise RuntimeError(f"Atomize screen missed expected text: {missing!r}")


def _provider_event_count() -> int:
    from memcommit.profile_config import load_profile_registry
    from memcommit.store import MemoryStore
    from memcommit.study_action_log import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    return sum(
        event.action.startswith("PROVIDER_")
        for event in StudyActionLedger(profile, store_dir=store.store_dir).list()
    )


def _verify_latest_atomize_attempt() -> None:
    from memcommit.profile_config import load_profile_registry
    from memcommit.store import MemoryStore
    from memcommit.study_action_log import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    ledger = StudyActionLedger(profile, store_dir=store.store_dir)
    start = next(
        event
        for event in ledger.list()
        if event.action == "COMMAND_STARTED"
        and event.data.get("operation") == "atomize"
    )
    attempt = ledger.events_for_attempt(start.attempt_uid)
    if any(event.action.startswith("PROVIDER_") for event in attempt):
        raise RuntimeError("Atomize application attempt contacted a provider.")
    required = {"APPROVAL_PRESENTED", "APPROVAL_ACCEPTED", "COMMAND_FINISHED"}
    if not required.issubset({event.action for event in attempt}):
        raise RuntimeError("Atomize application attempt is missing approval evidence.")


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.profile_config import load_profile_registry
    from memcommit.store import MemoryStore
    from memcommit.study_scenarios.legacy.prewarm.atomize import (
        is_installed_atomize_prewarm,
    )

    registry = load_profile_registry()
    if registry.active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")
    store = MemoryStore(create=False)
    output_exists = store.context_exists(OUTPUT)

    source = store.load_direct(SOURCE)
    analysis = store.load_atomize_analysis(source.uid)
    if analysis is None or not is_installed_atomize_prewarm(store, analysis):
        raise RuntimeError("Tutorial Atomize exact prewarm is not installed.")
    provider_events_before = _provider_event_count()

    if not output_exists:
        child, recorder = _spawn("atomize", "--context", SOURCE)
        try:
            _pump(child, recorder, seconds=2.0)
            _require_visible(
                recorder,
                "MEM ATOMIZE",
                "READY_TO_APPLY_AS_IS",
                "1 SOURCE MEMORIES",
                "8 PROJECTED MEMORIES",
                "Esc/Backspace/Q close",
            )
            _snapshot(recorder, "06-atomize-exact-prewarm-entry")

            # Viewer -> Items, then open the one actionable split in Viewer.
            child.send("\t\x1b[B\r")
            _pump(child, recorder, seconds=0.8)
            _require_visible(recorder, "SUGGESTED SPLIT 1/1", "PROPOSED CHILDREN")
            _snapshot(recorder, "07-atomize-split-detail")

            # Return to the complete report. The common A shortcut opens the same
            # final-review boundary as the visible To Do handoff.
            child.send("\x7f")
            _pump(child, recorder, seconds=0.6)
            _require_visible(
                recorder,
                "REVIEW AND APPLY",
                "APPLY AS IS is available",
            )
            _snapshot(recorder, "08-atomize-review-handoff")

            child.send("a")
            _pump(child, recorder, seconds=0.6)
            _require_visible(
                recorder,
                "REVIEW AND APPLY",
                "Nothing changes until the final action below is confirmed",
            )
            _snapshot(recorder, "09-atomize-final-review")

            child.send("\x1b[F")
            _pump(child, recorder, seconds=0.5)
            _require_visible(
                recorder,
                "APPLY AS IS",
                "Enter to apply the exact current proposal as is",
            )
            _snapshot(recorder, "10-atomize-exact-approval")

            child.send("\r")
            _pump(child, recorder, seconds=30, require_eof=True)
            raw = recorder.getvalue()
            if "Created and atomized 'practice/source-atomized'" not in raw:
                raise RuntimeError("Atomize did not publish the reviewed Output.")
            _snapshot(recorder, "11-atomize-apply-receipt")
        finally:
            if child.isalive():
                child.close(force=True)

    output = store.load_direct(OUTPUT)
    if len(output.memories) != 8:
        raise RuntimeError("Atomize Output does not contain eight projected Memories.")
    if not output_exists and _provider_event_count() != provider_events_before:
        raise RuntimeError("Exact-prewarm Atomize unexpectedly contacted a provider.")
    _verify_latest_atomize_attempt()

    _capture_read_only(
        ("show", "--context", OUTPUT),
        stem="12-atomize-output-verification",
        expected=(OUTPUT, "Please avoid using the expression"),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "35"),
        stem="13-atomize-action-log",
        expected=(
            "operation=atomize",
            "APPROVAL_PRESENTED",
            "APPROVAL_ACCEPTED",
        ),
    )


if __name__ == "__main__":
    main()
