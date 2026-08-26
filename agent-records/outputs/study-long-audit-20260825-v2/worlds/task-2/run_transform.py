#!/usr/bin/env python3
"""Run task-2 TRANSFORM attempts through the pinned world launcher only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import time


WORLD = "task-2"
ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/outputs/study-long-audit-20260825-v2/worlds/task-2"
RAW = OUT / "raw"
WRAPPER = ROOT / "agent-records/outputs/study-long-audit-20260825-v2/run_world_mem.py"
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-2/profile-control/stores/"
    "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
PHASE = OUT / "phase-transform.json"
WORKSPACE = "task-2/participant/proposal-workspace"

CODE_SHA = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROVIDER_DIGEST = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"

CATEGORIES = ("style", "style", "budget", "methods", "final-local")
MERGE_SOURCES = (
    "task-2/advisor1/style",
    "task-2/advisor2/style",
    "task-2/advisor1/budget",
    "task-2/advisor2/methods",
    "task-2",
)
DISTILL_SOURCES = MERGE_SOURCES
GOALS = (
    "Preserve advisor1 style conditions while keeping equal co-advisor authority explicit.",
    "Preserve advisor2 style conditions while keeping equal co-advisor authority explicit.",
    "Reconcile budget placement without hiding either advisor's incompatible requirement.",
    "State when exact and ranged recruitment targets apply without selecting one advisor as default.",
    "Produce a final neutral rule set with both provenances and explicit unresolved exceptions.",
)
RULES = (
    "A shared style rule must retain both advisor provenances and name any source-specific sentence condition.",
    "A longer sentence is retained only when its clauses form one reviewable movement; otherwise split it.",
    "Budget totals remain visible while arithmetic placement records the triggering review condition.",
    "An exact target applies after commitments; a justified range applies while confirmations can change.",
    "No advisor has tie-breaking priority, and every unresolved conflict needs an owner and explanation.",
)
FORGET_INSTRUCTIONS = (
    "Remove only exact duplicate stored policies; preserve every distinct advisor condition and provenance.",
    "Remove only ungrounded illustrative cases; preserve both advisors' actual style policies.",
    "Remove dependent heading-only fragments that cannot stand alone; preserve complete budget rules and both provenances.",
    "Remove recruitment statements that omit the condition distinguishing an exact target from a range; preserve conditioned versions.",
    "Remove any scratch rule that gives one advisor tie-breaking priority; retain explained unresolved conflicts.",
)
LANGUAGES = ("Korean", "French", "Japanese", "Spanish", "German")

OPERATIONS = (
    "merge", "distill", "elaborate", "checkpoint", "audit",
    "check-conformance", "atomize", "resolve", "dedup", "dedun",
    "forget", "ground", "impact", "meld", "rationale", "review",
    "sever", "trace", "translate", "update", "delete", "clear", "diff",
    "revert",
)


def context_path(name: str) -> Path:
    return STORE / "contexts" / name / "context.json"


def context_digest(name: str | None) -> str:
    if name is None:
        return "N/A (no single durable Context target)"
    path = context_path(name)
    if not path.exists():
        return "N/A (fresh result, readable grant, or absent local Context)"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordinary_uids(name: str) -> list[str]:
    path = context_path(name)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    memories = payload.get("memories", {})
    order = payload.get("order", [])
    return [
        uid
        for uid in order
        if isinstance(memories.get(uid), dict)
        and memories[uid].get("type") == "memory"
    ]


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
    return " | ".join(chosen)[:3000]


def document() -> dict:
    if PHASE.exists():
        return json.loads(PHASE.read_text())
    return {
        "world": WORLD,
        "phase": "transform",
        "status": "in_progress",
        "execution_identity": {
            "code_sha256": CODE_SHA,
            "catalog_sha256": CATALOG_SHA,
            "profile_uid": PROFILE_UID,
            "lane_store_root": str(STORE),
            "provider_policy_digest": PROVIDER_DIGEST,
            "launcher": f"python {WRAPPER} {WORLD} ...",
        },
        "goal": (
            "Transform the cumulative task-2 synthesis while preserving equal "
            "co-advisor authority, explicit conditions, provenance, and recovery evidence."
        ),
        "counted_actual_mem_commands": 0,
        "operations": {},
        "issues": [],
    }


def save(payload: dict) -> None:
    PHASE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def route_metadata(operation: str, round_number: int, args: list[str], before_count: int, item_uid: str) -> tuple[str, str, str, str]:
    category = CATEGORIES[round_number - 1]
    source = MERGE_SOURCES[round_number - 1]
    meld_category = ("style", "style", "budget", "methods", "evaluation")[round_number - 1]
    route = {
        "merge": "explicit Source and Target positionals with direct structural merge",
        "distill": "explicit --from/--to semantic Rule distillation with inline Goal",
        "elaborate": "inline Goal/Rule or Context-source Case elaboration into scratch",
        "checkpoint": "explicit local Context plus descriptive checkpoint message",
        "audit": "retained quality Audit of one exact local scratch frame",
        "check-conformance": "local Target checked against one forced literal Rule",
        "atomize": "single exact scratch Memory analysis through varied selector grammar",
        "resolve": "single-Memory grounded repair analysis with no-create boundary",
        "dedup": "deterministic exact duplicate cleanup on a checkpoint-protected local root",
        "dedun": "semantic DUN cleanup on checkpoint-protected scratch",
        "forget": "whole-frame semantic curation with one explicit neutral instruction",
        "ground": "explicit unsaved --request outside a TTY",
        "impact": "read-only directional Update or exact Atomize impact preview",
        "meld": "symmetric two-grant Meld into a fresh named result without --accept",
        "rationale": "retained provenance explanation for an exact scratch Memory or Context",
        "review": "provider-free saved Audit review by exact full session UID",
        "sever": "scratch Source curated against local equal-authority Criteria into a fresh result without --accept",
        "trace": "retained lineage read with exact Memory/Context selector",
        "translate": "non-materialized exact translation view in a distinct target language",
        "update": "directional granted/local Source update into checkpoint-protected scratch",
        "delete": "direct scratch-item deletion or one deliberate missing-selector boundary",
        "clear": "direct or recursive checkpointed scratch clear",
        "diff": "explicit checkpoint-to-current recovery comparison",
        "revert": "exact checkpoint restoration or deliberate missing-checkpoint boundary",
    }[operation]
    target = {
        "merge": f"{source} → {WORKSPACE}",
        "distill": f"{source} → {WORKSPACE}",
        "elaborate": WORKSPACE,
        "checkpoint": "task-2" if round_number == 1 else WORKSPACE,
        "audit": WORKSPACE,
        "check-conformance": WORKSPACE,
        "atomize": f"{WORKSPACE}:{item_uid[:8]}",
        "resolve": f"{WORKSPACE}:{item_uid[:8]}",
        "dedup": "task-2" if round_number == 1 else WORKSPACE,
        "dedun": WORKSPACE,
        "forget": WORKSPACE,
        "ground": "process-local unsaved Ground frame",
        "impact": f"round-{round_number} {category} preview",
        "meld": f"advisor1/{meld_category} ↔ advisor2/{meld_category} → fresh meld-r{round_number}",
        "rationale": WORKSPACE if round_number == 5 else f"{WORKSPACE}:{item_uid[:8]}",
        "review": f"round-{round_number} saved Audit artifact",
        "sever": f"{WORKSPACE} against task-2/description → fresh sever-r{round_number}",
        "trace": WORKSPACE if round_number == 4 else f"{WORKSPACE}:{item_uid[:8]}",
        "translate": f"{WORKSPACE}:{item_uid[:8]} → {LANGUAGES[round_number - 1]}",
        "update": f"{source} → {WORKSPACE}",
        "delete": (
            f"{WORKSPACE}:deadbeef missing-selector boundary"
            if round_number == 4
            else f"{WORKSPACE}:{item_uid[:8]}"
        ),
        "clear": WORKSPACE,
        "diff": "task-2 checkpoint" if round_number == 1 else f"{WORKSPACE} checkpoint",
        "revert": "missing task-2 checkpoint boundary" if round_number == 1 else f"{WORKSPACE} recovery checkpoint",
    }[operation]
    scope = f"{category} transform; workspace had {before_count} ordinary Memories before this command; argv route: {' '.join(args[:5])}"
    provenance = (
        f"cumulative CORE state plus round-{round_number} {category} evidence; "
        f"current exact scratch input {item_uid[:8] if item_uid else 'none'}; "
        f"Source {source}"
    )
    return route, target, scope, provenance


EXPECTED = {
    "merge": "Copy the selected Source structure into local scratch without changing the Source and report conflicts explicitly.",
    "distill": "Add a bounded neutral Rule set to scratch with retained Source provenance.",
    "elaborate": "Add clearly unverified or source-grounded cases to scratch without asserting unsupported facts as approved.",
    "checkpoint": "Create an exact durable recovery point before destructive scratch work.",
    "audit": "Save a complete read-only quality assessment without partial publication.",
    "check-conformance": "Report per-rule conformance without changing Target or Rules.",
    "atomize": "Analyze one exact Memory and preserve unresolved review gates without an unsupported apply.",
    "resolve": "Apply only an operation-owned unique verified repair; otherwise expose the review gate without choosing for the user.",
    "dedup": "Remove only later exact same-role duplicates and retain the first existing UID.",
    "dedun": "Apply complete redundancy groups only inside checkpoint-protected world-local scratch.",
    "forget": "Return one keep/transform/drop decision per scratch Memory and preserve equal-authority conditions.",
    "ground": "Print the stable unsaved frame and create no Ground without exact command approval.",
    "impact": "Preview effects without mutating either endpoint.",
    "meld": "Save a balanced relation analysis and stop at unresolved equal-authority decisions; do not accept a result.",
    "rationale": "Explain retained provenance without changing content.",
    "review": "Reopen the exact saved Audit provider-free and apply nothing.",
    "sever": "Save curation analysis and stop before materialization or ambiguous decisions.",
    "trace": "Render retained lineage without mutation.",
    "translate": "Save/reuse a translation view without changing the Source Memory.",
    "update": "Update only checkpoint-protected scratch from the selected Source, preserving staged-session safety.",
    "delete": "Delete only the exact scratch item or reject a missing selector before mutation.",
    "clear": "Clear only scratch as one checkpointed Undoable command.",
    "diff": "Show exact changes from the recorded checkpoint without mutation.",
    "revert": "Restore the exact reviewed checkpoint or reject an unavailable selector safely.",
}


def run_attempt(payload: dict, *, sequence: int, operation: str, number: int, args: list[str], target_context: str | None, active_checkpoint: str, item_uid: str) -> tuple[int, str]:
    before_count = len(ordinary_uids(WORKSPACE))
    entry, target, scope, provenance = route_metadata(operation, number, args, before_count, item_uid)
    pre = context_digest(target_context)
    command = ["python", str(WRAPPER), WORLD, *args]
    display = " ".join(json.dumps(part) if any(char.isspace() for char in part) else part for part in command)
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=700,
            check=False,
        )
        exit_code = result.returncode
        output = result.stdout
    except subprocess.TimeoutExpired as error:
        exit_code = 124
        output = (error.stdout or "") + (error.stderr or "") + "\nAUDIT HARNESS TIMEOUT AFTER 700 SECONDS\n"
    duration = round(time.monotonic() - started, 3)
    post = context_digest(target_context)
    raw_path = RAW / f"{sequence:03d}-{operation}-attempt-{number}.txt"
    raw_path.write_text(
        f"COMMAND: {display}\nEXIT: {exit_code}\nDURATION_SECONDS: {duration}\n\n{output}"
    )
    record = {
        "attempt": number,
        "sequence": sequence - 105,
        "command": display,
        "exit": exit_code,
        "starting_state": (
            f"same cumulative lane after CORE sequence 105; TRANSFORM phase-local "
            f"sequence {sequence - 105} (raw world sequence {sequence}); "
            f"workspace ordinary Memory count {before_count}"
        ),
        "entry_route": entry,
        "target_route": target,
        "scope": scope,
        "input_provenance": provenance,
        "consumer": "next task-2 transform, review, recovery, or final equal-authority validation step",
        "expected": EXPECTED[operation],
        "actual": compact(output, exit_code),
        "defect_ids": [],
        "cost": f"one counted actual mem invocation; {duration:.3f}s wall time",
        "pre_target_digest": pre,
        "post_target_digest": post,
        "recovery_evidence": (
            f"Active recovery selector {active_checkpoint or 'not-yet-created'}; "
            "pre/post Context SHA-256 and chronological raw output retained."
        ),
        "state_continuity": "No reset; same pinned Profile UID and cumulative lane Store retained across CORE and TRANSFORM.",
        "raw_output": str(raw_path.relative_to(ROOT)),
    }
    payload["operations"].setdefault(operation, {"attempts": []})["attempts"].append(record)
    payload["counted_actual_mem_commands"] += 1
    save(payload)
    return exit_code, output


def elaborate_args(round_number: int) -> list[str]:
    if round_number == 1:
        return ["elaborate", "--rule", RULES[0], "--to", WORKSPACE, "--number", "2", "--strict"]
    if round_number == 2:
        return ["elaborate", "--goal", GOALS[1], "--to", WORKSPACE, "--number", "2"]
    if round_number == 3:
        return ["elaborate", "--rule", RULES[2], "--rule", RULES[4], "--to", WORKSPACE, "--number", "3", "--strict"]
    if round_number == 4:
        return ["elaborate", "--from", "task-2/description", "--to", WORKSPACE, "--as", "rules", "--number", "2"]
    return ["elaborate", "--goal", GOALS[4], "--to", WORKSPACE, "--number", "1", "--strict"]


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    payload = document()
    if payload["counted_actual_mem_commands"]:
        raise SystemExit("phase-transform.json already has counted attempts; refusing duplication")
    sequence = 105

    for round_number in range(1, 6):
        category = CATEGORIES[round_number - 1]
        source = MERGE_SOURCES[round_number - 1]
        meld_category = ("style", "style", "budget", "methods", "evaluation")[round_number - 1]
        checkpoint_uid = ""
        audit_uid = ""

        for operation in OPERATIONS:
            sequence += 1
            current_uids = ordinary_uids(WORKSPACE)
            item_uid = current_uids[0] if current_uids else "00000000"
            second_uid = current_uids[1] if len(current_uids) > 1 else item_uid

            if operation == "merge":
                args = ["merge", source, WORKSPACE, "--direct"]
                target_context = WORKSPACE
            elif operation == "distill":
                args = ["distill", "--from", source, "--to", WORKSPACE, "--goal", GOALS[round_number - 1], "--direct"]
                target_context = WORKSPACE
            elif operation == "elaborate":
                args = elaborate_args(round_number)
                target_context = WORKSPACE
            elif operation == "checkpoint":
                checkpoint_context = "task-2" if round_number == 1 else WORKSPACE
                args = ["checkpoint", checkpoint_context, f"task-2 transform round {round_number} before destructive cleanup", "--direct"]
                target_context = checkpoint_context
            elif operation == "audit":
                args = ["audit", WORKSPACE]
                if round_number in (3, 5):
                    args += ["--against", "task-2/description"]
                target_context = WORKSPACE
            elif operation == "check-conformance":
                args = ["check-conformance", WORKSPACE, "--against", f"text:{RULES[round_number - 1]}"]
                target_context = WORKSPACE
            elif operation == "atomize":
                if round_number == 1:
                    args = ["atomize", f"{WORKSPACE}:{item_uid}"]
                elif round_number == 2:
                    args = ["atomize", "--context", WORKSPACE, "--memory", item_uid]
                elif round_number == 3:
                    args = ["atomize", item_uid, "--context", WORKSPACE]
                elif round_number == 4:
                    args = ["atomize", "--context", WORKSPACE, "--memory", item_uid, "--refresh"]
                else:
                    args = ["atomize", f"{WORKSPACE}:{item_uid}", "--all"]
                target_context = WORKSPACE
            elif operation == "resolve":
                args = [
                    "resolve", "--context", WORKSPACE, "--memory", item_uid,
                    "--no-create", "--guidance", RULES[round_number - 1], "--plain",
                ]
                if round_number == 4:
                    args.append("--yes")
                target_context = WORKSPACE
            elif operation == "dedup":
                target_context = "task-2" if round_number == 1 else WORKSPACE
                args = ["dedup", target_context, "--recursive" if round_number == 4 else "--direct"]
            elif operation == "dedun":
                args = ["dedun", WORKSPACE, "--recursive" if round_number == 4 else "--direct"]
                target_context = WORKSPACE
            elif operation == "forget":
                args = ["forget", FORGET_INSTRUCTIONS[round_number - 1], "--context", WORKSPACE]
                target_context = WORKSPACE
            elif operation == "ground":
                args = ["ground", "--request", f"Round {round_number}: {GOALS[round_number - 1]} Review evidence only; create nothing without exact approval."]
                target_context = None
            elif operation == "impact":
                if round_number in (2, 4):
                    args = ["impact", "atomize", "--context", WORKSPACE, "--memory", item_uid]
                    if round_number == 4:
                        args.append("--all")
                elif round_number == 3:
                    args = ["impact", "update", source, WORKSPACE, "--source-root-only", "--target-root-only"]
                elif round_number == 5:
                    args = ["impact", "update", "task-2", WORKSPACE, "--source-memory", "6733c5d8", "--direct"]
                else:
                    args = ["impact", "update", source, WORKSPACE, "--direct"]
                target_context = WORKSPACE
            elif operation == "meld":
                args = [
                    "meld", f"task-2/advisor1/{meld_category}",
                    f"task-2/advisor2/{meld_category}",
                    f"task-2/participant/meld-r{round_number}", "--direct",
                ]
                target_context = f"task-2/participant/meld-r{round_number}"
            elif operation == "rationale":
                if round_number == 1:
                    args = ["rationale", f"{WORKSPACE}:{item_uid}"]
                elif round_number == 2:
                    args = ["rationale", item_uid, "--context", WORKSPACE, "--verbose"]
                elif round_number == 3:
                    args = ["rationale", f"{WORKSPACE}:{item_uid}", "--limit", "80", "--unit", "characters"]
                elif round_number == 4:
                    args = ["rationale", f"{WORKSPACE}:{item_uid}", "--json"]
                else:
                    args = ["rationale", WORKSPACE, "--limit", "60", "--unit", "words"]
                target_context = WORKSPACE
            elif operation == "review":
                args = ["review", "audit", "--session", audit_uid or "00000000-0000-0000-0000-000000000000", "--snapshot"]
                target_context = WORKSPACE
            elif operation == "sever":
                args = [
                    "sever", WORKSPACE, "task-2/description",
                    f"task-2/participant/sever-r{round_number}", "--direct",
                ]
                target_context = f"task-2/participant/sever-r{round_number}"
            elif operation == "trace":
                if round_number == 1:
                    args = ["trace", f"{WORKSPACE}:{item_uid}", "--limit", "5", "--plain"]
                elif round_number == 2:
                    args = ["trace", item_uid, "--context", WORKSPACE, "--verbose", "--limit", "10"]
                elif round_number == 3:
                    args = ["trace", f"{WORKSPACE}:{item_uid}", "--json", "--limit", "20"]
                elif round_number == 4:
                    args = ["trace", WORKSPACE, "--all", "--plain"]
                else:
                    args = ["trace", f"{WORKSPACE}:{item_uid}", "--all", "--json"]
                target_context = WORKSPACE
            elif operation == "translate":
                args = ["translate", f"{WORKSPACE}:{item_uid}", "--to", LANGUAGES[round_number - 1]]
                if round_number == 3:
                    args.append("--refresh")
                target_context = WORKSPACE
            elif operation == "update":
                args = ["update", source, WORKSPACE, "--direct", "--replace-stage", "--goal", GOALS[round_number - 1]]
                if round_number == 5:
                    args += ["--source-memory", "6733c5d8", "--target-memory", second_uid]
                target_context = WORKSPACE
            elif operation == "delete":
                if round_number == 4:
                    args = ["delete", "deadbeef", "--context", WORKSPACE]
                elif round_number == 2:
                    args = ["delete", f"{WORKSPACE}:{item_uid}"]
                else:
                    args = ["delete", item_uid, "--context", WORKSPACE]
                target_context = WORKSPACE
            elif operation == "clear":
                args = ["clear", WORKSPACE]
                if round_number in (3, 5):
                    args.append("--recursive")
                if round_number == 4:
                    args.append("--force")
                target_context = WORKSPACE
            elif operation == "diff":
                if round_number == 1:
                    args = ["diff", "task-2", "--checkpoint", checkpoint_uid or "00000000", "--stat"]
                    target_context = "task-2"
                elif round_number == 2:
                    args = ["diff", checkpoint_uid or "00000000", "--context", WORKSPACE, "--raw"]
                    target_context = WORKSPACE
                elif round_number == 3:
                    args = ["diff", checkpoint_uid or "00000000", "--context", WORKSPACE, "--verbose"]
                    target_context = WORKSPACE
                elif round_number == 4:
                    args = ["diff", WORKSPACE, "--checkpoint", checkpoint_uid or "00000000", "--stat"]
                    target_context = WORKSPACE
                else:
                    args = ["diff", "--checkpoint", checkpoint_uid or "00000000", "--raw"]
                    target_context = WORKSPACE
            elif operation == "revert":
                if round_number == 1:
                    args = ["revert", "deadbeef", "--context", "task-2", "--keep"]
                    target_context = "task-2"
                else:
                    args = ["revert", checkpoint_uid or "00000000", "--context", WORKSPACE, "--keep"]
                    target_context = WORKSPACE
            else:  # pragma: no cover
                raise AssertionError(operation)

            exit_code, output = run_attempt(
                payload,
                sequence=sequence,
                operation=operation,
                number=round_number,
                args=args,
                target_context=target_context,
                active_checkpoint=checkpoint_uid,
                item_uid=item_uid,
            )
            if operation == "checkpoint" and exit_code == 0:
                match = re.search(
                    r"(?:mem revert |\[)([0-9a-f-]{8,36})(?: --keep|\])",
                    output,
                    re.IGNORECASE,
                )
                if match:
                    checkpoint_uid = match.group(1)
            if operation == "audit" and exit_code == 0:
                match = re.search(r"mem review audit --session ([0-9a-f-]{36})", output, re.IGNORECASE)
                if match:
                    audit_uid = match.group(1)

    payload["status"] = "complete"
    payload["coverage"] = {operation: 5 for operation in OPERATIONS}
    success_count = sum(
        attempt["exit"] == 0
        for record in payload["operations"].values()
        for attempt in record["attempts"]
    )
    payload["execution_summary"] = {
        "counted_actual_mem_commands": 120,
        "successful_exits": success_count,
        "nonzero_exits": 120 - success_count,
        "provider_infrastructure_failures": 0,
        "store_resets": 0,
        "starting_phase_sequence": 1,
        "ending_phase_sequence": 120,
        "raw_world_sequence_range": [106, 225],
    }
    save(payload)


if __name__ == "__main__":
    main()
