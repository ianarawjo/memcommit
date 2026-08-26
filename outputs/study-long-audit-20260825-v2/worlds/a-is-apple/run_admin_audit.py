#!/usr/bin/env python3
"""Run the counted ADMIN phase for the cumulative a-is-apple audit lane.

The 105 child processes are the only ``mem`` calls made by this harness.  All
identity, stack, digest, shell, and screenshot work is host-side evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from typing import Callable

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


REPO = Path("/Users/KimMunyeong/Github/memcommit")
AUDIT = REPO / "outputs/study-long-audit-20260825-v2"
WORLD = AUDIT / "worlds/a-is-apple"
RUNNER = AUDIT / "run_world_mem.py"
LEDGER = WORLD / "phase-admin.json"
RAW = WORLD / "raw/admin"
HOST = WORLD / "host_reads/admin"
SHOT_WORLD = WORLD / "screenshots/admin"
SHOT_DOCS = REPO / "docs/screenshots/six-world-audit-v2-20260825/a-is-apple-admin"
PROFILE_CONTROL = Path(
    "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/"
    "worlds/a-is-apple/profile-control"
)
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROFILE_NAME = "sixworld-v2-template"
STORE = PROFILE_CONTROL / "stores" / PROFILE_UID
RECEIVER_UID = "01203d49-da6a-4ee1-9cb6-8321890e8559"
RECEIVER_STORE = PROFILE_CONTROL / "stores" / RECEIVER_UID
CODE_ROOT = Path("/Users/KimMunyeong/.codex/audit-snapshots/memcommit-six-world-v2-20260825-code")
EVAL_DIR = Path(
    "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/"
    "worlds/a-is-apple/admin-eval-ledger"
)

CODE_SHA = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROVIDER_SHA = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"
C = "audit/a-is-apple/admin-v2-scratch"
R = "practice"
O = "practice"
ENTRY = "practice"
R_CHILD = "practice/source"
M = "f1c940a1"
IMPORT_MEMORY = "1cb2aa88"
ENDPOINT = "task-3/government/healthcare-agent"


@dataclass(frozen=True)
class Spec:
    operation: str
    attempt: int
    args: tuple[str, ...] | Callable[[], tuple[str, ...]]
    route: str
    target: str
    scope: str
    provenance: str
    expected: str
    tui: str | None = None
    stdin: str | None = None


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _current() -> str | None:
    return _json(STORE / "state.json").get("current")


def _target_digest() -> str:
    digest = hashlib.sha256()
    contexts = STORE / "contexts"
    for path in sorted(contexts.rglob("context.json")):
        digest.update(path.relative_to(STORE).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(b"state.json\0")
    digest.update((STORE / "state.json").read_bytes())
    return digest.hexdigest()


def _store_digest(root: Path) -> str:
    """Hash delivery-visible durable state, excluding append-only audit logs.

    Every entered Study command appends its attempt/action audit receipt, even
    when Share fails before setup.  Those records prove the attempt but are not
    Share delivery.  Sender/receiver non-delivery therefore compares Context,
    state, Grant, and configuration artifacts while retaining separate full
    Store hashes in the Share evidence.
    """
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == "ledger":
            continue
        if path.name.endswith(".lock"):
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _post_identity(sequence: int) -> Path:
    """First host action after every counted child process exits."""
    registry = _json(PROFILE_CONTROL / "registry.json")
    active_uid = registry.get("active_uid")
    profiles = {item["uid"]: item for item in registry.get("profiles", [])}
    name = profiles.get(active_uid, {}).get("name")
    resolved = (PROFILE_CONTROL / "stores" / str(active_uid)).resolve()
    evidence = {
        "sequence": sequence,
        "read_at": datetime.now(timezone.utc).isoformat(),
        "active_profile_name": name,
        "active_profile_uid": active_uid,
        "resolved_store_root": str(resolved),
        "expected": {
            "name": PROFILE_NAME,
            "uid": PROFILE_UID,
            "store_root": str(STORE.resolve()),
        },
        "matches": name == PROFILE_NAME and active_uid == PROFILE_UID and resolved == STORE.resolve(),
    }
    path = HOST / f"post-identity-{sequence:03d}.json"
    _write_json(path, evidence)
    if not evidence["matches"]:
        raise RuntimeError(f"post-call Profile identity drift at sequence {sequence}")
    return path


def _stack_snapshot(label: str) -> Path:
    if str(CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(CODE_ROOT))
    from memcommit.command_history import build_command_stacks
    from memcommit.store import MemoryStore

    builder_error = None
    try:
        stacks = build_command_stacks(
            MemoryStore(root=STORE, create=False, resolve_granted_links=False)
        )
    except Exception as error:
        # Preserve the product failure, then independently freeze the newest
        # branch receipt's exact UID/member set.  This does not claim a valid
        # stack: it supplies the safety identity required before exercising
        # Undo's own fail-closed handling of the corrupt stack.
        builder_error = f"{type(error).__name__}: {error}"
        candidates = []
        for checkpoint in (STORE / "contexts").rglob("checkpoints/*.json"):
            try:
                value = _json(checkpoint)
            except Exception:
                continue
            args_value = value.get("args")
            record = args_value.get("branch_tree") if isinstance(args_value, dict) else None
            if isinstance(record, dict) and record.get("version") == 1 and record.get("operation_uid"):
                candidates.append((str(value.get("timestamp", "")), value, record, checkpoint))
        candidates.sort(key=lambda item: (item[0], str(item[3])))
        if not candidates:
            raise
        _, checkpoint_value, receipt, checkpoint_path = candidates[-1]
        fallback_unit = {
            "uid": f"branch:{receipt['operation_uid']}",
            "command": "branch",
            "members": [
                {"context_uid": item["target_uid"], "context_name": item["target_name"],
                 "checkpoint_uid": "receipt member; see target Context checkpoint"}
                for item in receipt.get("contexts", [])
            ],
            "receipt_checkpoint": str(checkpoint_path),
            "source_root": receipt.get("source_root"),
            "target_root": receipt.get("target_root"),
            "include_descendants": receipt.get("include_descendants"),
            "current_before": receipt.get("current_before"),
            "receipt_checkpoint_uid": checkpoint_value.get("uid"),
        }
        stacks = None

    def unit(value):
        if value is None:
            return None
        return {
            "uid": value.uid,
            "command": value.command,
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
    staged = _json(staged_path) if staged_path.exists() else None
    value = {
        "label": label,
        "read_at": datetime.now(timezone.utc).isoformat(),
        "undo_top": unit(stacks.undo[-1] if stacks and stacks.undo else None) if stacks else fallback_unit,
        "redo_top": unit(stacks.redo[-1] if stacks and stacks.redo else None) if stacks else None,
        "undo_depth": len(stacks.undo) if stacks else None,
        "redo_depth": len(stacks.redo) if stacks else None,
        "builder_error": builder_error,
        "fallback_semantics": ("Exact newest branch receipt UID/member set only; no valid stack claimed." if builder_error else None),
        "staged_update_exists": staged is not None,
        "staged_update_granted_target": staged.get("granted_target") if isinstance(staged, dict) else None,
    }
    path = HOST / f"stack-{label}.json"
    _write_json(path, value)
    return path


def _clean(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text).replace("\r", "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    summary = " | ".join(lines[:10]) or "No stdout/stderr text was emitted."
    if len(lines) > 10:
        summary += f" | … ({len(lines)} non-empty lines; see raw output)"
    return summary[:3000]


def _ansi_screen(data: bytes) -> pyte.Screen:
    screen = pyte.Screen(180, 52)
    stream = pyte.Stream(screen)
    stream.feed(data.decode("utf-8", "replace"))
    return screen


def _rgb(value: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    names = {
        "black": (0, 0, 0), "red": (205, 49, 49), "green": (13, 188, 121),
        "yellow": (229, 229, 16), "blue": (36, 114, 200), "magenta": (188, 63, 188),
        "cyan": (17, 168, 205), "white": (229, 229, 229), "default": default,
        "brightblack": (102, 102, 102), "brightred": (241, 76, 76),
        "brightgreen": (35, 209, 139), "brightyellow": (245, 245, 67),
        "brightblue": (59, 142, 234), "brightmagenta": (214, 112, 214),
        "brightcyan": (41, 184, 219), "brightwhite": (255, 255, 255),
    }
    if value in names:
        return names[value]
    if re.fullmatch(r"[0-9a-fA-F]{6}", str(value)):
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    return default


def _render(data: bytes, path: Path) -> None:
    screen = _ansi_screen(data)
    font_path = "/System/Library/Fonts/Menlo.ttc"
    font = ImageFont.truetype(font_path, 15)
    bold = ImageFont.truetype(font_path, 15, index=1)
    cell_w, cell_h = 9, 19
    image = Image.new("RGB", (180 * cell_w + 24, 52 * cell_h + 24), (12, 12, 16))
    draw = ImageDraw.Draw(image)
    for y in range(52):
        for x in range(180):
            char = screen.buffer[y][x]
            fg = _rgb(str(char.fg), (229, 229, 229))
            bg = _rgb(str(char.bg), (12, 12, 16))
            px, py = 12 + x * cell_w, 12 + y * cell_h
            if char.reverse:
                fg, bg = bg, fg
            if bg != (12, 12, 16):
                draw.rectangle((px, py, px + cell_w, py + cell_h), fill=bg)
            if char.data != " ":
                draw.text((px, py), char.data, font=bold if char.bold else font, fill=fg)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _tui_steps(kind: str, child, buf: BytesIO, sequence: int, operation: str, attempt: int):
    shots: list[Path] = []
    log: list[dict] = []

    def snap(label: str, key: str = "none", mutation: bool = False) -> None:
        time.sleep(0.25)
        data = buf.getvalue()
        number = len(shots) + 1
        name = f"{sequence:03d}-{operation}-{attempt}-{number:02d}-{label}.png"
        world_path = SHOT_WORLD / name
        docs_path = SHOT_DOCS / name
        _render(data, world_path)
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        if docs_path.exists():
            docs_path.unlink()
        os.link(world_path, docs_path)
        shots.append(world_path)
        log.append({
            "step": number, "screenshot": str(world_path.relative_to(AUDIT)),
            "docs_copy": str(docs_path.relative_to(REPO)), "preceding_keys_or_text": key,
            "visible_state": label, "durable_state_mutated_at_step": mutation,
        })

    time.sleep(0.8)
    snap("entry")
    if kind == "cancel":
        child.send(b"\x1b")
    elif kind == "help-form":
        child.send(b"\x1b[B\r")
        snap("operation-and-form", "Down, Enter")
        child.send(b"q")
    elif kind == "help-emit":
        child.send(b"\x1b[B\r")
        snap("operation-selected", "Down, Enter")
        child.send(b"\r")
    elif kind == "branch":
        child.send(b"\x1b[B\x15" + f"{C}/b5-tui".encode())
        snap("target-input", f"Down, Ctrl-U, type {C}/b5-tui")
        child.send(b"\x1b[B")
        snap("apply-review", "Down")
        child.send(b"\r")
    elif kind == "switch-entry":
        # Left repeatedly climbs from the scratch descendant to root audit;
        # Down reaches the next root, practice, without using a hidden locator.
        child.send(b"\x1b[D" * 12)
        snap("root-navigation", "Left ×12")
        child.send(b"\x1b[B")
        snap("entry-target-selected", "Down")
        child.send(b"\r")
    else:
        raise RuntimeError(kind)
    return shots, log


def _run_tui(spec: Spec, args: tuple[str, ...], sequence: int):
    env = os.environ.copy()
    env.pop("NO_COLOR", None)
    env.update({"TERM": "xterm-256color", "COLORTERM": "truecolor", "MEMCOMMIT_AUDIT_COLOR": "1"})
    buf = BytesIO()
    child = pexpect.spawn(
        sys.executable, [str(RUNNER), "a-is-apple", *args], cwd=str(REPO), env=env,
        dimensions=(52, 180), timeout=60, encoding=None,
    )
    child.logfile = buf
    began = time.monotonic()
    shots, log = _tui_steps(spec.tui or "cancel", child, buf, sequence, spec.operation, spec.attempt)
    timed_out = False
    try:
        child.expect(pexpect.EOF, timeout=180)
    except pexpect.TIMEOUT:
        timed_out = True
        child.close(force=True)
    else:
        child.close()
    elapsed = time.monotonic() - began
    data = buf.getvalue()
    post_identity = _post_identity(sequence)
    # Receipt is a distinct state even when a cancellation receipt is the only
    # post-TUI line.  Render it after the mandatory immediate identity read.
    receipt_label = "success-receipt" if child.exitstatus == 0 and spec.tui in {"branch", "switch-entry", "help-emit"} else "cancel-or-failure-receipt"
    receipt_name = f"{sequence:03d}-{spec.operation}-{spec.attempt}-{len(shots)+1:02d}-{receipt_label}.png"
    receipt_world = SHOT_WORLD / receipt_name
    receipt_docs = SHOT_DOCS / receipt_name
    _render(data, receipt_world)
    if receipt_docs.exists():
        receipt_docs.unlink()
    os.link(receipt_world, receipt_docs)
    shots.append(receipt_world)
    log.append({"step": len(shots), "screenshot": str(receipt_world.relative_to(AUDIT)),
                "docs_copy": str(receipt_docs.relative_to(REPO)), "preceding_keys_or_text": "Enter/Escape then process exit",
                "visible_state": receipt_label, "durable_state_mutated_at_step": spec.tui in {"branch", "switch-entry"} and child.exitstatus == 0})
    raw_path = SHOT_WORLD / f"{sequence:03d}-{spec.operation}-{spec.attempt}-pty.bin"
    raw_path.write_bytes(data)
    log_path = SHOT_WORLD / f"{sequence:03d}-{spec.operation}-{spec.attempt}-interaction.json"
    _write_json(log_path, {
        "command": shlex.join(["python", str(RUNNER), "a-is-apple", *args]),
        "pty": {"columns": 180, "rows": 52, "TERM": "xterm-256color", "COLORTERM": "truecolor", "NO_COLOR": "removed"},
        "profile": PROFILE_NAME, "profile_uid": PROFILE_UID, "entry_current_context": log[0].get("entry_current_context", "recorded by ledger starting_state"),
        "steps": log,
    })
    return child.exitstatus if child.exitstatus is not None else 124, data.decode("utf-8", "replace"), elapsed, timed_out, post_identity, raw_path, log_path, shots


RUN_ID = ""


def _specs() -> list[Spec]:
    by: dict[tuple[str, int], Spec] = {}
    def add(op, attempt, args, route, target, scope, provenance, expected, tui=None, stdin=None):
        by[(op, attempt)] = Spec(op, attempt, args, route, target, scope, provenance, expected, tui, stdin)

    # Every diversity signature names the materially distinct actual route.
    status = [("status", "--short"), ("status", "--branch"), ("status", "--recursive"), ("status", "--direct", "--recursive"), ("status",)]
    for i, args in enumerate(status, 1): add("status", i, args, f"status route M{i}: {shlex.join(args)}", _current() or R, f"status projection M{i}", f"cumulative Store state at round {i}", "Report state or reject incompatible direct+recursive flags without mutation.")
    branches = [("branch", f"{C}/b1", "--from", R, "--direct"), ("branch", f"{C}/b2-tree", "--from", R, "--recursive"), ("branch", f"{C}/b3", "--from", f"{C}/renamed-1", "--source-root-only"), ("branch", C, "--from", R, "--direct"), ("branch",)]
    for i,args in enumerate(branches,1): add("branch",i,args,f"branch method M{i}: {'TUI compact endpoint form' if i==5 else shlex.join(args)}", args[1] if len(args)>1 else f"{C}/b5-tui", ("direct source" if i in {1,4} else "recursive source" if i==2 else "source-root-only" if i==3 else "TUI edited direct source"), f"live cumulative Source; round {i}; {'interactive exact-name input' if i==5 else 'explicit argv'}", "Create an undoable lane-local branch, except the deliberate collision.", "branch" if i==5 else None)
    checkouts=[("checkout",R),("checkout",".."),("checkout","-b",f"{C}/co3","--direct"),("checkout","-b",f"{C}/co4-tree","--recursive"),("checkout",)]
    for i,args in enumerate(checkouts,1): add("checkout",i,args,f"checkout method M{i}: {'TUI picker cancel' if i==5 else shlex.join(args)}", args[-1] if i<3 else (args[2] if i<5 else "process-local picker"), ("exact switch" if i<3 else "direct branch checkout" if i==3 else "recursive branch checkout" if i==4 else "TUI selection boundary"), f"round {i} current Context snapshot; actual argv {shlex.join(args)}", "Switch or create the prescribed branch; TUI route may cancel safely.", "cancel" if i==5 else None)
    configs=[("config",),("config","set","audit_v2_world","a-is-apple"),("config","show"),("config","set","provider","codex_chatgpt"),("config","set","provider")]
    for i,args in enumerate(configs,1): add("config",i,args,f"config method M{i}: {shlex.join(args)}","lane-local config",f"config read/write/validation method {i}",f"round {i} lane configuration", "Read or update only lane config; missing value fails safely.")
    evals=[("eval","semantic","status","--ledger-dir",str(EVAL_DIR)),lambda:("eval","semantic","run","ambiguity","--provider","codex_chatgpt","--model","gpt-5.6-sol","--reasoning","none","--pipeline","v2","--corpus","calibration","--runs","1","--case","single-none-main-entrance-hours","--ledger-dir",str(EVAL_DIR)),lambda:("eval","semantic","check",RUN_ID,"--ledger-dir",str(EVAL_DIR)),("eval","semantic","task2-status","--all","--ledger-dir",str(EVAL_DIR)),("eval","semantic","status","--ledger-dir",str(EVAL_DIR))]
    for i,args in enumerate(evals,1): add("eval",i,args,f"Eval ledger method M{i}",str(EVAL_DIR),f"semantic Eval scope M{i}",f"lane-local Eval ledger; {'one bounded provider case' if i==2 else 'host-produced evidence only'}", "Produce/check only lane-local Eval evidence.")
    helps=[("help",),("help","Which command shows my current Context and branch orientation?"),("help",),("help","--emit-selection"),("help","Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view.")]
    for i,args in enumerate(helps,1): add("help",i,args,f"Help route M{i}: {'interactive inventory/form' if i==3 else 'TTY safe command selection' if i==4 else shlex.join(args)}","operation catalog",f"help lookup scope M{i}",f"frozen catalog; {'one synthetic provider lookup' if i==2 else 'local catalog/guard text'}", "Render help, emit one inert command line, or reject copied-text guard before provider.", "help-form" if i==3 else "help-emit" if i==4 else None)
    imports=[("import","context","campus-wiki/building-access","--from-profile","task-1","--as",f"{C}/import-direct"),("import","context","campus-wiki","--from-profile","task-1","--as",f"{C}/import-tree","--recursive"),("import","memory",IMPORT_MEMORY,"--from-profile","task-1","--context","campus-wiki/building-access","--into",C),("import","memory",IMPORT_MEMORY,"--from-profile","task-1","--context","campus-wiki/building-access","--into",C),("import",)]
    for i,args in enumerate(imports,1): add("import",i,args,f"Import route M{i}: {'TUI resource picker cancel' if i==5 else shlex.join(args)}", (args[-1] if i in {1,2} else C if i in {3,4} else "resource workbench"), f"import scope M{i}: {'direct Context' if i==1 else 'recursive Context' if i==2 else 'exact Memory' if i in {3,4} else 'TUI entry'}", f"registered task-1 source Profile; method {i}; repeat collision only in M4", "Copy only registered source evidence or cancel without mutation.", "cancel" if i==5 else None)
    inits=[("init",C),("init",f"{C}/tree/leaf","--parents"),("init",C),("init","11111111-1111-4111-8111-111111111111"),("init",)]
    for i,args in enumerate(inits,1): add("init",i,args,f"Init route M{i}: {'TUI cancel' if i==5 else shlex.join(args)}", args[1] if len(args)>1 else "name editor", f"creation/validation scope M{i}",f"lane-local scratch namespace; method {i}", "Create only the prescribed scratch names or fail/cancel safely.", "cancel" if i==5 else None)
    studies=[("init-study","invalid/name"),("init-study","authoring"),("init-study","admin-v2-missing-baseline","--from-profile","missing-admin-v2-baseline"),("init-study","admin-v2-workers-zero","--prewarm-workers","0"),("init-study",)]
    for i,args in enumerate(studies,1): add("init-study",i,args,f"Init Study safe route M{i}: {'TUI cancel' if i==5 else shlex.join(args)}",args[1] if len(args)>1 else "Study name editor",f"pre-creation validation M{i}",f"deliberately invalid/reserved/missing/cancelled Study request {i}", "No Study/Profile creation or activation succeeds.", "cancel" if i==5 else None)
    locks=[("lock",),("lock",f"{C}/b2-tree","--recursive"),("lock",f"{C}/co3:{M}"),("lock",f"{C}/co4-tree"),("lock","--profile")]
    unlocks=[("unlock",),("unlock",f"{C}/b2-tree","--recursive"),("unlock",f"{C}/co3:{M}"),("unlock",f"{C}/co4-tree"),("unlock","--profile")]
    for op,rows in (("lock",locks),("unlock",unlocks)):
        for i,args in enumerate(rows,1): add(op,i,args,f"{op.title()} route M{i}: {shlex.join(args)}",args[1] if len(args)>1 else (_current() or R),f"{'current' if i==1 else 'recursive tree' if i==2 else 'exact Memory' if i==3 else 'exact Context' if i==4 else 'whole Profile'} lock boundary",f"paired round {i} host-state evidence",f"{op.title()} only the prescribed boundary and preserve adjacent-pair semantics.")
    logs=[("log","--context",C),("log","--context",C,"--manual"),("log","--context",f"{C}/co3","--memory",M,"--limit","5"),("log","--operations","--limit","50"),("log","--actions","--limit","100")]
    for i,args in enumerate(logs,1): add("log",i,args,f"Log route M{i}: {shlex.join(args)}",C if i<4 else "Profile history",f"history filter M{i}",f"retained lane-local audit history; method {i}","Render bounded history without mutation.")
    profiles=[("profile","current"),("profile","create","admin-v2-a-is-apple-inactive"),("profile","list"),("profile","use",PROFILE_NAME),("profile",)]
    for i,args in enumerate(profiles,1): add("profile",i,args,f"Profile route M{i}: {'TUI cancel' if i==5 else shlex.join(args)}",PROFILE_NAME if i!=2 else "inactive Profile record",f"Profile control scope M{i}",f"frozen active Profile identity; method {i}","Read/create inactive/use same active/cancel without active identity drift.","cancel" if i==5 else None)
    providers=[("provider",),("provider","status"),("provider","status","--operation","query"),("provider","use","codex_chatgpt","--operation","query"),("provider","probe","--operation","query")]
    for i,args in enumerate(providers,1): add("provider",i,args,f"Provider route M{i}: {shlex.join(args)}","query provider policy",f"provider policy scope M{i}",f"frozen Study provider policy; {'one bounded probe' if i==5 else 'local configuration/status'}", "Report policy, reject Study-locked change, or run one probe.")
    for i in range(1,6): add("pwd",i,("pwd",),f"pwd route M{i} after round-{i} producer/current transitions",f"round-{i} current Context",f"exact current identity after distinct transaction state M{i}",f"cumulative Store after round {i} operations", "Print the exact current Context without mutation.")
    for i in range(1,6): add("undo",i,("undo","--keep") if i==2 else ("undo",),f"Undo route M{i}: {'retain branch contexts' if i==2 else 'exact stack top'}",f"round-{i} producer unit",f"stack restoration boundary M{i}",f"host-read command unit UID/member set and granted_target null before Undo {i}", "Restore the exact producer; round 4 must fail while locked.")
    for i in range(1,6): add("redo",i,("redo",),f"Redo route M{i}: {'empty-stack negative boundary' if i==4 else 'exact prior Undo unit'}",f"round-{i} redo stack",f"redo stack boundary M{i}",f"host-read redo top UID/member set before Redo {i}", "Reapply exact unit, except deliberate no-redo M4.")
    renames=[("rename",f"{C}/b1",f"{C}/renamed-1","--force"),("rename",f"{C}/b2-tree",f"{C}/renamed-2-tree","--force"),("rename",f"{C}/co3",f"{C}/renamed-3","--force"),("rename",f"{C}/co4-tree",f"{C}/renamed-4","--force"),("rename",f"{C}/b5-tui",f"{C}/renamed-5")]
    for i,args in enumerate(renames,1): add("rename",i,args,f"Rename route M{i}: {shlex.join(args)}",f"{args[1]} → {args[2]}",f"{'tree' if i==2 else 'locked Context negative' if i==4 else 'exact Context'} rename",f"lane-local scratch producer result; {'interactive n confirmation' if i==5 else 'explicit force or protected failure'}", "Rename within scratch only; M4 lock-fails and M5 confirmation is declined.",stdin="n\n" if i==5 else None)
    shares=[("share",),("share",),("share","--to",ENDPOINT),("share",R,"--to",ENDPOINT,"--direct","--recursive"),("share",R,"--to","missing-admin-v2-endpoint")]
    for i,args in enumerate(shares,1): add("share",i,args,f"Share zero-delivery route M{i}: {'TUI Source cancel' if i in {2,3} else shlex.join(args)}",ENDPOINT if i in {3,4} else "no complete receiver",f"pre-delivery boundary M{i}",f"sender+receiver Store digests frozen before/after; method {i}", "Stop before delivery and preserve both Store digests.","cancel" if i in {2,3} else None)
    shells=[("shell-init",),("shell-init","zsh"),("shell-init","zsh"),("shell-init","zsh"),("shell-init","bash")]
    for i,args in enumerate(shells,1): add("shell-init",i,args,f"Shell integration route M{i}: {shlex.join(args)}","stdout shell text",f"{'default output' if i==1 else 'byte equality' if i==2 else 'zsh syntax consumer' if i==3 else 'disposable source-only consumer' if i==4 else 'unsupported shell validation'}",f"frozen generated zsh integration; method {i}","Emit stable safe shell text or reject unsupported bash.")
    switches=[("switch","--previous"),("switch","--next"),("switch",O),("switch",f"{C}/co4-tree/source"),("switch",)]
    for i,args in enumerate(switches,1): add("switch",i,args,f"Switch route M{i}: {'TUI tree restore' if i==5 else shlex.join(args)}",ENTRY if i==5 else args[-1],f"transaction navigation M{i}",f"round {i} frozen current/previous/next or visible tree selection", "Navigate exactly as ordered and preserve command-stack identity.","switch-entry" if i==5 else None)

    # Exact interleaved transaction order, one of every operation per round.
    orders = [
        ["branch","undo","redo","rename","checkout","lock","unlock","status","config","eval","help","import","init","init-study","log","profile","provider","pwd","share","shell-init","switch"],
        ["switch","branch","undo","redo","lock","unlock","rename","checkout","status","config","eval","help","import","init","init-study","log","profile","provider","pwd","share","shell-init"],
        ["branch","checkout","switch","undo","redo","lock","unlock","rename","status","config","eval","help","import","init","init-study","log","profile","provider","pwd","share","shell-init"],
        ["redo","status","config","eval","help","import","init","init-study","log","profile","provider","pwd","share","shell-init","branch","checkout","switch","lock","rename","undo","unlock"],
        ["undo","redo","status","config","eval","help","import","init","init-study","log","profile","provider","pwd","share","shell-init","checkout","branch","rename","lock","unlock","switch"],
    ]
    specs = [by[(op, attempt)] for attempt, order in enumerate(orders, 1) for op in order]
    assert len(specs) == 105 and len(by) == 105
    return specs


def _new_ledger(initial: str) -> dict:
    operations=("status","branch","checkout","config","eval","help","import","init","init-study","lock","log","profile","provider","pwd","redo","rename","share","shell-init","switch","undo","unlock")
    return {
        "schema_version":2,"study":"study-long-audit-20260825-v2","world":"a-is-apple","phase":"admin","status":"running",
        "contract":{"operations":21,"attempts_per_operation":5,"attempts":105},
        "execution_identity":{"code_snapshot_sha256":CODE_SHA,"catalog_sha256":CATALOG_SHA,"profile_uid":PROFILE_UID,"store_root":str(STORE),"provider_policy_sha256":PROVIDER_SHA},
        "starting_boundary":{"cumulative_from_transform":True,"admin_initial_digest":initial,"no_reset":True,"entry_current_context":ENTRY,
                             "safety":"Share delivery zero; init-study success zero; exact host-read Undo/Redo stack units; post-call Profile identity read after every counted command."},
        "launcher":f"python {RUNNER} a-is-apple","started_at":datetime.now(timezone.utc).isoformat(),
        "operations":{op:{"attempts":[]} for op in operations},
    }


def main() -> None:
    global RUN_ID
    for directory in (RAW,HOST,SHOT_WORLD,SHOT_DOCS,EVAL_DIR): directory.mkdir(parents=True,exist_ok=True)
    ledger=_json(LEDGER) if LEDGER.exists() else _new_ledger(_target_digest())
    completed={r["sequence"] for p in ledger["operations"].values() for r in p["attempts"]}
    prior=sorted((r for p in ledger["operations"].values() for r in p["attempts"]),key=lambda r:r["sequence"])
    prior_post=prior[-1]["post_target_digest"] if prior else ledger["starting_boundary"]["admin_initial_digest"]
    # Recover the one Eval run ID only from counted raw output when resuming.
    for record in ledger["operations"]["eval"]["attempts"]:
        if record["attempt"]==2:
            text=(AUDIT/record["raw_output"]).read_text(errors="replace")
            match=re.search(r"(?:FULL_RUN_ID|full_run_id|run_id)\s*[=:·]\s*([0-9A-Za-z._:-]+)",text)
            if match: RUN_ID=match.group(1)
            if not RUN_ID:
                ledger_match=re.search(r"/runs/([^/\s]+)\.json",text)
                if ledger_match: RUN_ID=ledger_match.group(1)
    shell_first: bytes|None=None
    for sequence,spec in enumerate(_specs(),1):
        if sequence in completed: continue
        args=spec.args() if callable(spec.args) else spec.args
        if spec.operation=="eval" and spec.attempt==3 and not RUN_ID:
            raise RuntimeError("Eval M2 did not yield FULL_RUN_ID; stopping before counted M3")
        pre=_target_digest(); entry_current=_current(); pre_share=None
        if spec.operation in {"undo","redo"}:
            stack_path=_stack_snapshot(f"pre-{spec.operation}-{spec.attempt}-seq-{sequence:03d}")
            stack=_json(stack_path)
            if spec.operation=="undo" and stack["staged_update_granted_target"] is not None:
                raise RuntimeError("Undo safety gate: granted staged target present")
        if spec.operation=="share":
            pre_share={"sender_delivery_state":_store_digest(STORE),"receiver_delivery_state":_store_digest(RECEIVER_STORE),
                       "digest_semantics":"All delivery-visible durable state excluding append-only Study command audit ledger and lock files."}
            _write_json(HOST/f"share-{spec.attempt}-pre.json",pre_share)
        began=time.monotonic(); timed_out=False; tui_evidence=None
        if spec.tui:
            exit_code,output,elapsed,timed_out,identity_path,pty_path,interaction_path,shots=_run_tui(spec,args,sequence)
            tui_evidence={"pty":{"columns":180,"rows":52,"term":"xterm-256color","colorterm":"truecolor","no_color_removed":True},
                          "ansi_color_verified":b"\x1b[" in pty_path.read_bytes(),"raw_pty_path":str(pty_path.relative_to(AUDIT)),
                          "interaction_log_path":str(interaction_path.relative_to(AUDIT)),"screenshots":[str(p.relative_to(AUDIT)) for p in shots]}
        else:
            command=[sys.executable,str(RUNNER),"a-is-apple",*args]
            try:
                result=subprocess.run(command,cwd=REPO,input=spec.stdin,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300,check=False)
                exit_code=result.returncode; output=result.stdout
            except subprocess.TimeoutExpired as error:
                timed_out=True; exit_code=124; partial=error.stdout or ""; output=partial if isinstance(partial,str) else partial.decode("utf-8","replace")
                output+="\nAUDIT RUNNER TIMEOUT; child terminated.\n"
            elapsed=time.monotonic()-began
            identity_path=_post_identity(sequence)
        if spec.operation=="eval" and spec.attempt==2:
            matches=list(re.finditer(r"(?:FULL_RUN_ID|full_run_id|run_id)\s*[=:·]\s*([0-9A-Za-z._:-]+)",output))
            if matches: RUN_ID=matches[-1].group(1)
            else:
                run_files=sorted(EVAL_DIR.rglob("*.json"),key=lambda p:p.stat().st_mtime)
                for p in reversed(run_files):
                    try: value=_json(p)
                    except Exception: continue
                    candidate=value.get("full_run_id") or value.get("FULL_RUN_ID") or value.get("run_id")
                    if candidate: RUN_ID=str(candidate); break
        shell_check=None
        if spec.operation=="shell-init" and exit_code==0:
            payload=output.encode()
            if spec.attempt==1: shell_first=payload
            elif spec.attempt==2:
                shell_check={"byte_equal_to_M1":shell_first==payload}
            elif spec.attempt==3:
                check=subprocess.run(["zsh","-n"],input=output,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                shell_check={"host_command":"zsh -n","exit":check.returncode,"stderr":check.stderr}
            elif spec.attempt==4:
                check=subprocess.run(["zsh","-dfc","source /dev/stdin; whence -w mem"],input=output,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                shell_check={"host_command":"zsh -dfc source-only; whence -w mem; function never invoked","exit":check.returncode,"stdout":check.stdout,"stderr":check.stderr}
            if shell_check is not None: _write_json(HOST/f"shell-init-{spec.attempt}-host-check.json",shell_check)
        share_evidence=None
        if spec.operation=="share":
            post_share={"sender_delivery_state":_store_digest(STORE),"receiver_delivery_state":_store_digest(RECEIVER_STORE),
                        "digest_semantics":"All delivery-visible durable state excluding append-only Study command audit ledger and lock files."}
            _write_json(HOST/f"share-{spec.attempt}-post.json",post_share)
            share_evidence={"pre":pre_share,"post":post_share,"unchanged":pre_share==post_share,"delivery":"zero"}
            if pre_share!=post_share: raise RuntimeError(f"Share {spec.attempt} changed a Store")
        post=_target_digest()
        raw=RAW/f"{sequence:03d}-{spec.operation}-{spec.attempt}.txt"
        command_text=shlex.join(["python",str(RUNNER),"a-is-apple",*args])
        raw.write_text(f"COMMAND\n{command_text}\n\nEXIT\n{exit_code}\n\nOUTPUT\n{output}")
        record={"attempt":spec.attempt,"sequence":sequence,"command":command_text,"exit":exit_code,
                "starting_state":f"One cumulative no-reset Store; current={entry_current}; pre-digest={pre}; round={spec.attempt}; previous post={prior_post}.",
                "entry_route":spec.route,"target_route":spec.target,"scope":spec.scope,
                "input_provenance":spec.provenance+f"; actual argv `{shlex.join(args)}`; phase-local sequence {sequence}",
                "consumer":f"ADMIN {spec.operation} method {spec.attempt} audit consumer","expected":spec.expected,"actual":_clean(output),"defect_ids":[],
                "cost":{"wall_seconds":round(elapsed,3),"output_bytes":len(output.encode()),"timed_out":timed_out,"tui":bool(spec.tui)},
                "pre_target_digest":pre,"post_target_digest":post,
                "recovery_evidence":("Undo/Redo stack evidence and paired unlock/recovery are recorded host-side." if spec.operation in {"branch","checkout","undo","redo","lock","unlock"} else "No separate recovery required; cumulative continuity and host identity are recorded."),
                "state_continuity":{"same_as_previous_post":prior_post==pre,"durable_context_tree_changed":pre!=post,"one_cumulative_store":True,
                                    "post_identity_evidence":str(identity_path.relative_to(AUDIT))},
                "raw_output":str(raw.relative_to(AUDIT))}
        if tui_evidence: record["tui_evidence"]=tui_evidence
        if share_evidence: record["share_evidence"]=share_evidence
        if shell_check: record["host_consumer_evidence"]=shell_check
        ledger["operations"][spec.operation]["attempts"].append(record)
        ledger["last_completed_sequence"]=sequence; ledger["updated_at"]=datetime.now(timezone.utc).isoformat()
        _write_json(LEDGER,ledger); prior_post=post
        print(f"[{sequence:03d}/105] {spec.operation}#{spec.attempt} exit={exit_code} {elapsed:.2f}s changed={pre!=post}",flush=True)
    records=[r for p in ledger["operations"].values() for r in p["attempts"]]
    ledger["status"]="complete"; ledger["attempt_count"]=len(records); ledger["completed_at"]=datetime.now(timezone.utc).isoformat()
    ledger["summary"]={"attempts":len(records),"successful_exits":sum(r["exit"]==0 for r in records),"nonzero_exits":sum(r["exit"]!=0 for r in records),
                       "tui_attempts":sum(bool(r["cost"].get("tui")) for r in records),"share_deliveries":0,
                       "init_study_successes":sum(r["exit"]==0 and "cancel" not in r["actual"].lower() for r in ledger["operations"]["init-study"]["attempts"]),
                       "identity_host_reads":len(list(HOST.glob("post-identity-*.json"))),"final_current_context":_current(),
                       "wall_seconds":round(sum(r["cost"]["wall_seconds"] for r in records),3)}
    _write_json(LEDGER,ledger)
    readme=SHOT_DOCS/"README.md"
    image_lines="\n".join(f"- `{p.name}`" for p in sorted(SHOT_DOCS.glob("*.png")))
    readme.write_text("# a-is-apple ADMIN interactive evidence\n\nAll captures are actual 180×52 xterm-256color PTY states. See the per-attempt interaction JSON mirrors under the world output.\n\n"+image_lines+"\n")


if __name__=="__main__": main()
