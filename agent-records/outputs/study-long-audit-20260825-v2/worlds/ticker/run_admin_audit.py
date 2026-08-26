#!/usr/bin/env python3
"""Run the 105 counted ticker ADMIN attempts in the cumulative frozen lane.

Only subprocesses launched through ``run_world_mem.py ticker`` are counted
mem calls.  Every other observation in this harness is a host filesystem read
or a host shell syntax/source consumer.  The supplemental mistaken ``-h``
preflight is recorded separately and is never counted here.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from typing import Callable


WORLD_NAME = "ticker"
REPO = Path("/Users/KimMunyeong/Github/memcommit")
AUDIT = REPO / "agent-records/outputs/study-long-audit-20260825-v2"
WORLD = AUDIT / "worlds/ticker"
RAW = WORLD / "raw/admin"
HOST = WORLD / "host_reads/admin"
PHASE = WORLD / "phase-admin.json"
SUPPLEMENTAL = WORLD / "supplemental-admin-preflight.json"
TRANSFORM = WORLD / "phase-transform.json"
RUNNER = AUDIT / "run_world_mem.py"
LANE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/"
    "worlds/ticker"
)
PROFILE_CONTROL = LANE / "profile-control"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROFILE_NAME = "sixworld-v2-template"
STORE = PROFILE_CONTROL / "stores" / PROFILE_UID
REGISTRY = PROFILE_CONTROL / "registry.json"
COMMAND_ATTEMPTS = STORE / "ledger/command-attempts"
CODE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-snapshots/"
    "memcommit-six-world-v2-20260825-code"
)
EVAL_LEDGER = LANE / "admin-eval-ledger"

CODE_SHA = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROVIDER_SHA = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"

C = "audit/ticker/admin-v2-scratch"
R = "task-1/participant/construction-updates"
R_CHILD = "task-1/participant/construction-updates/building-access"
O = "task-2/participant"
O_CHILD = "task-2/participant/proposal-workspace"
ENTRY = "practice"
IMPORT_PROFILE = "task-1"
IMPORT_CONTEXT = "participant/construction-updates"
IMPORT_MEMORY_CONTEXT = "participant/construction-updates/shop-updates"
IMPORT_MEMORY_UID = "37113bd0-5194-521b-9d9e-48903d819520"
ENDPOINT = "task-3/government/healthcare-agent"
INACTIVE_PROFILE = "admin-v2-ticker-inactive"

OPERATIONS = (
    "status", "branch", "checkout", "config", "eval", "help", "import",
    "init", "init-study", "lock", "log", "profile", "provider", "pwd",
    "redo", "rename", "share", "shell-init", "switch", "undo", "unlock",
)


@dataclass(frozen=True)
class Spec:
    operation: str
    attempt: int
    args: tuple[str, ...] | Callable[[], tuple[str, ...]]
    method: str
    target_route: str
    scope: str
    provenance: str
    expected: str
    targets: tuple[str, ...] = ()
    stdin: str | None = None


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def context_path(name: str) -> Path:
    return STORE / "contexts" / Path(*name.split("/")) / "context.json"


def current_identity() -> dict[str, str | None]:
    registry = read_json(REGISTRY)
    active_uid = registry.get("active_uid")
    active = next(
        (item for item in registry.get("profiles", ()) if item.get("uid") == active_uid),
        {},
    )
    resolved = (PROFILE_CONTROL / "stores" / str(active_uid)).resolve()
    current = read_json(STORE / "state.json").get("current")
    current_file = context_path(current) if isinstance(current, str) else None
    current_uid = (
        read_json(current_file).get("uid")
        if current_file is not None and current_file.is_file()
        else None
    )
    return {
        "profile_name": active.get("name"),
        "profile_uid": active_uid,
        "resolved_store": str(resolved),
        "current_context": current,
        "current_context_uid": current_uid,
    }


def assert_identity(*, sequence: int, position: str, label: str) -> tuple[dict, Path]:
    actual = current_identity()
    expected = {
        "profile_name": PROFILE_NAME,
        "profile_uid": PROFILE_UID,
        "resolved_store": str(STORE.resolve()),
    }
    matches = all(actual[key] == value for key, value in expected.items())
    evidence = {
        "sequence": sequence,
        "position": position,
        "label": label,
        "read_at": datetime.now(timezone.utc).isoformat(),
        "actual": actual,
        "expected": expected,
        "matches": matches,
    }
    path = HOST / f"identity-{sequence:03d}-{position}.json"
    write_json(path, evidence)
    if not matches:
        raise RuntimeError(f"Pinned Profile identity drift at {label}: {actual}")
    return actual, path


def context_tree_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted((STORE / "contexts").rglob("context.json")):
        digest.update(path.relative_to(STORE).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(b"state.json\0")
    digest.update((STORE / "state.json").read_bytes())
    return digest.hexdigest()


def selected_digest(names: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for name in sorted(set(names)):
        path = context_path(name)
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<absent>")
        digest.update(b"\0")
    return digest.hexdigest()


def subtree_digest(root_name: str) -> str:
    digest = hashlib.sha256()
    prefix = root_name + "/"
    names = []
    for path in (STORE / "contexts").rglob("context.json"):
        value = read_json(path)
        name = value.get("name")
        if name == root_name or isinstance(name, str) and name.startswith(prefix):
            names.append((str(name), path))
    for name, path in sorted(names):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def branch_checkpoint_precondition(
    *, sequence: int, label: str, root_name: str, recursive: bool,
    require_disjoint: bool = True,
) -> tuple[dict, Path]:
    """Prove a Branch/checkout -b Source does not retain Branch receipts."""
    names: list[str] = []
    branch_checkpoints: list[dict[str, str]] = []
    direct_item_counts: dict[str, int] = {}
    prefix = root_name + "/"
    for path in sorted((STORE / "contexts").rglob("context.json")):
        value = read_json(path)
        name = value.get("name")
        if name != root_name and not (
            recursive and isinstance(name, str) and name.startswith(prefix)
        ):
            continue
        names.append(str(name))
        direct_item_counts[str(name)] = len(value.get("order", ()))
        for checkpoint in sorted((path.parent / "checkpoints").glob("*.json")):
            try:
                saved = read_json(checkpoint)
            except (OSError, ValueError):
                continue
            args = saved.get("args")
            if isinstance(args, dict) and "branch_tree" in args:
                branch_checkpoints.append(
                    {
                        "context": str(name),
                        "checkpoint": str(checkpoint.relative_to(STORE)),
                        "operation_uid": str(args.get("branch_tree", {}).get("operation_uid")),
                    }
                )
    evidence = {
        "sequence": sequence,
        "label": label,
        "read_at": datetime.now(timezone.utc).isoformat(),
        "source_root": root_name,
        "recursive": recursive,
        "lexically_disjoint_from_scratch": not (
            root_name == C or root_name.startswith(C + "/") or C.startswith(root_name + "/")
        ),
        "resolved_context_names": names,
        "direct_item_counts": direct_item_counts,
        "retained_branch_checkpoint_count": len(branch_checkpoints),
        "retained_branch_checkpoints": branch_checkpoints,
        "result": "PASS" if names and not branch_checkpoints else "FAIL",
    }
    safe_label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", label).strip("-").lower()
    path = HOST / f"source-precondition-{sequence:03d}-{safe_label}.json"
    write_json(path, evidence)
    if not names or branch_checkpoints or (
        require_disjoint and not evidence["lexically_disjoint_from_scratch"]
    ):
        raise RuntimeError(f"Unsafe Branch source precondition at {label}: {evidence}")
    return evidence, path


def profile_universe_delivery_digest() -> str:
    """Hash delivery-visible Profile/Context state, excluding audit ledgers."""
    digest = hashlib.sha256()
    paths: list[Path] = [REGISTRY]
    stores = PROFILE_CONTROL / "stores"
    for root in sorted(path for path in stores.iterdir() if path.is_dir()):
        for fixed in ("state.json", "write-protection.json"):
            path = root / fixed
            if path.is_file():
                paths.append(path)
        contexts = root / "contexts"
        if contexts.is_dir():
            paths.extend(path for path in contexts.rglob("*") if path.is_file() and not path.name.endswith(".lock"))
    for path in sorted(set(paths)):
        digest.update(path.relative_to(PROFILE_CONTROL).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def command_attempt_snapshot() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in COMMAND_ATTEMPTS.glob("*.json"):
        try:
            value = read_json(path)
        except (OSError, ValueError):
            continue
        result[path.stem] = value
    return result


def stack_snapshot(
    label: str,
    *,
    expected_side: str | None = None,
    expected_uid: str | None = None,
    expected_command: str | None = None,
    require_granted_null: bool = False,
) -> tuple[dict, Path]:
    if str(CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(CODE_ROOT))
    from memcommit.command_history import build_command_stacks
    from memcommit.store import MemoryStore

    stacks = build_command_stacks(
        MemoryStore(root=STORE, create=False, resolve_granted_links=False)
    )

    def unit(value) -> dict | None:
        if value is None:
            return None
        return {
            "uid": value.uid,
            "command": value.command,
            "description": value.description,
            "members": [
                {
                    "context_uid": change.context_uid,
                    "context_name": change.context_name,
                    "checkpoint_uid": change.checkpoint_uid,
                }
                for change in value.changes
            ],
        }

    staged_path = STORE / "staged-update.json"
    staged = read_json(staged_path) if staged_path.is_file() else None
    granted = staged.get("granted_target") if isinstance(staged, dict) else None
    value = {
        "label": label,
        "read_at": datetime.now(timezone.utc).isoformat(),
        "undo_top": unit(stacks.undo[-1] if stacks.undo else None),
        "redo_top": unit(stacks.redo[-1] if stacks.redo else None),
        "undo_depth": len(stacks.undo),
        "redo_depth": len(stacks.redo),
        "staged_update_granted_target": granted,
        "assertions": {
            "expected_side": expected_side,
            "expected_uid": expected_uid,
            "expected_command": expected_command,
            "require_granted_null": require_granted_null,
        },
    }
    if expected_side is not None:
        top = value[f"{expected_side}_top"]
        if top is None:
            raise RuntimeError(f"{label}: {expected_side} stack is empty")
        if expected_uid is not None and top["uid"] != expected_uid:
            raise RuntimeError(f"{label}: expected {expected_uid}, got {top['uid']}")
        if expected_command is not None and top["command"] != expected_command:
            raise RuntimeError(f"{label}: expected {expected_command}, got {top['command']}")
    if require_granted_null and granted is not None:
        raise RuntimeError(f"{label}: staged-update.granted_target is not null")
    value["assertions"]["result"] = "PASS"
    safe_label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", label).strip("-").lower()
    path = HOST / f"stack-{safe_label}.json"
    write_json(path, value)
    return value, path


def compact(stdout: str, stderr: str, exit_code: int) -> str:
    clean = re.sub(
        r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", stdout + "\n" + stderr
    ).replace("\r", "")
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if not lines:
        return f"Exit {exit_code}; no stdout/stderr text."
    chosen = lines if len(lines) <= 10 else lines[:8] + [f"… ({len(lines)} lines)"]
    return (f"Exit {exit_code}. " + " | ".join(chosen))[:3200]


def expected_for(operation: str, attempt: int) -> str:
    common = {
        "status": "Report only the requested orientation/scope; incompatible flags fail without mutation.",
        "branch": "Create only the declared undoable scratch branch, or reject collision/missing Source atomically.",
        "checkout": "Switch exactly or create only the declared -b branch; missing targets fail safely.",
        "config": "Read or update only lane configuration; a missing value fails before mutation.",
        "eval": "Use only the lane-local Eval ledger; one provider case is run and its full ID is checked.",
        "help": "Use local catalog/exact lookup except one synthetic lookup; copied-description guard fails before provider.",
        "import": "Copy only registered source evidence by value; collision or missing Profile fails without mutation.",
        "init": "Create only declared scratch names; collisions and invalid/missing-parent cases fail safely.",
        "init-study": "Create/activate zero Studies or Profiles and preserve the frozen active identity.",
        "lock": "Protect exactly the declared current, tree, Memory, Context, or whole-Profile boundary.",
        "log": "Render only the requested bounded history without mutation.",
        "profile": "Inspect/create inactive/use same active, or reject missing Profile without active identity drift.",
        "provider": "Inspect frozen Study routes, reject mutation, or run the single bounded probe.",
        "pwd": "Print the canonical current Context without mutation.",
        "redo": "Redo the exact host-verified unit, except the deliberate empty-stack boundary.",
        "rename": "Rename only scratch state; protected and declined routes publish no rename.",
        "share": "Stop before delivery and preserve the complete Profile Context universe digest.",
        "shell-init": "Emit stable zsh integration or reject bash; host consumers never invoke mem.",
        "switch": "Move only the current pointer through the declared navigation/exact route.",
        "undo": "Undo only the host-verified local Branch/Checkout unit with granted_target null; lock failure is atomic.",
        "unlock": "Remove exactly the paired protection boundary.",
    }[operation]
    return f"{common} ADMIN method M{attempt}."


EVAL_RUN_ID = ""


def specs() -> list[Spec]:
    by: dict[tuple[str, int], Spec] = {}

    def add(
        operation: str,
        attempt: int,
        args: tuple[str, ...] | Callable[[], tuple[str, ...]],
        method: str,
        target: str,
        scope: str,
        provenance: str,
        targets: tuple[str, ...] = (),
        stdin: str | None = None,
    ) -> None:
        by[(operation, attempt)] = Spec(
            operation, attempt, args, method, target, scope, provenance,
            expected_for(operation, attempt), targets, stdin,
        )

    status_args = [
        ("status", "--short"), ("status", "--branch"),
        ("status", "--recursive"), ("status", "--direct", "--recursive"),
        ("status",),
    ]
    for i, args in enumerate(status_args, 1):
        add("status", i, args, f"status projection M{i}: {shlex.join(args)}",
            f"round-{i} current Context", f"orientation projection variant {i}",
            f"cumulative ADMIN transaction state after round-{i} producers", ())

    branch_args = [
        ("branch", f"{C}/b1", "--from", R, "--direct"),
        ("branch", f"{C}/b2-tree", "--from", R, "--recursive"),
        ("branch", f"{C}/b3", "--from", R, "--source-root-only"),
        ("branch", C, "--from", R, "--direct"),
        ("branch", f"{C}/b5", "--from", "audit/ticker/admin-v2-missing-source", "--direct"),
    ]
    for i, args in enumerate(branch_args, 1):
        add("branch", i, args, f"branch method M{i}: {shlex.join(args)}", args[1],
            "direct Source" if i in {1, 4, 5} else "recursive Source tree" if i == 2 else "source-root-only live branch",
            f"checkpoint-free exact Source route for round {i}; M3 target was deliberately precreated by positive-control Rename2 so it collision-fails without becoming the Checkout3 Source; M4 collision and M5 missing Source are negative boundaries",
            (args[1], args[3]))

    checkout_args = [
        ("checkout", R), ("checkout", ".."),
        ("checkout", "-b", f"{C}/co3", "--direct"),
        ("checkout", "-b", f"{C}/co4-tree", "--recursive"),
        ("checkout", "audit/ticker/admin-v2-missing-target"),
    ]
    for i, args in enumerate(checkout_args, 1):
        add("checkout", i, args, f"checkout method M{i}: {shlex.join(args)}",
            args[2] if i in {3, 4} else args[1],
            "exact switch" if i in {1, 2, 5} else "direct branch checkout" if i == 3 else "recursive branch checkout",
            f"frozen current Context locator snapshot in round {i}",
            ((args[2],) if i in {3, 4} else (args[1],)))

    config_args = [
        ("config",), ("config", "set", "audit_v2_world", WORLD_NAME),
        ("config", "show"), ("config", "set", "provider", "codex_chatgpt"),
        ("config", "set", "provider"),
    ]
    for i, args in enumerate(config_args, 1):
        add("config", i, args, f"config method M{i}: {shlex.join(args)}", "lane-local config",
            f"config read/write/validation variant {i}", f"ticker lane configuration round {i}")

    eval_args: list[tuple[str, ...] | Callable[[], tuple[str, ...]]] = [
        ("eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)),
        ("eval", "semantic", "run", "ambiguity", "--provider", "codex_chatgpt",
         "--model", "gpt-5.6-sol", "--reasoning", "none", "--pipeline", "v2",
         "--corpus", "calibration", "--runs", "1", "--case",
         "single-none-main-entrance-hours", "--ledger-dir", str(EVAL_LEDGER)),
        lambda: ("eval", "semantic", "check", EVAL_RUN_ID, "--ledger-dir", str(EVAL_LEDGER)),
        ("eval", "semantic", "task2-status", "--all", "--ledger-dir", str(EVAL_LEDGER)),
        ("eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)),
    ]
    for i, args in enumerate(eval_args, 1):
        add("eval", i, args, f"Eval ledger method M{i}", str(EVAL_LEDGER),
            f"semantic Eval scope {i}",
            "one bounded provider ambiguity case" if i == 2 else f"host/lane-local Eval evidence round {i}")

    help_args = [
        ("help",),
        ("help", "How do I inspect where I am and what the current Context contains?"),
        ("help", "query"), ("help", "update"),
        ("help", "Show the current Context's inventory, first five direct Memories, relationships, and latest checkpoints."),
    ]
    for i, args in enumerate(help_args, 1):
        add("help", i, args, f"Help method M{i}: {shlex.join(args)}", "frozen operation catalog",
            f"inventory/exact/provider-guard lookup {i}",
            "single synthetic natural-language provider lookup" if i == 2 else f"local catalog or copied-description guard round {i}")

    import_args = [
        ("import", "context", f"{IMPORT_CONTEXT}/shop-updates", "--from-profile", IMPORT_PROFILE,
         "--as", f"{C}/import-direct", "--direct"),
        ("import", "context", IMPORT_CONTEXT, "--from-profile", IMPORT_PROFILE,
         "--as", f"{C}/import-tree", "--recursive"),
        ("import", "memory", IMPORT_MEMORY_UID, "--from-profile", IMPORT_PROFILE,
         "--context", IMPORT_MEMORY_CONTEXT, "--into", C),
        ("import", "memory", IMPORT_MEMORY_UID, "--from-profile", IMPORT_PROFILE,
         "--context", IMPORT_MEMORY_CONTEXT, "--into", C),
        ("import", "context", IMPORT_CONTEXT, "--from-profile", "admin-v2-ticker-missing-profile",
         "--as", f"{C}/import-missing", "--direct"),
    ]
    for i, args in enumerate(import_args, 1):
        target = f"{C}/import-direct" if i == 1 else f"{C}/import-tree" if i == 2 else C if i in {3, 4} else f"{C}/import-missing"
        add("import", i, args, f"Import method M{i}: {shlex.join(args)}", target,
            "direct Context" if i == 1 else "recursive Context tree" if i == 2 else "exact Memory" if i in {3, 4} else "missing source Profile",
            f"registered task-1 source evidence; repeat collision only M4; absent Profile M5",
            (target,))

    init_args = [
        ("init", C), ("init", f"{C}/tree/leaf", "--parents"), ("init", C),
        ("init", "00000000-0000-0000-0000-000000000001"),
        ("init", f"{C}/missing-parent/leaf"),
    ]
    for i, args in enumerate(init_args, 1):
        add("init", i, args, f"Init method M{i}: {shlex.join(args)}", args[1],
            f"creation/validation boundary {i}", f"lane-local scratch namespace round {i}",
            (args[1],))

    study_args = [
        ("init-study", "admin/v2/ticker"), ("init-study", "authoring"),
        ("init-study", "admin-v2-ticker-missing-baseline", "--scenario", "legacy-v1",
         "--from-profile", "admin-v2-missing-baseline"),
        ("init-study", "admin-v2-ticker-workers", "--prewarm-workers", "0"),
        ("init-study", "ticker/admin-v2-final"),
    ]
    for i, args in enumerate(study_args, 1):
        add("init-study", i, args, f"Init Study safe method M{i}: {shlex.join(args)}", args[1],
            f"pre-creation validation route {i}", f"deliberately invalid/reserved/missing Study request {i}")

    lock_args = [
        ("lock",), ("lock", f"{C}/b2-tree", "--recursive"),
        ("lock", "--memory", IMPORT_MEMORY_UID[:8], "--context", C),
        ("lock", f"{C}/co4-tree", "--recursive"), ("lock", "--profile"),
    ]
    unlock_args = [
        ("unlock",), ("unlock", f"{C}/b2-tree", "--recursive"),
        ("unlock", "--memory", IMPORT_MEMORY_UID[:8], "--context", C),
        ("unlock", f"{C}/co4-tree", "--recursive"), ("unlock", "--profile"),
    ]
    for operation, rows in (("lock", lock_args), ("unlock", unlock_args)):
        for i, args in enumerate(rows, 1):
            target = "frozen current Context" if i == 1 else f"{C}/b2-tree" if i == 2 else f"{C}:{IMPORT_MEMORY_UID[:8]}" if i == 3 else f"{C}/co4-tree" if i == 4 else PROFILE_NAME
            add(operation, i, args, f"{operation.title()} method M{i}: {shlex.join(args)}", target,
                "current Context" if i == 1 else "recursive tree" if i in {2, 4} else "exact imported Memory" if i == 3 else "whole active Profile",
                f"adjacent paired protection boundary round {i}",
                (() if i in {1, 5} else (f"{C}/b2-tree",) if i == 2 else (C,) if i == 3 else (f"{C}/co4-tree",)))

    log_args = [
        ("log", "--context", C), ("log", "--context", C, "--manual"),
        ("log", "--context", C, "--memory", IMPORT_MEMORY_UID[:8], "--limit", "5"),
        ("log", "--operations", "--limit", "50"),
        ("log", "--actions", "--limit", "100"),
    ]
    for i, args in enumerate(log_args, 1):
        add("log", i, args, f"Log method M{i}: {shlex.join(args)}", C if i <= 3 else "Profile audit ledger",
            f"history filter variant {i}", f"retained lane-local history after round-{i} mutations", (C,) if i <= 3 else ())

    profile_args = [
        ("profile", "current"), ("profile", "create", INACTIVE_PROFILE),
        ("profile", "list"), ("profile", "use", PROFILE_NAME),
        ("profile", "use", "admin-v2-ticker-missing"),
    ]
    for i, args in enumerate(profile_args, 1):
        add("profile", i, args, f"Profile method M{i}: {shlex.join(args)}",
            INACTIVE_PROFILE if i == 2 else PROFILE_NAME if i != 5 else "missing Profile",
            f"Profile control surface {i}", f"frozen active identity; inactive creation only in M2")

    provider_args = [
        ("provider",), ("provider", "status"),
        ("provider", "status", "--operation", "query"),
        ("provider", "use", "codex_chatgpt", "--operation", "query"),
        ("provider", "probe", "--operation", "query"),
    ]
    for i, args in enumerate(provider_args, 1):
        add("provider", i, args, f"Provider method M{i}: {shlex.join(args)}", "Query provider policy",
            f"provider status/mutation/probe variant {i}",
            "single bounded provider probe" if i == 5 else f"frozen Study provider route round {i}")

    for i in range(1, 6):
        add("pwd", i, ("pwd",), f"pwd method M{i} after round-{i} current-pointer transitions",
            f"round-{i} current Context", f"exact current pointer state {i}",
            f"distinct cumulative transaction state round {i}")

    for i in range(1, 6):
        add("undo", i, ("undo", "--keep") if i == 2 else ("undo",),
            f"Undo method M{i}: {'compatibility --keep' if i == 2 else 'exact stack top'}",
            f"round-{i} producer command unit", f"host-verified restore boundary {i}",
            f"exact host-read unit UID/member set and granted_target null before Undo {i}")
        add("redo", i, ("redo",),
            f"Redo method M{i}: {'empty-stack negative boundary' if i == 4 else 'exact prior Undo unit'}",
            f"round-{i} redo stack", f"host-verified redo boundary {i}",
            f"exact host-read redo top for round {i}")

    rename_args = [
        ("rename", f"{C}/import-direct", f"{C}/renamed-1", "--force"),
        ("rename", f"{C}/import-tree", f"{C}/b3", "--force"),
        ("rename", f"{C}/tree/leaf", f"{C}/co3", "--force"),
        ("rename", f"{C}/co4-tree", f"{C}/co4-locked-renamed", "--force"),
        ("rename", f"{C}/co4-tree", f"{C}/declined-5"),
    ]
    for i, args in enumerate(rename_args, 1):
        add("rename", i, args, f"Rename method M{i}: {shlex.join(args)}", f"{args[1]} → {args[2]}",
            "recursive import-created tree" if i == 2 else "protected tree negative" if i == 4 else "declined exact confirmation" if i == 5 else "init/import-created exact scratch Context",
            f"positive Rename M{i} is restricted to init/import-created scratch and never renames a Branch/checkout target; literal decline input only M5", (args[1], args[2]), "n\n" if i == 5 else None)

    share_args = [
        ("share",),
        ("share", "audit/ticker/missing-share-source", "--to", ENDPOINT, "--direct"),
        ("share", "--to", "audit/ticker/missing-receiver"),
        ("share", R, "--to", ENDPOINT, "--direct", "--recursive"),
        ("share", R, "--to", "task-3/missing-endpoint", "--direct"),
    ]
    for i, args in enumerate(share_args, 1):
        add("share", i, args, f"Share zero-delivery method M{i}: {shlex.join(args)}",
            "incomplete receiver" if i == 1 else args[args.index("--to") + 1],
            f"pre-delivery failure boundary {i}",
            f"complete Profile-universe delivery digest frozen before/after method {i}")

    shell_args = [
        ("shell-init",), ("shell-init", "zsh"), ("shell-init", "zsh"),
        ("shell-init", "zsh"), ("shell-init", "bash"),
    ]
    for i, args in enumerate(shell_args, 1):
        add("shell-init", i, args, f"Shell-init method M{i}: {shlex.join(args)}", "stdout shell integration",
            "default output" if i == 1 else "byte equality to M1" if i == 2 else "zsh -n host consumer" if i == 3 else "disposable source-only zsh consumer" if i == 4 else "unsupported bash validation",
            f"frozen generated shell integration round {i}")

    switch_args = [
        ("switch", "--previous"), ("switch", "--next"), ("switch", O),
        ("switch", f"{C}/co4-tree/proposal-workspace"), ("switch", ENTRY),
    ]
    for i, args in enumerate(switch_args, 1):
        add("switch", i, args, f"Switch method M{i}: {shlex.join(args)}", args[-1],
            f"transaction navigation variant {i}", f"frozen previous/next/exact Context route round {i}",
            (args[-1],) if not args[-1].startswith("--") else ())

    orders = [
        ["branch", "undo", "redo", "checkout", "lock", "unlock", "status", "config", "eval", "help", "init", "import", "rename", "init-study", "log", "profile", "provider", "pwd", "share", "shell-init", "switch"],
        ["switch", "status", "config", "eval", "help", "import", "init", "init-study", "log", "profile", "provider", "pwd", "share", "shell-init", "branch", "undo", "redo", "lock", "unlock", "rename", "checkout"],
        ["branch", "switch", "rename", "checkout", "undo", "redo", "status", "config", "eval", "help", "import", "lock", "unlock", "log", "profile", "provider", "pwd", "share", "shell-init", "init", "init-study"],
        ["redo", "branch", "status", "config", "eval", "help", "import", "init", "init-study", "log", "profile", "provider", "pwd", "share", "shell-init", "checkout", "switch", "lock", "rename", "undo", "unlock"],
        ["undo", "redo", "branch", "rename", "status", "checkout", "config", "eval", "help", "import", "init", "init-study", "lock", "unlock", "log", "profile", "provider", "pwd", "share", "shell-init", "switch"],
    ]
    result = [by[(operation, attempt)] for attempt, order in enumerate(orders, 1) for operation in order]
    if len(result) != 105 or len(by) != 105:
        raise RuntimeError("ADMIN specs do not satisfy 21×5")
    return result


def new_ledger(initial_digest: str, source_digest: str) -> dict:
    transform = read_json(TRANSFORM)
    transform_records = sorted(
        (record for payload in transform["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    transform_final = transform_records[-1]["post_target_digest"]
    supplemental = read_json(SUPPLEMENTAL)
    initial_attempt_count = len(command_attempt_snapshot())
    if initial_digest != transform_final:
        raise RuntimeError("Transform final → Admin initial digest continuity failed")
    if not supplemental.get("excluded_from_1980") or len(supplemental.get("calls", ())) != 21:
        raise RuntimeError("Supplemental Admin preflight ledger is absent or incomplete")
    return {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": WORLD_NAME,
        "phase": "admin",
        "status": "running",
        "contract": {"operations": 21, "attempts_per_operation": 5, "attempts": 105},
        "execution_identity": {
            "code_snapshot_sha256": CODE_SHA,
            "catalog_sha256": CATALOG_SHA,
            "profile_name": PROFILE_NAME,
            "profile_uid": PROFILE_UID,
            "store_root": str(STORE),
            "provider_policy_sha256": PROVIDER_SHA,
            "launcher": f"python {RUNNER} ticker",
        },
        "starting_boundary": {
            "cumulative_from_transform": True,
            "transform_final_tree_digest": transform_final,
            "admin_initial_tree_digest": initial_digest,
            "matching_boundary_digest": transform_final == initial_digest,
            "no_reset": True,
            "entry_current_context": ENTRY,
            "scratch_direct_set_verified_absent": True,
            "dedicated_ticker_context_missing": True,
            "clean_evidence_boundary": "Exact/direct ticker scratch routes and exact host identity/stack reads.",
            "noisy_boundary": "Recursive Branch exposure of borrowed task-3/local descendants is deliberate noisy-boundary evidence, not clean ticker semantics.",
            "supplemental_preflight_preceded_phase": True,
            "supplemental_preflight": str(SUPPLEMENTAL.relative_to(AUDIT)),
            "supplemental_preflight_excluded_from_1980": True,
            "supplemental_preflight_launcher_calls": 21,
            "supplemental_preflight_product_attempts": 20,
            "command_attempt_ledger_count_at_admin_start": initial_attempt_count,
            "methodology_limitation": supplemental["methodology_limitation"],
            "safety": "Share delivery zero; init-study success zero; lane-local Eval; exact host-read Undo/Redo UID/member sets; post-call Profile identity first-read after every call.",
        },
        "source_guard": {
            "root": R,
            "initial_subtree_digest": source_digest,
            "preserved": True,
        },
        "representative_tui_lane": False,
        "noninteractive_substitutes": True,
        "screenshots": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "transaction_units": {},
        "operations": {operation: {"attempts": []} for operation in OPERATIONS},
    }


def records(ledger: dict) -> list[dict]:
    return sorted(
        (record for payload in ledger["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )


def save(ledger: dict) -> None:
    write_json(PHASE, ledger)


def eval_run_from_files() -> tuple[str, str] | None:
    candidates: list[tuple[float, str, str]] = []
    for path in EVAL_LEDGER.rglob("*.json") if EVAL_LEDGER.exists() else ():
        try:
            value = read_json(path)
        except (OSError, ValueError):
            continue
        run_id = value.get("run_id") or value.get("full_run_id")
        if run_id:
            candidates.append((path.stat().st_mtime, str(run_id), str(path)))
    if not candidates:
        return None
    _, run_id, path = sorted(candidates)[-1]
    return run_id, path


def host_shell_check(attempt: int, stdout_path: Path, baseline_path: Path | None) -> dict | None:
    payload = stdout_path.read_text(encoding="utf-8")
    if attempt == 1:
        return {"baseline_stdout_sha256": hashlib.sha256(payload.encode()).hexdigest()}
    if attempt == 2:
        if baseline_path is None:
            raise RuntimeError("shell-init M1 stdout missing")
        baseline = baseline_path.read_bytes()
        current = stdout_path.read_bytes()
        if baseline != current:
            raise RuntimeError("shell-init M2 is not byte-equal to M1")
        return {"byte_equal_to_M1": True, "sha256": hashlib.sha256(current).hexdigest()}
    if attempt == 3:
        result = subprocess.run(["zsh", "-n"], input=payload, text=True, capture_output=True, check=False)
        evidence = {"host_command": "zsh -n", "exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        if result.returncode != 0:
            raise RuntimeError(f"zsh -n rejected shell-init output: {result.stderr}")
        return evidence
    if attempt == 4:
        result = subprocess.run(
            ["zsh", "-dfc", "source /dev/stdin; whence -w mem"],
            input=payload, text=True, capture_output=True, check=False,
        )
        evidence = {
            "host_command": "zsh -dfc source-only; whence -w mem",
            "mem_function_invoked": False,
            "exit": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if result.returncode != 0:
            raise RuntimeError(f"disposable source-only zsh rejected output: {result.stderr}")
        return evidence
    return None


def capture_transaction_after(
    ledger: dict, sequence: int, spec: Spec,
) -> list[str]:
    evidence: list[str] = []
    producer_labels = {
        ("branch", 1): "round1",
        ("branch", 2): "round2",
        ("checkout", 4): "round4",
    }
    label = producer_labels.get((spec.operation, spec.attempt))
    if label is not None:
        snapshot, path = stack_snapshot(
            f"{label}-producer-seq-{sequence:03d}", expected_side="undo",
            expected_command="branch",
        )
        unit = snapshot["undo_top"]
        ledger["transaction_units"][label] = unit
        evidence.append(str(path.relative_to(AUDIT)))
    if (spec.operation, spec.attempt) in {("undo", 1), ("undo", 2), ("undo", 3), ("undo", 5)}:
        label = f"round{spec.attempt}" if spec.attempt != 5 else "round4"
        expected = ledger["transaction_units"][label]["uid"]
        snapshot, path = stack_snapshot(
            f"after-undo-{spec.attempt}-seq-{sequence:03d}", expected_side="redo",
            expected_uid=expected, expected_command="branch",
        )
        del snapshot
        evidence.append(str(path.relative_to(AUDIT)))
    if (spec.operation, spec.attempt) == ("undo", 4):
        expected = ledger["transaction_units"]["round4"]["uid"]
        snapshot, path = stack_snapshot(
            f"after-protected-undo-4-seq-{sequence:03d}", expected_side="undo",
            expected_uid=expected, expected_command="branch",
        )
        del snapshot
        evidence.append(str(path.relative_to(AUDIT)))
    if (spec.operation, spec.attempt) == ("switch", 3):
        expected = ledger["transaction_units"]["round3"]["uid"]
        snapshot, path = stack_snapshot(
            f"after-switch-3-seq-{sequence:03d}", expected_side="undo",
            expected_uid=expected, expected_command="branch",
        )
        del snapshot
        evidence.append(str(path.relative_to(AUDIT)))
    if (spec.operation, spec.attempt) == ("switch", 4):
        expected = ledger["transaction_units"]["round4"]["uid"]
        snapshot, path = stack_snapshot(
            f"after-switch-4-seq-{sequence:03d}", expected_side="undo",
            expected_uid=expected, expected_command="branch",
        )
        del snapshot
        evidence.append(str(path.relative_to(AUDIT)))
    return evidence


def before_transaction(ledger: dict, sequence: int, spec: Spec) -> list[str]:
    evidence: list[str] = []
    if spec.operation == "undo":
        if spec.attempt in {1, 2, 3}:
            label = f"round{spec.attempt}"
        else:
            label = "round4"
        expected = ledger.get("transaction_units", {}).get(label, {}).get("uid")
        if expected is None:
            raise RuntimeError(f"Missing transaction unit for {label}")
        snapshot, path = stack_snapshot(
            f"before-undo-{spec.attempt}-seq-{sequence:03d}",
            expected_side="undo", expected_uid=expected,
            expected_command="branch", require_granted_null=True,
        )
        del snapshot
        evidence.append(str(path.relative_to(AUDIT)))
    elif spec.operation == "redo" and spec.attempt != 4:
        label = f"round{spec.attempt}" if spec.attempt in {1, 2, 3} else "round4"
        expected = ledger.get("transaction_units", {}).get(label, {}).get("uid")
        if expected is None:
            raise RuntimeError(f"Missing transaction unit for {label}")
        snapshot, path = stack_snapshot(
            f"before-redo-{spec.attempt}-seq-{sequence:03d}",
            expected_side="redo", expected_uid=expected,
            expected_command="branch",
        )
        del snapshot
        evidence.append(str(path.relative_to(AUDIT)))
    elif (spec.operation, spec.attempt) == ("redo", 4):
        snapshot, path = stack_snapshot(f"before-empty-redo-4-seq-{sequence:03d}")
        if snapshot["redo_top"] is not None:
            raise RuntimeError("Redo4 expected no redo stack")
        evidence.append(str(path.relative_to(AUDIT)))
    return evidence


def run_one(
    ledger: dict, sequence: int, spec: Spec, prior_post: str,
    source_guard: str,
) -> str:
    global EVAL_RUN_ID
    args = spec.args() if callable(spec.args) else spec.args
    if spec.operation == "eval" and spec.attempt == 3 and not EVAL_RUN_ID:
        raise RuntimeError("Eval M2 did not yield a full run ID")
    transaction_pre = before_transaction(ledger, sequence, spec)
    pre_identity, pre_identity_path = assert_identity(
        sequence=sequence, position="pre", label=f"Admin {sequence} pre-call"
    )
    source_preconditions: list[str] = []
    if spec.operation == "branch" and spec.attempt in {1, 2, 3, 4}:
        _, path = branch_checkpoint_precondition(
            sequence=sequence,
            label=f"branch-{spec.attempt}-source",
            root_name=R,
            recursive=spec.attempt == 2,
        )
        source_preconditions.append(str(path.relative_to(AUDIT)))
    if spec.operation == "checkout" and spec.attempt in {3, 4}:
        current_source = pre_identity["current_context"]
        if not isinstance(current_source, str):
            raise RuntimeError(f"Checkout{spec.attempt} has no current Source")
        _, path = branch_checkpoint_precondition(
            sequence=sequence,
            label=f"checkout-{spec.attempt}-source",
            root_name=current_source,
            recursive=spec.attempt == 4,
            require_disjoint=spec.attempt == 4,
        )
        source_preconditions.append(str(path.relative_to(AUDIT)))
    pre_tree = context_tree_digest()
    pre_selected = selected_digest(spec.targets)
    pre_registry = sha_file(REGISTRY)
    pre_attempts = command_attempt_snapshot()
    share_pre = profile_universe_delivery_digest() if spec.operation == "share" else None
    profiles_pre = {item.get("name") for item in read_json(REGISTRY).get("profiles", ())}

    command_argv = ["python", str(RUNNER), WORLD_NAME, *args]
    command = shlex.join(command_argv)
    began = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(
            command_argv, cwd=REPO, input=spec.stdin, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=600, check=False,
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        exit_code = 124
        raw_stdout = error.stdout or ""
        raw_stderr = error.stderr or ""
        stdout = raw_stdout if isinstance(raw_stdout, str) else raw_stdout.decode("utf-8", "replace")
        stderr = raw_stderr if isinstance(raw_stderr, str) else raw_stderr.decode("utf-8", "replace")
        stderr += "\nAUDIT RUNNER TIMEOUT after 600 seconds; child terminated.\n"

    # This is deliberately the first host observation after the child exits.
    post_identity, post_identity_path = assert_identity(
        sequence=sequence, position="post", label=f"Admin {sequence} immediate post-call"
    )
    elapsed = time.monotonic() - began
    post_attempts = command_attempt_snapshot()
    new_attempt_uids = sorted(set(post_attempts) - set(pre_attempts))
    attempt_evidence = {
        "sequence": sequence,
        "count_before": len(pre_attempts),
        "count_after": len(post_attempts),
        "delta": len(new_attempt_uids),
        "new_attempt_uids": new_attempt_uids,
        "records": [post_attempts[uid] for uid in new_attempt_uids],
    }
    attempt_path = HOST / f"command-attempt-{sequence:03d}.json"
    write_json(attempt_path, attempt_evidence)

    post_tree = context_tree_digest()
    post_selected = selected_digest(spec.targets)
    post_registry = sha_file(REGISTRY)
    if subtree_digest(R) != source_guard:
        raise RuntimeError(f"Borrowed Source subtree {R} changed at Admin sequence {sequence}")

    share_evidence = None
    if spec.operation == "share":
        share_post = profile_universe_delivery_digest()
        share_evidence = {
            "pre_profile_universe_delivery_digest": share_pre,
            "post_profile_universe_delivery_digest": share_post,
            "unchanged": share_pre == share_post,
            "delivery_count": 0,
            "digest_semantics": "registry plus all Profile Store Context/state/write-protection artifacts; audit ledgers and lock files excluded",
        }
        write_json(HOST / f"share-{spec.attempt}-zero-delivery.json", share_evidence)
        if share_pre != share_post:
            raise RuntimeError(f"Share M{spec.attempt} changed delivery-visible Profile state")

    init_study_evidence = None
    if spec.operation == "init-study":
        registry_after = read_json(REGISTRY)
        profiles_post = {item.get("name") for item in registry_after.get("profiles", ())}
        init_study_evidence = {
            "exit": exit_code,
            "profile_names_unchanged": profiles_pre == profiles_post,
            "active_identity_unchanged": post_identity["profile_uid"] == PROFILE_UID,
            "success_count": 0,
        }
        write_json(HOST / f"init-study-{spec.attempt}-zero-success.json", init_study_evidence)
        if exit_code == 0 or profiles_pre != profiles_post:
            raise RuntimeError(f"init-study M{spec.attempt} unexpectedly succeeded or changed Profiles")

    raw_base = RAW / f"{sequence:03d}-{spec.operation}-{spec.attempt}"
    stdout_path = raw_base.with_suffix(".stdout.txt")
    stderr_path = raw_base.with_suffix(".stderr.txt")
    combined_path = raw_base.with_suffix(".txt")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    combined_path.write_text(
        f"COMMAND\n{command}\n\nSTDIN\n{('<none>' if spec.stdin is None else repr(spec.stdin))}"
        f"\n\nEXIT\n{exit_code}\n\nWALL_SECONDS\n{elapsed:.6f}"
        f"\n\nPRE_IDENTITY\n{json.dumps(pre_identity, ensure_ascii=False, sort_keys=True)}"
        f"\n\nIMMEDIATE_POST_IDENTITY\n{json.dumps(post_identity, ensure_ascii=False, sort_keys=True)}"
        f"\n\nCOMMAND_ATTEMPT_DELTA\n{json.dumps(attempt_evidence, ensure_ascii=False, sort_keys=True)}"
        f"\n\nSTDOUT\n{stdout}\n\nSTDERR\n{stderr}",
        encoding="utf-8",
    )

    host_consumer = None
    if spec.operation == "shell-init" and exit_code == 0:
        baseline = RAW / "020-shell-init-1.stdout.txt"
        host_consumer = host_shell_check(spec.attempt, stdout_path, baseline if baseline.is_file() else None)
        if host_consumer is not None:
            write_json(HOST / f"shell-init-{spec.attempt}-host-consumer.json", host_consumer)

    if spec.operation == "eval" and spec.attempt == 2:
        match = re.search(r"(?:FULL_RUN_ID|full_run_id|run_id)\s*[=:·]\s*([0-9A-Za-z._:-]+)", stdout + "\n" + stderr)
        found = (match.group(1), "command output") if match else eval_run_from_files()
        if found is not None:
            EVAL_RUN_ID = found[0]
            write_json(HOST / "eval-m2-full-run-id.json", {"full_run_id": EVAL_RUN_ID, "source": found[1]})

    transaction_post = capture_transaction_after(ledger, sequence, spec)
    record = {
        "operation": spec.operation,
        "attempt": spec.attempt,
        "sequence": sequence,
        "round": spec.attempt,
        "command": command,
        "exit": exit_code,
        "starting_state": (
            f"One cumulative no-reset CORE→TRANSFORM→ADMIN ticker Store; ADMIN round {spec.attempt}; "
            f"phase-local sequence {sequence}; current={pre_identity['current_context']}; pre-tree={pre_tree}; "
            f"previous post={prior_post}; the explicit excluded supplemental Admin preflight preceded this phase."
        ),
        "entry_route": f"pinned noninteractive ADMIN CLI · M{spec.attempt} · {spec.method}",
        "target_route": spec.target_route,
        "scope": spec.scope,
        "input_provenance": (
            f"{spec.provenance}; actual argv `{shlex.join(args)}`; phase-local round {spec.attempt}, sequence {sequence}; "
            "supplemental -h preflight excluded from coverage"
        ),
        "consumer": f"ADMIN {spec.operation} safety/recoverability/orientation audit consumer M{spec.attempt}",
        "expected": spec.expected,
        "actual": compact(stdout, stderr, exit_code),
        "defect_ids": [],
        "cost": {
            "wall_seconds": round(elapsed, 6),
            "stdout_bytes": len(stdout.encode()),
            "stderr_bytes": len(stderr.encode()),
            "timed_out": timed_out,
            "tui": False,
            "screenshots": 0,
        },
        "pre_target_digest": pre_tree,
        "post_target_digest": post_tree,
        "selected_target_digest": {"pre": pre_selected, "post": post_selected},
        "recovery_evidence": (
            "Exact transaction stack UID/member evidence recorded host-side; paired lock/unlock or following Undo/Redo verifies recovery."
            if spec.operation in {"branch", "checkout", "undo", "redo", "lock", "unlock"}
            else "No independent recovery required; complete Context-tree continuity and immediate post-call identity are recorded."
        ),
        "state_continuity": {
            "same_as_previous_post": prior_post == pre_tree,
            "durable_context_tree_changed": pre_tree != post_tree,
            "one_cumulative_store": True,
            "source_subtree_preserved": True,
            "supplemental_preflight_preceded_but_excluded": True,
        },
        "post_execution_identity": post_identity,
        "host_reads": {
            "pre_identity": str(pre_identity_path.relative_to(AUDIT)),
            "immediate_post_identity": str(post_identity_path.relative_to(AUDIT)),
            "command_attempt_delta": str(attempt_path.relative_to(AUDIT)),
            "branch_source_preconditions": source_preconditions,
            "transaction_pre": transaction_pre,
            "transaction_post": transaction_post,
        },
        "command_attempt_ledger_delta": attempt_evidence,
        "raw_output": str(combined_path.relative_to(AUDIT)),
        "raw_stdout": str(stdout_path.relative_to(AUDIT)),
        "raw_stderr": str(stderr_path.relative_to(AUDIT)),
    }
    if share_evidence is not None:
        record["share_evidence"] = share_evidence
    if init_study_evidence is not None:
        record["init_study_evidence"] = init_study_evidence
    if host_consumer is not None:
        record["host_consumer_evidence"] = host_consumer
    ledger["operations"][spec.operation]["attempts"].append(record)
    ledger["last_completed_sequence"] = sequence
    ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
    save(ledger)
    print(
        f"[{sequence:03d}/105] {spec.operation}#{spec.attempt} exit={exit_code} "
        f"{elapsed:.2f}s changed={pre_tree != post_tree} attempt_delta={len(new_attempt_uids)}",
        flush=True,
    )
    return post_tree


def main() -> None:
    global EVAL_RUN_ID
    RAW.mkdir(parents=True, exist_ok=True)
    HOST.mkdir(parents=True, exist_ok=True)
    EVAL_LEDGER.mkdir(parents=True, exist_ok=True)
    initial = context_tree_digest()
    source_guard = subtree_digest(R)
    if PHASE.exists():
        ledger = read_json(PHASE)
    else:
        if not SUPPLEMENTAL.is_file():
            raise SystemExit("supplemental-admin-preflight.json is required")
        if current_identity()["current_context"] != ENTRY:
            raise SystemExit("Ticker ADMIN entry current Context is not practice")
        if context_path(C).exists():
            raise SystemExit("Ticker ADMIN scratch Context already exists")
        registry = read_json(REGISTRY)
        if any(item.get("name") == INACTIVE_PROFILE for item in registry.get("profiles", ())):
            raise SystemExit("Ticker ADMIN inactive Profile fixture already exists")
        if any(EVAL_LEDGER.rglob("*.json")):
            raise SystemExit("Ticker ADMIN Eval ledger is not empty")
        ledger = new_ledger(initial, source_guard)
        entry_identity, entry_path = assert_identity(sequence=0, position="phase-entry", label="Admin phase entry")
        ledger["starting_boundary"]["phase_entry_identity"] = entry_identity
        ledger["starting_boundary"]["phase_entry_identity_evidence"] = str(entry_path.relative_to(AUDIT))
        save(ledger)

    completed = {record["sequence"] for record in records(ledger)}
    if ledger["source_guard"]["initial_subtree_digest"] != source_guard:
        raise RuntimeError("Borrowed Source subtree digest differs from Admin boundary")
    prior_records = records(ledger)
    prior_post = (
        prior_records[-1]["post_target_digest"]
        if prior_records
        else ledger["starting_boundary"]["admin_initial_tree_digest"]
    )
    found_eval = eval_run_from_files()
    if found_eval is not None:
        EVAL_RUN_ID = found_eval[0]
    if 43 in completed and "round3" not in ledger.get("transaction_units", {}):
        # Import Context M1/M2 collided on stable UIDs already present in this
        # cumulative ticker Profile, so their planned positive Rename fixtures
        # did not exist. Branch3 therefore succeeded before the clean-Source
        # Checkout safety gate stopped sequence 44. Preserve that actual state:
        # use Branch3 as the exact verified round-3 restore unit, precreate co3
        # only by renaming the init-created leaf, and make Checkout3 a clean-O
        # target-collision trial. No Store reset, restoration, or extra mem call
        # is permitted to manufacture the originally planned boundary.
        snapshot, path = stack_snapshot(
            "round3-resume-actual-branch3-producer",
            expected_side="undo", expected_command="branch",
            require_granted_null=True,
        )
        ledger["transaction_units"]["round3"] = snapshot["undo_top"]
        ledger.setdefault("runtime_deviations", []).append(
            {
                "at_sequence": 43,
                "classification": "campaign-fixture-and-protocol-limitation",
                "trigger": "Import M1/M2 stable-UID collisions left Rename M1/M2 targets absent; Branch3 then succeeded and became current.",
                "unsafe_route_rejected": "Checkout3 -b from Branch3-created current with a retained Branch receipt.",
                "safe_cumulative_continuation": "Switch3 to checkpoint-free O; Rename3 init-created leaf to co3; Checkout3 clean-O target collision; Undo3/Redo3 exact Branch3 unit.",
                "no_reset_restore_or_extra_mem": True,
                "host_stack_evidence": str(path.relative_to(AUDIT)),
            }
        )
        save(ledger)
    plan = specs()
    for sequence, spec in enumerate(plan, 1):
        if sequence in completed:
            continue
        prior_post = run_one(ledger, sequence, spec, prior_post, source_guard)

    all_records = records(ledger)
    counts = Counter(record["operation"] for record in all_records)
    if len(all_records) != 105 or set(counts) != set(OPERATIONS) or set(counts.values()) != {5}:
        raise RuntimeError(f"ADMIN 21×5 contract failed: {len(all_records)}, {counts}")
    if any(not record["state_continuity"]["same_as_previous_post"] for record in all_records):
        raise RuntimeError("ADMIN Context-tree continuity break")
    if subtree_digest(R) != source_guard:
        raise RuntimeError("Ticker borrowed Source subtree changed")
    if current_identity()["current_context"] != ENTRY:
        raise RuntimeError("Ticker ADMIN did not restore phase-entry current Context")
    if any(record["operation"] == "init-study" and record["exit"] == 0 for record in all_records):
        raise RuntimeError("Ticker ADMIN had an init-study success")
    if any(not record.get("share_evidence", {}).get("unchanged", True) for record in all_records):
        raise RuntimeError("Ticker ADMIN Share delivery-visible state changed")
    ledger["status"] = "complete"
    ledger["attempt_count"] = 105
    ledger["coverage"] = dict(sorted(counts.items()))
    ledger["source_guard"]["final_subtree_digest"] = subtree_digest(R)
    ledger["source_guard"]["preserved"] = True
    ledger["completed_at"] = datetime.now(timezone.utc).isoformat()
    ledger["summary"] = {
        "attempts": 105,
        "successful_exits": sum(record["exit"] == 0 for record in all_records),
        "nonzero_exits": sum(record["exit"] != 0 for record in all_records),
        "durable_context_tree_mutations": sum(record["state_continuity"]["durable_context_tree_changed"] for record in all_records),
        "continuity_breaks": 0,
        "share_deliveries": 0,
        "init_study_successes": 0,
        "tui_attempts": 0,
        "screenshots": 0,
        "identity_host_reads": 105,
        "supplemental_preflight_excluded_calls": 21,
        "final_current_context": ENTRY,
        "final_context_tree_digest": context_tree_digest(),
        "wall_seconds": round(sum(record["cost"]["wall_seconds"] for record in all_records), 3),
    }
    save(ledger)
    print("TICKER_ADMIN_CAPTURE_COMPLETE 105/105", flush=True)


if __name__ == "__main__":
    main()
