#!/usr/bin/env python3
"""Run the 105 counted practice-source ADMIN attempts exactly once.

Every counted command crosses the pinned world runner. Host-side reads are
recorded separately and never invoke mem: identity is asserted after every
call, while Undo/Redo transactions additionally inspect the exact retained
command-stack unit and staged-update authority boundary.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time


WORLD = "practice-source"
ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw" / "admin"
LEDGER = ROOT / "phase-admin.json"
HOST_READS = ROOT / "admin-host-reads.json"
RUNNER = Path(
    "/Users/KimMunyeong/Github/memcommit/outputs/"
    "study-long-audit-20260825-v2/run_world_mem.py"
)
CODE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-snapshots/"
    "memcommit-six-world-v2-20260825-code"
)
LANE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/practice-source"
)
PROFILE_CONTROL = LANE / "profile-control"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROFILE_NAME = "sixworld-v2-template"
STORE = PROFILE_CONTROL / "stores" / PROFILE_UID
REGISTRY = PROFILE_CONTROL / "registry.json"
CONFIG = PROFILE_CONTROL / "authoring-store" / "config.json"
EVAL_LEDGER = LANE / "admin-eval-ledger"

C = "practice/audit-workspace/admin-v2-scratch"
R = "practice-source-v2-transform"
R_CHILD = f"{R}/goals"
O = "task-1"
O_CHILD = "task-1/description"
ENTRY = "practice"
IMPORT_PROFILE = "task-1"
IMPORT_CONTEXT = "participant/construction-updates"
IMPORT_MEMORY_CONTEXT = "participant/construction-updates/building-access"
IMPORT_MEMORY_UID = "8b077f2a-6a9f-50f0-ae91-f6536fb226cb"
SOURCE_PATH = STORE / "contexts/practice/source/context.json"
SOURCE_DIGEST = "3c7872e184194b45295052ec4efe40c9088f1b962e12fd4d30cfd2aeed7de212"

OPERATIONS = (
    "status", "branch", "checkout", "config", "eval", "help", "import",
    "init", "init-study", "lock", "log", "profile", "provider", "pwd",
    "redo", "rename", "share", "shell-init", "switch", "undo", "unlock",
)


sys.path.insert(0, str(CODE_ROOT))
import memcommit.profile_config as profile_config  # noqa: E402
from memcommit.command_history import build_command_stacks  # noqa: E402
from memcommit.store import MemoryStore  # noqa: E402

profile_config.profile_control_dir = lambda: PROFILE_CONTROL
profile_config.default_store_dir = lambda: PROFILE_CONTROL / "authoring-store"


host_reads: list[dict[str, object]] = []
attempts_by_operation: dict[str, list[dict[str, object]]] = {
    operation: [] for operation in OPERATIONS
}
sequence = 0
round_number = 0
shell_init_m1: str | None = None
eval_run_id: str | None = None


def sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context_tree_digest() -> str:
    digest = hashlib.sha256()
    paths = sorted((STORE / "contexts").glob("**/context.json"))
    paths.append(STORE / "state.json")
    for path in paths:
        digest.update(str(path.relative_to(STORE)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<absent>")
        digest.update(b"\0")
    return digest.hexdigest()


def persist_host_reads() -> None:
    HOST_READS.write_text(
        json.dumps(
            {
                "world": WORLD,
                "phase": "admin",
                "counted_mem_calls": sequence,
                "host_reads": host_reads,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def record_host(kind: str, **data: object) -> None:
    host_reads.append(
        {
            "index": len(host_reads) + 1,
            "after_counted_sequence": sequence,
            "kind": kind,
            **data,
        }
    )
    persist_host_reads()


def assert_identity(*, label: str) -> dict[str, str]:
    registry = profile_config.load_profile_registry()
    resolved = profile_config.resolve_active_store_dir().resolve()
    actual = {
        "profile_name": registry.active.name,
        "profile_uid": registry.active.uid,
        "resolved_store": str(resolved),
    }
    if actual != {
        "profile_name": PROFILE_NAME,
        "profile_uid": PROFILE_UID,
        "resolved_store": str(STORE.resolve()),
    }:
        raise RuntimeError(f"Pinned identity changed after {label}: {actual}")
    record_host("identity_assertion", label=label, result="PASS", **actual)
    return actual


def staged_granted_target() -> object:
    path = STORE / "staged-update.json"
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value.get("granted_target")


def stack_snapshot(
    *,
    label: str,
    side: str,
    expected_uid: str | None = None,
    expected_command: str = "branch",
) -> str:
    store = MemoryStore(root=STORE, create=False, resolve_granted_links=False)
    stacks = build_command_stacks(store)
    stack = stacks.undo if side == "undo" else stacks.redo
    if not stack:
        raise RuntimeError(f"{label}: {side} stack is empty")
    unit = stack[-1]
    members = [
        {
            "context_uid": change.context_uid,
            "context_name": change.context_name,
            "checkpoint_uid": change.checkpoint_uid,
        }
        for change in unit.changes
    ]
    granted_target = staged_granted_target()
    if unit.command != expected_command:
        raise RuntimeError(f"{label}: expected {expected_command}, got {unit.command}")
    if expected_uid is not None and unit.uid != expected_uid:
        raise RuntimeError(f"{label}: expected unit {expected_uid}, got {unit.uid}")
    if granted_target is not None:
        raise RuntimeError(f"{label}: staged-update.granted_target is not null")
    record_host(
        "command_stack_assertion",
        label=label,
        side=side,
        unit_uid=unit.uid,
        command=unit.command,
        member_set=members,
        staged_update_granted_target=granted_target,
        result="PASS",
    )
    return unit.uid


def compact(stdout: str, stderr: str, exit_code: int) -> str:
    lines = [
        line.strip()
        for line in "\n".join((stdout.strip(), stderr.strip())).splitlines()
        if line.strip()
    ]
    if not lines:
        return f"Exit {exit_code} with no visible output."
    chosen = lines if len(lines) <= 9 else lines[:7] + ["…"] + lines[-1:]
    return (f"Exit {exit_code}. " + " | ".join(chosen))[:3200]


def target_digest(names: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for name in sorted(set(names)):
        path = STORE / "contexts" / Path(*name.split("/")) / "context.json"
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<absent>")
        digest.update(b"\0")
    return digest.hexdigest()


def expected_for(operation: str, attempt: int) -> str:
    base = {
        "status": "Report orientation and requested scope without mutation; incompatible direct+recursive flags fail safely.",
        "branch": "Create only the declared lane-local branch, record one exact command-stack unit, or fail without mutation on collision/missing Source.",
        "checkout": "Switch to the exact existing Context or create only the declared -b branch; missing/relative-unavailable targets fail safely.",
        "config": "Read or mutate only the lane-local config; missing values fail before change.",
        "eval": "Keep the semantic Eval ledger lane-local, run only the one declared case, and reuse its full run ID for validation.",
        "help": "Provide local inventory or the declared lookup while the copied-text guard fails before provider contact.",
        "import": "Import only the declared by-value Context/Memory into scratch, preserve identity, and reject collisions or missing source Profiles without mutation.",
        "init": "Create only the declared scratch Context namespace; collisions, UID-shaped names, and missing-parent boundary attempts must not broaden scope.",
        "init-study": "Fail before creating or selecting any Study/Profile; active identity and Store remain pinned.",
        "lock": "Apply exactly the declared current/Context/Memory/Profile write-protection scope.",
        "log": "Render only the requested retained history/operation/action scope without mutation.",
        "profile": "Inspect, create one inactive Profile, or retain the same active Profile; missing selection fails without changing identity.",
        "provider": "Inspect locked Study routing or perform only the single declared provider probe; configuration change is rejected.",
        "pwd": "Print the current canonical Context name without loading content or mutating state.",
        "redo": "Redo exactly the host-verified top command unit, or fail when no redo exists.",
        "rename": "Rename only the declared scratch namespace; lock and explicit no-confirmation boundaries publish no rename.",
        "share": "Stop before delivery; incomplete/conflicting/missing endpoint routes leave sender, registry, and any receiver unchanged.",
        "shell-init": "Emit stable zsh integration only; host syntax/source checks never invoke the defined mem function and unsupported shells fail.",
        "switch": "Move only the current pointer through the declared navigation/exact route without changing Context content.",
        "undo": "Undo exactly the host-verified local Branch unit with granted_target null; protected targets fail without partial restoration.",
        "unlock": "Remove exactly the paired write-protection scope and no broader protection.",
    }[operation]
    return base + f" ADMIN method M{attempt}."


def persist_ledger() -> None:
    records = sorted(
        (item for values in attempts_by_operation.values() for item in values),
        key=lambda item: item["sequence"],
    )
    ledger = {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": WORLD,
        "phase": "admin",
        "status": "running" if len(records) < 105 else "captured",
        "starting_boundary": {
            "cumulative_from_transform": True,
            "no_reset": True,
            "same_pinned_identity": True,
            "transform_final_digest": (
                "9f84f2ab172c599223285a8b996060b30001fb24e0dbb78f32235652dad05136"
            ),
            "admin_initial_digest": (
                "9f84f2ab172c599223285a8b996060b30001fb24e0dbb78f32235652dad05136"
            ),
            "transform_final_to_admin_first_pre_digest_bridge": {
                "source_sha256": {
                    "transform_final": SOURCE_DIGEST,
                    "admin_phase_entry_pre": SOURCE_DIGEST,
                    "match": True,
                },
                "context_tree_sha256": {
                    "transform_final_host_boundary": (
                        "9f84f2ab172c599223285a8b996060b30001fb24e0dbb78f32235652dad05136"
                    ),
                    "admin_first_attempt_pre": (
                        "9f84f2ab172c599223285a8b996060b30001fb24e0dbb78f32235652dad05136"
                    ),
                    "match": True,
                },
                "note": (
                    "The phase-entry host read occurred after TRANSFORM and before "
                    "ADMIN sequence 1 with no reset or intervening mem invocation; "
                    "operation-local target digests use different selectors and are "
                    "not compared across phases."
                ),
            },
        },
        "interleave_exceptions": [
            {
                "operation": "switch",
                "attempts": [1, 2],
                "sequences": [21, 22],
                "commands": [
                    f"python {RUNNER} {WORLD} switch --previous",
                    f"python {RUNNER} {WORLD} switch --next",
                ],
                "logical_commands": [
                    "mem switch --previous",
                    "mem switch --next",
                ],
                "rationale": (
                    "Protocol-required round-1-last then round-2-first adjacency "
                    "verifies the previous/next history pair; no intervening mem "
                    "invocation occurred between the two Switch calls."
                ),
            }
        ],
        "execution_identity": {
            "code_sha256": "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84",
            "catalog_sha256": "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5",
            "profile_uid": PROFILE_UID,
            "profile_name": PROFILE_NAME,
            "store_root": str(STORE),
            "provider_policy_sha256": "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca",
        },
        "execution_boundary": {
            "runner": str(RUNNER),
            "entry_current_context": ENTRY,
            "scratch_root": C,
            "existing_root": R,
            "existing_child": R_CHILD,
            "separate_existing_root": O,
            "eval_ledger": str(EVAL_LEDGER),
            "representative_tui_lane": False,
            "screenshots": 0,
        },
        "operation_order": list(OPERATIONS),
        "total_attempts": len(records),
        "operations": {
            operation: {"attempts": attempts_by_operation[operation]}
            for operation in OPERATIONS
        },
        "source_guard": {
            "path": str(SOURCE_PATH),
            "expected_sha256": SOURCE_DIGEST,
            "current_sha256": sha(SOURCE_PATH),
            "preserved": sha(SOURCE_PATH) == SOURCE_DIGEST,
        },
        "non_counted_host_read_ledger": HOST_READS.name,
        "outcome": (
            f"Captured {len(records)}/105 ADMIN attempts; final classification pending."
        ),
    }
    LEDGER.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run(
    operation: str,
    args: list[str],
    *,
    method: str,
    targets: tuple[str, ...] = (),
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    global sequence
    sequence += 1
    attempt = len(attempts_by_operation[operation]) + 1
    if attempt != round_number:
        raise RuntimeError(
            f"Interleaving error: {operation} attempt {attempt} in round {round_number}"
        )
    command = ["python", str(RUNNER), WORLD, *args]
    command_text = shlex.join(command)
    before_target = target_digest(targets)
    before_tree = context_tree_digest()
    before_registry = sha(REGISTRY)
    before_config = sha(CONFIG)
    before_source = sha(SOURCE_PATH)
    started = time.monotonic()
    completed = subprocess.run(
        command,
        text=True,
        input=stdin_text,
        capture_output=True,
        check=False,
    )
    elapsed = time.monotonic() - started

    # Root correction: the frozen launcher asserts only before the call. This
    # host read is deliberately the first post-process observation.
    identity = assert_identity(label=f"admin sequence {sequence} {operation} M{attempt}")
    after_target = target_digest(targets)
    after_tree = context_tree_digest()
    after_registry = sha(REGISTRY)
    after_config = sha(CONFIG)
    after_source = sha(SOURCE_PATH)
    if after_source != SOURCE_DIGEST:
        raise RuntimeError(f"practice/source changed at sequence {sequence}")

    slug = operation.replace("-", "_")
    raw_path = RAW / f"{sequence:03d}-{slug}-m{attempt}.txt"
    raw_path.write_text(
        "COMMAND\n"
        + command_text
        + "\n\nSTDIN\n"
        + ("<none>" if stdin_text is None else repr(stdin_text))
        + "\n\nEXIT\n"
        + str(completed.returncode)
        + "\n\nWALL_SECONDS\n"
        + f"{elapsed:.6f}"
        + "\n\nPOST_CALL_IDENTITY_HOST_ASSERTION\n"
        + json.dumps(identity, ensure_ascii=False, sort_keys=True)
        + "\n\nSTDOUT\n"
        + completed.stdout
        + "\n\nSTDERR\n"
        + completed.stderr,
        encoding="utf-8",
    )
    attempt_record = {
        "attempt": attempt,
        "sequence": sequence,
        "command": command_text,
        "exit": completed.returncode,
        "starting_state": (
            f"One cumulative no-reset Store; ADMIN round {round_number}; "
            f"phase-local sequence {sequence}; current Context captured by command output/host state."
        ),
        "entry_route": f"pinned noninteractive ADMIN CLI · M{attempt} · {method}",
        "target_route": ", ".join(targets) if targets else "Profile/process-local admin surface",
        "scope": f"ADMIN round {attempt} exact argv · {method}",
        "input_provenance": (
            f"cumulative CORE+TRANSFORM+ADMIN Store; protocol M{attempt}; "
            f"actual argv `{shlex.join(args)}`"
        ),
        "consumer": "admin safety, recoverability, orientation, and exact-identity audit",
        "expected": expected_for(operation, attempt),
        "actual": compact(completed.stdout, completed.stderr, completed.returncode),
        "defect_ids": [],
        "cost": {
            "wall_seconds": round(elapsed, 6),
            "output_bytes": len((completed.stdout + completed.stderr).encode()),
            "output_lines": (completed.stdout + completed.stderr).count("\n"),
            "timed_out": False,
            "tui": False,
            "terminal_screens": 0,
            "extra_manual_steps": 0 if stdin_text is None else 1,
        },
        "pre_target_digest": before_target,
        "post_target_digest": after_target,
        "pre_context_tree_digest": before_tree,
        "post_context_tree_digest": after_tree,
        "pre_registry_digest": before_registry,
        "post_registry_digest": after_registry,
        "pre_config_digest": before_config,
        "post_config_digest": after_config,
        "recovery_evidence": "No recovery required or transaction-specific host evidence recorded separately.",
        "state_continuity": {
            "one_cumulative_store": True,
            "source_digest_preserved": after_source == SOURCE_DIGEST,
            "post_call_identity_asserted": True,
            "profile_name": identity["profile_name"],
            "profile_uid": identity["profile_uid"],
            "resolved_store": identity["resolved_store"],
        },
        "stdin_provenance": "none" if stdin_text is None else "literal audit cancellation input",
        "raw_output": str(raw_path.relative_to(ROOT)),
    }
    attempts_by_operation[operation].append(attempt_record)
    persist_ledger()
    print(
        f"ADMIN {sequence:03d}/105 · {operation} M{attempt} · "
        f"exit {completed.returncode} · {elapsed:.2f}s",
        flush=True,
    )
    return completed


def host_shell_check(kind: str, command: list[str], input_text: str) -> None:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    record_host(
        kind,
        command=shlex.join(command),
        exit=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        result="PASS" if result.returncode == 0 else "FAIL",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Host shell check failed: {kind}: {result.stderr}")


def round_1() -> None:
    global round_number, shell_init_m1
    round_number = 1
    run("branch", ["branch", f"{C}/b1", "--from", R, "--direct"], method="direct explicit Source branch", targets=(R, f"{C}/b1"))
    unit = stack_snapshot(label="round1 immediately before Undo1", side="undo")
    run("undo", ["undo"], method="verified direct Branch undo", targets=(f"{C}/b1",))
    stack_snapshot(label="round1 redo-top same UID", side="redo", expected_uid=unit)
    run("redo", ["redo"], method="verified direct Branch redo", targets=(f"{C}/b1",))
    run("lock", ["lock"], method="frozen current Context lock", targets=(f"{C}/b1",))
    run("unlock", ["unlock"], method="paired current Context unlock", targets=(f"{C}/b1",))
    run("rename", ["rename", ".", f"{C}/renamed-1", "--force"], method="relative current branch rename", targets=(f"{C}/b1", f"{C}/renamed-1"))
    run("checkout", ["checkout", R], method="exact existing Context checkout", targets=(R,))
    run("status", ["status", "--short"], method="short orientation", targets=(R,))
    run("config", ["config"], method="lane-local config inventory")
    run("eval", ["eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)], method="empty semantic Eval status", targets=())
    run("help", ["help"], method="non-TTY deterministic inventory")
    run("init", ["init", C], method="exact scratch root creation", targets=(C,))
    run("import", ["import", "context", f"{IMPORT_CONTEXT}/building-access", "--from-profile", IMPORT_PROFILE, "--as", f"{C}/import-direct", "--direct"], method="direct Context by-value import", targets=(f"{C}/import-direct",))
    run("init-study", ["init-study", "admin/v2-practice-source"], method="invalid slash Study name")
    run("log", ["log", "--context", C], method="scratch Context history", targets=(C,))
    run("profile", ["profile", "current"], method="exact active Profile inspection")
    run("provider", ["provider"], method="bare locked Study provider overview")
    run("pwd", ["pwd"], method="post-init current pointer", targets=(C,))
    run("share", ["share"], method="non-TTY incomplete bare Share")
    shell = run("shell-init", ["shell-init"], method="default zsh integration output")
    shell_init_m1 = shell.stdout
    run("switch", ["switch", "--previous"], method="round-boundary previous navigation", targets=(ENTRY, C))


def round_2() -> None:
    global round_number, eval_run_id
    round_number = 2
    run("switch", ["switch", "--next"], method="round-boundary next with no intervening mem", targets=(ENTRY, C))
    run("checkout", ["checkout", ".."], method="relative lexical parent checkout", targets=("practice/audit-workspace",))
    run("status", ["status", "--branch"], method="Profile and Context lineage status")
    run("config", ["config", "set", "audit_v2_world", WORLD], method="lane-only audit world key")
    before_runs = set(EVAL_LEDGER.glob("**/*.json"))
    result = run(
        "eval",
        [
            "eval", "semantic", "run", "ambiguity",
            "--provider", "codex_chatgpt", "--model", "gpt-5.6-sol",
            "--reasoning", "none", "--pipeline", "v2", "--corpus", "calibration",
            "--runs", "1", "--case", "single-none-main-entrance-hours",
            "--ledger-dir", str(EVAL_LEDGER),
        ],
        method="one-case ambiguity Eval under frozen provider/model policy",
    )
    after_runs = set(EVAL_LEDGER.glob("**/*.json"))
    created = sorted(after_runs - before_runs)
    if result.returncode not in {0, 1} or len(created) != 1:
        raise RuntimeError(f"Expected exactly one Eval ledger record, got {created}")
    eval_record = json.loads(created[0].read_text(encoding="utf-8"))
    eval_run_id = str(eval_record["run_id"])
    record_host("eval_full_run_id", path=str(created[0]), run_id=eval_run_id, result="PASS")
    run("help", ["help", "Which operation gives a grounded answer from readable memories without changing them?"], method="synthetic natural-language Help lookup")
    run("init", ["init", f"{C}/tree/leaf", "--parents"], method="parent-expanding nested init", targets=(C, f"{C}/tree", f"{C}/tree/leaf"))
    run("import", ["import", "context", IMPORT_CONTEXT, "--from-profile", IMPORT_PROFILE, "--as", f"{C}/import-tree", "--recursive"], method="recursive Context-tree import", targets=(f"{C}/import-tree", f"{C}/import-tree/building-access"))
    run("init-study", ["init-study", "authoring"], method="reserved authoring Profile name")
    run("log", ["log", "--context", C, "--manual"], method="manual-only scratch history", targets=(C,))
    run("profile", ["profile", "create", "admin-v2-practice-source-inactive"], method="create one inactive managed Profile")
    run("provider", ["provider", "status"], method="effective default provider status")
    run("pwd", ["pwd"], method="nested-init current pointer", targets=(f"{C}/tree/leaf",))
    run("share", ["share", "practice/admin-v2-missing-share-source", "--to", "admin-v2-missing-endpoint"], method="missing explicit Share Source")
    shell = run("shell-init", ["shell-init", "zsh"], method="explicit zsh output")
    if shell_init_m1 is None or shell.stdout != shell_init_m1:
        raise RuntimeError("shell-init default and explicit zsh outputs differ")
    record_host("shell_init_byte_equality", compared_sequences=[20, sequence], sha256=hashlib.sha256(shell.stdout.encode()).hexdigest(), result="PASS")
    run("branch", ["branch", f"{C}/b2-tree", "--from", R, "--recursive"], method="recursive explicit Source branch", targets=(R, f"{C}/b2-tree", f"{C}/b2-tree/goals"))
    run(
        "rename",
        ["rename", f"{C}/renamed-1", f"{C}/b1", "--force"],
        method="inverse recovery rename restoring retained Branch membership",
        targets=(f"{C}/renamed-1", f"{C}/b1"),
    )
    unit = stack_snapshot(label="round2 immediately before Undo2 --keep", side="undo")
    run("undo", ["undo", "--keep"], method="verified recursive Branch undo compatibility route", targets=(f"{C}/b2-tree", f"{C}/b2-tree/goals"))
    stack_snapshot(label="round2 redo-top same UID", side="redo", expected_uid=unit)
    run("redo", ["redo"], method="verified recursive Branch redo", targets=(f"{C}/b2-tree", f"{C}/b2-tree/goals"))
    run("lock", ["lock", f"{C}/b2-tree", "--recursive"], method="recursive branch-tree lock", targets=(f"{C}/b2-tree", f"{C}/b2-tree/goals"))
    run("unlock", ["unlock", f"{C}/b2-tree", "--recursive"], method="paired recursive branch-tree unlock", targets=(f"{C}/b2-tree", f"{C}/b2-tree/goals"))


def round_3() -> None:
    global round_number
    round_number = 3
    run("branch", ["branch", f"{C}/b3", "--from", f"{C}/b1", "--source-root-only"], method="live recovered prior-branch Source root-only", targets=(f"{C}/b1", f"{C}/b3"))
    run("checkout", ["checkout", "-b", f"{C}/co3", "--direct"], method="Git-style direct branch checkout", targets=(f"{C}/b3", f"{C}/co3"))
    unit = stack_snapshot(label="round3 Checkout3 producer before Switch O", side="undo")
    run("switch", ["switch", O], method="switch away while Checkout3 stays stack-top", targets=(O, f"{C}/co3"))
    stack_snapshot(label="round3 top UID unchanged immediately before Undo3", side="undo", expected_uid=unit)
    run("undo", ["undo"], method="verified Checkout3 undo after independent Switch", targets=(f"{C}/co3", O))
    stack_snapshot(label="round3 redo-top same UID", side="redo", expected_uid=unit)
    run("redo", ["redo"], method="verified Checkout3 redo preserving independent current", targets=(f"{C}/co3", O))
    run("status", ["status", "--recursive"], method="recursive current inventory", targets=(O, O_CHILD))
    run("config", ["config", "show"], method="explicit lane config show")
    if eval_run_id is None:
        raise RuntimeError("Eval M2 full run ID unavailable")
    run("eval", ["eval", "semantic", "check", eval_run_id, "--ledger-dir", str(EVAL_LEDGER)], method="full M2 run-ID validation")
    run("help", ["help", "query"], method="exact Query operation lookup")
    run("import", ["import", "memory", IMPORT_MEMORY_UID, "--from-profile", IMPORT_PROFILE, "--context", IMPORT_MEMORY_CONTEXT, "--into", C], method="exact Memory by-value import", targets=(C,))
    run("lock", ["lock", "--memory", IMPORT_MEMORY_UID[:8], "--context", C], method="exact imported Memory lock", targets=(C,))
    run("unlock", ["unlock", "--memory", IMPORT_MEMORY_UID[:8], "--context", C], method="paired exact imported Memory unlock", targets=(C,))
    run("log", ["log", "--memory", IMPORT_MEMORY_UID[:8], "--context", C, "--limit", "5"], method="exact imported Memory lineage", targets=(C,))
    run("profile", ["profile", "list"], method="full Profile inventory")
    run("provider", ["provider", "status", "--operation", "query"], method="effective Query provider status")
    run("pwd", ["pwd"], method="independent O pointer after Redo3", targets=(O,))
    run("share", ["share", "--to", "admin-v2-missing-endpoint"], method="missing Source with incomplete receiver route")
    shell = run("shell-init", ["shell-init", "zsh"], method="zsh output for host syntax validation")
    host_shell_check("shell_init_zsh_syntax", ["zsh", "-n"], shell.stdout)
    run("init", ["init", C], method="existing scratch collision", targets=(C,))
    run("init-study", ["init-study", "admin-v2-practice-source-study", "--scenario", "legacy-v1", "--from-profile", "admin-v2-missing-baseline"], method="missing baseline Profile")
    run("rename", ["rename", f"{C}/tree/leaf", f"{C}/tree/renamed-leaf", "--force"], method="init-created scratch leaf rename", targets=(f"{C}/tree/leaf", f"{C}/tree/renamed-leaf"))


def round_4() -> None:
    global round_number
    round_number = 4
    run("redo", ["redo"], method="early no-redo boundary")
    run("branch", ["branch", C, "--from", R, "--direct"], method="existing scratch-root collision", targets=(C, R))
    run("status", ["status", "--direct", "--recursive"], method="conflicting direct+recursive validation", targets=(O,))
    run("config", ["config", "set", "provider", "codex_chatgpt"], method="lane-local semantic provider config key")
    run("eval", ["eval", "semantic", "task2-status", "--all", "--ledger-dir", str(EVAL_LEDGER)], method="all retained Task2 status")
    run("help", ["help", "atomize"], method="different exact Atomize operation lookup")
    run("import", ["import", "memory", IMPORT_MEMORY_UID, "--from-profile", IMPORT_PROFILE, "--context", IMPORT_MEMORY_CONTEXT, "--into", C], method="repeat exact Memory collision", targets=(C,))
    run("init", ["init", "00000000-0000-0000-0000-000000000777"], method="UID-shaped Context name failure")
    run("init-study", ["init-study", "admin-v2-practice-source-workers", "--prewarm-workers", "0"], method="prewarm worker validation failure")
    run("log", ["log", "--operations", "--limit", "50"], method="Profile operation-attempt ledger")
    run("profile", ["profile", "use", PROFILE_NAME], method="idempotent use of same active Profile")
    run("provider", ["provider", "use", "codex_chatgpt", "--operation", "query"], method="Study-locked Query provider mutation failure")
    run("pwd", ["pwd"], method="pre-Checkout4 independent root pointer", targets=(O,))
    run("share", ["share", C, "--direct", "--recursive"], method="mutually exclusive Share scope flags", targets=(C,))
    shell = run("shell-init", ["shell-init", "zsh"], method="zsh output sourced in disposable shell")
    host_shell_check("shell_init_disposable_source", ["zsh", "-dfc", "source /dev/stdin; whence -w mem"], shell.stdout)
    run("checkout", ["checkout", "-b", f"{C}/co4-tree", "--recursive"], method="Git-style recursive branch checkout", targets=(O, f"{C}/co4-tree", f"{C}/co4-tree/description"))
    unit = stack_snapshot(label="round4 Checkout4 producer before child Switch", side="undo")
    run("switch", ["switch", f"{C}/co4-tree/description"], method="verified branched child switch", targets=(f"{C}/co4-tree", f"{C}/co4-tree/description"))
    run("lock", ["lock", f"{C}/co4-tree", "--recursive"], method="recursive Checkout4 tree lock", targets=(f"{C}/co4-tree", f"{C}/co4-tree/description"))
    run("rename", ["rename", f"{C}/co4-tree", f"{C}/renamed-co4-tree", "--force"], method="locked Checkout4 rename failure", targets=(f"{C}/co4-tree", f"{C}/renamed-co4-tree"))
    stack_snapshot(label="round4 immediately before protected Undo4", side="undo", expected_uid=unit)
    run("undo", ["undo"], method="locked Checkout4 protected undo failure", targets=(f"{C}/co4-tree", f"{C}/co4-tree/description"))
    run("unlock", ["unlock", f"{C}/co4-tree", "--recursive"], method="paired Checkout4 tree unlock", targets=(f"{C}/co4-tree", f"{C}/co4-tree/description"))


def round_5() -> None:
    global round_number
    round_number = 5
    unit = stack_snapshot(label="round5 first action immediately before Undo5", side="undo")
    run("undo", ["undo"], method="same Checkout4 producer after Unlock", targets=(f"{C}/co4-tree", f"{C}/co4-tree/description"))
    stack_snapshot(label="round5 redo-top same UID", side="redo", expected_uid=unit)
    run("redo", ["redo"], method="same Checkout4 producer redo", targets=(f"{C}/co4-tree", f"{C}/co4-tree/description"))
    run("status", ["status"], method="default direct status", targets=(f"{C}/co4-tree",))
    run("branch", ["branch", f"{C}/b5", "--from", "practice/admin-v2-missing-branch-source", "--direct"], method="missing explicit Branch Source", targets=(f"{C}/b5",))
    run("checkout", ["checkout", "practice/admin-v2-missing-checkout"], method="missing exact checkout target")
    run("config", ["config", "set", "provider"], method="missing config value validation")
    run("eval", ["eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)], method="accumulated semantic Eval status")
    run("help", ["help", "Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view."], method="Study copied-text guard before provider")
    run("import", ["import", "context", IMPORT_CONTEXT, "--from-profile", "admin-v2-missing-source-profile", "--as", f"{C}/import-missing", "--direct"], method="missing source Profile import", targets=(f"{C}/import-missing",))
    run("init", ["init", f"{C}/missing-parent/leaf"], method="missing lexical parent without --parents", targets=(f"{C}/missing-parent/leaf",))
    run("init-study", ["init-study", "00000000-0000-0000-0000-000000000999"], method="UID-shaped invalid Study name")
    run("lock", ["lock", "--profile"], method="whole active Profile lock")
    run("unlock", ["unlock", "--profile"], method="paired whole active Profile unlock")
    run("log", ["log", "--actions", "--limit", "100"], method="Study action ledger")
    run("profile", ["profile", "use", "admin-v2-practice-source-missing"], method="missing Profile selection")
    run("provider", ["provider", "probe", "--operation", "query"], method="single synthetic Query provider probe")
    run("pwd", ["pwd"], method="late accumulated current pointer")
    run("share", ["share", C, "--to", "admin-v2-missing-endpoint", "--direct"], method="valid Source to missing receiver endpoint", targets=(C,))
    run("shell-init", ["shell-init", "bash"], method="unsupported shell validation")
    run("rename", ["rename", f"{C}/co4-tree", f"{C}/renamed-co4-cancel"], method="explicit confirmation declined", targets=(f"{C}/co4-tree", f"{C}/renamed-co4-cancel"), stdin_text="n\n")
    run("switch", ["switch", ENTRY], method="exact phase-entry restoration", targets=(ENTRY,))


def main() -> None:
    global sequence
    if LEDGER.exists() or RAW.exists() or HOST_READS.exists():
        raise SystemExit("ADMIN evidence already exists; refusing any replay.")
    RAW.mkdir(parents=True)
    if sha(SOURCE_PATH) != SOURCE_DIGEST:
        raise SystemExit("practice/source digest does not match phase boundary.")
    if json.loads((STORE / "state.json").read_text(encoding="utf-8")).get("current") != ENTRY:
        raise SystemExit("ADMIN entry current Context is not practice.")
    if (STORE / "contexts" / Path(*C.split("/")) / "context.json").exists():
        raise SystemExit("ADMIN scratch root already exists.")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if any(item.get("name") == "admin-v2-practice-source-inactive" for item in registry["profiles"]):
        raise SystemExit("ADMIN inactive Profile test name already exists.")
    if EVAL_LEDGER.exists() and any(EVAL_LEDGER.rglob("*.json")):
        raise SystemExit("ADMIN Eval ledger already contains run records.")

    record_host(
        "phase_entry_boundary",
        current_context=ENTRY,
        scratch_absent=True,
        source_sha256=sha(SOURCE_PATH),
        context_tree_sha256=context_tree_digest(),
        registry_sha256=sha(REGISTRY),
        config_sha256=sha(CONFIG),
        staged_update_granted_target=staged_granted_target(),
        result="PASS",
    )
    assert_identity(label="ADMIN phase entry")
    round_1()
    round_2()
    round_3()
    round_4()
    round_5()

    counts = Counter(
        operation for operation, values in attempts_by_operation.items() for _ in values
    )
    if sequence != 105 or set(counts.values()) != {5} or set(counts) != set(OPERATIONS):
        raise RuntimeError(f"ADMIN attempt contract failed: {sequence}, {counts}")
    if sha(SOURCE_PATH) != SOURCE_DIGEST:
        raise RuntimeError("practice/source changed during ADMIN.")
    final_registry = profile_config.load_profile_registry()
    if final_registry.active.uid != PROFILE_UID:
        raise RuntimeError("ADMIN finished on the wrong active Profile.")
    if json.loads((STORE / "state.json").read_text(encoding="utf-8")).get("current") != ENTRY:
        raise RuntimeError("ADMIN did not restore ENTRY current Context.")
    persist_ledger()
    print("ADMIN_CAPTURE_COMPLETE 105/105", flush=True)


if __name__ == "__main__":
    main()
