"""Capture the accumulated-editing Tutorial Atomize path in a real color PTY."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
HELPERS = ROOT / "agent-records" / "docs" / "screenshots" / "study-full-replay-20260811"
PROFILE_NAME = "atomize-line-memory-direct-capture3-20260815"
SOURCE = "practice/source"
OUTPUT = "practice/source-atomized"

sys.path.insert(0, str(HELPERS))
import capture_init_study as replay  # noqa: E402

replay.OUT = OUT
_capture_read_only = replay._capture_read_only
_pump = replay._pump
_snapshot = replay._snapshot
_spawn = replay._spawn
_visible_text = replay._visible_text


def _require_visible(recorder, *expected: str) -> None:
    visible = _visible_text(recorder)
    missing = [value for value in expected if value not in visible]
    if missing:
        raise RuntimeError(f"Atomize screen missed expected text: {missing!r}")


def _provider_event_count() -> int:
    from memcommit.application.operations.profiles.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore
    from memcommit.persistence.command_ledger.study_actions import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    return sum(
        event.action.startswith("PROVIDER_")
        for event in StudyActionLedger(profile, store_dir=store.store_dir).list()
    )


def _verify_latest_atomize_attempt() -> None:
    from memcommit.application.operations.profiles.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore
    from memcommit.persistence.command_ledger.study_actions import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    ledger = StudyActionLedger(profile, store_dir=store.store_dir)
    start = next(
        event
        for event in reversed(ledger.list())
        if event.action == "COMMAND_STARTED"
        and event.data.get("operation") == "atomize"
    )
    attempt = ledger.events_for_attempt(start.attempt_uid)
    if any(event.action.startswith("PROVIDER_") for event in attempt):
        raise RuntimeError("Exact-prewarm Atomize contacted a provider.")
    required = {"DECISION_FREE_AUTO_ACCEPT", "COMMAND_FINISHED"}
    if not required.issubset({event.action for event in attempt}):
        raise RuntimeError("Atomize attempt is missing local auto-apply evidence.")
    if any(
        event.action in {"APPROVAL_PRESENTED", "APPROVAL_ACCEPTED"} for event in attempt
    ):
        raise RuntimeError("Decision-free local Atomize unexpectedly asked approval.")


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.application.operations.profiles.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore
    from memcommit.study_scenarios.legacy.prewarm.atomize import find_declared_atomize_prewarm

    OUT.mkdir(parents=True, exist_ok=True)
    registry = load_profile_registry()
    if registry.active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active Profile {PROFILE_NAME!r}.")
    store = MemoryStore(create=False)
    if store.context_exists(OUTPUT):
        raise RuntimeError("Capture requires a not-yet-created Atomize Output.")
    source = store.load_direct(SOURCE)
    if store.load_atomize_analysis(source.uid) is not None:
        raise RuntimeError("Capture requires an unmaterialized exact prewarm.")
    prepared = find_declared_atomize_prewarm(store=store, context=source)
    if (
        prepared is None
        or prepared.analysis.memory_count != 12
        or prepared.analysis.projected_memory_count != 17
        or sum(bool(item.children) for item in prepared.analysis.items) != 3
        or sum(len(item.children) for item in prepared.analysis.items) != 8
    ):
        raise RuntimeError("The exact 12-source tutorial prewarm is unavailable.")
    provider_events_before = _provider_event_count()

    _capture_read_only(
        ("show", "--context", SOURCE),
        stem="01-source-verification",
        expected=(SOURCE, "Memories 12", "How does this read?", "refferences"),
    )

    # There is no separate Impact or inspection step. The exact proposal has
    # no REQUIRED decision and creates only a local, checkpointed Output, so
    # the ordinary Atomize command applies without rendering a review surface.
    child, recorder = _spawn("atomize", "--context", SOURCE)
    try:
        _pump(child, recorder, seconds=30, require_eof=True)
        if "Created and atomized 'practice/source-atomized'" not in recorder.getvalue():
            raise RuntimeError("Atomize did not publish the reviewed Output.")
        _snapshot(recorder, "02-auto-apply-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    output = store.load_direct(OUTPUT)
    if len(output.memories) != 17:
        raise RuntimeError("Atomize Output does not contain 17 projected Memories.")
    analysis = store.load_atomize_analysis(source.uid)
    if analysis is None or analysis.uid != prepared.analysis.uid:
        raise RuntimeError("Applied analysis changed the exact prepared identity.")
    if _provider_event_count() != provider_events_before:
        raise RuntimeError("Exact-prewarm Atomize unexpectedly contacted a provider.")
    _verify_latest_atomize_attempt()

    _capture_read_only(
        ("show", "--context", OUTPUT),
        stem="03-output-verification",
        expected=(
            OUTPUT,
            "How does this read?",
            "citations and refferences",
            "silently rewriting the draft",
        ),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "35"),
        stem="04-action-log",
        expected=(
            "operation=atomize",
            "DECISION_FREE_AUTO_ACCEPT",
        ),
    )
    if "\x1b[32m" not in (OUT / "02-auto-apply-receipt.typescript").read_text(
        encoding="utf-8"
    ):
        raise RuntimeError(
            "PTY stream did not contain the expected green receipt ANSI."
        )


if __name__ == "__main__":
    main()
