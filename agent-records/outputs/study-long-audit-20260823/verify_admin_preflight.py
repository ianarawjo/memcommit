#!/usr/bin/env python3
"""Validate the 630-cell admin preflight without invoking mem."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
MANIFEST = ROOT / "admin-preflight.json"
PLAN = ROOT / "admin-execution-plan.md"
TASK1_SHEET = ROOT / "worlds" / "task-1" / "admin-execution-sheet.md"
TASK1_PARTIAL = ROOT / "worlds" / "task-1" / "phase-admin.partial.json"
LAUNCHER = (
    "env PYTHONDONTWRITEBYTECODE=1 "
    "PYTHONPATH=/Users/KimMunyeong/.codex/audit-snapshots/"
    "memcommit-study-long-audit-20260823-code python -m memcommit.cli"
)
WORLDS = ("task-1", "task-2", "task-3", "ticker", "a-is-apple", "practice-source")
ADMIN = {
    "task-1": "task-1/participant/admin-scratch",
    "task-2": "task-2/participant/admin-scratch",
    "task-3": "task-3/local/admin-scratch",
    "ticker": "audit/ticker/admin-scratch",
    "a-is-apple": "audit/a-is-apple/admin-scratch",
    "practice-source": "practice/audit-workspace/admin-scratch",
}
ROOTS = {
    "task-1": "task-1/participant/transform-scratch",
    "task-2": "task-2/participant/transform-scratch",
    "task-3": "task-3/local/transform-scratch",
    "ticker": "audit/ticker/transform-scratch",
    "a-is-apple": "audit/a-is-apple/transform-scratch",
    "practice-source": "practice/audit-workspace/transform-scratch/source",
}
READ_SOURCES = {
    "task-1": "task-1/participant/transform-scratch/source/building-access",
    "task-2": "task-2/participant/transform-scratch/source",
    "task-3": "task-3/local/transform-scratch/source",
    "ticker": "audit/ticker/transform-scratch/result",
    "a-is-apple": "audit/a-is-apple/transform-scratch/result",
    "practice-source": "practice/audit-workspace/transform-scratch/source",
}
IMPORT_MAP = {
    "task-1": {
        1: ("study-baseline", "granted-memory/task-2/advisor1/methods"),
        2: ("study-baseline", "granted-memory/task-1/campus-wiki/construction-details"),
        3: ("study-baseline", "granted-memory/task-2/advisor2/methods"),
        4: ("study-baseline", "granted-memory/task-2/advisor1/claim-evidence"),
        5: ("study-baseline", "granted-memory/task-2/advisor2/claim-evidence"),
    },
    "task-2": {
        1: ("study-baseline", "granted-memory/task-2/advisor1/terminology"),
        2: ("study-baseline", "granted-memory/task-2/proposal-submission-guidelines"),
        3: ("study-baseline", "granted-memory/task-2/advisor2/terminology"),
        4: ("study-baseline", "granted-memory/task-2/advisor1/compensation"),
        5: ("study-baseline", "granted-memory/task-2/advisor2/compensation"),
    },
    "task-3": {
        1: ("study-baseline", "granted-memory/task-2/advisor1/reproducibility"),
        2: ("study-baseline", "granted-memory/task-3/remote/government/healthcare-agent/info-request/questions-and-answers"),
        3: ("study-baseline", "granted-memory/task-2/advisor2/reproducibility"),
        4: ("study-baseline", "granted-memory/task-2/advisor1/ethics"),
        5: ("study-baseline", "granted-memory/task-2/advisor2/ethics"),
    },
    "ticker": {
        1: ("study-baseline", "granted-memory/task-2/advisor1/style"),
        2: ("study-baseline", "granted-memory/task-3/remote/government/healthcare-agent/info-request/transmission-guidance"),
        3: ("study-baseline", "granted-memory/task-2/advisor2/style"),
        4: ("study-baseline", "granted-memory/task-2/advisor1/review"),
        5: ("study-baseline", "granted-memory/task-2/advisor2/review"),
    },
    "a-is-apple": {
        1: ("study-baseline", "granted-memory/task-2/advisor1/scope"),
        2: ("teststudy0803", "granted-memory/task-3/guardrails"),
        3: ("study-baseline", "granted-memory/task-2/advisor2/scope"),
        4: ("study-baseline", "granted-memory/task-2/advisor1/emphasis"),
        5: ("study-baseline", "granted-memory/task-2/advisor2/emphasis"),
    },
    "practice-source": {
        1: ("study-baseline", "granted-memory/task-2/advisor1/safety"),
        2: ("teststudy0803", "granted-memory/task-3/government/healthcare-agent/information-request"),
        3: ("study-baseline", "granted-memory/task-2/advisor2/safety"),
        4: ("study-baseline", "granted-memory/task-2/advisor1/evaluation"),
        5: ("study-baseline", "granted-memory/task-2/advisor2/evaluation"),
    },
}
PROFILE_EVIDENCE = {
    "study-baseline": (
        "e2cdbdc7-3db4-4d23-b59e-2a2783545005",
        "1cbcfb9bb72a3392eb6be707b134e6fb3effe17eab0f472c1ce2072c81f9589f",
    ),
    "teststudy0803": (
        "feb5b648-7ec3-44d8-8e17-6ffe85238311",
        "1515a565acd4e8aa9f2af28252b366ac5f6bf562acf8e9af4195caa59d310fa1",
    ),
}
OPS = (
    "status", "branch", "checkout", "config", "eval", "help", "import",
    "init", "init-study", "lock", "log", "profile", "provider", "pwd",
    "redo", "rename", "share", "shell-init", "switch", "undo", "unlock",
)
ROUND_ORDER = {
    1: ("profile", "config", "provider", "checkout", "status", "pwd", "branch", "undo", "redo", "init", "import", "lock", "unlock", "log", "eval", "help", "rename", "share", "shell-init", "switch", "init-study"),
    2: ("profile", "config", "provider", "checkout", "switch", "branch", "undo", "redo", "status", "pwd", "init", "import", "lock", "unlock", "log", "eval", "help", "rename", "share", "shell-init", "init-study"),
    3: ("profile", "config", "provider", "branch", "undo", "redo", "switch", "rename", "status", "pwd", "checkout", "init", "import", "lock", "unlock", "log", "eval", "help", "share", "shell-init", "init-study"),
    4: ("profile", "config", "provider", "lock", "rename", "unlock", "checkout", "undo", "branch", "redo", "status", "pwd", "import", "init", "log", "eval", "help", "share", "shell-init", "switch", "init-study"),
    5: ("config", "provider", "checkout", "init", "import", "help", "share", "branch", "undo", "redo", "lock", "unlock", "rename", "log", "eval", "shell-init", "init-study", "profile", "switch", "status", "pwd"),
}
TASK1_EXECUTED_ROUND1_ORDER = (
    "profile", "config", "provider", "checkout", "status", "pwd", "init",
    "undo", "redo", "branch", "import", "lock", "unlock", "log", "eval",
    "help", "rename", "share", "shell-init", "switch", "init-study",
)
TUIS = {
    ("branch", 5), ("checkout", 5), ("help", 5), ("import", 5),
    ("init", 5), ("init-study", 4), ("profile", 5),
    ("share", 4), ("share", 5), ("switch", 5),
}
INIT_CREATE = {"task-2", "ticker", "a-is-apple"}
DECISIONS = {
    "none": 600,
    "init_study_durable_residue": 6,
    "depends_on_init_study_decision": 24,
}
FORBIDDEN_ENV = re.compile(r"(?:^|\s)(?:HOME|home|CODEX_HOME)=")


def fail(message: str) -> None:
    raise AssertionError(message)


def gate(op: str, attempt: int) -> str:
    if op == "init-study" and attempt == 5:
        return "init_study_durable_residue"
    if attempt == 5 and op in {"profile", "switch", "status", "pwd"}:
        return "depends_on_init_study_decision"
    return "none"


def outbound(op: str, attempt: int) -> bool:
    return (op, attempt) in {("help", 2), ("eval", 2), ("provider", 5)}


def schedule_index(world: str, op: str, attempt: int) -> int:
    order = (
        TASK1_EXECUTED_ROUND1_ORDER
        if world == "task-1" and attempt == 1
        else ROUND_ORDER[attempt]
    )
    return (
        WORLDS.index(world) * 105
        + (attempt - 1) * 21
        + order.index(op)
        + 1
    )


def argv(world: str, op: str, attempt: int) -> list[str]:
    admin, root = ADMIN[world], ROOTS[world]
    missing, eval_dir = f"{admin}/admin-preflight-missing", f"agent-records/outputs/eval-admin-{world}"
    ip, ic = IMPORT_MAP[world][attempt] if op == "import" else ("", "")
    table = {
        "status": (["status", "-s"], ["status", "-b"], ["status", "-r"], ["status", "-d", "-r"], ["status"]),
        "branch": (["branch", f"{admin}/r1-branch", "--from", root, "--direct"], ["branch", f"{admin}/r2-tree", "--from", root, "--recursive"], ["branch", f"{admin}/r3-from-prior", "--from", f"{admin}/r1-renamed", "--direct"], ["branch", f"{admin}/r4-redo-invalidator", "--from", root, "--direct"], ["branch"]),
        "checkout": (["checkout", root], ["checkout", "."], ["checkout", "-b", f"{admin}/r3-checkout", "--direct"], ["checkout", "-b", f"{admin}/r4-invalidator", "--direct"], ["checkout"]),
        "config": (["config"], ["config", "show"], ["config", "set", "provider"], ["config", "set", "--help"], ["config", "admin-preflight-invalid"]),
        "eval": (["eval", "semantic", "status", "--ledger-dir", eval_dir], ["eval", "semantic", "run", "ambiguity", "--case", "single-none-main-entrance-hours", "--runs", "1", "--provider", "codex_chatgpt", "--model", "gpt-5.6-sol", "--reasoning", "none", "--ledger-dir", eval_dir], ["eval", "semantic", "status", "--ledger-dir", eval_dir], ["eval", "semantic", "check", "${EVAL_RUN_ID_FROM_M2_LEDGER}", "--ledger-dir", eval_dir], ["eval", "semantic", "check", f"admin-{world}-missing-run-id", "--ledger-dir", eval_dir]),
        "help": (["help"], ["help", "which command inspects current orientation?"], ["help", "Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view."], ["help", "--emit-selection"], ["help"]),
        "import": (["import", "context", ic, "--from-profile", ip, "--as", f"{admin}/import-direct", "--direct"], ["import", "context", ic, "--from-profile", ip, "--as", f"{admin}/import-tree", "--recursive"], ["import", "memory", "${BASELINE_IMPORT_MEMORY_UID}", "--from-profile", ip, "--context", ic, "--into", admin], ["import", "context", ic, "--from-profile", ip, "--as", f"{admin}/r4-import-owned", "--direct"], ["import"]),
        "init": (["init", admin], ["init", f"{admin}/tree/leaf", "--parents"], ["init", admin], ["init", "00000000-0000-4000-8000-000000000000"], ["init"]),
        "init-study": (["init-study", "study-long-audit-20260823", "--from-profile", "study-baseline"], ["init-study", f"admin/{world}-invalid", "--from-profile", "study-baseline"], ["init-study", f"study-long-admin-{world}-r3", "--from-profile", f"admin-{world}-missing-baseline"], ["init-study"], ["init-study", f"study-long-admin-{world}-r5", "--from-profile", "study-baseline"]),
        "lock": (["lock", "--context", admin, "--direct"], ["lock", "--context", admin, "--recursive"], ["lock", "--memory", "${IMPORTED_MEMORY_UID_FROM_IMPORT_M3}", "--context", admin], ["lock", "--profile"], ["lock", "--context", missing, "--direct"]),
        "log": (["log", "--context", root], ["log", "--context", root, "--manual"], ["log", "--memory", "${WORLD_LOG_MEMORY_UID}", "--context", READ_SOURCES[world]], ["log", "--memory", "ffffffff-ffff-4fff-8fff-ffffffffffff", "--context", root], ["log", "--actions"] if WORLDS.index(world) < 3 else ["log", "--operations", "--limit", "20"]),
        "profile": (["profile", "list"], ["profile", "current"], ["profile", "use", "study-long-audit-20260823"], ["profile", "use", f"admin-{world}-missing"], ["profile"]),
        "provider": (["provider"], ["provider", "status"], ["provider", "status", "--operation", "query"], ["provider", "use", "codex_chatgpt", "--operation", "query"], ["provider", "probe", "--operation", "query"]),
        "pwd": (["pwd"],) * 5,
        "redo": (["redo"],) * 5,
        "rename": (["rename", f"{admin}/r1-branch", f"{admin}/r1-renamed", "--force"], ["rename", f"{admin}/r2-tree", f"{admin}/r2-renamed", "--force"], ["rename", ".", f"{admin}/r3-renamed", "--force"], ["rename", f"{admin}/r1-renamed", f"{admin}/r4-protected-rename", "--force"], ["rename", f"{admin}/r5-missing-old", f"{admin}/r5-renamed", "--force"]),
        "share": (["share"], ["share", READ_SOURCES[world], "--to", f"admin-{world}-missing-endpoint"], ["share", READ_SOURCES[world], "--direct", "--recursive"], ["share", READ_SOURCES[world]], ["share", "--to", "task-3/government/healthcare-agent"]),
        "shell-init": (["shell-init"], ["shell-init", "zsh"], ["shell-init", "bash"], ["shell-init", "zsh"], ["shell-init", "zsh"]),
        "switch": (["switch", root], ["switch", "./source"], ["switch", f"{admin}/r3-from-prior"], ["switch", "task-3/remote/government/healthcare-agent/info-request/questions-and-answers"] if world == "task-3" else ["switch", missing], ["switch"]),
        "undo": (["undo"], ["undo", "--keep"], ["undo"], ["undo"], ["undo"]),
        "unlock": (["unlock", "--context", admin, "--direct"], ["unlock", "--context", admin, "--recursive"], ["unlock", "--memory", "${IMPORTED_MEMORY_UID_FROM_IMPORT_M3}", "--context", admin], ["unlock", "--profile"], ["unlock", "--context", missing, "--direct"]),
    }
    return table[op][attempt - 1]


def canonical_digest(record: dict[str, object]) -> str:
    encoded = json.dumps(
        record, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def store_digest(root: Path) -> str:
    files = [root / "state.json", *sorted((root / "contexts").rglob("context.json"))]
    for name in ("query-sources", "study-semantic-prewarm", "translation-views"):
        directory = root / name
        if directory.exists():
            files.extend(sorted(path for path in directory.rglob("*") if path.is_file()))
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def host_inventory() -> tuple[dict[str, dict[str, object]], dict[str, dict[str, dict[str, object]]]]:
    home = Path.home()
    registry = json.loads((home / ".mem-profiles" / "registry.json").read_text())
    profiles = {row["name"]: row for row in registry["profiles"]}
    contexts: dict[str, dict[str, dict[str, object]]] = {}
    for name in {*PROFILE_EVIDENCE, "study-long-audit-20260823"}:
        profile = profiles[name]
        root = home / ".mem" if profile["kind"] == "AUTHORING" else home / ".mem-profiles" / "stores" / profile["uid"]
        records = {}
        # Only the live canonical store participates. Profile-root recursion can
        # enter .mem/backups and silently overwrite a live name with a stale UID.
        for path in (root / "contexts").rglob("context.json"):
            record = json.loads(path.read_text())
            records[record["name"]] = record
        contexts[name] = records
        if name in PROFILE_EVIDENCE:
            expected_uid, expected_digest = PROFILE_EVIDENCE[name]
            if profile["uid"] != expected_uid or store_digest(root) != expected_digest:
                fail(f"host Source Profile evidence changed for {name}")
    if registry["active_uid"] != "39ce9847-0483-45ec-a35e-5f83b4e9d630":
        fail("active Profile is not the frozen long-audit Study")
    return profiles, contexts


def validate_host_sources(payload: dict[str, object]) -> None:
    _profiles, contexts = host_inventory()
    declared = payload.get("import_sources")
    if not isinstance(declared, dict) or declared.get("source_profiles") != {
        name: {"uid": evidence[0], "store_sha256": evidence[1]}
        for name, evidence in PROFILE_EVIDENCE.items()
    }:
        fail("declared Source Profile UID/store digests differ from host evidence")
    declared_worlds = declared.get("worlds")
    if not isinstance(declared_worlds, dict):
        fail("missing per-world Import evidence")
    active_uids = {row["uid"] for row in contexts["study-long-audit-20260823"].values()}
    planned_uids: set[str] = set()
    for world in WORLDS:
        rows = declared_worlds.get(world)
        if not isinstance(rows, dict):
            fail(f"missing Import map for {world}")
        for attempt in range(1, 6):
            key = f"m{attempt}"
            row = rows.get(key)
            profile, name = IMPORT_MAP[world][attempt]
            if not isinstance(row, dict) or row.get("profile") != profile or row.get("context") != name:
                fail(f"{world} Import {key} Source mapping differs")
            record = contexts[profile].get(name)
            if record is None:
                fail(f"{world} Import {key} Source Context is absent")
            if row.get("profile_uid") != PROFILE_EVIDENCE[profile][0] or row.get("store_sha256") != PROFILE_EVIDENCE[profile][1]:
                fail(f"{world} Import {key} Source Profile evidence differs")
            if row.get("context_uid") != record["uid"] or row.get("context_sha256") != canonical_digest(record):
                fail(f"{world} Import {key} Source Context evidence differs")
            if attempt == 2:
                names = sorted(q for q in contexts[profile] if q == name or q.startswith(name + "/"))
                expected_members = [
                    {"name": q, "uid": contexts[profile][q]["uid"], "sha256": canonical_digest(contexts[profile][q])}
                    for q in names
                ]
                if row.get("recursive_contexts") != expected_members or len(names) < 2:
                    fail(f"{world} Import M2 recursive set is absent, stale, or trivial")
                selected = set(names)
                for q in names:
                    for item in contexts[profile][q].get("memories", {}).values():
                        kind = item.get("type")
                        if kind in {"query_context_ref", "granted_context_ref"}:
                            fail(f"{world} Import M2 contains a forbidden pointer")
                        if kind == "context_ref" and item.get("name") not in selected:
                            fail(f"{world} Import M2 is not a closed Context set")
                        if kind == "memory_ref" and (item.get("target_context") or {}).get("name") not in selected:
                            fail(f"{world} Import M2 has an external live Memory reference")
                imported = [contexts[profile][q]["uid"] for q in names]
            elif attempt in {1, 4}:
                imported = [record["uid"]]
            else:
                imported = []
            for uid in imported:
                if uid in active_uids or uid in planned_uids:
                    fail(f"{world} Import M{attempt} has a global Context UID collision")
                planned_uids.add(uid)
            if attempt == 3:
                memory_uid = row.get("memory_uid")
                memory = record.get("memories", {}).get(memory_uid)
                if not isinstance(memory, dict) or memory.get("type") != "memory":
                    fail(f"{world} Import M3 Memory is not directly owned")
                digest = hashlib.sha256(memory["content"].encode()).hexdigest()
                if row.get("memory_sha256") != digest:
                    fail(f"{world} Import M3 Memory digest differs")
                target = contexts["study-long-audit-20260823"].get(ADMIN[world])
                if target and memory_uid in target.get("memories", {}):
                    fail(f"{world} Import M3 Memory UID already exists in bare A_W")
            if attempt == 5 and record["uid"] in active_uids | planned_uids:
                fail(f"{world} Import M5 preview Source would hit a UID collision")
    evidence = payload.get("host_source_evidence")
    if not isinstance(evidence, dict) or evidence.get("inspected_without_mem") is not True:
        fail("missing read-only host Source evidence")
    world_reads = evidence.get("world_reads")
    if not isinstance(world_reads, dict):
        fail("missing world read-source evidence")
    active = contexts["study-long-audit-20260823"]
    for world in WORLDS:
        root_record = active.get(ROOTS[world])
        read_record = active.get(READ_SOURCES[world])
        declared_read = world_reads.get(world)
        if root_record is None or read_record is None or not isinstance(declared_read, dict):
            fail(f"{world} goal/read Source Context is absent")
        goal = declared_read.get("goal_root")
        direct = declared_read.get("direct_memory_source")
        if not isinstance(goal, dict) or goal.get("uid") != root_record["uid"] or goal.get("sha256") != canonical_digest(root_record):
            fail(f"{world} goal-root evidence differs")
        if not isinstance(direct, dict) or direct.get("context_uid") != read_record["uid"] or direct.get("context_sha256") != canonical_digest(read_record):
            fail(f"{world} direct owner Context evidence differs")
        memory = read_record.get("memories", {}).get(direct.get("memory_uid"))
        if not isinstance(memory, dict) or memory.get("type") != "memory":
            fail(f"{world} direct Log/Share Memory is absent")
        item_types = sorted({
            item.get("type") for item in read_record.get("memories", {}).values()
        })
        direct_memory_count = sum(
            item.get("type") == "memory"
            for item in read_record.get("memories", {}).values()
        )
        if item_types != ["memory"] or direct_memory_count < 1:
            fail(f"{world} Share Source is not a nonempty Memory-only Context")
        if direct.get("item_types") != item_types or direct.get("direct_memory_count") != direct_memory_count:
            fail(f"{world} Share Source item-type/count evidence differs")
        if direct.get("memory_sha256") != hashlib.sha256(memory["content"].encode()).hexdigest():
            fail(f"{world} direct Log/Share Memory digest differs")


def validate_tui(cell: dict[str, object]) -> None:
    tui = cell.get("tui")
    world, op, attempt = cell["world"], cell["op"], cell["attempt"]
    should = (op, attempt) in TUIS
    if not should:
        if tui is not None:
            fail(f"{world} {op} M{attempt} has unexpected TUI")
        return
    if not isinstance(tui, dict) or tui.get("required") is not True:
        fail(f"{world} {op} M{attempt} lacks required TUI")
    if tui.get("pty") != {
        "rows": 52, "cols": 180, "TERM": "xterm-256color",
        "COLORTERM": "truecolor", "NO_COLOR": "unset", "home_overrides": False,
    }:
        fail(f"{world} {op} M{attempt} PTY differs")
    contract = tui.get("interaction_contract")
    if not isinstance(contract, dict) or contract.get("mode") != "adaptive_visible_state":
        fail(f"{world} {op} M{attempt} is not adaptive")
    required = {
        "allowed_key_grammar", "semantic_target_search_text",
        "required_visible_state_before_each_key", "ordered_semantic_actions",
        "max_transitions", "escape_back_stop", "forbidden_semantic_actions",
        "approval_condition", "concrete_keys_after_run", "concrete_keys_recording",
    }
    if required - contract.keys() or contract.get("concrete_keys_after_run") != []:
        fail(f"{world} {op} M{attempt} adaptive contract is incomplete")
    actions = contract["ordered_semantic_actions"]
    predicates = contract["required_visible_state_before_each_key"]
    if not actions or len(actions) != len(predicates) or any(
        not row.get("before_key_predicate") or not row.get("allowed_next_keys")
        for row in predicates
    ):
        fail(f"{world} {op} M{attempt} visible-state predicates differ")
    if not isinstance(contract.get("max_transitions"), int) or contract["max_transitions"] <= 0:
        fail(f"{world} {op} M{attempt} lacks a finite transition limit")
    if op in {"share", "init-study"}:
        forbidden = " ".join(contract["forbidden_semantic_actions"])
        if tui.get("apply_forbidden") is not True or not any(x in forbidden for x in ("Apply", "Approve", "Create", "Send")):
            fail(f"{world} {op} M{attempt} does not forbid approval")
    if op == "init-study" and attempt == 4:
        proposed = f"study-long-admin-{world}-r4-preview"
        expected_actions = [
            f"type exact proposed Study name {proposed} in the single name field",
            "after the exact name and footer are visible, press Escape directly; never Enter",
        ]
        forbidden = set(contract["forbidden_semantic_actions"])
        encoded = json.dumps(contract).lower()
        predicates = contract["required_visible_state_before_each_key"]
        if (
            contract["semantic_target_search_text"]
            != [proposed, "Enter create", "Esc cancel"]
            or contract["allowed_key_grammar"]
            != ["Escape", "Backspace", "printable UTF-8 text"]
            or contract["ordered_semantic_actions"] != expected_actions
            or len(predicates) != 2
            or predicates[1].get("allowed_next_keys") != ["Escape"]
            or "single 5-line Init-study name field" not in predicates[0].get("before_key_predicate", "")
            or "Enter create · Esc cancel" not in predicates[1].get("before_key_predicate", "")
            or not {"Enter", "Create"}.issubset(forbidden)
            or contract.get("approval_condition") is not None
            or "study-baseline" in encoded
            or "final review" in encoded
            or tui.get("expected_outcome") != "cancelled"
            or "single Init-study name-field screen" not in tui.get("stop_predicate", "")
        ):
            fail(f"{world} Init-study M4 is not the single-field Escape-only cancel route")
    if op == "help" and attempt == 5:
        expected_actions = [
            "choose the A–Z inventory view using only the visibly focused view control",
            "navigate the A–Z operation rows until the exact switch row is visibly focused",
            "press Enter once on the focused switch row to expand Forms",
            "after switch Forms and the ← back token are visible, press Left once to collapse",
            "after the switch row is collapsed and Q/Esc close is visible, press Escape once to close",
        ]
        expected_grammar = [
            "Tab", "Shift-Tab", "Up", "Down", "Home", "End", "PageUp",
            "PageDown", "Left", "Right", "Enter", "Escape", "Q",
        ]
        predicates = contract["required_visible_state_before_each_key"]
        forbidden = set(contract["forbidden_semantic_actions"])
        active_route = " ".join(
            [*contract["semantic_target_search_text"], *contract["ordered_semantic_actions"]]
            + [row.get("before_key_predicate", "") for row in predicates]
        ).lower()
        if (
            contract["semantic_target_search_text"]
            != ["A–Z", "switch", "Forms", "← back", "Q/Esc close"]
            or contract["allowed_key_grammar"] != expected_grammar
            or contract["ordered_semantic_actions"] != expected_actions
            or len(predicates) != 5
            or predicates[2].get("allowed_next_keys") != ["Enter"]
            or predicates[3].get("allowed_next_keys") != ["Left"]
            or predicates[4].get("allowed_next_keys") != ["Escape"]
            or not {
                "search input", "printable query entry", "SYNTAX layer",
                "Escape as back-navigation", "H full-help/static-help path",
            }.issubset(forbidden)
            or not isinstance(contract.get("approval_condition"), str)
            or "visible focused operation row is switch" not in contract["approval_condition"]
            or any(token in active_route for token in ("search", "query", "syntax", "escape back", "full help"))
            or tui.get("expected_outcome") != "closed_no_mutation"
            or "one Escape closes the Help inventory" not in tui.get("stop_predicate", "")
        ):
            fail(f"{world} Help M5 is not the A–Z Switch Forms/Left/Escape route")
    if op == "import":
        profile, source = IMPORT_MAP[world][5]
        targets = contract["semantic_target_search_text"]
        if profile not in targets or source not in targets or ADMIN[world] + "/r5-import-cancel" not in targets:
            fail(f"{world} Import M5 TUI Source/target differs")
    if op == "share":
        if READ_SOURCES[world] not in contract["semantic_target_search_text"]:
            fail(f"{world} Share TUI does not use the nonempty safe Source")
    if op == "checkout":
        target = ADMIN[world] + "/r1-renamed"
        actions = " ".join(contract["ordered_semantic_actions"])
        approval = contract.get("approval_condition")
        stale_current = ADMIN[world] + "/r3-checkout"
        if (
            contract["semantic_target_search_text"] != [target]
            or target not in actions
            or not isinstance(approval, str)
            or target not in approval
            or stale_current in approval
            or target not in tui["stop_predicate"]
            or tui["expected_outcome"] != "current_changed"
        ):
            fail(f"{world} Checkout M5 does not change to a retained different Context")
    if op == "switch" and attempt == 5:
        target = "${PHASE_ENTRY_CURRENT}"
        expected_actions = [
            f"navigate the picker until the exact host-bound phase-entry Context name {target} is visibly focused",
            "after the focused row is proven selectable, materialized, and different from the pre-attempt current, press Enter once to switch",
        ]
        expected_grammar = [
            "Up", "Down", "Home", "End", "PageUp", "PageDown", "Enter",
            "Escape",
        ]
        predicates = contract["required_visible_state_before_each_key"]
        prelaunch = contract.get("prelaunch_host_binding")
        approval = contract.get("approval_condition")
        forbidden = set(contract["forbidden_semantic_actions"])
        if (
            contract["semantic_target_search_text"] != [target]
            or contract["allowed_key_grammar"] != expected_grammar
            or contract["ordered_semantic_actions"] != expected_actions
            or len(predicates) != 2
            or predicates[1].get("allowed_next_keys") != ["Enter"]
            or not isinstance(prelaunch, str)
            or not all(token in prelaunch for token in (target, "name, UID, and digest", "materialized/selectable", "differs"))
            or not isinstance(approval, str)
            or not all(token in approval for token in (target, "ordinary local Context UID/digest", "materialized/selectable", "pre-attempt current is different"))
            or any(token in approval for token in ("LOCAL |", "GRANT |", "QUERY ONLY"))
            or not {
                "selecting any granted route", "selecting any query route",
                "Enter on any row other than the exact phase-entry ordinary local Context",
                "requiring LOCAL/GRANT/QUERY ONLY to be simultaneously visible",
            }.issubset(forbidden)
            or tui.get("expected_outcome") != "entry_current_restored"
            or target not in tui.get("stop_predicate", "")
            or "differ from the recorded pre-attempt current" not in tui.get("stop_predicate", "")
        ):
            fail(f"{world} Switch M5 is not the exact local phase-entry restoration route")
    if op == "profile":
        if contract.get("approval_condition") is not None:
            fail(f"{world} Profile M5 common route must not preselect a branch")
        branches = contract.get("decision_branches")
        if not isinstance(branches, dict) or set(branches) != {"approved", "declined", "branch_binding"}:
            fail(f"{world} Profile M5 branches are incomplete")
        approved, declined = branches["approved"], branches["declined"]
        if not isinstance(approved, dict) or not isinstance(declined, dict):
            fail(f"{world} Profile M5 branch actions are not structured")
        if approved.get("expected_outcome") != "original_profile_restored" or not approved.get("approval_condition"):
            fail(f"{world} Profile M5 approved restoration branch differs")
        if declined.get("expected_outcome") != "unchanged_cancel" or declined.get("approval_condition") is not None:
            fail(f"{world} Profile M5 declined cancel branch differs")
        for branch in (approved, declined):
            branch_actions = branch.get("ordered_semantic_actions")
            branch_predicates = branch.get("required_visible_state_before_each_key")
            if not branch_actions or len(branch_actions) != len(branch_predicates or []):
                fail(f"{world} Profile M5 branch action predicates differ")


def main() -> int:
    payload = json.loads(MANIFEST.read_text())
    if payload.get("schema_version") != 4 or "TBD" in json.dumps(payload):
        fail("manifest schema/TUI placeholders are invalid")
    if "completion stdout" in json.dumps(payload):
        fail("Eval run-ID binding still relies on completion stdout")
    cells = payload.get("cells")
    if not isinstance(cells, list) or len(cells) != 630:
        fail("manifest must contain exactly 630 cells")
    if payload.get("launcher") != LAUNCHER or FORBIDDEN_ENV.search(LAUNCHER):
        fail("frozen launcher/home boundary differs")
    validate_host_sources(payload)

    seen = set()
    decisions: Counter[str] = Counter()
    outbound_count = 0
    tui_count = 0
    by_id = {}
    for index, cell in enumerate(cells):
        world, op, attempt = cell.get("world"), cell.get("op"), cell.get("attempt")
        if world not in WORLDS or op not in OPS or attempt not in range(1, 6):
            fail(f"cell {index} identity differs")
        identity = (world, op, attempt)
        if identity in seen:
            fail(f"duplicate cell {identity}")
        seen.add(identity)
        by_id[identity] = cell
        if cell.get("method") != f"M{attempt}" or cell.get("argv") != argv(world, op, attempt):
            fail(f"{identity} exact argv/method differs")
        if cell.get("schedule_index") != schedule_index(world, op, attempt):
            fail(f"{identity} schedule index differs")
        if cell.get("launcher") != LAUNCHER or FORBIDDEN_ENV.search(cell["launcher"]):
            fail(f"{identity} launcher/home boundary differs")
        if cell.get("decision_class") != gate(op, attempt):
            fail(f"{identity} decision class differs")
        if cell.get("outbound") is not outbound(op, attempt):
            fail(f"{identity} outbound class differs")
        if not cell.get("mutation_scope") or not cell.get("recovery"):
            fail(f"{identity} mutation/recovery contract is empty")
        if op == "share" and not cell["mutation_scope"].startswith("none:"):
            fail(f"{identity} Share is not no-delivery")
        if op == "config" and not cell["mutation_scope"].startswith(("none:", "read_only:")):
            fail(f"{identity} Config may write")
        if op == "import" and attempt <= 4:
            source_profile = cell["argv"][cell["argv"].index("--from-profile") + 1]
            if source_profile == "study-long-audit-20260823":
                fail(f"{identity} Import uses the active Profile")
            if attempt == 3 and cell["argv"][-1] != ADMIN[world]:
                fail(f"{identity} Import M3 does not target bare A_W")
        if op == "eval" and attempt == 2 and not all(
            token in cell["recovery"]
            for token in ("immediately before and after M2", "full run_id")
        ):
            fail(f"{identity} Eval M2 run-ID binding lacks the isolated ledger set difference")
        if op == "eval" and attempt in {3, 4} and cell.get("consumer") != "${EVAL_RUN_ID_FROM_M2_LEDGER}":
            fail(f"{identity} Eval does not consume the M2 host-ledger binding")
        if op == "log" and attempt == 3 and cell.get("consumer") != "${WORLD_LOG_MEMORY_CONTEXT}:${WORLD_LOG_MEMORY_UID}":
            fail(f"{identity} Log M3 lacks exact direct-owner binding")
        validate_tui(cell)
        tui_count += int(cell.get("tui") is not None)
        decisions[cell["decision_class"]] += 1
        outbound_count += int(cell["outbound"])

    expected = {(w, o, a) for w in WORLDS for o in OPS for a in range(1, 6)}
    if seen != expected or decisions != Counter(DECISIONS):
        fail("cell Cartesian product or decision totals differ")
    if [cell["schedule_index"] for cell in cells] != list(range(1, 631)):
        fail("cells are not stored in global schedule order")
    if tui_count != 60 or outbound_count != 18:
        fail("TUI/outbound totals differ")
    for world in WORLDS:
        chains = [
            (1, ("lock", "unlock"), "r1:lock-unlock"),
            (2, ("branch", "undo", "redo"), "r2:branch-undo-redo"),
            (2, ("lock", "unlock"), "r2:lock-unlock"),
            (3, ("branch", "undo", "redo"), "r3:branch-undo-redo"),
            (3, ("lock", "unlock"), "r3:lock-unlock"),
            (4, ("lock", "rename", "unlock"), "r4:profile-lock-rename-unlock"),
            (4, ("checkout", "undo", "branch", "redo"), "r4:checkout-undo-branch-redo"),
            (5, ("branch", "undo", "redo"), "r5:branch-undo-redo"),
        ]
        if world != "task-1":
            chains.insert(0, (1, ("branch", "undo", "redo"), "r1:branch-undo-redo"))
        for attempt, ops, suffix in chains:
            rows = [by_id[(world, op, attempt)] for op in ops]
            indices = [row["schedule_index"] for row in rows]
            if indices != list(range(indices[0], indices[0] + len(indices))):
                fail(f"{world} {suffix} is not adjacent")
            if any(row.get("transaction_id") != f"{world}:{suffix}" for row in rows):
                fail(f"{world} {suffix} transaction differs")

    if {row["key"]: row["goal_root"] for row in payload["worlds"]} != ROOTS:
        fail("world Goal roots differ")
    boundary = payload.get("execution_boundary")
    if not isinstance(boundary, dict) or boundary.get("currently_executable_prefix") != {
        "world": "task-1", "schedule_indices": [1, 100], "count": 100
    }:
        fail("world-serial gate boundary does not stop after task-1 sequence 100")
    if payload.get("decision_summary") != DECISIONS:
        fail("decision summary differs")
    bindings = payload.get("runtime_bindings", {})
    for token in (
        "${IMPORT_SOURCE_PROFILE_UID_AND_STORE_SHA256}",
        "${IMPORT_SOURCE_CONTEXT_UID_AND_SHA256}",
        "${BASELINE_IMPORT_MEMORY_UID}",
        "${IMPORTED_MEMORY_UID_FROM_IMPORT_M3}",
        "${WORLD_LOG_MEMORY_CONTEXT}",
        "${WORLD_LOG_MEMORY_UID}",
        "${EVAL_RUN_ID_FROM_M2_LEDGER}",
        "${PINNED_STUDY_PROVIDER_POLICY_SHA256}",
        "${PHASE_ENTRY_CURRENT}",
    ):
        if token not in bindings:
            fail(f"missing runtime binding {token}")
    if "receipt alone prints only uid[:8]" not in bindings["${IMPORTED_MEMORY_UID_FROM_IMPORT_M3}"]:
        fail("Import M3 full-UID binding incorrectly trusts the receipt")
    if "immediately before and after M2" not in bindings["${EVAL_RUN_ID_FROM_M2_LEDGER}"]:
        fail("Eval M2 binding lacks isolated ledger set-difference proof")
    if payload.get("actual_mem_commands_executed_during_preflight") != 0:
        fail("preflight must record zero mem calls")

    partial = json.loads(TASK1_PARTIAL.read_text())
    task1 = [cell for cell in cells if cell["world"] == "task-1"]
    attempts = partial.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != 105:
        fail("W1 partial must retain exactly 105 planned cells")
    for source, attempt in zip(task1, attempts, strict=True):
        for source_key, attempt_key in (
            ("schedule_index", "sequence"), ("op", "operation"), ("method", "method"),
            ("argv", "argv"), ("decision_class", "decision_class"),
            ("launcher", "launcher"), ("outbound", "outbound"), ("tui", "tui"),
        ):
            if source[source_key] != attempt.get(attempt_key):
                fail(f"W1 partial {attempt_key} differs at {attempt.get('sequence')}")

    executed = [row for row in attempts if str(row.get("status", "")).startswith("executed_")]
    executed_sequences = [row.get("sequence") for row in executed]
    if executed_sequences != list(range(1, len(executed) + 1)):
        fail("W1 planned execution is not one exact contiguous prefix")
    for row in executed:
        execution = row.get("execution")
        if (
            not isinstance(execution, dict)
            or not execution.get("completed_at")
            or not isinstance(execution.get("exit_code"), int)
            or not isinstance(execution.get("stdout"), str)
            or not isinstance(execution.get("stderr"), str)
            or not isinstance(row.get("pre_host"), dict)
            or not isinstance(row.get("post_host"), dict)
            or not isinstance(row.get("recovery_verified"), dict)
        ):
            fail(f"W1 executed evidence is incomplete at {row.get('sequence')}")
    for row in attempts[len(executed):]:
        if row.get("status") != "prepared_not_executed":
            fail(f"W1 non-prefix row is not prepared at {row.get('sequence')}")
        execution = row.get("execution")
        if not isinstance(execution, dict) or any(
            execution.get(key) is not None
            for key in ("completed_at", "exit_code", "stdout", "stderr", "duration_seconds", "outbound_attempted")
        ):
            fail(f"W1 prepared row contains execution evidence at {row.get('sequence')}")

    extras = partial.get("recovery_attempts")
    if not isinstance(extras, list) or len(extras) != 2:
        fail("W1 must declare exactly the two M1 recovery-qualified extras")
    expected_extras = (
        ("8R", "undo", ["undo"], 8),
        ("9R", "redo", ["redo"], 9),
    )
    executed_extra_count = 0
    for row, (label, op, exact_argv, replaces) in zip(extras, expected_extras, strict=True):
        if (
            row.get("execution_order") != label
            or row.get("operation") != op
            or row.get("method") != "M1-recovery"
            or row.get("argv") != exact_argv
            or row.get("qualifies_for") != {
                "world": "task-1", "operation": op, "method": "M1",
                "replaces_unqualified_sequence": replaces,
            }
            or row.get("producer_command_uid") != "branch:caaa88f1-aa5b-48ee-9857-a0cda234b4a7"
            or row.get("transaction_id") != "task-1:r1:branch-undo-redo-recovery"
        ):
            fail(f"W1 recovery extra {label} differs")
        status = row.get("status")
        if status == "prepared_not_executed":
            if executed_extra_count:
                # 8R may be executed while 9R is still pending, but never the inverse.
                pass
            execution = row.get("execution")
            if not isinstance(execution, dict) or any(
                execution.get(key) is not None
                for key in ("completed_at", "exit_code", "stdout", "stderr", "duration_seconds", "outbound_attempted")
            ):
                fail(f"W1 prepared recovery extra {label} contains execution evidence")
        elif status == "executed_success":
            if label == "9R" and executed_extra_count != 1:
                fail("W1 9R cannot execute before 8R")
            execution = row.get("execution")
            if not isinstance(execution, dict) or execution.get("exit_code") != 0 or not execution.get("completed_at"):
                fail(f"W1 executed recovery extra {label} evidence differs")
            executed_extra_count += 1
        else:
            fail(f"W1 recovery extra {label} has unsupported status")
    if extras[0].get("status") == "prepared_not_executed" and extras[1].get("status") != "prepared_not_executed":
        fail("W1 recovery extras are not an ordered prefix")

    actual_calls = len(executed) + executed_extra_count
    counts = partial.get("counts")
    qualified_executed = len(executed) - sum(
        row.get("status") == "executed_plan_mismatch" for row in executed
    ) + executed_extra_count
    if (
        partial.get("actual_mem_calls") != actual_calls
        or not isinstance(counts, dict)
        or counts.get("executed") != len(executed)
        or counts.get("executed_recovery_extras") != executed_extra_count
        or counts.get("qualified_executed") != qualified_executed
        or counts.get("unqualified_executed") != sum(
            row.get("status") == "executed_plan_mismatch" for row in executed
        )
    ):
        fail("W1 actual/qualified execution counters differ")
    if actual_calls == 0:
        if partial.get("status") != "prepared_not_executed":
            fail("W1 zero-call ledger is not in prepared mode")
    else:
        if partial.get("status") not in {
            "stopped_plan_runtime_mismatch", "recovery_in_progress", "executing"
        }:
            fail("W1 nonzero-call ledger is not in an executing/paused mode")
        if len(executed) >= 8:
            mismatch = {row["sequence"]: row for row in executed if row.get("status") == "executed_plan_mismatch"}
            if set(mismatch) != {8, 9} or any(
                row.get("defect_links") != ["ADM-PLAN-INIT-UNDO-001"]
                for row in mismatch.values()
            ):
                fail("W1 seq8/9 mismatch evidence differs")
    if len(executed) > 10 and executed_extra_count != 2:
        fail("W1 seq11 cannot execute before both recovery extras qualify M1")

    qualification = {
        (world, op, attempt)
        for world in WORLDS for op in OPS for attempt in range(1, 6)
    }
    qualification.remove(("task-1", "undo", 1))
    qualification.remove(("task-1", "redo", 1))
    qualification.update((row["qualifies_for"]["world"], row["qualifies_for"]["operation"], 1) for row in extras)
    qualified_counts = Counter((world, op) for world, op, _attempt in qualification)
    if qualified_counts != Counter({(world, op): 5 for world in WORLDS for op in OPS}):
        fail("qualified route plan is not exactly five methods per world/operation")
    source_freeze = partial.get("source_freeze", {})
    if source_freeze.get("profiles") != payload["import_sources"]["source_profiles"]:
        fail("W1 partial Source Profile evidence differs")
    if source_freeze.get("imports") != payload["import_sources"]["worlds"]["task-1"]:
        fail("W1 partial Import evidence differs")
    if source_freeze.get("world_reads") != payload["host_source_evidence"]["world_reads"]["task-1"]:
        fail("W1 partial Log/Share Source evidence differs")
    sheet = TASK1_SHEET.read_text()
    if "TBD" in sheet or len(re.findall(r"^\|\s+\d+\s+\|", sheet, re.MULTILINE)) != 105:
        fail("W1 sheet placeholders/row count differ")
    for required in (
        IMPORT_MAP["task-1"][2][1], READ_SOURCES["task-1"],
        "Only sequences 1–100", "receipt alone prints only uid[:8]",
        "exact selected semantic target (task-1/participant/admin-scratch/r1-renamed)",
        "single 5-line Init-study name field",
        "press Escape directly; never Enter",
        "A–Z</code>, <code>switch</code>, <code>Forms</code>, <code>← back</code>, <code>Q/Esc close",
        "press Left once to collapse",
        "Search text: <code>${PHASE_ENTRY_CURRENT}</code>",
        "materialized/selectable, and the pre-attempt current is different",
    ):
        if required not in sheet:
            fail(f"W1 sheet lacks exact contract: {required}")
    init_study_sheet = sheet.split("### 84 · init-study M4", 1)[1].split(
        "### 87 · checkout M5", 1
    )[0]
    if (
        "<code>Enter</code>" in init_study_sheet
        or "study-baseline" in init_study_sheet
        or "final review" in init_study_sheet.lower()
    ):
        fail("W1 Init-study M4 sheet retains a create key or nonexistent layer")
    help_sheet = sheet.split("### 90 · help M5", 1)[1].split(
        "### 91 · share M5", 1
    )[0]
    if (
        "focus search" in help_sheet.lower()
        or "enter query" in help_sheet.lower()
        or "open syntax" in help_sheet.lower()
        or "Escape back to inventory" in help_sheet
        or "<code>H</code>" in help_sheet
    ):
        fail("W1 Help M5 sheet retains a nonexistent or exiting layer")
    switch_sheet = sheet.split("### 103 · switch M5", 1)[1].split(
        "## Atomic ledger procedure", 1
    )[0]
    search_line = next(
        line for line in switch_sheet.splitlines() if line.startswith("- Search text:")
    )
    if (
        search_line != "- Search text: <code>${PHASE_ENTRY_CURRENT}</code>"
        or "inspect LOCAL/GRANT/QUERY ONLY" in switch_sheet
        or "exact semantic target (LOCAL | GRANT | QUERY ONLY" in switch_sheet
    ):
        fail("W1 Switch M5 sheet retains simultaneous category-token targeting")

    plan = PLAN.read_text()
    for world in WORLDS:
        if ROOTS[world] not in plan or READ_SOURCES[world] not in plan:
            fail(f"plan lacks {world} Goal/Share Source mapping")
        for attempt in range(1, 6):
            if IMPORT_MAP[world][attempt][1] not in plan:
                fail(f"plan lacks {world} Import M{attempt} Source")
    for stale in (
        "M2 completion stdout", "600 executable-now", "pre-gate state contains exactly 600",
        "practice/audit-workspace/transform-scratch` |",
        "local/GRANT/QUERY ONLY rows",
    ):
        if stale in plan:
            fail(f"plan retains stale contract: {stale}")
    for required in (
        "one 5-line Study-name field",
        "Enter create · Esc cancel",
        "Never press Enter",
        "choose the A–Z inventory view",
        "Left once to collapse",
        "Escape is never a back action",
        "host-bind the exact phase-entry ordinary local Context name/UID/digest",
        "prove it materialized/selectable and different from current",
    ):
        if required not in plan:
            fail(f"plan lacks a required revised TUI contract: {required}")

    print(
        "admin-preflight OK: 630 exact world-serial cells; current prefix W1 1-100; "
        "Import Context UID sets collision-free; M3 direct Memory/Log owners verified; "
        "TUI=60 adaptive; outbound=18; Share delivery=0; mem calls=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, json.JSONDecodeError, OSError, KeyError, TypeError) as error:
        print(f"admin-preflight INVALID: {error}", file=sys.stderr)
        raise SystemExit(1)
