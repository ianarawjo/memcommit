"""Replay all three exact Task 3 year-pair Compare bases."""

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


ROOT_CONTEXT = "task-3/local/personal-memory"
PAIRS = (
    ("2024", "2025", 120, 120, 119, 57),
    ("2024", "2026", 120, 60, 96, 61),
    ("2025", "2026", 120, 60, 102, 65),
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


def _argv(left: str, right: str) -> tuple[str, ...]:
    return (
        "compare",
        "--from",
        f"{ROOT_CONTEXT}/{left}",
        "--to",
        f"{ROOT_CONTEXT}/{right}",
        "--reference-descendants",
        "--compared-descendants",
    )


def _capture_pair(
    left: str,
    right: str,
    left_count: int,
    right_count: int,
    relations: int,
    first_number: int,
) -> float:
    argv = _argv(left, right)
    slug = f"task3-{left}-{right}-compare"
    child, recorder = _spawn(*argv)
    started = time.monotonic()
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            _pump(child, recorder, seconds=0.05)
            visible = _visible_text(recorder)
            if (
                "EXACT PREWARM" in visible
                and f"MEMORIES {left_count} + {right_count}" in visible
                and f"RELATIONS {relations}" in visible
            ):
                break
        else:
            raise RuntimeError(f"Timed out waiting for {left}-{right} Compare.")
        elapsed = time.monotonic() - started
        _pump(child, recorder, seconds=0.4)
        _snapshot(recorder, f"{first_number:02d}-{slug}-exact-entry")

        child.send("\t")
        _pump(child, recorder, seconds=0.3)
        child.send("\x1b[F")
        _pump(child, recorder, seconds=0.3)
        child.send("\x1b[A" * (relations - 1))
        _pump(child, recorder, seconds=0.8)
        child.send("\r")
        _pump(child, recorder, seconds=0.7)
        visible = _visible_text(recorder)
        if "RELATION ·" not in visible or ROOT_CONTEXT not in visible:
            raise RuntimeError(f"{left}-{right} relation detail did not open.")
        _snapshot(recorder, f"{first_number + 1:02d}-{slug}-relation-detail")

        child.send("q")
        _pump(child, recorder, seconds=10, require_eof=True)
        if "Compare view closed." not in recorder.getvalue():
            raise RuntimeError(f"{left}-{right} Compare did not close cleanly.")
        _snapshot(recorder, f"{first_number + 2:02d}-{slug}-close-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    _capture_read_only(
        (*argv, "--snapshot"),
        stem=f"{first_number + 3:02d}-{slug}-snapshot-verification",
        expected=(
            "EXACT PREWARM",
            f"MEMORIES {left_count} + {right_count}",
            f"RELATIONS {relations}",
        ),
    )
    return elapsed


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.application.operations.profiles.profile.config import load_profile_registry

    if load_profile_registry().active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")
    provider_events_before = _provider_event_count()
    timings: dict[str, float] = {}
    for left, right, left_count, right_count, relations, first_number in PAIRS:
        timings[f"{left}-{right}"] = _capture_pair(
            left,
            right,
            left_count,
            right_count,
            relations,
            first_number,
        )

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Task 3 year Compare replay contacted a provider.")
    _capture_read_only(
        ("log", "--actions", "--limit", "30"),
        stem="69-task3-year-compares-action-log",
        expected=("operation=compare", "COMMAND_FINISHED"),
    )
    (OUT / "task3-year-compares-replay-metrics.json").write_text(
        json.dumps(
            {
                "profile": PROFILE_NAME,
                "pairs": [
                    {
                        "years": [left, right],
                        "input_memories": [left_count, right_count],
                        "relations": relations,
                        "elapsed_to_report_seconds": timings[f"{left}-{right}"],
                        "origin": "EXACT_PREWARM",
                    }
                    for (
                        left,
                        right,
                        left_count,
                        right_count,
                        relations,
                        _first_number,
                    ) in PAIRS
                ],
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
