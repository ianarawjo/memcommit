#!/usr/bin/env python3
"""Run task-1's 105 counted ADMIN attempts exactly once.

Every counted command crosses the pinned world runner.  Identity, stack,
delivery-state, and shell-consumer checks are host reads and never invoke mem.
The harness stops before any Undo/Redo mutation if command-stack construction
fails, after persisting the raw producer receipt and authority evidence.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time


WORLD_NAME = "task-1"
ROOT = Path(__file__).resolve().parent
AUDIT_ROOT = ROOT.parents[1]
RAW = ROOT / "raw/admin"
LEDGER = ROOT / "phase-admin.json"
HOST_READS = ROOT / "admin-host-reads.json"
RUNNER = AUDIT_ROOT / "run_world_mem.py"
CODE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-snapshots/"
    "memcommit-six-world-v2-20260825-code"
)
LANE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-1"
)
PROFILE_CONTROL = LANE / "profile-control"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROFILE_NAME = "sixworld-v2-template"
STORE = PROFILE_CONTROL / "stores" / PROFILE_UID
REGISTRY = PROFILE_CONTROL / "registry.json"
CONFIG = PROFILE_CONTROL / "authoring-store/config.json"
EVAL_LEDGER = LANE / "admin-eval-ledger"
TRANSFORM_LEDGER = ROOT / "phase-transform.json"

CODE_SHA = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROVIDER_SHA = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"

C = "task-1/participant/admin-v2-scratch"
R = "practice"
R_CHILD = "practice/source"
O = "task-2"
O_CHILD = "task-2/description"
ENTRY = "practice"
IMPORT_PROFILE = "task-1"
IMPORT_CONTEXT = "participant/construction-updates"
IMPORT_MEMORY_CONTEXT = "participant/construction-updates/building-access"
IMPORT_MEMORY_UID = "8b077f2a-6a9f-50f0-ae91-f6536fb226cb"
SOURCE_PATH = STORE / "contexts/practice/source/context.json"

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
attempts_by_operation: dict[str, list[dict[str, object]]] = {op: [] for op in OPERATIONS}
sequence = 0
round_number = 0
prior_post_digest = ""
shell_init_m1: str | None = None
eval_run_id: str | None = None
source_digest = ""
transform_final_digest = ""


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def lane_digest() -> str:
    """Match CORE/TRANSFORM's length-delimited full profile-control digest."""
    digest = hashlib.sha256()
    for path in sorted(path for path in PROFILE_CONTROL.rglob("*") if path.is_file()):
        if path.suffix == ".lock" or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(PROFILE_CONTROL).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def target_digest(names: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for name in sorted(set(names)):
        path = STORE / "contexts" / Path(*name.split("/")) / "context.json"
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<absent>")
        digest.update(b"\0")
    return digest.hexdigest()


def delivery_digest(root: Path) -> str:
    """Hash delivery-visible state, excluding append-only command ledgers/locks."""
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = path.relative_to(root)
        if "ledger" in relative.parts or path.suffix == ".lock":
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def other_store_digest() -> str:
    digest = hashlib.sha256()
    stores = PROFILE_CONTROL / "stores"
    for path in sorted(path for path in stores.rglob("*") if path.is_file()):
        if STORE in path.parents or "ledger" in path.parts or path.suffix == ".lock":
            continue
        relative = path.relative_to(stores)
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def persist_host_reads() -> None:
    HOST_READS.write_text(json.dumps({
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": WORLD_NAME,
        "phase": "admin",
        "counted_mem_calls": sequence,
        "host_reads": host_reads,
    }, ensure_ascii=False, indent=2) + "\n")


def record_host(kind: str, **data: object) -> None:
    host_reads.append({
        "index": len(host_reads) + 1,
        "after_counted_sequence": sequence,
        "kind": kind,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **data,
    })
    persist_host_reads()


def assert_identity(*, label: str) -> dict[str, str]:
    registry = profile_config.load_profile_registry()
    resolved = profile_config.resolve_active_store_dir().resolve()
    actual = {
        "profile_name": registry.active.name,
        "profile_uid": registry.active.uid,
        "resolved_store": str(resolved),
    }
    expected = {
        "profile_name": PROFILE_NAME,
        "profile_uid": PROFILE_UID,
        "resolved_store": str(STORE.resolve()),
    }
    if actual != expected:
        record_host("identity_assertion", label=label, result="FAIL", actual=actual, expected=expected)
        raise RuntimeError(f"Pinned identity changed after {label}: {actual}")
    record_host("identity_assertion", label=label, result="PASS", **actual)
    return actual


def staged_granted_target() -> object:
    path = STORE / "staged-update.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text()).get("granted_target")


def raw_stack_fallback(label: str, error: Exception) -> None:
    """Freeze raw producer receipt evidence, then stop without mutation."""
    candidates: list[tuple[str, Path, dict, dict]] = []
    for path in (STORE / "contexts").rglob("checkpoints/*.json"):
        try:
            value = json.loads(path.read_text())
        except Exception:
            continue
        args = value.get("args")
        receipt = args.get("branch_tree") if isinstance(args, dict) else None
        if isinstance(receipt, dict) and receipt.get("operation_uid"):
            candidates.append((str(value.get("timestamp", "")), path, value, receipt))
    candidates.sort(key=lambda item: (item[0], str(item[1])))
    raw = None
    if candidates:
        _, path, checkpoint, receipt = candidates[-1]
        raw = {
            "receipt_checkpoint": str(path),
            "receipt_checkpoint_uid": checkpoint.get("uid"),
            "operation_uid": receipt.get("operation_uid"),
            "source_root": receipt.get("source_root"),
            "target_root": receipt.get("target_root"),
            "include_descendants": receipt.get("include_descendants"),
            "current_before": receipt.get("current_before"),
            "members": [
                {"source_uid": item.get("source_uid"), "source_name": item.get("source_name"),
                 "target_uid": item.get("target_uid"), "target_name": item.get("target_name")}
                for item in receipt.get("contexts", [])
            ],
        }
    record_host(
        "command_stack_builder_error",
        label=label,
        error=f"{type(error).__name__}: {error}",
        raw_exact_producer=raw,
        staged_update_granted_target=staged_granted_target(),
        action="STOPPED before Undo/Redo mutation; parent decision required",
        result="BLOCKED",
    )


def branch_checkpoint_gate(*, label: str, source: str, recursive: bool) -> None:
    """Require a checkpoint-free producer Source before Branch/Checkout -b."""
    contexts_root = STORE / "contexts"
    source_path = contexts_root / Path(*source.split("/"))
    roots = [source_path]
    if recursive and source_path.exists():
        roots = [path.parent for path in source_path.rglob("context.json")]
    branch_receipts: list[dict[str, object]] = []
    for root in sorted(set(roots)):
        for checkpoint_path in root.glob("checkpoints/*.json"):
            try:
                value = json.loads(checkpoint_path.read_text())
            except Exception:
                continue
            args = value.get("args")
            receipt = args.get("branch_tree") if isinstance(args, dict) else None
            if isinstance(receipt, dict) and receipt.get("operation_uid"):
                branch_receipts.append({
                    "checkpoint": str(checkpoint_path),
                    "operation_uid": receipt.get("operation_uid"),
                    "source_root": receipt.get("source_root"),
                    "target_root": receipt.get("target_root"),
                })
    record_host("producer_source_branch_checkpoint_gate", label=label, source=source,
                recursive=recursive, branch_checkpoint_count=len(branch_receipts),
                branch_receipts=branch_receipts, result="PASS" if not branch_receipts else "FAIL")
    if branch_receipts:
        raise RuntimeError(f"{label}: Source {source} contains existing Branch checkpoints")


def stack_snapshot(*, label: str, side: str, expected_uid: str | None = None) -> str:
    try:
        stacks = build_command_stacks(MemoryStore(root=STORE, create=False, resolve_granted_links=False))
    except Exception as error:
        raw_stack_fallback(label, error)
        raise RuntimeError(f"STACK_BUILDER_GATE: {type(error).__name__}: {error}") from error
    stack = stacks.undo if side == "undo" else stacks.redo
    if not stack:
        raise RuntimeError(f"{label}: {side} stack is empty")
    unit = stack[-1]
    members = [
        {"context_uid": change.context_uid, "context_name": change.context_name, "checkpoint_uid": change.checkpoint_uid}
        for change in unit.changes
    ]
    granted = staged_granted_target()
    if unit.command not in {"branch", "checkout"}:
        raise RuntimeError(f"{label}: expected branch/checkout producer, got {unit.command}")
    if expected_uid is not None and unit.uid != expected_uid:
        raise RuntimeError(f"{label}: expected unit {expected_uid}, got {unit.uid}")
    if granted is not None:
        raise RuntimeError(f"{label}: staged-update.granted_target is not null")
    record_host("command_stack_assertion", label=label, side=side, unit_uid=unit.uid,
                command=unit.command, member_set=members, staged_update_granted_target=granted, result="PASS")
    return unit.uid


def compact(stdout: str, stderr: str, exit_code: int) -> str:
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", "\n".join((stdout, stderr))).replace("\r", "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return f"Exit {exit_code} with no visible output."
    chosen = lines if len(lines) <= 9 else lines[:7] + ["…"] + lines[-1:]
    return (f"Exit {exit_code}. " + " | ".join(chosen))[:3200]


def expected_for(operation: str, attempt: int) -> str:
    base = {
        "status": "Report orientation/scope without mutation; incompatible direct+recursive flags fail safely.",
        "branch": "Create only the declared scratch branch and one exact command-stack unit, or fail atomically.",
        "checkout": "Switch/create only the exact declared Context; missing targets fail safely.",
        "config": "Read or mutate only lane-local config; missing values fail before change.",
        "eval": "Keep Eval evidence lane-local, run one declared case, and validate its full run ID.",
        "help": "Provide local/exact lookup while copied-text guard fails before provider.",
        "import": "Import only declared by-value evidence into scratch; collision/missing Profile fails atomically.",
        "init": "Create only declared scratch names; collision/UID/missing-parent boundaries do not broaden scope.",
        "init-study": "Fail before creating or activating any Study/Profile; active identity remains pinned.",
        "lock": "Apply exactly the declared current/tree/Memory/Profile protection scope.",
        "log": "Render only requested retained history scope without mutation.",
        "profile": "Inspect/create inactive/use same active/missing selection without identity drift.",
        "provider": "Inspect locked routing or perform only the single probe; Study-locked change is rejected.",
        "pwd": "Print the exact current Context without loading content or mutation.",
        "redo": "Redo the host-verified top producer unit, or fail when no redo exists.",
        "rename": "Rename only scratch; lock and declined-confirmation boundaries publish no rename.",
        "share": "Stop before delivery and preserve sender/other-store delivery digests.",
        "shell-init": "Emit stable zsh integration; host checks never invoke mem; unsupported bash fails.",
        "switch": "Move only the current pointer through the declared route and preserve stack identity.",
        "undo": "Undo the host-verified local producer with granted_target null; protection fails atomically.",
        "unlock": "Remove exactly the paired protection scope.",
    }[operation]
    return base + f" ADMIN method M{attempt}."


def persist_ledger() -> None:
    records = sorted((item for values in attempts_by_operation.values() for item in values), key=lambda item: item["sequence"])
    ledger = {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": WORLD_NAME,
        "phase": "admin",
        "status": "running" if len(records) < 105 else "complete",
        "contract": {"operations": 21, "attempts_per_operation": 5, "attempts": 105},
        "sequence_semantics": "Phase-local ADMIN sequence 1..105; TRANSFORM used its own phase-local sequence 1..120.",
        "execution_identity": {
            "code_sha": CODE_SHA, "code_sha256": CODE_SHA,
            "catalog_sha": CATALOG_SHA, "catalog_sha256": CATALOG_SHA,
            "profile_uid": PROFILE_UID, "profile_name": PROFILE_NAME,
            "lane_store_root": str(STORE), "store_root": str(STORE),
            "provider_digest": PROVIDER_SHA, "provider_policy_sha256": PROVIDER_SHA,
            "runner": f"python {RUNNER} {WORLD_NAME}",
        },
        "starting_boundary": {
            "cumulative_from_transform": True,
            "transform_final_digest": transform_final_digest,
            "admin_initial_digest": records[0]["pre_target_digest"] if records else prior_post_digest,
            "matches_transform_final_digest": (records[0]["pre_target_digest"] if records else prior_post_digest) == transform_final_digest,
            "no_reset": True,
            "entry_current_context": ENTRY,
            "scratch_root_absent_at_entry": True,
        },
        "interleave_exceptions": [{
            "operation": "switch",
            "attempts": ["switch#1", "switch#2"],
            "sequences": [21, 22],
            "commands": ["mem switch --previous", "mem switch --next"],
            "rationale": "Protocol-required round-1 last --previous then round-2 first --next with no intervening mem call.",
        }],
        "execution_boundary": {
            "entry_current_context": ENTRY, "scratch_root": C,
            "existing_root": R, "existing_child": R_CHILD,
            "separate_existing_root": O, "separate_existing_child": O_CHILD,
            "eval_ledger": str(EVAL_LEDGER), "representative_tui_lane": False, "screenshots": 0,
        },
        "operations": {op: {"attempts": attempts_by_operation[op]} for op in OPERATIONS},
        "non_counted_host_read_ledger": HOST_READS.name,
        "source_guard": {"path": str(SOURCE_PATH), "entry_sha256": source_digest,
                         "current_sha256": sha(SOURCE_PATH), "preserved": sha(SOURCE_PATH) == source_digest},
        "coverage": {
            "operations": 21, "attempts_per_operation": 5, "counted_actual_mem_commands": len(records),
            "exit_zero": sum(item["exit"] == 0 for item in records),
            "nonzero_boundary_or_failure": sum(item["exit"] != 0 for item in records),
            "wall_seconds": round(sum(item["cost"]["wall_seconds"] for item in records), 6),
            "tui_attempts": 0,
            "continuity_breaks": sum(not item["state_continuity_facts"]["same_as_previous_post"] for item in records),
        },
    }
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")


def run(operation: str, args: list[str], *, method: str, targets: tuple[str, ...] = (), stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
    global sequence, prior_post_digest
    sequence += 1
    attempt = len(attempts_by_operation[operation]) + 1
    command = ["python", str(RUNNER), WORLD_NAME, *args]
    command_text = shlex.join(command)
    before_lane = lane_digest()
    if before_lane != prior_post_digest:
        raise RuntimeError(f"lane continuity break before sequence {sequence}: {before_lane} != {prior_post_digest}")
    before_selected = target_digest(targets)
    before_registry, before_config, before_source = sha(REGISTRY), sha(CONFIG), sha(SOURCE_PATH)
    entry_current = json.loads((STORE / "state.json").read_text()).get("current")
    pre_share = None
    if operation == "share":
        pre_share = {"sender": delivery_digest(STORE), "other_stores": other_store_digest(), "registry": sha(REGISTRY)}
        record_host("share_pre_delivery_digest", attempt=attempt, **pre_share)
    started = time.monotonic()
    completed = subprocess.run(command, text=True, input=stdin_text, capture_output=True, check=False)
    elapsed = time.monotonic() - started

    # Required first post-process observation.
    identity = assert_identity(label=f"admin sequence {sequence} {operation} M{attempt}")
    after_lane = lane_digest()
    after_selected = target_digest(targets)
    after_registry, after_config, after_source = sha(REGISTRY), sha(CONFIG), sha(SOURCE_PATH)
    if after_source != source_digest:
        raise RuntimeError(f"Source guard changed at sequence {sequence}")
    share_evidence = None
    if operation == "share":
        post_share = {"sender": delivery_digest(STORE), "other_stores": other_store_digest(), "registry": sha(REGISTRY)}
        record_host("share_post_delivery_digest", attempt=attempt, **post_share)
        share_evidence = {"pre": pre_share, "post": post_share, "unchanged": pre_share == post_share, "delivery": "zero"}
        if pre_share != post_share:
            raise RuntimeError(f"Share M{attempt} changed delivery-visible state")

    slug = operation.replace("-", "_")
    raw_path = RAW / f"{sequence:03d}-{slug}-m{attempt}.txt"
    raw_path.write_text(
        f"COMMAND\n{command_text}\n\nSTDIN\n{'<none>' if stdin_text is None else repr(stdin_text)}\n\n"
        f"EXIT\n{completed.returncode}\n\nWALL_SECONDS\n{elapsed:.6f}\n\n"
        f"POST_CALL_IDENTITY_HOST_ASSERTION\n{json.dumps(identity, ensure_ascii=False, sort_keys=True)}\n\n"
        f"STDOUT\n{completed.stdout}\n\nSTDERR\n{completed.stderr}"
    )
    no_reset = f"no reset; same pinned Profile UID {PROFILE_UID} and lane Store {STORE}"
    record = {
        "attempt": attempt, "sequence": sequence, "command": command_text, "exit": completed.returncode,
        "starting_state": f"One cumulative no-reset Store; ADMIN round {round_number}; phase-local sequence {sequence}; current={entry_current}; pre-lane-digest={before_lane}; previous-post={prior_post_digest}.",
        "entry_route": f"pinned noninteractive ADMIN CLI · M{attempt} · {method} · argv={shlex.join(args)}",
        "target_route": ", ".join(targets) if targets else "Profile/process-local admin surface",
        "scope": f"ADMIN round {attempt} exact argv · {method}",
        "input_provenance": f"cumulative CORE+TRANSFORM+ADMIN Store; protocol M{attempt}; actual argv `{shlex.join(args)}`",
        "consumer": "admin safety, recoverability, orientation, and exact-identity audit",
        "expected": expected_for(operation, attempt),
        "actual": compact(completed.stdout, completed.stderr, completed.returncode),
        "defect_ids": [],
        "cost": {"wall_seconds": round(elapsed, 6), "output_bytes": len((completed.stdout + completed.stderr).encode()),
                 "output_lines": (completed.stdout + completed.stderr).count("\n"), "timed_out": False, "tui": False,
                 "terminal_screens": 0, "extra_manual_steps": 0 if stdin_text is None else 1},
        "pre_target_digest": before_lane, "post_target_digest": after_lane,
        "pre_selected_target_digest": before_selected, "post_selected_target_digest": after_selected,
        "pre_registry_digest": before_registry, "post_registry_digest": after_registry,
        "pre_config_digest": before_config, "post_config_digest": after_config,
        "recovery_evidence": "Transaction-specific host stack evidence or paired recovery is in admin-host-reads.json; otherwise no recovery required.",
        "state_continuity": f"{no_reset}; pre digest equals prior phase-local post digest; post-call Profile identity host-read PASS.",
        "state_continuity_facts": {"reset": False, "same_as_previous_post": before_lane == prior_post_digest,
                                   "lane_digest_changed": before_lane != after_lane, "one_cumulative_store": True,
                                   "source_digest_preserved": after_source == source_digest, "post_call_identity_asserted": True},
        "raw_output": str(raw_path.relative_to(ROOT)),
        "evidence_id": f"T1-V2-ADMIN-{sequence:03d}",
    }
    if share_evidence is not None:
        record["share_evidence"] = share_evidence
    attempts_by_operation[operation].append(record)
    prior_post_digest = after_lane
    persist_ledger()
    print(f"ADMIN {sequence:03d}/105 · {operation} M{attempt} · exit {completed.returncode} · {elapsed:.2f}s", flush=True)
    return completed


def host_shell_check(kind: str, command: list[str], input_text: str) -> None:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    record_host(kind, command=shlex.join(command), exit=result.returncode, stdout=result.stdout,
                stderr=result.stderr, result="PASS" if result.returncode == 0 else "FAIL")
    if result.returncode != 0:
        raise RuntimeError(f"Host shell check failed: {kind}: {result.stderr}")


def round_1() -> None:
    global round_number, shell_init_m1
    round_number = 1
    branch_checkpoint_gate(label="Branch1 direct Source", source=R, recursive=False)
    run("branch", ["branch", f"{C}/b1", "--from", R, "--direct"], method="direct explicit Source branch", targets=(R, f"{C}/b1"))
    unit = stack_snapshot(label="round1 immediately before Undo1", side="undo")
    run("undo", ["undo"], method="verified direct Branch undo", targets=(f"{C}/b1",))
    stack_snapshot(label="round1 redo-top same UID", side="redo", expected_uid=unit)
    run("redo", ["redo"], method="verified direct Branch redo", targets=(f"{C}/b1",))
    run("lock", ["lock"], method="frozen current Context lock", targets=(f"{C}/b1",))
    run("unlock", ["unlock"], method="paired current Context unlock", targets=(f"{C}/b1",))
    run("checkout", ["checkout", R], method="exact existing Context checkout", targets=(R,))
    run("status", ["status", "--short"], method="short orientation", targets=(R,))
    run("config", ["config"], method="lane-local config inventory")
    run("eval", ["eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)], method="empty semantic Eval status")
    run("help", ["help"], method="non-TTY deterministic inventory")
    run("init", ["init", C], method="exact scratch root creation", targets=(C,))
    run("import", ["import", "context", f"{IMPORT_CONTEXT}/building-access", "--from-profile", IMPORT_PROFILE, "--as", f"{C}/import-direct", "--direct"], method="direct Context by-value import", targets=(f"{C}/import-direct",))
    run("rename", ["rename", f"{C}/import-direct", f"{C}/renamed-import-direct", "--force"], method="positive-control rename of import-created scratch", targets=(f"{C}/import-direct", f"{C}/renamed-import-direct"))
    run("init-study", ["init-study", "admin/v2-task-1"], method="invalid slash Study name")
    run("log", ["log", "--context", C], method="scratch Context history", targets=(C,))
    run("profile", ["profile", "current"], method="exact active Profile inspection")
    run("provider", ["provider"], method="bare locked Study provider overview")
    run("pwd", ["pwd"], method="post-init current pointer", targets=(C,))
    run("share", ["share"], method="non-TTY incomplete bare Share")
    shell = run("shell-init", ["shell-init"], method="default zsh integration output")
    shell_init_m1 = shell.stdout
    run("switch", ["switch", "--previous"], method="round-boundary previous navigation", targets=(ENTRY, C))


def round_1_resume_after_status() -> None:
    """Continue the intentionally interrupted pre-correction run at sequence 8."""
    global round_number, shell_init_m1
    round_number = 1
    # Branch1's Source was unchanged by the already-counted direct Branch; the
    # correction arrived after sequence 7, so freeze the zero-receipt positive
    # control before any later producer and explicitly label it retrospective.
    branch_checkpoint_gate(label="Branch1 direct Source retrospective positive-control after correction", source=R, recursive=False)
    run("config", ["config"], method="lane-local config inventory")
    run("eval", ["eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)], method="empty semantic Eval status")
    run("help", ["help"], method="non-TTY deterministic inventory")
    run("init", ["init", C], method="exact scratch root creation", targets=(C,))
    run("import", ["import", "context", f"{IMPORT_CONTEXT}/building-access", "--from-profile", IMPORT_PROFILE, "--as", f"{C}/import-direct", "--direct"], method="direct Context by-value import", targets=(f"{C}/import-direct",))
    run("rename", ["rename", f"{C}/import-direct", f"{C}/renamed-import-direct", "--force"], method="positive-control rename of import-created scratch", targets=(f"{C}/import-direct", f"{C}/renamed-import-direct"))
    run("init-study", ["init-study", "admin/v2-task-1"], method="invalid slash Study name")
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
    run("status", ["status", "--branch"], method="Profile and Context lineage status")
    run("config", ["config", "set", "audit_v2_world", WORLD_NAME], method="lane-only audit world key")
    before_runs = set(EVAL_LEDGER.glob("**/*.json"))
    result = run("eval", ["eval", "semantic", "run", "ambiguity", "--provider", "codex_chatgpt", "--model", "gpt-5.6-sol", "--reasoning", "none", "--pipeline", "v2", "--corpus", "calibration", "--runs", "1", "--case", "single-none-main-entrance-hours", "--ledger-dir", str(EVAL_LEDGER)], method="one-case ambiguity Eval under frozen provider/model policy")
    created = sorted(set(EVAL_LEDGER.glob("**/*.json")) - before_runs)
    if result.returncode not in {0, 1} or len(created) != 1:
        raise RuntimeError(f"Expected exactly one Eval ledger record, got {created}")
    eval_record = json.loads(created[0].read_text())
    eval_run_id = str(eval_record.get("run_id") or eval_record.get("full_run_id"))
    record_host("eval_full_run_id", path=str(created[0]), run_id=eval_run_id, result="PASS")
    run("help", ["help", "Which operation gives a grounded answer from readable memories without changing them?"], method="synthetic natural-language Help lookup")
    run("init", ["init", f"{C}/tree/leaf", "--parents"], method="parent-expanding nested init", targets=(C, f"{C}/tree", f"{C}/tree/leaf"))
    run("import", ["import", "context", IMPORT_CONTEXT, "--from-profile", IMPORT_PROFILE, "--as", f"{C}/import-tree", "--recursive"], method="recursive Context-tree import", targets=(f"{C}/import-tree", f"{C}/import-tree/building-access"))
    run("init-study", ["init-study", "authoring"], method="reserved authoring Profile name")
    run("log", ["log", "--context", C, "--manual"], method="manual-only scratch history", targets=(C,))
    run("profile", ["profile", "create", "admin-v2-task-1-inactive"], method="create one inactive managed Profile")
    run("provider", ["provider", "status"], method="effective default provider status")
    run("pwd", ["pwd"], method="nested-init current pointer", targets=(f"{C}/tree/leaf",))
    run("share", ["share", "task-1/participant/admin-v2-missing-share-source", "--to", "admin-v2-missing-endpoint"], method="missing explicit Share Source")
    shell = run("shell-init", ["shell-init", "zsh"], method="explicit zsh output")
    if shell_init_m1 is None or shell.stdout != shell_init_m1:
        raise RuntimeError("shell-init default and explicit zsh outputs differ")
    record_host("shell_init_byte_equality", sha256=hashlib.sha256(shell.stdout.encode()).hexdigest(), result="PASS")
    branch_checkpoint_gate(label="Branch2 recursive Source", source=R, recursive=True)
    run("branch", ["branch", f"{C}/b2-tree", "--from", R, "--recursive"], method="recursive explicit Source branch", targets=(R, f"{C}/b2-tree", f"{C}/b2-tree/source"))
    unit = stack_snapshot(label="round2 immediately before Undo2 --keep", side="undo")
    run("undo", ["undo", "--keep"], method="verified recursive Branch undo compatibility route", targets=(f"{C}/b2-tree", f"{C}/b2-tree/source"))
    stack_snapshot(label="round2 redo-top same UID", side="redo", expected_uid=unit)
    run("redo", ["redo"], method="verified recursive Branch redo", targets=(f"{C}/b2-tree", f"{C}/b2-tree/source"))
    run("lock", ["lock", f"{C}/b2-tree", "--recursive"], method="recursive branch-tree lock", targets=(f"{C}/b2-tree", f"{C}/b2-tree/source"))
    run("unlock", ["unlock", f"{C}/b2-tree", "--recursive"], method="paired recursive branch-tree unlock", targets=(f"{C}/b2-tree", f"{C}/b2-tree/source"))
    run("rename", ["rename", f"{C}/tree/leaf", f"{C}/tree/renamed-leaf-r2", "--force"], method="positive-control rename of init-created leaf", targets=(f"{C}/tree/leaf", f"{C}/tree/renamed-leaf-r2"))


def round_3() -> None:
    global round_number
    round_number = 3
    clean_branch_source = f"{C}/tree/renamed-leaf-r2"
    branch_checkpoint_gate(label="Branch3 clean import-created Source", source=clean_branch_source, recursive=False)
    run("branch", ["branch", f"{C}/b3", "--from", clean_branch_source, "--source-root-only"], method="checkpoint-free import-created Source root-only", targets=(clean_branch_source, f"{C}/b3"))
    run("checkout", ["checkout", R], method="pre-Checkout3 exact clean Source checkout", targets=(R,))
    run("status", ["status", "--recursive"], method="read-only interleave after clean Checkout and before Checkout3", targets=(R, R_CHILD))
    branch_checkpoint_gate(label="Checkout3 direct clean current Source", source=R, recursive=False)
    run("checkout", ["checkout", "-b", f"{C}/co3", "--direct"], method="Git-style direct branch checkout", targets=(f"{C}/b3", f"{C}/co3"))
    unit = stack_snapshot(label="round3 Checkout3 producer before Switch O", side="undo")
    run("switch", ["switch", O], method="switch away while Checkout3 stays stack-top", targets=(O, f"{C}/co3"))
    stack_snapshot(label="round3 top UID unchanged immediately before Undo3", side="undo", expected_uid=unit)
    run("undo", ["undo"], method="verified Checkout3 undo after independent Switch", targets=(f"{C}/co3", O))
    stack_snapshot(label="round3 redo-top same UID", side="redo", expected_uid=unit)
    run("redo", ["redo"], method="verified Checkout3 redo preserving independent current", targets=(f"{C}/co3", O))
    run("config", ["config", "show"], method="explicit lane config show")
    if eval_run_id is None or eval_run_id == "None":
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
    run("init-study", ["init-study", "admin-v2-task-1-study", "--scenario", "legacy-v1", "--from-profile", "admin-v2-missing-baseline"], method="missing baseline Profile")
    run("rename", ["rename", f"{C}/tree", f"{C}/renamed-tree-r3", "--force"], method="positive-control rename of init-created scratch tree", targets=(f"{C}/tree", f"{C}/renamed-tree-r3"))


def round_2_resume_after_eval() -> None:
    """Resume after the host-recovered counted Eval M2 at sequence 25."""
    global round_number
    round_number = 2
    run("help", ["help", "Which operation gives a grounded answer from readable memories without changing them?"], method="synthetic natural-language Help lookup")
    run("init", ["init", f"{C}/tree/leaf", "--parents"], method="parent-expanding nested init", targets=(C, f"{C}/tree", f"{C}/tree/leaf"))
    run("import", ["import", "context", IMPORT_CONTEXT, "--from-profile", IMPORT_PROFILE, "--as", f"{C}/import-tree", "--recursive"], method="recursive Context-tree import", targets=(f"{C}/import-tree", f"{C}/import-tree/building-access"))
    run("init-study", ["init-study", "authoring"], method="reserved authoring Profile name")
    run("log", ["log", "--context", C, "--manual"], method="manual-only scratch history", targets=(C,))
    run("profile", ["profile", "create", "admin-v2-task-1-inactive"], method="create one inactive managed Profile")
    run("provider", ["provider", "status"], method="effective default provider status")
    run("pwd", ["pwd"], method="nested-init current pointer", targets=(f"{C}/tree/leaf",))
    run("share", ["share", "task-1/participant/admin-v2-missing-share-source", "--to", "admin-v2-missing-endpoint"], method="missing explicit Share Source")
    shell = run("shell-init", ["shell-init", "zsh"], method="explicit zsh output")
    if shell_init_m1 is None or shell.stdout != shell_init_m1:
        raise RuntimeError("shell-init default and explicit zsh outputs differ")
    record_host("shell_init_byte_equality", sha256=hashlib.sha256(shell.stdout.encode()).hexdigest(), result="PASS")
    branch_checkpoint_gate(label="Branch2 recursive Source", source=R, recursive=True)
    run("branch", ["branch", f"{C}/b2-tree", "--from", R, "--recursive"], method="recursive explicit Source branch", targets=(R, f"{C}/b2-tree", f"{C}/b2-tree/source"))
    unit = stack_snapshot(label="round2 immediately before Undo2 --keep", side="undo")
    run("undo", ["undo", "--keep"], method="verified recursive Branch undo compatibility route", targets=(f"{C}/b2-tree", f"{C}/b2-tree/source"))
    stack_snapshot(label="round2 redo-top same UID", side="redo", expected_uid=unit)
    run("redo", ["redo"], method="verified recursive Branch redo", targets=(f"{C}/b2-tree", f"{C}/b2-tree/source"))
    run("lock", ["lock", f"{C}/b2-tree", "--recursive"], method="recursive branch-tree lock", targets=(f"{C}/b2-tree", f"{C}/b2-tree/source"))
    run("unlock", ["unlock", f"{C}/b2-tree", "--recursive"], method="paired recursive branch-tree unlock", targets=(f"{C}/b2-tree", f"{C}/b2-tree/source"))
    run("rename", ["rename", f"{C}/tree/leaf", f"{C}/tree/renamed-leaf-r2", "--force"], method="positive-control rename of init-created leaf", targets=(f"{C}/tree/leaf", f"{C}/tree/renamed-leaf-r2"))


def round_4() -> None:
    global round_number
    round_number = 4
    run("redo", ["redo"], method="early no-redo boundary")
    branch_checkpoint_gate(label="Branch4 collision direct Source", source=R, recursive=False)
    run("branch", ["branch", C, "--from", R, "--direct"], method="existing scratch-root collision", targets=(C, R))
    run("status", ["status", "--direct", "--recursive"], method="conflicting direct+recursive validation", targets=(O,))
    run("config", ["config", "set", "provider", "codex_chatgpt"], method="lane-local semantic provider config key")
    run("eval", ["eval", "semantic", "task2-status", "--all", "--ledger-dir", str(EVAL_LEDGER)], method="all retained Task2 status")
    run("help", ["help", "atomize"], method="different exact Atomize operation lookup")
    run("import", ["import", "memory", IMPORT_MEMORY_UID, "--from-profile", IMPORT_PROFILE, "--context", IMPORT_MEMORY_CONTEXT, "--into", C], method="repeat exact Memory collision", targets=(C,))
    run("init", ["init", "00000000-0000-0000-0000-000000000777"], method="UID-shaped Context name failure")
    run("init-study", ["init-study", "admin-v2-task-1-workers", "--prewarm-workers", "0"], method="prewarm worker validation failure")
    run("log", ["log", "--operations", "--limit", "50"], method="Profile operation-attempt ledger")
    run("profile", ["profile", "use", PROFILE_NAME], method="idempotent use of same active Profile")
    run("provider", ["provider", "use", "codex_chatgpt", "--operation", "query"], method="Study-locked Query provider mutation failure")
    run("pwd", ["pwd"], method="pre-Checkout4 independent root pointer", targets=(O,))
    run("share", ["share", C, "--direct", "--recursive"], method="mutually exclusive Share scope flags", targets=(C,))
    shell = run("shell-init", ["shell-init", "zsh"], method="zsh output sourced in disposable shell")
    host_shell_check("shell_init_disposable_source", ["zsh", "-dfc", "source /dev/stdin; whence -w mem"], shell.stdout)
    branch_checkpoint_gate(label="Checkout4 recursive clean current Source", source=O, recursive=True)
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
    record_host("producer_source_branch_checkpoint_gate", label="Branch5 missing Source", source="task-1/participant/admin-v2-missing-branch-source",
                recursive=False, branch_checkpoint_count=0, branch_receipts=[], absent_source=True, result="PASS")
    run("branch", ["branch", f"{C}/b5", "--from", "task-1/participant/admin-v2-missing-branch-source", "--direct"], method="missing explicit Branch Source", targets=(f"{C}/b5",))
    run("checkout", ["checkout", "task-1/participant/admin-v2-missing-checkout"], method="missing exact checkout target")
    run("config", ["config", "set", "provider"], method="missing config value validation")
    run("eval", ["eval", "semantic", "status", "--ledger-dir", str(EVAL_LEDGER)], method="accumulated semantic Eval status")
    run("help", ["help", "Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view."], method="Study copied-text guard before provider")
    run("import", ["import", "context", IMPORT_CONTEXT, "--from-profile", "admin-v2-missing-source-profile", "--as", f"{C}/import-missing", "--direct"], method="missing source Profile import", targets=(f"{C}/import-missing",))
    run("init", ["init", f"{C}/missing-parent/leaf"], method="missing lexical parent without --parents", targets=(f"{C}/missing-parent/leaf",))
    run("init-study", ["init-study", "admin-v2-task-1-bad-workers-neg", "--from-profile", "study-baseline", "--prewarm-workers", "-1"], method="negative prewarm-worker validation; no UUID-shaped or bare non-TTY name")
    run("lock", ["lock", "--profile"], method="whole active Profile lock")
    run("unlock", ["unlock", "--profile"], method="paired whole active Profile unlock")
    run("log", ["log", "--actions", "--limit", "100"], method="Study action ledger")
    run("profile", ["profile", "use", "admin-v2-task-1-missing"], method="missing Profile selection")
    run("provider", ["provider", "probe", "--operation", "query"], method="single synthetic Query provider probe")
    run("pwd", ["pwd"], method="late accumulated current pointer")
    run("share", ["share", C, "--to", "admin-v2-missing-endpoint", "--direct"], method="valid Source to missing receiver endpoint", targets=(C,))
    run("shell-init", ["shell-init", "bash"], method="unsupported shell validation")
    run("rename", ["rename", f"{C}/co4-tree", f"{C}/renamed-co4-cancel"], method="explicit confirmation declined", targets=(f"{C}/co4-tree", f"{C}/renamed-co4-cancel"), stdin_text="n\n")
    run("switch", ["switch", ENTRY], method="exact phase-entry restoration", targets=(ENTRY,))


def main() -> None:
    global sequence, prior_post_digest, source_digest, transform_final_digest, shell_init_m1, eval_run_id
    transform = json.loads(TRANSFORM_LEDGER.read_text())
    transform_records = sorted((item for values in transform["operations"].values() for item in values["attempts"]), key=lambda item: item["sequence"])
    transform_final_digest = transform_records[-1]["post_target_digest"]
    resuming = LEDGER.exists()
    if resuming:
        existing = json.loads(LEDGER.read_text())
        records = sorted((item for values in existing["operations"].values() for item in values["attempts"]), key=lambda item: item["sequence"])
        persisted_sequences = [item["sequence"] for item in records]
        if persisted_sequences not in (list(range(1, 8)), list(range(1, 26))):
            raise SystemExit("Only the reviewed sequence-7 or recovered sequence-25 interruption is resumable; refusing replay.")
        for operation, payload in existing["operations"].items():
            attempts_by_operation[operation].extend(payload["attempts"])
        sequence = records[-1]["sequence"]
        prior_post_digest = records[-1]["post_target_digest"]
        source_digest = existing["source_guard"]["entry_sha256"]
        transform_final_digest = existing["starting_boundary"]["transform_final_digest"]
        if lane_digest() != prior_post_digest:
            raise SystemExit(f"ADMIN resume lane digest does not match sequence {sequence} post digest.")
        if HOST_READS.exists():
            host_reads.extend(json.loads(HOST_READS.read_text()).get("host_reads", []))
        if sequence >= 20:
            raw_shell = (RAW / "020-shell_init-m1.txt").read_text()
            shell_init_m1 = raw_shell.split("\nSTDOUT\n", 1)[1].split("\n\nSTDERR\n", 1)[0]
        if sequence >= 25:
            runs = sorted((EVAL_LEDGER / "runs").glob("*.json"))
            if len(runs) != 1:
                raise SystemExit("Recovered Eval M2 run ID is unavailable or ambiguous.")
            eval_run_id = str(json.loads(runs[0].read_text())["run_id"])
        record_host("protocol_correction_resume", completed_sequences=persisted_sequences,
                    last_counted="status M1" if sequence == 7 else "eval M2 (host-recovered)",
                    next_counted="config M1" if sequence == 7 else "help M2",
                    reason="Resume without counted replay after reviewed protocol/harness interruption.",
                    result="PASS")
    else:
        if RAW.exists() or HOST_READS.exists():
            raise SystemExit("Partial ADMIN artifacts without a ledger; refusing any replay.")
        prior_post_digest = lane_digest()
        if prior_post_digest != transform_final_digest:
            raise SystemExit(f"ADMIN/TRANSFORM digest bridge mismatch: {prior_post_digest} != {transform_final_digest}")
        if json.loads((STORE / "state.json").read_text()).get("current") != ENTRY:
            raise SystemExit("ADMIN entry current Context is not practice.")
        if (STORE / "contexts" / Path(*C.split("/")) / "context.json").exists():
            raise SystemExit("ADMIN scratch root already exists.")
        registry_value = json.loads(REGISTRY.read_text())
        if any(item.get("name") == "admin-v2-task-1-inactive" for item in registry_value["profiles"]):
            raise SystemExit("ADMIN inactive Profile test name already exists.")
        if EVAL_LEDGER.exists() and any(EVAL_LEDGER.rglob("*.json")):
            raise SystemExit("ADMIN Eval ledger already contains records.")
        RAW.mkdir(parents=True)
        source_digest = sha(SOURCE_PATH) or ""
    def overlaps(left: str, right: str) -> bool:
        return left == right or left.startswith(right + "/") or right.startswith(left + "/")
    if overlaps(R, C) or overlaps(O, C):
        raise SystemExit(f"ADMIN recursive producer Source overlaps scratch: R={R}, O={O}, C={C}")
    if not resuming:
        record_host("phase_entry_boundary", current_context=ENTRY, scratch_absent=True,
                    transform_final_digest=transform_final_digest, admin_initial_digest=prior_post_digest,
                    bridge_matches=True, source_sha256=source_digest, registry_sha256=sha(REGISTRY),
                    config_sha256=sha(CONFIG), staged_update_granted_target=staged_granted_target(),
                    recursive_branch_source=R, recursive_checkout_source=O, scratch_root=C,
                    branch_source_lexically_disjoint=True, checkout_source_lexically_disjoint=True,
                    positive_control="Rename M1-M3 targets are import/init-created scratch; branch/checkout targets are never successfully renamed.",
                    result="PASS")
        assert_identity(label="ADMIN phase entry")
        persist_ledger()
    if resuming and sequence == 7:
        round_1_resume_after_status()
        round_2(); round_3(); round_4(); round_5()
    elif resuming and sequence == 25:
        round_2_resume_after_eval(); round_3(); round_4(); round_5()
    else:
        round_1()
        round_2(); round_3(); round_4(); round_5()
    counts = Counter(op for op, values in attempts_by_operation.items() for _ in values)
    if sequence != 105 or set(counts.values()) != {5} or set(counts) != set(OPERATIONS):
        raise RuntimeError(f"ADMIN attempt contract failed: {sequence}, {counts}")
    if sha(SOURCE_PATH) != source_digest:
        raise RuntimeError("Source guard changed during ADMIN.")
    registry = profile_config.load_profile_registry()
    if registry.active.uid != PROFILE_UID:
        raise RuntimeError("ADMIN finished on wrong Profile.")
    if json.loads((STORE / "state.json").read_text()).get("current") != ENTRY:
        raise RuntimeError("ADMIN did not restore ENTRY current Context.")
    persist_ledger()
    print("ADMIN_CAPTURE_COMPLETE 105/105", flush=True)


if __name__ == "__main__":
    main()
