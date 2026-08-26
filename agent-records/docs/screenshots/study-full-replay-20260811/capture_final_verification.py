"""Capture and verify the complete fresh Study replay."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from capture_init_study import OUT, PROFILE_NAME, ROOT, _capture_read_only
from capture_task1_directional_meld import _load_scopes, _memory_count
from capture_task3_sever import _bindings, _provider_event_count


def _timings(value: object, *, path: str = "") -> dict[str, float]:
    found: dict[str, float] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if key.endswith("_seconds") and isinstance(child, (int, float)):
                found[child_path] = float(child)
            else:
                found.update(_timings(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.update(_timings(child, path=f"{path}[{index}]"))
    return found


def _metric_files() -> tuple[Path, ...]:
    return tuple(sorted(OUT.glob("*-replay-metrics.json")))


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.context_targeting.loading import load_context_scope
    from memcommit.profile_config import load_profile_registry
    from memcommit.sever_store import SeverSessionStore
    from memcommit.store import MemoryStore

    registry = load_profile_registry()
    if registry.active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")

    _capture_read_only(
        ("profile", "current"),
        stem="114-final-profile-verification",
        expected=(
            f"Profile: {PROFILE_NAME}",
            "Current Context: practice/source-atomized",
        ),
    )
    _capture_read_only(
        ("status",),
        stem="115-final-current-context-verification",
        expected=(
            "On context: practice/source-atomized",
            "Memories 8",
            "Applied atomize",
        ),
    )
    _capture_read_only(
        ("log", "--operations", "--limit", "20"),
        stem="116-final-action-log",
        expected=(
            "Operation attempts · recent first",
            "COMPLETED   sever",
            "COMPLETED   redo",
            "SEVER · task-3/local/personal-memory (300)",
        ),
    )

    store = MemoryStore(create=False)
    if store.current_context_name() != "practice/source-atomized":
        raise RuntimeError("Fresh replay did not restore its current Context.")

    task1_store, (task1_incoming, task1_baseline) = _load_scopes()
    if task1_store.store_dir != store.store_dir:
        raise RuntimeError("Task 1 verification crossed Profile stores.")
    _, sever_source, sever_criteria = _bindings()

    local_recursive_names = {
        "task2_result": "task-2/participant/symmetric-replay-result",
        "task3_year_2024_2025": "task-3/participant/year-meld-2024-2025",
        "task3_year_2024_2026": "task-3/participant/year-meld-2024-2026",
        "task3_year_2025_2026": "task-3/participant/year-meld-2025-2026",
        "task3_rule_result": "task-3/participant/rule-meld-replay-result",
        "task3_sever_result": "task-3/participant/subtractive-first",
    }
    final_counts = {
        "tutorial_atomized": len(tuple(store.load_direct("practice/source-atomized").iter_items())),
        "task1_incoming": _memory_count(task1_incoming),
        "task1_baseline_after_directional_meld": _memory_count(task1_baseline),
        "task1_symmetric_result": _memory_count(
            load_context_scope(
                store,
                "task-1/participant/symmetric-replay-result",
                include_descendants=True,
            )
        ),
        "task3_sever_source": len(sever_source.memories),
        "task3_sever_criteria": len(sever_criteria.memories),
    }
    for label, name in local_recursive_names.items():
        final_counts[label] = _memory_count(
            load_context_scope(store, name, include_descendants=True)
        )
    expected_counts = {
        "tutorial_atomized": 8,
        "task1_incoming": 75,
        "task1_baseline_after_directional_meld": 375,
        "task1_symmetric_result": 375,
        "task2_result": 249,
        "task3_year_2024_2025": 240,
        "task3_year_2024_2026": 180,
        "task3_year_2025_2026": 174,
        "task3_rule_result": 100,
        "task3_sever_source": 300,
        "task3_sever_criteria": 75,
        "task3_sever_result": 0,
    }
    if final_counts != expected_counts:
        raise RuntimeError(
            f"Fresh replay final counts differ: {final_counts!r}."
        )

    metric_files = _metric_files()
    if len(metric_files) != 11:
        raise RuntimeError(f"Expected 11 replay metric files, got {len(metric_files)}.")
    timings: dict[str, float] = {}
    metric_provider_fields: dict[str, int] = {}
    for metric_file in metric_files:
        payload = json.loads(metric_file.read_text(encoding="utf-8"))
        timings.update(
            {
                f"{metric_file.stem}.{key}": value
                for key, value in _timings(payload).items()
            }
        )
        for key in ("provider_events_before", "provider_events_after"):
            value = payload.get(key)
            if not isinstance(value, int):
                raise RuntimeError(f"{metric_file.name} has no integer {key}.")
            metric_provider_fields[f"{metric_file.stem}.{key}"] = value
    if not timings or max(timings.values()) >= 30:
        raise RuntimeError("At least one recorded foreground stage exceeds 30 seconds.")
    if any(metric_provider_fields.values()) or _provider_event_count() != 0:
        raise RuntimeError("Fresh replay recorded a semantic provider event.")

    sever_sessions = [
        session
        for session in SeverSessionStore(store).list()
        if session.output_name == "task-3/participant/subtractive-first"
    ]
    if len(sever_sessions) != 1 or sever_sessions[0].state != "APPLIED":
        raise RuntimeError("Task 3 Sever did not retain one applied participant session.")

    expected_numbers = set(range(1, 117))
    capture_numbers = {
        int(path.name.split("-", 1)[0])
        for path in OUT.glob("*.png")
        if path.name.split("-", 1)[0].isdigit()
    }
    if capture_numbers != expected_numbers:
        raise RuntimeError(
            f"Replay capture sequence differs: {sorted(capture_numbers)!r}."
        )
    for number in expected_numbers:
        pngs = tuple(OUT.glob(f"{number:02d}-*.png"))
        if number >= 100:
            pngs = tuple(OUT.glob(f"{number}-*.png"))
        if len(pngs) != 1:
            raise RuntimeError(f"Capture {number} is missing or duplicated.")
        for suffix in (".txt", ".typescript"):
            if not pngs[0].with_suffix(suffix).is_file():
                raise RuntimeError(f"Capture {number} lacks {suffix} evidence.")

    summary = {
        "profile": PROFILE_NAME,
        "current_context": store.current_context_name(),
        "capture_count": 116,
        "capture_range": [1, 116],
        "metric_files": [path.name for path in metric_files],
        "foreground_threshold_seconds": 30,
        "maximum_recorded_foreground_seconds": max(timings.values()),
        "all_recorded_foreground_stages_under_threshold": True,
        "foreground_timings_seconds": timings,
        "provider_event_count": 0,
        "metric_provider_fields": metric_provider_fields,
        "final_memory_counts": final_counts,
        "task3_sever_session_uid": sever_sessions[0].uid,
        "task3_sever_source_frame_digest": sever_source.frame_digest,
    }
    (OUT / "full-replay-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
