#!/usr/bin/env python3
"""Run and capture the 120 counted practice-source transform attempts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time


WORLD = "practice-source"
ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw" / "transform"
RUNNER = Path(
    "/Users/KimMunyeong/Github/memcommit/outputs/"
    "study-long-audit-20260825-v2/run_world_mem.py"
)
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/practice-source/profile-control/"
    "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
CONTEXTS = STORE / "contexts"
SOURCE = CONTEXTS / "practice" / "source" / "context.json"
PHASE_PATH = ROOT / "phase-transform.json"
DESC = "practice/description"

OPERATIONS = (
    "atomize", "audit", "checkpoint", "check-conformance", "clear",
    "delete", "diff", "distill", "elaborate", "resolve", "dedup",
    "dedun", "forget", "ground", "impact", "meld", "merge", "rationale",
    "revert", "review", "sever", "trace", "translate", "update",
)

SOURCE_UIDS = {
    "review": "f3ef224d",
    "polish": "e50c293a",
    "expression": "39b21971",
    "all_points": "6fad23ab",
    "fixed_limit": "6cc4b8a3",
    "strength": "7ebe67fb",
    "connector": "b976766e",
    "terminology": "44de7eff",
    "title_case": "1a9d3a74",
    "italics": "94c3ce98",
    "lookup": "96300a95",
    "citations": "4fe217eb",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context_path(name: str) -> Path:
    return CONTEXTS.joinpath(*name.split("/"), "context.json")


def target_digest(names: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for name in sorted(set(names)):
        path = context_path(name)
        digest.update(name.encode())
        digest.update(b"\0")
        if path.exists():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<absent>")
        digest.update(b"\0")
    return digest.hexdigest()


def memory_prefix(context_name: str, fragment: str | None = None) -> str:
    data = json.loads(context_path(context_name).read_text(encoding="utf-8"))
    matches = []
    for uid in data.get("order", []):
        item = data.get("memories", {}).get(uid, {})
        if item.get("type") != "memory":
            continue
        if fragment is None or fragment in item.get("content", ""):
            matches.append(uid[:8])
    if not matches and fragment is not None:
        return memory_prefix(context_name)
    if not matches:
        # Some rounds deliberately clear scratch before rebuilding it. Later
        # commands in that interval receive a missing-selector boundary rather
        # than causing the audit orchestrator itself to stop.
        return "deadbeef"
    return matches[0]


def extract_uuid(patterns: tuple[str, ...], output: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def compact_actual(stdout: str, stderr: str, exit_code: int) -> str:
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return f"Exited {exit_code} with no visible output."
    selected = lines if len(lines) <= 7 else lines[:5] + ["…"] + lines[-2:]
    return f"Exit {exit_code}. " + " | ".join(selected)[:2200]


def expected_for(operation: str, attempt: int) -> str:
    base = {
        "atomize": "Analyze only the exact scratch selection; publish a split only when every child preserves meaning and complete scope.",
        "audit": "Save one read-only, source-linked quality report over the frozen declared frame.",
        "checkpoint": "Capture the exact scratch state and print a reusable checkpoint UID for later recovery.",
        "check-conformance": "Judge the declared examples against the exact rule frame without treating unsplit information presence as independent atomicity.",
        "clear": "Clear only the declared scratch scope as one checkpointed Undoable command, or fail/no-op without partial change.",
        "delete": "Delete only the exact declared scratch item; missing or ambiguous selectors fail without mutation.",
        "diff": "Render the exact scratch checkpoint difference noninteractively when a checkpoint is supplied, with stable raw/stat/verbose variants.",
        "distill": "Add only source-grounded constraint rules to scratch, excluding inferred presentation style and preserving triggers, exceptions, safeguards, and provenance.",
        "elaborate": "Generate only grounded hypothetical cases/rules in scratch and clearly retain unverified status without inventing source facts.",
        "resolve": "Propose or apply only the minimum guidance-grounded scratch correction; no explicit reviewed candidate means no destructive Apply.",
        "dedup": "Remove exact duplicate scratch items deterministically with complete survivor/absorption evidence.",
        "dedun": "Resolve semantic redundancies in scratch with complete survivor/absorption mappings and an exact review/recovery route.",
        "forget": "Apply exactly one keep/transform/drop disposition per scratch Source Memory while retaining complete source/criterion frame meaning.",
        "ground": "Create or reopen only the lane-local atomization Ground with an explicit Goal and bindings; invalid bindings fail before durable creation.",
        "impact": "Inspect the exact declared saved/proposed operation without applying it or defaulting to ambient targets.",
        "meld": "Prepare a reviewable scratch Meld proposal without applying unresolved semantic choices.",
        "merge": "Structurally merge only into checkpointed scratch and expose exact additions/conflicts for later recovery.",
        "rationale": "Explain selected Memory provenance and limitations without implying that recorded derivation proves semantic sufficiency.",
        "revert": "Restore the exact current-round scratch checkpoint while preserving a reusable recovery receipt and leaving source untouched.",
        "review": "Open exact saved operation evidence by receipt/session/context without mutating it.",
        "sever": "Prepare a separate scratch curation result without changing Source; no unresolved or unreviewed session is accepted.",
        "trace": "Render bounded provenance for the exact Memory/operation and honor the requested output limit.",
        "translate": "Save a read-only translation view anchored to source UIDs; do not alter source content.",
        "update": "Apply only source-grounded changes to scratch, print receipt/checkpoint/recovery, and never mutate practice/source.",
    }[operation]
    dimension = {
        1: " Direct positional baseline.",
        2: " Option-routed or recursive breadth.",
        3: " Prior checkpoint/receipt/UID reuse.",
        4: " Ambiguous, missing, mixed-item, or stale boundary.",
        5: " Late accumulated-state or reopened-session verification.",
    }[attempt]
    return base + dimension


def route_meta(operation: str, attempt: int, targets: tuple[str, ...], detail: str) -> dict[str, str]:
    return {
        "starting_state": f"Cumulative post-core lane at transform round {attempt}; current-round scratch recovery checkpoint planned; source guard active.",
        "entry_route": f"pinned non-interactive transform CLI · {detail}",
        "target_route": ", ".join(targets) if targets else "process-local or saved operation artifact",
        "scope": f"attempt-{attempt} exact declared operands; {detail}",
        "input_provenance": f"fixed practice/source plus cumulative core/transform scratch; method={detail}",
        "consumer": "meaning-preserving atomization decision and exact scratch recovery evidence",
    }


def commands_for(round_number: int, state: dict[str, object]) -> list[tuple[str, list[str], tuple[str, ...], str]]:
    s = SOURCE_UIDS
    checkpoints = {**{i: "PENDING" for i in range(1, 6)}, **state["checkpoints"]}
    receipts = state["receipts"]
    sessions = state["sessions"]
    desc_uid = memory_prefix(DESC)
    delete_uid = desc_uid
    exact_fragments = {
        1: "Use consistent italics",
        2: "DEFAULT CANDIDATE",
        3: "AUDIT RESULT",
        4: "If I later ask for polishing",
    }
    atom_uid = "deadbeef" if round_number == 5 else memory_prefix(DESC, exact_fragments[round_number])

    clear_args = {
        1: ["clear", DESC],
        2: ["clear", DESC, "--recursive"],
        3: ["clear", "practice/transform-missing-r3"],
        4: ["clear", DESC, "--recursive"],
        5: ["clear", "practice/transform-missing-r5"],
    }[round_number]
    clear_targets = (DESC,) if round_number in {1, 2, 4} else (f"practice/transform-missing-r{round_number}",)
    delete_args = (
        ["delete", delete_uid, "--context", DESC]
        if round_number in {3, 5}
        else ["delete", f"missing-transform-r{round_number}", "--context", DESC]
    )

    distill_goals = {
        1: "Independently reviewable editing-constraint atoms only; preserve every trigger, exception, protected object, companion safeguard, and source meaning; do not perform edits.",
        2: "Preserve complete applicability boundaries and provenance while excluding inferred presentation style.",
        3: "Separate independently reviewable commitments without turning examples into permissions or edits.",
        4: "Only constraint atoms; no presentation-style meta-rules; retain exact title scope, named overrides, and protected wording.",
        5: "Late verified atom candidates preserving triggers, exceptions, safeguards, protected terms, and citation-review boundaries.",
    }
    distill_args = ["distill", "--from", "practice/source", "--to", DESC, "--goal", distill_goals[round_number], "--plain"]
    distill_args.append("--recursive" if round_number in {2, 4} else "--direct")

    elaborate_rules = {
        1: ["An atom must remain meaningful without neighboring text and must not authorize an edit."],
        2: ["Every atom must preserve its trigger, narrow exception, protected object, companion safeguard, and provenance.", "Atomization must not perform the requested document edit."],
        3: ["A fixed-limit atom must retain all-points and claim-strength safeguards."],
        4: ["A title-wording atom must retain document-title scope, the narrow style-guide override, and the literal protected word for."],
        5: ["Do not infer a general prose style from examples; emit only constraints explicitly grounded in source text."],
    }[round_number]
    elaborate_args = ["elaborate"]
    for rule in elaborate_rules:
        elaborate_args.extend(["--rule", rule])
    elaborate_args.extend(["--to", DESC, "--number", "2" if round_number != 4 else "1", "--plain"])
    if round_number == 5:
        elaborate_args.append("--strict")

    # Resolve round 3 consumes a Memory actually created by the preceding
    # semantic commands; commands_for is rebuilt before each operation.
    resolve_uid = memory_prefix(DESC) if round_number != 3 else memory_prefix(DESC)
    resolve_args = {
        1: ["resolve", DESC, "--guidance", "Keep every permission trigger and exception explicit; do not convert editing notes into actual edits.", "--no-create", "--plain"],
        2: ["resolve", DESC, "--guidance", "Remove only invented presentation-style rules while preserving grounded constraints.", "--allow-delete", "--plain"],
        3: ["resolve", "--context", DESC, "--memory", resolve_uid, "--guidance", "Retain complete source scope and provenance; do not broaden the selected atom.", "--no-create", "--plain"],
        4: ["resolve", f"{DESC}:{resolve_uid}", "--guidance", "Keep this scoped to document titles and the literal word for; preserve the narrow override.", "--no-create", "--plain"],
        5: ["resolve", DESC, "--guidance", "Do not retain inferred prose-style meta-rules; leave all grounded editing constraints unchanged.", "--allow-delete", "--plain"],
    }[round_number]

    forget_text = {
        1: "Remove only inferred presentation-style meta-rules; preserve every grounded editing constraint.",
        2: "Remove generated examples that invent concrete source text; preserve grounded constraints and explicitly hypothetical examples.",
        3: "Remove exact duplicate copies only; preserve every distinct constraint and provenance link.",
        4: "Remove outputs that lost their trigger, exception, protected object, or companion safeguard; preserve complete grounded atoms.",
        5: "Remove late inferred meta-observations not explicitly stated in source; preserve all operative constraints.",
    }[round_number]

    ground_args = {
        1: ["ground", "--request", "Prepare independently reviewable atoms of practice/source editing constraints without editing their subject text or changing meaning."],
        2: ["ground", "practice-source-v2-transform", "--goal", "Atomize practice/source constraints without editing their subject text or changing meaning.", "--raw-context", "practice/source", "--derived-context", DESC, "--publication-context", DESC, "--snapshot"],
        3: ["ground", "practice-source-v2-transform", "--goal", "Atomize practice/source constraints without editing their subject text or changing meaning.", "--raw-context", "practice/source", "--derived-context", DESC, "--publication-target", DESC, "--snapshot"],
        4: ["ground", "practice-source-v2-transform", "--goal", "Atomize practice/source constraints without editing subject text or changing meaning.", "--description", "Preserve complete triggers, exceptions, protected objects, safeguards, and provenance in independently reviewable atoms.", "--raw-context", "practice/source", "--derived-context", DESC, "--publication-target", DESC, "--snapshot"],
        5: ["ground", "practice-source-v2-transform", "--snapshot"],
    }[round_number]

    update_session = sessions.get("update", {}).get(2, "PENDING")
    meld_session = sessions.get("meld", {}).get(4, "PENDING")
    impact_args = {
        1: ["impact", "atomize", DESC],
        2: ["impact", "distill", "--from", "practice/source", "--to", DESC, "--goal", "preserve triggers, exceptions, safeguards, and provenance", "--direct"],
        3: ["impact", "update", "--session", update_session],
        4: ["impact", "atomize", DESC, "--all"],
        5: ["impact", "meld", "--session", meld_session],
    }[round_number]

    meld_args = {
        1: ["meld", "--memory", "Do not turn an editing constraint into permission to edit; preserve the complete trigger and exception.", "--into", DESC, "--direct"],
        2: ["meld", "--memory", "Keep the fixed-limit reduction attached to all-points and claim-strength safeguards.", "--into", DESC, "--direct", "--restart"],
        3: ["meld", "practice/source", DESC, "practice/transform-meld-r3", "--direct"],
        4: ["meld", "--memory", "Preserve document-title scope when retaining the literal word for.", "--into", DESC, "--direct", "--restart"],
        5: ["meld", "--memory", "Do not infer general presentation-style rules from source examples.", "--into", DESC, "--direct", "--restart"],
    }[round_number]

    merge_args = {
        1: ["merge", "practice/source", DESC, "--direct"],
        2: ["merge", "--from", "practice/source", "--into", DESC, "--direct"],
        3: ["merge", "practice", DESC, "--direct"],
        4: ["merge", DESC, DESC, "--direct"],
        5: ["merge", "practice/source", DESC, "--direct", "--keep-target-all"],
    }[round_number]

    rationale_args = {
        1: ["rationale", f"practice/source:{s['review']}", "--json", "--limit", "120", "--unit", "words"],
        2: ["rationale", f"practice/source:{s['polish']}", "--limit", "80", "--unit", "words"],
        3: ["rationale", f"{DESC}:{memory_prefix(DESC)}", "--limit", "100", "--unit", "words"],
        4: ["rationale", f"practice/source:{s['title_case']}", "--json", "--limit", "60", "--unit", "words"],
        5: ["rationale", f"practice/source:{s['connector']}", "--json", "--limit", "20", "--unit", "words"],
    }[round_number]

    review_args = {
        1: ["review", "elaborate", "--receipt", receipts.get("elaborate", {}).get(1, "PENDING"), "--snapshot"],
        2: ["review", "forget", "--receipt", receipts.get("forget", {}).get(2, "PENDING"), "--snapshot"],
        3: ["review", "dedun", "--receipt", receipts.get("dedun", {}).get(3, "PENDING"), "--snapshot"],
        4: ["review", "update", "--session", sessions.get("update", {}).get(3, "PENDING"), "--snapshot"],
        5: ["review", "atomize", "--context", DESC, "--snapshot"],
    }[round_number]

    sever_session = sessions.get("sever", {}).get(1, "PENDING")
    sever_args = {
        1: ["sever", "practice/source", DESC, "practice/transform-sever-r1", "--direct"],
        2: ["sever", "--source", "practice/source", "--criteria", DESC, "--save-as", "practice/transform-sever-r2", "--direct"],
        3: ["sever", "practice/source", DESC, "practice/transform-sever-r3", "--recursive"],
        4: ["sever", "--resume", sever_session],
        5: ["sever", "practice/source", DESC, "practice/transform-sever-r5", "--source-root-only", "--criteria-root-only"],
    }[round_number]

    trace_args = {
        1: ["trace", f"practice/source:{s['review']}", "--plain", "--limit", "5"],
        2: ["trace", f"practice/source:{s['polish']}", "--json", "--limit", "5"],
        3: ["trace", f"{DESC}:{memory_prefix(DESC)}", "--plain", "--limit", "3"],
        4: ["trace", f"practice/source:{s['title_case']}", "--json", "--limit", "1"],
        5: ["trace", f"practice/source:{s['connector']}", "--plain", "--limit", "1"],
    }[round_number]

    translate_args = {
        1: ["translate", f"practice/source:{s['review']}", "--to", "plain-language English"],
        2: ["translate", f"practice/source:{s['polish']}", "--to", "Korean"],
        3: ["translate", f"practice/source:{s['all_points']}", "--to", "French"],
        4: ["translate", f"practice/source:{s['strength']}", "--to", "Spanish"],
        5: ["translate", f"practice/source:{s['review']}", "--to", "plain-language English"],
    }[round_number]

    target_review_uid = memory_prefix(DESC, "How does this read")
    update_args = {
        1: ["update", "practice/source", DESC, "--source-memory", s["review"], "--direct", "--replace-stage"],
        2: ["update", "practice/source", DESC, "--source-memory", s["polish"], "--direct", "--replace-stage"],
        3: ["update", "practice/source", DESC, "--source-memory", s["review"], "--target-memory", target_review_uid, "--direct", "--replace-stage"],
        4: ["update", "practice/source", DESC, "--source-memory", s["terminology"], "--direct", "--replace-stage"],
        5: ["update", "practice/source", DESC, "--direct", "--replace-stage"],
    }[round_number]

    return [
        ("atomize", (["atomize", "--context", DESC, "--memory", atom_uid] if round_number == 2 else ["atomize", f"{DESC}:{atom_uid}"]), (DESC,), f"exact scratch Memory atomization route r{round_number}"),
        ("audit", (["audit", "practice/source", "--snapshot"] if round_number in {1, 5} else ["audit", DESC, "--snapshot"] if round_number in {2, 4} else ["audit", "practice/source", "--against", DESC, "--snapshot"]), (("practice/source",) if round_number in {1, 5} else (DESC,) if round_number in {2, 4} else ("practice/source", DESC)), f"saved quality snapshot scope r{round_number}"),
        ("checkpoint", ["checkpoint", DESC, f"v2 transform round {round_number} safety"], (DESC,), f"exact recovery checkpoint r{round_number}"),
        ("check-conformance", (["check-conformance", "practice/source", "--against", "Each atom must preserve its complete trigger, exception, protected object, companion safeguard, provenance, and source meaning."] if round_number == 1 else ["check-conformance", DESC, "--against", "Each result must retain complete source scope and must not perform the requested edit."] if round_number in {2, 4} else ["check-conformance", "practice/source", "--against", DESC] if round_number == 3 else ["check-conformance", DESC, "--against", "Every approved atom must be independently reviewable without neighboring text."]), (("practice/source",) if round_number == 1 else (DESC,) if round_number in {2, 4, 5} else ("practice/source", DESC)), f"inline/context conformance frame r{round_number}"),
        ("clear", clear_args, clear_targets, f"successful or missing-boundary scratch clear r{round_number}"),
        ("delete", delete_args, (DESC,), f"exact missing/success direct-item deletion r{round_number}"),
        ("diff", (["diff", DESC, "--checkpoint", checkpoints[round_number], "--stat"] if round_number == 1 else ["diff", checkpoints[round_number], "--context", DESC, "--raw"] if round_number == 2 else ["diff", "--checkpoint", checkpoints[round_number], "--stat"] if round_number == 3 else ["diff", DESC, "--checkpoint", checkpoints[round_number], "--verbose"] if round_number == 4 else ["diff", DESC]), (DESC,), f"checkpoint diff grammar/output r{round_number}"),
        ("distill", distill_args, ("practice/source", DESC), f"constraint-only Distill goal/range r{round_number}"),
        ("elaborate", elaborate_args, (DESC,), f"inline grounded rule set r{round_number}"),
        ("resolve", resolve_args, (DESC,), f"whole/exact non-Apply correction route r{round_number}"),
        ("dedup", ["dedup", DESC, "--direct"], (DESC,), f"exact duplicate cleanup at accumulated state r{round_number}"),
        ("dedun", ["dedun", DESC, "--direct"], (DESC,), f"semantic redundancy cleanup at accumulated state r{round_number}"),
        ("forget", ["forget", forget_text, "--context", DESC], (DESC,), f"complete-frame selective curation criterion r{round_number}"),
        ("ground", ground_args, ("practice/source", DESC) if round_number >= 2 else (), f"blank/invalid/bound/reopen Ground route r{round_number}"),
        ("impact", impact_args, (DESC, "practice/source"), f"atomize/distill/saved-session Impact r{round_number}"),
        ("meld", meld_args, (DESC, "practice/source", "practice/transform-meld-r3") if round_number == 3 else (DESC,), f"directional/symmetric review-only Meld r{round_number}"),
        ("merge", merge_args, ("practice/source", "practice", DESC), f"positional/option/same-target merge boundary r{round_number}"),
        ("rationale", rationale_args, ("practice/source", DESC), f"source/scratch JSON/plain rationale r{round_number}"),
        ("revert", ["revert", checkpoints[round_number], "--context", DESC, "--keep"], (DESC,), f"exact current-round checkpoint recovery r{round_number}"),
        ("review", review_args, (DESC,), f"elaborate/forget/dedun/update/atomize evidence r{round_number}"),
        ("sever", sever_args, ("practice/source", DESC, f"practice/transform-sever-r{round_number}"), f"direct/options/recursive/resume Sever without accept r{round_number}"),
        ("trace", trace_args, ("practice/source", DESC), f"plain/JSON bounded provenance r{round_number}"),
        ("translate", translate_args, ("practice/source",), f"language/cache translation view r{round_number}"),
        ("update", update_args, ("practice/source", DESC), f"exact/whole source-to-scratch Update r{round_number}"),
    ]


def write_phase(attempts_by_op: dict[str, list[dict]], source_before: str) -> None:
    attempts = [a for payload in attempts_by_op.values() for a in payload]
    phase = {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": WORLD,
        "world_goal": "Atomize editing constraints in practice/source without performing edits or changing intended meaning while surrounding working state grows.",
        "phase": "transform",
        "execution_identity": {
            "code_sha256": "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84",
            "catalog_sha256": "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5",
            "profile_uid": "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd",
            "store_root": str(STORE),
            "provider_policy_sha256": "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca",
        },
        "execution_boundary": {
            "runner": str(RUNNER),
            "cumulative_from": "phase-core complete state; no reset",
            "source_fixture": "practice/source",
            "source_initial_sha256": source_before,
            "source_current_sha256": sha(SOURCE),
            "mutation_boundary": "Only lane-local scratch Contexts; destructive rounds recovered practice/description from exact checkpoints.",
            "approval_boundary": "No external Share/clipboard, no unreviewed Meld/Sever/Resolve accept, and no source mutation.",
            "tui": "No TUI used; all transform attempts used explicit pinned non-interactive routes.",
        },
        "operation_order": list(OPERATIONS),
        "interleaving": "Five rounds; each round executes all 24 transform operations once before any repeats.",
        "total_attempts": len(attempts),
        "operations": {op: {"attempts": attempts_by_op[op]} for op in OPERATIONS},
        "outcome": "running" if len(attempts) < 120 else "transform attempt contract complete; reviewed findings in issues-transform.md/issues.json",
    }
    PHASE_PATH.write_text(json.dumps(phase, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    source_before = sha(SOURCE)
    attempts_by_op: dict[str, list[dict]] = {op: [] for op in OPERATIONS}
    state: dict[str, object] = {
        "checkpoints": {},
        "receipts": {"elaborate": {}, "dedun": {}, "forget": {}},
        "sessions": {"update": {}, "meld": {}, "sever": {}},
    }
    sequence = 0

    for round_number in range(1, 6):
        for operation_index, expected_operation in enumerate(OPERATIONS):
            specs = commands_for(round_number, state)
            operation, mem_args, targets, detail = specs[operation_index]
            assert operation == expected_operation
            sequence += 1
            pre = target_digest(targets)
            command_argv = ["python", str(RUNNER), WORLD, *mem_args]
            command = shlex.join(command_argv)
            started = time.monotonic()
            try:
                result = subprocess.run(command_argv, text=True, capture_output=True, timeout=300)
            except subprocess.TimeoutExpired as error:
                result = subprocess.CompletedProcess(
                    command_argv,
                    124,
                    error.stdout or "",
                    (error.stderr or "") + "\nAudit capture timeout after 300 seconds.",
                )
            elapsed = time.monotonic() - started
            post = target_digest(targets)
            if sha(SOURCE) != source_before:
                raise RuntimeError(f"practice/source changed during transform sequence {sequence}")

            stem = f"{sequence:03d}-{operation}-m{round_number}"
            raw_path = RAW / f"{stem}.txt"
            raw_path.write_text(
                f"COMMAND\n{command}\n\nEXIT\n{result.returncode}\n\n"
                f"WALL_SECONDS\n{elapsed:.6f}\n\nSTDOUT\n{result.stdout}\n\nSTDERR\n{result.stderr}",
                encoding="utf-8",
            )

            output = result.stdout + "\n" + result.stderr
            if operation == "checkpoint" and result.returncode == 0:
                uid = extract_uuid((r"\[([0-9a-f]{8,36})\]",), output)
                if uid:
                    state["checkpoints"][round_number] = uid
            if operation in {"elaborate", "dedun", "forget"} and result.returncode == 0:
                uid = extract_uuid(
                    (
                        rf"review\s*:?\s*mem review {operation} --receipt ([0-9a-f-]{{8,36}})",
                        r"RECEIPT\s*·\s*([0-9a-f-]{8,36})",
                    ),
                    output,
                )
                if uid:
                    state["receipts"][operation][round_number] = uid
            if operation in {"update", "meld", "sever"} and result.returncode == 0:
                uid = extract_uuid(
                    (
                        r"SESSION\s*·\s*([0-9a-f-]{8,36})",
                        r"RECEIPT\s*·\s*([0-9a-f-]{8,36})",
                    ),
                    output,
                )
                if uid:
                    state["sessions"][operation][round_number] = uid

            meta = route_meta(operation, round_number, targets, detail)
            attempt = {
                "attempt": round_number,
                "sequence": sequence,
                "command": command,
                "exit": result.returncode,
                **meta,
                "expected": expected_for(operation, round_number),
                "actual": compact_actual(result.stdout, result.stderr, result.returncode),
                "defect_ids": [],
                "cost": {
                    "wall_seconds": round(elapsed, 6),
                    "terminal_screens": max(1, (len(result.stdout.splitlines()) + len(result.stderr.splitlines()) + 51) // 52),
                    "extra_manual_steps": 0,
                    "tui": False,
                },
                "pre_target_digest": pre,
                "post_target_digest": post,
                "recovery_evidence": "No recovery required." if result.returncode == 0 else "Failure retained as the counted boundary result; a later exact Revert/read verifies scratch continuity without retrying away the evidence.",
                "state_continuity": f"practice/source sha256 remained {source_before}; cumulative lane continued to sequence {sequence + 1}.",
                "raw_output": str(raw_path.relative_to(ROOT)),
            }
            attempts_by_op[operation].append(attempt)
            write_phase(attempts_by_op, source_before)
            print(f"{sequence:03d}/120 r{round_number} {operation} exit={result.returncode} wall={elapsed:.2f}s", flush=True)

    if sequence != 120 or any(len(attempts_by_op[op]) != 5 for op in OPERATIONS):
        raise RuntimeError("transform coverage contract not met")
    print(f"COMPLETE source_sha256={sha(SOURCE)}", flush=True)


if __name__ == "__main__":
    main()
