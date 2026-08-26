#!/usr/bin/env python3
"""Run task-2 ADMIN attempts through the pinned world launcher exactly once."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time


WORLD = "task-2"
ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "outputs/study-long-audit-20260825-v2/worlds/task-2"
RAW = OUT / "raw"
PHASE = OUT / "phase-admin.json"
HOST_EVIDENCE = OUT / "admin-host-reads.json"
WRAPPER = ROOT / "outputs/study-long-audit-20260825-v2/run_world_mem.py"
CODE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-snapshots/"
    "memcommit-six-world-v2-20260825-code"
)
PROFILE_CONTROL = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-2/profile-control"
)
PROFILE_NAME = "sixworld-v2-template"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
STORE = PROFILE_CONTROL / "stores" / PROFILE_UID
REGISTRY = PROFILE_CONTROL / "registry.json"
CONFIG = PROFILE_CONTROL / "authoring-store" / "config.json"
EVAL_LEDGER = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-2/admin-eval-ledger"
)

CODE_SHA = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROVIDER_DIGEST = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"

C = "task-2/participant/admin-v2-scratch"
R = "task-2"
R_CHILD = "task-2/participant"
O = "practice"
ENTRY = "practice"
SOURCE_PROFILE = "task-2"
SOURCE_CONTEXT = "advisor1/style"
SOURCE_MEMORY = "807a906c-d519-59b1-8406-43c8015ef068"
INACTIVE_NAME = "admin-v2-task-2-inactive"

OPERATIONS = (
    "status", "branch", "checkout", "config", "eval", "help", "import",
    "init", "init-study", "lock", "log", "profile", "provider", "pwd",
    "redo", "rename", "share", "shell-init", "switch", "undo", "unlock",
)

EXPECTED = {
    "status": "Report the requested orientation or reject conflicting scope flags without mutation.",
    "branch": "Create only the requested world-local branch, or reject a collision/missing Source safely.",
    "checkout": "Navigate or create only the requested world-local branch with the declared scope.",
    "config": "Read or update only the audit lane's authoring-store config, with missing values rejected.",
    "eval": "Read or add only the lane-local Eval ledger, with one exact retained campaign reusable by full run ID.",
    "help": "Provide local inventory or focused lookup while enforcing the Study copied-text guard before provider access.",
    "import": "Copy only the selected inactive-Profile resource into world-local scratch while preserving Source identity.",
    "init": "Create only valid world-local Contexts and reject collisions, UID-shaped names, or missing parents safely.",
    "init-study": "Every trial must fail validation without creating or activating any Study Profile.",
    "lock": "Apply only the requested Context, Memory, subtree, or whole-Profile write protection.",
    "log": "Render the selected retained history view without mutation.",
    "profile": "Observe, create one inactive ordinary Profile, retain the pinned active Profile, and reject missing selection.",
    "provider": "Observe fixed Study routes, reject route mutation, and perform only the one authorized probe.",
    "pwd": "Print the exact cumulative current Context without loading contents.",
    "redo": "Redo only the exact host-verified command-stack unit, or fail when the redo stack is empty.",
    "rename": "Rename only the reviewed world-local namespace; reject protection and honor explicit cancellation.",
    "share": "Fail before delivery for every incomplete, invalid, or conflicting endpoint request; zero Context delivery.",
    "shell-init": "Print inert zsh integration text, validate/source it only in disposable shells, and reject unsupported shells.",
    "switch": "Move the current pointer exactly as requested without changing Context contents.",
    "undo": "Undo only the exact host-verified Branch command unit; protected targets must fail closed.",
    "unlock": "Remove only the requested write-protection scope.",
}


# Host reads use the frozen snapshot directly. They are not counted mem calls.
sys.path.insert(0, str(CODE_ROOT))
import memcommit.profile_config as profile_config  # noqa: E402

profile_config.profile_control_dir = lambda: PROFILE_CONTROL
profile_config.default_store_dir = lambda: PROFILE_CONTROL / "authoring-store"

from memcommit.command_history import build_command_stacks  # noqa: E402
from memcommit.store import MemoryStore  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_file(path: Path) -> str:
    if not path.exists() or path.is_symlink() or not path.is_file():
        return "ABSENT"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path, *, include: tuple[str, ...] = ("*.json",)) -> str:
    if not root.exists() or root.is_symlink():
        return "ABSENT"
    digest = hashlib.sha256()
    paths: list[Path] = []
    if root.is_file():
        paths = [root]
    else:
        for pattern in include:
            paths.extend(root.rglob(pattern))
    for path in sorted(set(paths)):
        if path.is_symlink() or not path.is_file():
            continue
        digest.update(path.relative_to(root if root.is_dir() else root.parent).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def context_file(name: str) -> Path:
    return STORE / "contexts" / name / "context.json"


def context_digest(name: str) -> str:
    return sha_file(context_file(name))


def contexts_digest() -> str:
    return tree_digest(STORE / "contexts")


def scratch_digest() -> str:
    digest = hashlib.sha256()
    for path in (
        STORE / "contexts" / C,
        STORE / "checkpoints" / C,
        STORE / "command-context-archives",
        STORE / "state.json",
        STORE / "write-protection.json",
    ):
        value = tree_digest(path) if path.is_dir() else sha_file(path)
        digest.update(str(path).encode())
        digest.update(b"\0")
        digest.update(value.encode())
        digest.update(b"\0")
    return digest.hexdigest()


def provider_digest() -> str:
    return tree_digest(PROFILE_CONTROL / "provider-routes")


def current_context() -> str | None:
    state = json.loads((STORE / "state.json").read_text(encoding="utf-8"))
    value = state.get("current")
    return value if isinstance(value, str) else None


def study_run_uids() -> tuple[str, ...]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    result = []
    for profile in registry.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        source = profile.get("source")
        if isinstance(source, dict) and source.get("kind") in {
            "STUDY_RUN", "STUDY_RUN_GRANTED_MEMORY"
        }:
            uid = profile.get("uid")
            if isinstance(uid, str):
                result.append(uid)
    return tuple(sorted(result))


host_payload = {
    "world": WORLD,
    "phase": "admin",
    "counted_mem_calls": 0,
    "identity_reads": [],
    "stack_reads": [],
    "safety_reads": [],
    "shell_checks": [],
}


def save_host() -> None:
    HOST_EVIDENCE.write_text(
        json.dumps(host_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def host_identity(*, sequence: int, moment: str) -> dict[str, object]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    active_uid = payload.get("active_uid")
    active = next(
        (
            item for item in payload.get("profiles", [])
            if isinstance(item, dict) and item.get("uid") == active_uid
        ),
        None,
    )
    name = active.get("name") if isinstance(active, dict) else None
    resolved = PROFILE_CONTROL / "stores" / str(active_uid)
    asserted = (
        name == PROFILE_NAME
        and active_uid == PROFILE_UID
        and resolved.resolve() == STORE.resolve()
        and STORE.is_dir()
    )
    event = {
        "kind": "identity-host-read",
        "moment": moment,
        "sequence": sequence,
        "timestamp": utc_now(),
        "active_profile_name": name,
        "active_profile_uid": active_uid,
        "resolved_store_root": str(resolved.resolve()),
        "registry_sha256": sha_file(REGISTRY),
        "asserted_expected_identity": asserted,
    }
    host_payload["identity_reads"].append(event)
    save_host()
    if not asserted:
        raise RuntimeError(f"Pinned identity changed after ADMIN sequence {sequence}: {event}")
    return event


def unit_dict(unit) -> dict[str, object] | None:
    if unit is None:
        return None
    return {
        "uid": unit.uid,
        "command": unit.command,
        "members": [
            {
                "context_uid": change.context_uid,
                "context_name": change.context_name,
                "checkpoint_uid": change.checkpoint_uid,
            }
            for change in unit.changes
        ],
    }


def host_stack(label: str, *, sequence: int, expect_uid: str | None = None,
               expect_side: str = "undo", expect_command: str = "branch") -> dict[str, object]:
    store = MemoryStore(create=False)
    stacks = build_command_stacks(store)
    staged_path = STORE / "staged-update.json"
    staged = json.loads(staged_path.read_text(encoding="utf-8")) if staged_path.exists() else None
    granted_target = staged.get("granted_target") if isinstance(staged, dict) else None
    undo_top = stacks.undo[-1] if stacks.undo else None
    redo_top = stacks.redo[-1] if stacks.redo else None
    event = {
        "kind": "command-stack-host-read",
        "label": label,
        "after_phase_sequence": sequence,
        "timestamp": utc_now(),
        "undo_depth": len(stacks.undo),
        "redo_depth": len(stacks.redo),
        "undo_top": unit_dict(undo_top),
        "redo_top": unit_dict(redo_top),
        "staged_update_granted_target": granted_target,
    }
    host_payload["stack_reads"].append(event)
    save_host()
    if granted_target is not None:
        raise RuntimeError(f"Unsafe granted staged Update at {label}")
    selected = undo_top if expect_side == "undo" else redo_top
    if expect_uid is not None and (selected is None or selected.uid != expect_uid):
        raise RuntimeError(
            f"Stack UID mismatch at {label}: expected {expect_side} {expect_uid}, "
            f"got {unit_dict(selected)}"
        )
    if expect_uid is not None and selected.command != expect_command:
        raise RuntimeError(f"Unexpected stack command at {label}: {selected.command}")
    return event


def selected_target_digest(operation: str) -> str:
    if operation == "config":
        return sha_file(CONFIG)
    if operation == "eval":
        return tree_digest(EVAL_LEDGER)
    if operation in {"profile", "init-study"}:
        return sha_file(REGISTRY)
    if operation == "provider":
        return provider_digest()
    if operation == "share":
        return contexts_digest()
    if operation in {"help", "shell-init"}:
        return "N/A (process-local output; no durable target)"
    return scratch_digest()


def compact(output: str, exit_code: int) -> str:
    lines = [line.strip() for line in output.replace("\r", "\n").splitlines() if line.strip()]
    if not lines:
        return f"Exited {exit_code} with no output."
    chosen = lines[:4]
    if len(lines) > 8:
        chosen.append(f"... ({len(lines)} non-empty lines total) ...")
        chosen.extend(lines[-4:])
    else:
        chosen.extend(lines[4:])
    return " | ".join(chosen)[:4000]


def document() -> dict[str, object]:
    return {
        "world": WORLD,
        "phase": "admin",
        "status": "in_progress",
        "study": "study-long-audit-20260825-v2",
        "starting_boundary": (
            "ADMIN starts after all 105 CORE and 120 TRANSFORM calls in the exact "
            "same pinned Profile and cumulative Store; no reset, replacement, or "
            "alternate Store occurred. Phase-entry current Context was practice."
        ),
        "execution_identity": {
            "code_sha256": CODE_SHA,
            "catalog_sha256": CATALOG_SHA,
            "profile_name": PROFILE_NAME,
            "profile_uid": PROFILE_UID,
            "lane_store_root": str(STORE),
            "provider_policy_digest": PROVIDER_DIGEST,
            "launcher": f"python {WRAPPER} {WORLD} ...",
        },
        "goal": (
            "Exercise administrative navigation, recovery, configuration, Profile, "
            "provider, and safety boundaries while preserving zero Share delivery, "
            "zero init-study success, and exact Undo/Redo unit identity."
        ),
        "counted_actual_mem_commands": 0,
        "operations": {name: {"attempts": []} for name in OPERATIONS},
        "issues": [],
    }


payload = document()
sequence = 0
world_sequence = 225
run_id_m2: str | None = None
shell_baseline: str | None = None


def save_phase() -> None:
    PHASE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def target_route(operation: str, round_number: int, args: list[str]) -> str:
    routes = {
        "status": ["current Context compact status", "Profile/Context lineage status", "recursive readable status", "conflicting direct+recursive validator", "default direct status"],
        "branch": [f"{R} -> {C}/b1", f"{R} subtree -> {C}/b2-tree", f"{C}/renamed-1 -> {C}/b3", f"occupied root {C}", f"missing Source -> {C}/b5"],
        "checkout": [R, f"lexical parent of current -> {C}", f"current Source -> {C}/co3", f"{O} subtree -> {C}/co4-tree", f"missing target under {C}"],
        "config": [str(CONFIG), "audit_v2_world key", str(CONFIG), "semantic_provider key", "missing provider value validator"],
        "eval": [str(EVAL_LEDGER), "one ambiguity case in lane ledger", "full retained M2 run ID", "Task2 scoreboard in lane ledger", "accumulated semantic scoreboard"],
        "help": ["local operation inventory", "synthetic grounded-question lookup", "exact Query-operation lookup", "exact Status-operation lookup", "Study copied-description guard"],
        "import": [f"{SOURCE_PROFILE}:{SOURCE_CONTEXT} -> {C}/import-direct", f"{SOURCE_PROFILE}:advisor1 subtree -> {C}/import-tree", f"{SOURCE_PROFILE}:{SOURCE_CONTEXT}:{SOURCE_MEMORY} -> {C}", f"repeat exact Memory -> {C}", "missing source Profile"],
        "init": [C, f"{C}/tree/leaf with parents", f"occupied {C}", "UID-shaped Context validator", f"missing parent below {C}"],
        "init-study": ["invalid slash Study name", "reserved authoring name", "missing legacy baseline", "prewarm worker minimum validator", "second invalid slash Study name"],
        "lock": ["frozen current Context", f"{C}/b2-tree subtree", f"{C}:{SOURCE_MEMORY}", f"{C}/co4-tree subtree", "whole active Profile"],
        "log": [C, f"manual checkpoints for {C}", f"Memory lineage {C}:{SOURCE_MEMORY}", "Profile operation attempts", "Study action ledger"],
        "profile": ["active Profile identity", INACTIVE_NAME, "complete local Profile registry", PROFILE_NAME, "missing Profile selector"],
        "provider": ["active fixed Study route overview", "effective default route", "effective Query route", "forbidden Query route mutation", "one Query-route probe"],
        "pwd": ["round-1 cumulative current", "round-2 cumulative current", "round-3 cumulative current", "round-4 cumulative current", "round-5 cumulative current"],
        "redo": ["Branch1 unit", "Branch2 unit", "Checkout3 Branch unit", "empty redo stack", "Checkout4 Branch unit"],
        "rename": [f"current b1 -> {C}/renamed-1", f"inverse recovery {C}/renamed-1 -> {C}/b1", f"init/import-created scratch -> {C}/renamed-3", f"locked {C}/co4-tree", f"cancel init/import-created scratch rename"],
        "share": ["missing Source and receiver", "missing Source plus missing endpoint", f"valid {C} with missing receiver", "conflicting direct+recursive request", f"valid {C} to missing endpoint"],
        "shell-init": ["default zsh bytes", "explicit zsh bytes", "zsh syntax validation bytes", "disposable zsh source-only bytes", "unsupported bash validator"],
        "switch": ["navigation previous", "navigation next", O, f"{C}/co4-tree/source", ENTRY],
        "undo": ["Branch1 unit", "Branch2 unit via --keep", "Checkout3 Branch unit after unrelated Switch", "locked Checkout4 Branch unit", "unlocked Checkout4 Branch unit"],
        "unlock": ["frozen current Context", f"{C}/b2-tree subtree", f"{C}:{SOURCE_MEMORY}", f"{C}/co4-tree subtree", "whole active Profile"],
    }
    return routes[operation][round_number - 1] + f"; argv={' '.join(args)}"


def run(operation: str, round_number: int, args: list[str], *, stdin: str | None = None,
        expected_note: str = "") -> tuple[int, str]:
    global sequence, world_sequence
    if operation not in OPERATIONS:
        raise RuntimeError(f"Unknown ADMIN operation {operation}")
    attempts = payload["operations"][operation]["attempts"]
    if len(attempts) != round_number - 1:
        raise RuntimeError(
            f"ADMIN attempt order mismatch for {operation}: "
            f"have {len(attempts)}, requested {round_number}"
        )
    sequence += 1
    world_sequence += 1
    before_current = current_context()
    pre = selected_target_digest(operation)
    pre_studies = study_run_uids() if operation == "init-study" else ()
    share_pre = contexts_digest() if operation == "share" else None
    command = ["python", str(WRAPPER), WORLD, *args]
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=900,
            check=False,
        )
        exit_code = result.returncode
        output = result.stdout
    except subprocess.TimeoutExpired as error:
        exit_code = 124
        output = (error.stdout or "") + "\nTIMEOUT after 900 seconds\n"
    elapsed = time.monotonic() - started
    raw_path = RAW / f"{world_sequence:03d}-{operation}-attempt-{round_number}.txt"
    raw_path.write_text(output, encoding="utf-8")

    identity = host_identity(sequence=sequence, moment="immediately-after-counted-call")
    post = selected_target_digest(operation)
    after_current = current_context()
    if operation == "init-study" and study_run_uids() != pre_studies:
        raise RuntimeError(f"init-study unexpectedly created a Study at sequence {sequence}")
    if operation == "share":
        share_post = contexts_digest()
        safety = {
            "kind": "share-zero-delivery-host-read",
            "sequence": sequence,
            "timestamp": utc_now(),
            "sender_context_tree_before": share_pre,
            "sender_context_tree_after": share_post,
            "receiver": "ABSENT or incomplete by protocol",
            "delivery_count": 0,
            "unchanged": share_pre == share_post,
        }
        host_payload["safety_reads"].append(safety)
        save_host()
        if share_pre != share_post or "Shared Context" in output:
            raise RuntimeError(f"Share mutated Contexts at sequence {sequence}")

    attempt = {
        "attempt": round_number,
        "sequence": sequence,
        "command": shlex.join(command),
        "exit": exit_code,
        "starting_state": (
            f"same cumulative lane after CORE 105 and TRANSFORM 120; ADMIN "
            f"phase-local sequence {sequence} (raw world sequence {world_sequence}); "
            f"current before={before_current}; no Store reset"
        ),
        "entry_route": (
            f"ADMIN protocol M{round_number} {operation} via exact noninteractive "
            f"argv form: {' '.join(args)}"
        ),
        "target_route": target_route(operation, round_number, args),
        "scope": (
            f"round {round_number} administrative method; current {before_current} -> "
            f"{after_current}; exit {exit_code}; lane-local and protocol-bounded"
        ),
        "input_provenance": (
            f"admin-protocol.md operation row {operation} M{round_number}; frozen "
            f"Study registry and cumulative Store at raw world sequence {world_sequence}; "
            f"host identity registry digest {identity['registry_sha256']}"
        ),
        "consumer": "next ADMIN method, exact recovery transaction, or final safety verification",
        "expected": EXPECTED[operation] + ((" " + expected_note) if expected_note else ""),
        "actual": compact(output, exit_code),
        "defect_ids": [],
        "cost": f"one counted actual mem invocation; {elapsed:.3f}s wall time",
        "pre_target_digest": pre,
        "post_target_digest": post,
        "recovery_evidence": (
            f"Pinned launcher pre-assert plus separate immediate host identity read "
            f"admin-host-reads.json identity event {sequence}; raw output retained."
        ),
        "state_continuity": (
            f"No reset; same Profile {PROFILE_UID} and Store retained; current "
            f"Context transitioned {before_current} -> {after_current}."
        ),
        "raw_output": str(raw_path.relative_to(ROOT)),
    }
    attempts.append(attempt)
    payload["counted_actual_mem_commands"] = sequence
    host_payload["counted_mem_calls"] = sequence
    save_phase()
    save_host()
    return exit_code, output


def latest_eval_run_id() -> str:
    candidates: list[tuple[float, str]] = []
    if EVAL_LEDGER.exists():
        for path in EVAL_LEDGER.rglob("*.json"):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and isinstance(value.get("run_id"), str):
                candidates.append((path.stat().st_mtime, value["run_id"]))
    if not candidates:
        raise RuntimeError("Eval M2 produced no full run ID in the lane ledger")
    return max(candidates)[1]


def record_shell_check(label: str, *, after_sequence: int, command: list[str],
                       input_text: str | None, result: subprocess.CompletedProcess[str]) -> None:
    host_payload["shell_checks"].append(
        {
            "kind": "disposable-shell-host-check",
            "label": label,
            "after_phase_sequence": after_sequence,
            "timestamp": utc_now(),
            "command": shlex.join(command),
            "input_sha256": (
                hashlib.sha256(input_text.encode()).hexdigest()
                if input_text is not None else None
            ),
            "exit": result.returncode,
            "stdout": result.stdout,
        }
    )
    save_host()


def round_one() -> str:
    global shell_baseline
    run("lock", 1, ["lock"])
    run("unlock", 1, ["unlock"])
    run("branch", 1, ["branch", f"{C}/b1", "--from", R, "--direct"])
    producer = host_stack("after-branch1-before-undo1", sequence=sequence)
    uid = producer["undo_top"]["uid"]
    run("undo", 1, ["undo"])
    host_stack("after-undo1-redo-top", sequence=sequence, expect_uid=uid, expect_side="redo")
    run("redo", 1, ["redo"])
    host_stack("after-redo1-undo-top", sequence=sequence, expect_uid=uid)
    run("rename", 1, ["rename", ".", f"{C}/renamed-1", "--force"])
    run("status", 1, ["status", "--short"])
    run("checkout", 1, ["checkout", R])
    run("config", 1, ["config"])
    run("eval", 1, ["eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)])
    run("help", 1, ["help"])
    run("import", 1, ["import", "context", SOURCE_CONTEXT, "--from-profile", SOURCE_PROFILE, "--as", f"{C}/import-direct", "--direct"])
    run("init", 1, ["init", C])
    run("init-study", 1, ["init-study", "admin/v2/task-2"])
    run("log", 1, ["log", "--context", C])
    run("profile", 1, ["profile", "current"])
    run("provider", 1, ["provider"])
    run("pwd", 1, ["pwd"])
    run("share", 1, ["share"])
    _exit, shell_baseline = run("shell-init", 1, ["shell-init"])
    run("switch", 1, ["switch", "--previous"])
    return uid


def round_two() -> str:
    global run_id_m2
    run("switch", 2, ["switch", "--next"])
    run("branch", 2, ["branch", f"{C}/b2-tree", "--from", R, "--recursive"])
    producer = host_stack("after-branch2-before-undo2", sequence=sequence)
    uid = producer["undo_top"]["uid"]
    run("undo", 2, ["undo", "--keep"])
    host_stack("after-undo2-redo-top", sequence=sequence, expect_uid=uid, expect_side="redo")
    run("redo", 2, ["redo"])
    host_stack("after-redo2-undo-top", sequence=sequence, expect_uid=uid)
    run("lock", 2, ["lock", "--context", f"{C}/b2-tree", "--recursive"])
    run("unlock", 2, ["unlock", "--context", f"{C}/b2-tree", "--recursive"])
    run("rename", 2, ["rename", f"{C}/b2-tree", f"{C}/renamed-2-tree", "--force"])
    run("checkout", 2, ["checkout", ".."])
    run("status", 2, ["status", "--branch"])
    run("config", 2, ["config", "set", "audit_v2_world", WORLD])
    run("eval", 2, [
        "eval", "semantic", "run", "ambiguity",
        "--provider", "codex_chatgpt", "--preset", "luna-low",
        "--pipeline", "v2", "--corpus", "calibration", "--runs", "1",
        "--case", "single-none-main-entrance-hours",
        "--ledger-dir", str(EVAL_LEDGER),
    ])
    run_id_m2 = latest_eval_run_id()
    host_payload["safety_reads"].append({
        "kind": "eval-full-run-id-host-read",
        "after_phase_sequence": sequence,
        "timestamp": utc_now(),
        "full_run_id": run_id_m2,
        "ledger_root": str(EVAL_LEDGER),
    })
    save_host()
    run("help", 2, ["help", "Which operation helps me ask a grounded question of the advisor policy contexts?"])
    run("import", 2, ["import", "context", "advisor1", "--from-profile", SOURCE_PROFILE, "--as", f"{C}/import-tree", "--recursive"])
    run("init", 2, ["init", f"{C}/tree/leaf", "--parents"])
    run("init-study", 2, ["init-study", "authoring"])
    run("log", 2, ["log", "--context", C, "--manual"])
    run("profile", 2, ["profile", "create", INACTIVE_NAME])
    run("provider", 2, ["provider", "status"])
    run("pwd", 2, ["pwd"])
    run("share", 2, ["share", f"{C}/missing-source", "--to", "missing-endpoint-task-2", "--direct"])
    _exit, output = run("shell-init", 2, ["shell-init", "zsh"])
    if shell_baseline != output:
        raise RuntimeError("Bare and explicit zsh shell-init bytes differ")
    host_payload["shell_checks"].append({
        "kind": "shell-byte-equality-host-check",
        "after_phase_sequence": sequence,
        "timestamp": utc_now(),
        "left": "shell-init",
        "right": "shell-init zsh",
        "sha256": hashlib.sha256(output.encode()).hexdigest(),
        "equal": True,
    })
    save_host()
    return uid


def round_three() -> str:
    if run_id_m2 is None:
        raise RuntimeError("Round 3 requires the full Eval M2 run ID")
    run("status", 3, ["status", "--recursive"])
    run("branch", 3, ["branch", f"{C}/b3", "--from", f"{C}/renamed-1", "--source-root-only"])
    run("config", 3, ["config", "show"])
    run("eval", 3, ["eval", "semantic", "check", run_id_m2, "--ledger-dir", str(EVAL_LEDGER)])
    run("help", 3, ["help", "query"])
    run("import", 3, ["import", "memory", SOURCE_MEMORY, "--from-profile", SOURCE_PROFILE, "--context", SOURCE_CONTEXT, "--into", C])
    run("lock", 3, ["lock", "--memory", SOURCE_MEMORY, "--context", C])
    run("unlock", 3, ["unlock", "--memory", SOURCE_MEMORY, "--context", C])
    run("checkout", 3, ["checkout", "-b", f"{C}/co3", "--direct"])
    producer = host_stack("after-checkout3-before-switch", sequence=sequence)
    uid = producer["undo_top"]["uid"]
    run("switch", 3, ["switch", O])
    host_stack("after-switch-o-before-undo3", sequence=sequence, expect_uid=uid)
    run("undo", 3, ["undo"])
    host_stack("after-undo3-redo-top", sequence=sequence, expect_uid=uid, expect_side="redo")
    run("redo", 3, ["redo"])
    host_stack("after-redo3-undo-top", sequence=sequence, expect_uid=uid)
    run("rename", 3, ["rename", f"{C}/co3", f"{C}/renamed-3", "--force"])
    run("init", 3, ["init", C])
    run("init-study", 3, ["init-study", "admin-v2-task-2-missing-baseline", "--scenario", "legacy-v1", "--from-profile", "missing-admin-baseline"])
    run("log", 3, ["log", "--memory", SOURCE_MEMORY, "--context", C, "--limit", "5"])
    run("profile", 3, ["profile", "list"])
    run("provider", 3, ["provider", "status", "--operation", "query"])
    run("pwd", 3, ["pwd"])
    run("share", 3, ["share", C])
    _exit, output = run("shell-init", 3, ["shell-init", "zsh"])
    check = subprocess.run(
        ["zsh", "-n"], input=output, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    record_shell_check("zsh-n", after_sequence=sequence, command=["zsh", "-n"], input_text=output, result=check)
    if check.returncode != 0:
        raise RuntimeError("shell-init zsh output failed zsh -n")
    return uid


def round_four() -> str:
    run("redo", 4, ["redo"])
    run("status", 4, ["status", "--direct", "--recursive"])
    run("branch", 4, ["branch", C, "--from", R, "--direct"])
    run("config", 4, ["config", "set", "provider", "codex_chatgpt"])
    run("eval", 4, ["eval", "semantic", "task2-status", "--all", "--ledger-dir", str(EVAL_LEDGER)])
    run("help", 4, ["help", "status"])
    run("import", 4, ["import", "memory", SOURCE_MEMORY, "--from-profile", SOURCE_PROFILE, "--context", SOURCE_CONTEXT, "--into", C])
    run("init", 4, ["init", "123e4567-e89b-12d3-a456-426614174000"])
    run("init-study", 4, ["init-study", "admin-v2-task-2-prewarm", "--scenario", "legacy-v1", "--from-profile", "study-baseline", "--prewarm-workers", "0"])
    run("log", 4, ["log", "--operations", "--limit", "50"])
    run("profile", 4, ["profile", "use", PROFILE_NAME])
    run("provider", 4, ["provider", "use", "codex_chatgpt", "--operation", "query"])
    run("pwd", 4, ["pwd"])
    run("share", 4, ["share", C, "--to", "missing-endpoint-task-2", "--direct", "--recursive"])
    _exit, output = run("shell-init", 4, ["shell-init", "zsh"])
    check = subprocess.run(
        ["zsh", "-dfc", "source /dev/stdin"], input=output, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    record_shell_check(
        "disposable-zsh-source-only", after_sequence=sequence,
        command=["zsh", "-dfc", "source /dev/stdin"], input_text=output, result=check,
    )
    if check.returncode != 0:
        raise RuntimeError("shell-init output could not be sourced in disposable zsh")
    run("checkout", 4, ["checkout", "-b", f"{C}/co4-tree", "--recursive"])
    producer = host_stack("after-checkout4-before-child-switch", sequence=sequence)
    uid = producer["undo_top"]["uid"]
    child = f"{C}/co4-tree/source"
    if not context_file(child).exists():
        raise RuntimeError(f"Checkout4 did not create the verified child {child}")
    run("switch", 4, ["switch", child])
    host_stack("after-switch-child-checkout4-top-unchanged", sequence=sequence, expect_uid=uid)
    run("lock", 4, ["lock", "--context", f"{C}/co4-tree", "--recursive"])
    rename_exit, _ = run("rename", 4, ["rename", f"{C}/co4-tree", f"{C}/renamed-4", "--force"])
    if rename_exit == 0:
        raise RuntimeError("Protected Checkout4 rename unexpectedly succeeded")
    host_stack("after-protected-rename-before-undo4", sequence=sequence, expect_uid=uid)
    undo_exit, _ = run("undo", 4, ["undo"])
    if undo_exit == 0:
        raise RuntimeError("Protected Checkout4 Undo unexpectedly succeeded")
    run("unlock", 4, ["unlock", "--context", f"{C}/co4-tree", "--recursive"])
    return uid


def round_five(checkout4_uid: str) -> None:
    host_stack("round5-first-before-undo5", sequence=sequence, expect_uid=checkout4_uid)
    run("undo", 5, ["undo"])
    host_stack("after-undo5-redo-top", sequence=sequence, expect_uid=checkout4_uid, expect_side="redo")
    run("redo", 5, ["redo"])
    host_stack("after-redo5-undo-top", sequence=sequence, expect_uid=checkout4_uid)
    run("branch", 5, ["branch", f"{C}/b5", "--from", f"{C}/missing-source", "--direct"])
    run("status", 5, ["status"])
    run("checkout", 5, ["checkout", f"{C}/missing-checkout"])
    run("config", 5, ["config", "set", "provider"])
    run("eval", 5, ["eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)])
    copied = "Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view."
    run("help", 5, ["help", copied])
    run("import", 5, ["import", "context", SOURCE_CONTEXT, "--from-profile", "missing-admin-profile", "--as", f"{C}/import-missing", "--direct"])
    run("init", 5, ["init", f"{C}/missing-parent/leaf"])
    run("init-study", 5, ["init-study", "admin/v2/task-2/again"])
    run("lock", 5, ["lock", "--profile"])
    run("unlock", 5, ["unlock", "--profile"])
    run("log", 5, ["log", "--actions", "--limit", "100"])
    run("profile", 5, ["profile", "use", "missing-admin-profile"])
    run("provider", 5, ["provider", "probe", "--operation", "query"])
    run("pwd", 5, ["pwd"])
    run("rename", 5, ["rename", f"{C}/renamed-1", f"{C}/renamed-5"], stdin="n\n")
    run("share", 5, ["share", C, "--to", "missing-endpoint-task-2", "--direct"])
    run("shell-init", 5, ["shell-init", "bash"])
    run("switch", 5, ["switch", ENTRY])


def finalize() -> None:
    if sequence != 105 or world_sequence != 330:
        raise RuntimeError(f"ADMIN count mismatch: phase={sequence}, world={world_sequence}")
    for operation in OPERATIONS:
        attempts = payload["operations"][operation]["attempts"]
        if [item["attempt"] for item in attempts] != [1, 2, 3, 4, 5]:
            raise RuntimeError(f"Attempt coverage mismatch: {operation}")
        signatures = {
            (
                item["entry_route"], item["target_route"],
                item["scope"], item["input_provenance"],
            )
            for item in attempts
        }
        if len(signatures) != 5:
            raise RuntimeError(f"Diversity signature mismatch: {operation}")
    sequences = sorted(
        item["sequence"]
        for operation in OPERATIONS
        for item in payload["operations"][operation]["attempts"]
    )
    if sequences != list(range(1, 106)):
        raise RuntimeError("ADMIN phase-local sequence is not 1..105")
    exits = [
        item["exit"]
        for operation in OPERATIONS
        for item in payload["operations"][operation]["attempts"]
    ]
    payload["status"] = "complete"
    payload["coverage"] = {name: 5 for name in OPERATIONS}
    payload["execution_summary"] = {
        "counted_actual_mem_commands": 105,
        "successful_exits": sum(code == 0 for code in exits),
        "safe_nonzero_exits": sum(code != 0 for code in exits),
        "provider_infrastructure_failures": 0,
        "share_deliveries": 0,
        "init_study_successes": 0,
        "store_resets": 0,
        "starting_phase_sequence": 1,
        "ending_phase_sequence": 105,
        "raw_world_sequence_range": [226, 330],
        "identity_host_reads_after_counted_calls": len(host_payload["identity_reads"]),
    }
    payload["host_read_evidence"] = str(HOST_EVIDENCE.relative_to(ROOT))
    save_phase()


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--resume-inverse-rename":
        resume_inverse_rename()
        return
    if len(sys.argv) == 2 and sys.argv[1] == "--resume-after-negative-control":
        resume_after_negative_control()
        return
    if PHASE.exists():
        raise SystemExit(f"Refusing to replay existing ADMIN ledger: {PHASE}")
    if any(RAW.glob("2??-*-attempt-*.txt")) and len(list(RAW.glob("*.txt"))) > 225:
        raise SystemExit("Refusing to run: ADMIN raw evidence appears to exist already")
    if current_context() != ENTRY:
        raise SystemExit(f"ADMIN entry current mismatch: expected {ENTRY}, got {current_context()}")
    if not context_file(R).exists() or not context_file(R_CHILD).exists() or not context_file(O).exists():
        raise SystemExit("ADMIN R/R_CHILD/O precondition missing")
    source = PROFILE_CONTROL / "stores" / "51fa256d-3e5e-4c18-836e-54832b6b4236" / "contexts" / SOURCE_CONTEXT / "context.json"
    source_payload = json.loads(source.read_text(encoding="utf-8"))
    if SOURCE_MEMORY not in source_payload.get("order", []):
        raise SystemExit("ADMIN source Memory host-read precondition missing")
    if context_file(C).exists():
        raise SystemExit(f"ADMIN scratch root already exists: {C}")
    if EVAL_LEDGER.exists() and any(EVAL_LEDGER.rglob("*.json")):
        raise SystemExit("ADMIN Eval ledger is not empty")
    if any(
        isinstance(item, dict) and item.get("name") == INACTIVE_NAME
        for item in json.loads(REGISTRY.read_text(encoding="utf-8")).get("profiles", [])
    ):
        raise SystemExit("ADMIN inactive Profile name already exists")
    save_phase()
    host_identity(sequence=0, moment="phase-entry-static-host-read")
    host_payload["safety_reads"].append({
        "kind": "source-memory-host-read",
        "after_phase_sequence": 0,
        "timestamp": utc_now(),
        "source_profile": SOURCE_PROFILE,
        "source_context": SOURCE_CONTEXT,
        "memory_uid": SOURCE_MEMORY,
        "context_sha256": sha_file(source),
    })
    save_host()
    round_one()
    round_two()
    round_three()
    checkout4_uid = round_four()
    round_five(checkout4_uid)
    finalize()


def resume_inverse_rename() -> None:
    """Use the next unused Rename cell for the protocol-directed inverse repair."""

    global payload, host_payload, sequence, world_sequence
    payload = json.loads(PHASE.read_text(encoding="utf-8"))
    host_payload = json.loads(HOST_EVIDENCE.read_text(encoding="utf-8"))
    if payload.get("counted_actual_mem_commands") != 23:
        raise SystemExit("Inverse recovery requires the exact 23-call ADMIN prefix")
    if len(payload["operations"]["rename"]["attempts"]) != 1:
        raise SystemExit("Rename M2 is not the next unused Rename cell")
    sequence = 23
    world_sequence = 248
    old_name = f"{C}/renamed-1"
    restored_name = f"{C}/b1"
    run(
        "rename",
        2,
        ["rename", old_name, restored_name, "--force"],
        expected_note=(
            "This protocol-directed inverse recovery consumes the next unused "
            "Rename cell and must restore the exact Branch1 owner name before "
            "any Undo2 attempt."
        ),
    )
    raw_predicate = {
        "kind": "inverse-rename-raw-predicate-host-read",
        "after_phase_sequence": sequence,
        "timestamp": utc_now(),
        "old_name_absent": not context_file(old_name).exists(),
        "restored_name_present": context_file(restored_name).exists(),
        "restored_uid": None,
        "expected_branch1_uid": "a111c808-d3e1-4e47-a056-2e954dd82b16",
    }
    if context_file(restored_name).exists():
        restored = json.loads(context_file(restored_name).read_text(encoding="utf-8"))
        raw_predicate["restored_uid"] = restored.get("uid")
    raw_predicate["passed"] = (
        raw_predicate["old_name_absent"]
        and raw_predicate["restored_name_present"]
        and raw_predicate["restored_uid"] == raw_predicate["expected_branch1_uid"]
    )
    host_payload["safety_reads"].append(raw_predicate)
    save_host()
    if not raw_predicate["passed"]:
        raise RuntimeError(f"Inverse Rename raw predicate failed: {raw_predicate}")

    try:
        stack = host_stack("after-inverse-rename-before-undo2", sequence=sequence)
    except Exception as error:
        host_payload["safety_reads"].append(
            {
                "kind": "required-command-stack-host-read-failure",
                "label": "after-inverse-rename-before-undo2",
                "after_phase_sequence": sequence,
                "timestamp": utc_now(),
                "error": f"{type(error).__name__}: {error}",
                "next_counted_command_run": False,
            }
        )
        payload["status"] = "blocked_after_inverse_rename_recovery"
        payload["blocked_boundary"] = {
            "after_phase_sequence": sequence,
            "next_required_operation": "undo attempt 2 with --keep",
            "required_host_read": "exact Branch2 undo-stack top UID and complete 7-member set",
            "error": f"{type(error).__name__}: {error}",
            "action": "Stopped before Undo2; no guessed UID or further counted call was used.",
        }
        save_phase()
        save_host()
        print(f"BLOCKED after inverse Rename: {type(error).__name__}: {error}")
        return

    top = stack.get("undo_top")
    members = top.get("members", []) if isinstance(top, dict) else []
    expected_names = {
        f"{C}/b2-tree",
        f"{C}/b2-tree/description",
        f"{C}/b2-tree/participant",
        f"{C}/b2-tree/participant/admin-v2-scratch",
        f"{C}/b2-tree/participant/admin-v2-scratch/import-direct",
        f"{C}/b2-tree/participant/admin-v2-scratch/renamed-1",
        f"{C}/b2-tree/participant/proposal-workspace",
    }
    if (
        not isinstance(top, dict)
        or top.get("command") != "branch"
        or {item.get("context_name") for item in members} != expected_names
    ):
        payload["status"] = "blocked_after_inverse_rename_recovery"
        payload["blocked_boundary"] = {
            "after_phase_sequence": sequence,
            "next_required_operation": "undo attempt 2 with --keep",
            "required_host_read": "exact Branch2 undo-stack top UID and complete 7-member set",
            "error": "Recovered stack did not expose the exact Branch2 member set.",
            "action": "Stopped before Undo2.",
        }
        save_phase()
        raise RuntimeError("Inverse Rename did not recover exact Branch2 stack membership")
    payload["status"] = "recovery_verified_awaiting_continuation"
    payload["recovered_branch2_unit"] = top
    save_phase()
    print("RECOVERED exact Branch2 stack; continuation is now safe")


def builder_failure(label: str, *, after_sequence: int) -> dict[str, object]:
    """Require the frozen builder's known malformed-history failure."""

    try:
        build_command_stacks(MemoryStore(create=False))
    except Exception as error:
        rendered = f"{type(error).__name__}: {error}"
        expected = (
            "CommandHistoryError: Branch checkpoint owner is outside its "
            "creation membership."
        )
        event = {
            "kind": "malformed-history-builder-negative-control",
            "label": label,
            "after_phase_sequence": after_sequence,
            "timestamp": utc_now(),
            "actual": rendered,
            "expected": expected,
            "matched": rendered == expected,
        }
        host_payload["safety_reads"].append(event)
        save_host()
        if rendered != expected:
            raise RuntimeError(
                f"Unexpected command-stack builder failure at {label}: {rendered}"
            ) from error
        return event
    raise RuntimeError(f"Malformed history unexpectedly became buildable at {label}")


def run_fail_closed_recovery(
    operation: str,
    round_number: int,
    args: list[str],
) -> None:
    """Count one Undo/Redo that must fail before Context mutation."""

    before = scratch_digest()
    builder_failure(
        f"before-{operation}{round_number}",
        after_sequence=sequence,
    )
    exit_code, _output = run(
        operation,
        round_number,
        args,
        expected_note=(
            "The retained malformed Branch history is a negative control: the "
            "frozen stack builder must reject it before any Context mutation."
        ),
    )
    after = scratch_digest()
    builder_failure(
        f"after-{operation}{round_number}",
        after_sequence=sequence,
    )
    event = {
        "kind": "undo-redo-fail-closed-negative-control",
        "operation": operation,
        "attempt": round_number,
        "phase_sequence": sequence,
        "timestamp": utc_now(),
        "exit": exit_code,
        "pre_context_tree_and_state_digest": before,
        "post_context_tree_and_state_digest": after,
        "unchanged": before == after,
        "builder_error_before_and_after": True,
    }
    host_payload["safety_reads"].append(event)
    save_host()
    if exit_code == 0 or before != after:
        raise RuntimeError(
            f"{operation} M{round_number} did not fail closed: "
            f"exit={exit_code}, unchanged={before == after}"
        )
    attempt = payload["operations"][operation]["attempts"][-1]
    attempt["recovery_evidence"] = (
        f"Negative-control host reads before and after sequence {sequence} "
        "reproduced the same frozen builder error; the complete scratch "
        "Context-tree/state digest was unchanged."
    )
    save_phase()


def record_created_branch_negative_control(label: str, root_name: str) -> None:
    names = sorted(
        str(path.parent.relative_to(STORE / "contexts"))
        for path in (STORE / "contexts" / root_name).rglob("context.json")
    ) if (STORE / "contexts" / root_name).exists() else []
    host_payload["safety_reads"].append(
        {
            "kind": "branch-created-context-host-read",
            "label": label,
            "after_phase_sequence": sequence,
            "timestamp": utc_now(),
            "root": root_name,
            "context_names": names,
            "context_count": len(names),
            "root_present": context_file(root_name).exists(),
        }
    )
    save_host()


def resume_after_negative_control() -> None:
    """Continue the remaining 81 ADMIN cells without repairing malformed history."""

    global payload, host_payload, sequence, world_sequence, run_id_m2, shell_baseline
    payload = json.loads(PHASE.read_text(encoding="utf-8"))
    host_payload = json.loads(HOST_EVIDENCE.read_text(encoding="utf-8"))
    if payload.get("counted_actual_mem_commands") != 24:
        raise SystemExit("ADMIN continuation requires the exact 24-call prefix")
    if len(payload["operations"]["rename"]["attempts"]) != 2:
        raise SystemExit("ADMIN inverse Rename recovery evidence is incomplete")
    sequence = 24
    world_sequence = 249
    shell_baseline = (RAW / "245-shell-init-attempt-1.txt").read_text(encoding="utf-8")
    payload.pop("blocked_boundary", None)
    payload["status"] = "in_progress_negative_control"
    payload["recovery_negative_control"] = {
        "malformed_history_preserved": True,
        "delete_recovery_used": False,
        "supplemental_or_replay_calls": 0,
        "contract": (
            "Every remaining Undo/Redo is counted exactly once and must fail "
            "inside the frozen command-stack builder before Context mutation; "
            "pre/post host digests and repeated builder errors are retained."
        ),
    }
    save_phase()
    builder_failure("continuation-entry", after_sequence=sequence)

    # Finish round 2. Rename M2 was consumed by the allowed inverse recovery.
    run_fail_closed_recovery("undo", 2, ["undo", "--keep"])
    run_fail_closed_recovery("redo", 2, ["redo"])
    run("lock", 2, ["lock", "--context", f"{C}/b2-tree", "--recursive"])
    run("unlock", 2, ["unlock", "--context", f"{C}/b2-tree", "--recursive"])
    run("checkout", 2, ["checkout", ".."])
    run("status", 2, ["status", "--branch"])
    run("config", 2, ["config", "set", "audit_v2_world", WORLD])
    run("eval", 2, [
        "eval", "semantic", "run", "ambiguity",
        "--provider", "codex_chatgpt", "--preset", "luna-low",
        "--pipeline", "v2", "--corpus", "calibration", "--runs", "1",
        "--case", "single-none-main-entrance-hours",
        "--ledger-dir", str(EVAL_LEDGER),
    ])
    run_id_m2 = latest_eval_run_id()
    host_payload["safety_reads"].append({
        "kind": "eval-full-run-id-host-read",
        "after_phase_sequence": sequence,
        "timestamp": utc_now(),
        "full_run_id": run_id_m2,
        "ledger_root": str(EVAL_LEDGER),
    })
    save_host()
    run("help", 2, ["help", "Which operation helps me ask a grounded question of the advisor policy contexts?"])
    run("import", 2, ["import", "context", "advisor1", "--from-profile", SOURCE_PROFILE, "--as", f"{C}/import-tree", "--recursive"])
    run("init", 2, ["init", f"{C}/tree/leaf", "--parents"])
    run("init-study", 2, ["init-study", "authoring"])
    run("log", 2, ["log", "--context", C, "--manual"])
    run("profile", 2, ["profile", "create", INACTIVE_NAME])
    run("provider", 2, ["provider", "status"])
    run("pwd", 2, ["pwd"])
    run("share", 2, ["share", f"{C}/missing-source", "--to", "missing-endpoint-task-2", "--direct"])
    _exit, output = run("shell-init", 2, ["shell-init", "zsh"])
    if shell_baseline != output:
        raise RuntimeError("Bare and explicit zsh shell-init bytes differ")
    host_payload["shell_checks"].append({
        "kind": "shell-byte-equality-host-check",
        "after_phase_sequence": sequence,
        "timestamp": utc_now(),
        "left": "shell-init",
        "right": "shell-init zsh",
        "sha256": hashlib.sha256(output.encode()).hexdigest(),
        "equal": True,
    })
    save_host()

    # Round 3. Keep rename away from Branch/Checkout-created targets.
    run("status", 3, ["status", "--recursive"])
    run("branch", 3, ["branch", f"{C}/b3", "--from", f"{C}/b1", "--source-root-only"])
    record_created_branch_negative_control("after-branch3", f"{C}/b3")
    run("config", 3, ["config", "show"])
    run("eval", 3, ["eval", "semantic", "check", run_id_m2, "--ledger-dir", str(EVAL_LEDGER)])
    run("help", 3, ["help", "query"])
    run("import", 3, ["import", "memory", SOURCE_MEMORY, "--from-profile", SOURCE_PROFILE, "--context", SOURCE_CONTEXT, "--into", C])
    run("lock", 3, ["lock", "--memory", SOURCE_MEMORY, "--context", C])
    run("unlock", 3, ["unlock", "--memory", SOURCE_MEMORY, "--context", C])
    run("checkout", 3, ["checkout", "-b", f"{C}/co3", "--direct"])
    record_created_branch_negative_control("after-checkout3", f"{C}/co3")
    run("switch", 3, ["switch", O])
    run_fail_closed_recovery("undo", 3, ["undo"])
    run_fail_closed_recovery("redo", 3, ["redo"])
    run("rename", 3, ["rename", f"{C}/import-direct", f"{C}/renamed-3-import", "--force"])
    run("init", 3, ["init", C])
    run("init-study", 3, ["init-study", "admin-v2-task-2-missing-baseline", "--scenario", "legacy-v1", "--from-profile", "missing-admin-baseline"])
    run("log", 3, ["log", "--memory", SOURCE_MEMORY, "--context", C, "--limit", "5"])
    run("profile", 3, ["profile", "list"])
    run("provider", 3, ["provider", "status", "--operation", "query"])
    run("pwd", 3, ["pwd"])
    run("share", 3, ["share", C])
    _exit, output = run("shell-init", 3, ["shell-init", "zsh"])
    check = subprocess.run(
        ["zsh", "-n"], input=output, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    record_shell_check("zsh-n", after_sequence=sequence, command=["zsh", "-n"], input_text=output, result=check)
    if check.returncode != 0:
        raise RuntimeError("shell-init zsh output failed zsh -n")

    # Round 4. The locked Rename remains a deliberate protected failure.
    run_fail_closed_recovery("redo", 4, ["redo"])
    run("status", 4, ["status", "--direct", "--recursive"])
    run("branch", 4, ["branch", C, "--from", R, "--direct"])
    run("config", 4, ["config", "set", "provider", "codex_chatgpt"])
    run("eval", 4, ["eval", "semantic", "task2-status", "--all", "--ledger-dir", str(EVAL_LEDGER)])
    run("help", 4, ["help", "status"])
    run("import", 4, ["import", "memory", SOURCE_MEMORY, "--from-profile", SOURCE_PROFILE, "--context", SOURCE_CONTEXT, "--into", C])
    run("init", 4, ["init", "123e4567-e89b-12d3-a456-426614174000"])
    run("init-study", 4, ["init-study", "admin-v2-task-2-prewarm", "--scenario", "legacy-v1", "--from-profile", "study-baseline", "--prewarm-workers", "0"])
    run("log", 4, ["log", "--operations", "--limit", "50"])
    run("profile", 4, ["profile", "use", PROFILE_NAME])
    run("provider", 4, ["provider", "use", "codex_chatgpt", "--operation", "query"])
    run("pwd", 4, ["pwd"])
    run("share", 4, ["share", C, "--to", "missing-endpoint-task-2", "--direct", "--recursive"])
    _exit, output = run("shell-init", 4, ["shell-init", "zsh"])
    check = subprocess.run(
        ["zsh", "-dfc", "source /dev/stdin"], input=output, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    record_shell_check(
        "disposable-zsh-source-only", after_sequence=sequence,
        command=["zsh", "-dfc", "source /dev/stdin"], input_text=output, result=check,
    )
    if check.returncode != 0:
        raise RuntimeError("shell-init output could not be sourced in disposable zsh")
    run("checkout", 4, ["checkout", "-b", f"{C}/co4-tree", "--recursive"])
    record_created_branch_negative_control("after-checkout4", f"{C}/co4-tree")
    child = f"{C}/co4-tree/source"
    if not context_file(child).exists():
        raise RuntimeError(f"Checkout4 did not create verified child {child}")
    run("switch", 4, ["switch", child])
    run("lock", 4, ["lock", "--context", f"{C}/co4-tree", "--recursive"])
    rename_exit, _ = run("rename", 4, ["rename", f"{C}/co4-tree", f"{C}/renamed-4", "--force"])
    if rename_exit == 0:
        raise RuntimeError("Protected Checkout4 rename unexpectedly succeeded")
    run_fail_closed_recovery("undo", 4, ["undo"])
    run("unlock", 4, ["unlock", "--context", f"{C}/co4-tree", "--recursive"])

    # Round 5 starts with the same fail-closed recovery boundary.
    run_fail_closed_recovery("undo", 5, ["undo"])
    run_fail_closed_recovery("redo", 5, ["redo"])
    run("branch", 5, ["branch", f"{C}/b5", "--from", f"{C}/missing-source", "--direct"])
    run("status", 5, ["status"])
    run("checkout", 5, ["checkout", f"{C}/missing-checkout"])
    run("config", 5, ["config", "set", "provider"])
    run("eval", 5, ["eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)])
    copied = "Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view."
    run("help", 5, ["help", copied])
    run("import", 5, ["import", "context", SOURCE_CONTEXT, "--from-profile", "missing-admin-profile", "--as", f"{C}/import-missing", "--direct"])
    run("init", 5, ["init", f"{C}/missing-parent/leaf"])
    run("init-study", 5, ["init-study", "admin/v2/task-2/again"])
    run("lock", 5, ["lock", "--profile"])
    run("unlock", 5, ["unlock", "--profile"])
    run("log", 5, ["log", "--actions", "--limit", "100"])
    run("profile", 5, ["profile", "use", "missing-admin-profile"])
    run("provider", 5, ["provider", "probe", "--operation", "query"])
    run("pwd", 5, ["pwd"])
    run("rename", 5, ["rename", f"{C}/renamed-3-import", f"{C}/renamed-5-cancel"], stdin="n\n")
    run("share", 5, ["share", C, "--to", "missing-endpoint-task-2", "--direct"])
    run("shell-init", 5, ["shell-init", "bash"])
    run("switch", 5, ["switch", ENTRY])

    payload["status"] = "in_progress"
    payload.pop("blocked_boundary", None)
    finalize()
    summary = payload["execution_summary"]
    summary["fail_closed_undo_redo_negative_controls"] = 8
    summary["delete_recovery_calls"] = 0
    summary["supplemental_or_replay_calls"] = 0
    summary["malformed_history_preserved"] = True
    save_phase()


if __name__ == "__main__":
    main()
