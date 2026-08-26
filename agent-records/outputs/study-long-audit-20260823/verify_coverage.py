from __future__ import annotations

import json
from pathlib import Path

WORLDS = {
    "task-1",
    "task-2",
    "task-3",
    "ticker",
    "a-is-apple",
    "practice-source",
}
OPERATIONS = {
    "add", "atomize", "audit", "branch", "checkout", "checkpoint",
    "check-conformance", "chunk", "clear", "compare", "copy", "config",
    "contexts", "delete", "diff", "distill", "elaborate", "edit", "replace",
    "embed", "eval", "find", "search", "fit", "resolve", "dedup", "dedun",
    "find-ambiguities", "find-conflicts", "find-duplicates",
    "find-redundancies", "forget", "ground", "help", "impact", "import",
    "init", "init-study", "list", "lock", "log", "meld", "merge", "move",
    "profile", "provider", "pwd", "query", "rationale", "redo", "reference",
    "rename", "revert", "review", "sever", "share", "shell-init", "show",
    "status", "summarize", "switch", "trace", "translate", "undo", "unlock",
    "update",
}
REQUIRED_ATTEMPTS = 5
PHASE_OPERATIONS = {
    "core": {
        "contexts", "list", "show", "find", "search", "query", "summarize",
        "add", "copy", "reference", "embed", "edit", "move", "replace",
        "chunk", "compare", "find-duplicates", "find-redundancies",
        "find-ambiguities", "find-conflicts", "fit",
    },
    "transform": {
        "atomize", "audit", "checkpoint", "check-conformance", "clear",
        "delete", "diff", "distill", "elaborate", "resolve", "dedup", "dedun",
        "forget", "ground", "impact", "meld", "merge", "rationale", "revert",
        "review", "sever", "trace", "translate", "update",
    },
    "admin": {
        "status", "branch", "checkout", "config", "eval", "help", "import",
        "init", "init-study", "lock", "log", "profile", "provider", "pwd",
        "redo", "rename", "share", "shell-init", "switch", "undo", "unlock",
    },
}
REQUIRED_FIELDS = {
    "command", "exit", "starting_state", "entry_route", "target_route", "scope",
    "input_provenance", "consumer", "actual", "defect_ids", "cost",
}
DIVERSITY_FIELDS = (
    "entry_route", "target_route", "scope", "input_provenance", "starting_state",
)
FROZEN_LAUNCHER = (
    "env PYTHONDONTWRITEBYTECODE=1 "
    "PYTHONPATH=/Users/KimMunyeong/.codex/audit-snapshots/"
    "memcommit-study-long-audit-20260823-code python -m memcommit.cli "
)
TRANSITION_FROZEN_MARKER = (
    "PYTHONPATH=/tmp/memcommit-study-long-audit-20260823-code.yfgwbK "
    "python -m memcommit.cli "
)


def validate_attempt(
    path: Path,
    phase: str,
    operation: str,
    attempt: dict[str, object],
    errors: list[str],
) -> None:
    missing_fields = sorted(REQUIRED_FIELDS - attempt.keys())
    if missing_fields:
        errors.append(
            f"{path.name}: {operation} attempt missing fields {missing_fields}"
        )
    for field in REQUIRED_FIELDS - {"exit", "defect_ids", "cost"}:
        value = attempt.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(
                f"{path.name}: {operation} attempt has empty/non-text {field}"
            )
    if not isinstance(attempt.get("exit"), int):
        errors.append(f"{path.name}: {operation} attempt exit is not an integer")
    if not isinstance(attempt.get("defect_ids"), list):
        errors.append(f"{path.name}: {operation} attempt defect_ids is not a list")
    cost = attempt.get("cost")
    if not (
        (isinstance(cost, str) and cost.strip())
        or (isinstance(cost, (dict, list)) and bool(cost))
    ):
        errors.append(f"{path.name}: {operation} attempt cost is empty")
    command = attempt.get("command")
    if isinstance(command, str):
        if phase in {"transform", "admin"} and FROZEN_LAUNCHER not in command:
            errors.append(
                f"{path.name}: {operation} attempt did not use the frozen launcher"
            )
        elif phase == "core" and not (
            command.startswith("mem ")
            or FROZEN_LAUNCHER in command
            or TRANSITION_FROZEN_MARKER in command
        ):
            errors.append(
                f"{path.name}: {operation} attempt has an unknown command launcher"
            )


def main() -> int:
    root = Path(__file__).resolve().parent
    counts = {(world, operation): 0 for world in WORLDS for operation in OPERATIONS}
    errors: list[str] = []
    seen_ledgers: set[tuple[str, str]] = set()
    for path in sorted(root.glob("worlds/*/phase-*.json")):
        try:
            payload = json.loads(path.read_text())
        except Exception as error:  # noqa: BLE001 - audit verifier reports malformed evidence
            errors.append(f"{path.name}: invalid JSON: {error}")
            continue
        world = payload.get("world")
        if world not in WORLDS:
            errors.append(f"{path.name}: unknown world {world!r}")
            continue
        if path.parent.name != world:
            errors.append(
                f"{path.name}: payload world {world!r} does not match directory "
                f"{path.parent.name!r}"
            )
        phase = payload.get("phase")
        expected_phase = path.stem.removeprefix("phase-")
        if phase not in PHASE_OPERATIONS:
            errors.append(f"{path.name}: unknown phase {phase!r}")
            continue
        if phase != expected_phase:
            errors.append(
                f"{path.name}: payload phase {phase!r} does not match filename "
                f"{expected_phase!r}"
            )
        ledger_identity = (world, phase)
        if ledger_identity in seen_ledgers:
            errors.append(f"{path.name}: duplicate ledger for {world} {phase}")
        seen_ledgers.add(ledger_identity)
        phase_attempts: dict[str, list[dict[str, object]]] = {}
        operations = payload.get("operations")
        if isinstance(operations, dict):
            for operation, record in operations.items():
                if operation not in OPERATIONS:
                    errors.append(f"{path.name}: unknown operation {operation!r}")
                    continue
                attempts = record.get("attempts", [])
                if not isinstance(attempts, list):
                    errors.append(f"{path.name}: {operation} attempts is not a list")
                    continue
                seen = {attempt.get("attempt") for attempt in attempts}
                if len(seen) != len(attempts):
                    errors.append(
                        f"{path.name}: duplicate attempt number for {operation}"
                    )
                phase_attempts[operation] = attempts
        else:
            trials = payload.get("trials")
            if not isinstance(trials, list):
                errors.append(f"{path.name}: missing operations map or trials list")
                continue
            for trial in trials:
                operation = trial.get("operation")
                if operation not in OPERATIONS:
                    errors.append(f"{path.name}: unknown operation {operation!r}")
                    continue
                phase_attempts.setdefault(operation, []).append(trial)

        present_operations = set(phase_attempts)
        expected_operations = PHASE_OPERATIONS[phase]
        missing_operations = sorted(expected_operations - present_operations)
        extra_operations = sorted(present_operations - expected_operations)
        if missing_operations:
            errors.append(f"{path.name}: phase missing operations {missing_operations}")
        if extra_operations:
            errors.append(f"{path.name}: operations belong to another phase {extra_operations}")

        for operation, attempts in phase_attempts.items():
            attempt_ids = [attempt.get("attempt", attempt.get("round")) for attempt in attempts]
            if set(attempt_ids) != set(range(1, REQUIRED_ATTEMPTS + 1)):
                errors.append(
                    f"{path.name}: {operation} attempt IDs are {attempt_ids!r}, expected 1..5"
                )
            if len(attempts) != REQUIRED_ATTEMPTS:
                errors.append(
                    f"{path.name}: {operation} has {len(attempts)} attempts, expected 5"
                )
            signatures = {
                tuple(str(attempt.get(field, "")) for field in DIVERSITY_FIELDS)
                for attempt in attempts
            }
            if len(signatures) != len(attempts):
                errors.append(
                    f"{path.name}: {operation} repeats a five-method signature"
                )
            for attempt in attempts:
                validate_attempt(path, phase, operation, attempt, errors)
            counts[(world, operation)] += len(attempts)

    missing = [
        (world, operation, count)
        for (world, operation), count in sorted(counts.items())
        if count < REQUIRED_ATTEMPTS
    ]
    over = [
        (world, operation, count)
        for (world, operation), count in sorted(counts.items())
        if count > REQUIRED_ATTEMPTS
    ]
    total = sum(counts.values())
    print(f"recorded={total}/1980 complete_cells={len(counts) - len(missing)}/396")
    for error in errors:
        print(f"ERROR {error}")
    for world, operation, count in missing:
        print(f"MISSING {world} {operation} {count}/5")
    for world, operation, count in over:
        print(f"OVER {world} {operation} {count}/5")
    return 1 if errors or missing or over else 0


if __name__ == "__main__":
    raise SystemExit(main())
