#!/usr/bin/env python3
"""Run the 120 counted task-3 TRANSFORM attempts through the pinned runner.

This is world-local audit harness code.  It never invokes the live ``mem``
entry point, never resets the Store, and restores each checkpointed scratch
target after destructive trials in the same interleaved round.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
from typing import Callable


REPO = Path("/Users/KimMunyeong/Github/memcommit")
AUDIT_ROOT = REPO / "outputs/study-long-audit-20260825-v2"
WORLD_DIR = AUDIT_ROOT / "worlds/task-3"
RAW_DIR = WORLD_DIR / "raw/transform"
RUNNER = AUDIT_ROOT / "run_world_mem.py"
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-3/profile-control/"
    "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
CONTEXTS = STORE / "contexts"
TASK_TREE = CONTEXTS / "task-3"
LEDGER = WORLD_DIR / "phase-transform.json"
CORE_LEDGER = WORLD_DIR / "phase-core.json"

CODE_SHA256 = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA256 = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROVIDER_SHA256 = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"

LOCAL = "task-3/local"
AUDIT = "task-3/local/guardrails/audit-and-recovery"
PURPOSE = "task-3/local/guardrails/purpose-and-scope"
MINIMIZE = "task-3/local/guardrails/minimization-and-redaction"
PRIVACY = "task-3/local/guardrails/privacy-and-others"
APPROVAL = "task-3/local/guardrails/approval-and-delivery"
PERSONAL_2024 = "task-3/local/personal-memory/2024/03"
PERSONAL_2026 = "task-3/local/personal-memory/2026/06"
PUBLIC_GUIDANCE = (
    "task-3/remote/government/healthcare-agent/info-request/"
    "transmission-guidance/public-guidance"
)

OPERATIONS = (
    "atomize", "audit", "checkpoint", "check-conformance", "clear",
    "delete", "diff", "distill", "elaborate", "resolve", "dedup",
    "dedun", "forget", "ground", "impact", "meld", "merge",
    "rationale", "revert", "review", "sever", "trace", "translate",
    "update",
)

TARGETS = (LOCAL, AUDIT, AUDIT, LOCAL, AUDIT)
SOURCES = (PURPOSE, MINIMIZE, PERSONAL_2024, PUBLIC_GUIDANCE, APPROVAL)
SUBJECTS = (PERSONAL_2024, PERSONAL_2026, LOCAL, PERSONAL_2024, AUDIT)
RULES = (PURPOSE, MINIMIZE, PRIVACY, APPROVAL, PURPOSE)
LANGUAGES = ("Korean", "French", "Japanese", "Spanish", "German")
ARTIFACTS: dict[tuple[str, int], str] = {}
ROUND_TARGET_UIDS: dict[int, str] = {}


@dataclass(frozen=True)
class Spec:
    operation: str
    attempt: int
    args: tuple[str, ...] | Callable[[], tuple[str, ...]]
    entry_route: str
    target_route: str
    scope: str
    input_provenance: str
    consumer: str
    expected: str
    recovery_evidence: str


def task_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(TASK_TREE.rglob("context.json"), key=lambda item: str(item)):
        digest.update(str(path.relative_to(TASK_TREE)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def context_path(name: str) -> Path:
    return CONTEXTS.joinpath(*name.split("/"), "context.json")


def context_data(name: str) -> dict:
    path = context_path(name)
    return json.loads(path.read_text()) if path.exists() else {}


def ordinary_uids(name: str) -> list[str]:
    data = context_data(name)
    memories = data.get("memories", {})
    return [
        uid for uid in data.get("order", [])
        if isinstance(memories.get(uid), dict)
        and memories[uid].get("type") == "memory"
    ]


def memory_uid(name: str, needles: tuple[str, ...] = ()) -> str:
    data = context_data(name)
    memories = data.get("memories", {})
    ordered = data.get("order", [])
    for needle in needles:
        for uid in ordered:
            item = memories.get(uid, {})
            if item.get("type") == "memory" and needle.lower() in item.get("content", "").lower():
                return uid
    for uid in ordered:
        if memories.get(uid, {}).get("type") == "memory":
            return uid
    return "deadbeef"


def qualified(name: str, needles: tuple[str, ...] = ()) -> str:
    return f"{name}:{memory_uid(name, needles)[:8]}"


def artifact(kind: str, attempt: int) -> str:
    return ARTIFACTS.get((kind, attempt), "deadbeef")


def capture_artifact(operation: str, attempt: int, output: str) -> None:
    patterns = {
        "checkpoint": (r"\[([0-9a-f]{8})\]",),
        "audit": (
            r"mem review audit --session ([0-9a-f-]{8,36})",
            r"SESSION\s*\[([0-9a-f-]{8,36})\]",
        ),
        "atomize": (
            r"mem review atomize --session ([0-9a-f-]{8,36})",
            r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})",
        ),
        "meld": (r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})",),
        "sever": (r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})",),
        "update": (r"SESSION\s*[·:]\s*([0-9a-f-]{8,64})",),
    }
    for pattern in patterns.get(operation, ()):
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            ARTIFACTS[(operation, attempt)] = match.group(1)
            return


def actual_summary(output: str, exit_code: int) -> str:
    clean = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", output).replace("\r", "")
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if not lines:
        return f"Exited {exit_code} with no visible output."
    selected = lines if len(lines) <= 8 else lines[:6] + [f"… ({len(lines)} lines; raw evidence retained)"] + lines[-2:]
    return f"Exited {exit_code}. " + " | ".join(selected)[:3000]


def specs() -> list[Spec]:
    result: list[Spec] = []

    def add(
        operation: str,
        attempt: int,
        args: tuple[str, ...] | Callable[[], tuple[str, ...]],
        *,
        entry: str,
        target: str,
        scope: str,
        provenance: str,
        consumer: str,
        expected: str,
        recovery: str = "No separate recovery required; later interleaved reads verify state continuity.",
    ) -> None:
        result.append(Spec(operation, attempt, args, entry, target, scope, provenance, consumer, expected, recovery))

    for attempt in range(1, 6):
        target = TARGETS[attempt - 1]
        source = SOURCES[attempt - 1]
        subject = SUBJECTS[attempt - 1]
        rules = RULES[attempt - 1]
        state = (
            f"cumulative no-reset task-3 transform round {attempt}; scratch target {target}; "
            f"Source {source}; exact recovery checkpoint precedes every destructive command"
        )

        atom_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: ("atomize", PURPOSE),
            2: lambda: ("atomize", qualified(PERSONAL_2026, ("restaurant", "appointment"))),
            3: lambda: ("atomize", "--context", PERSONAL_2024, "--memory", memory_uid(PERSONAL_2024, ("medication", "back discomfort"))[:8]),
            4: lambda: ("atomize", qualified(PUBLIC_GUIDANCE, ("stale", "current")), "--all"),
            5: lambda: ("atomize", "--context", AUDIT, "--memory", memory_uid(AUDIT, ("no transfer", "no healthcare disclosure"))[:8], "--refresh"),
        }
        atom_routes = (
            "positional local Context analysis",
            "qualified local Memory analysis",
            "--context plus --memory focused analysis",
            "qualified granted Memory with --all projection",
            "focused local Memory with --refresh regeneration",
        )
        add("atomize", attempt, atom_args[attempt], entry=atom_routes[attempt - 1],
            target=subject if attempt != 4 else PUBLIC_GUIDANCE,
            scope=("complete direct policy frame" if attempt == 1 else "one exact actionable Memory with direct neighbors as non-actionable evidence"),
            provenance=f"{state}; selector and modifiers come from durable Context argv",
            consumer="healthcare disclosure atomicity review",
            expected="Save a source-bound analysis, preserve uncertainty, and do not apply a semantic split without human meaning approval.")

        audit_args = {
            1: ("audit", PERSONAL_2024, "--snapshot"),
            2: ("audit", "--context", PERSONAL_2026, "--snapshot"),
            3: ("audit", LOCAL, "--against", PRIVACY, "--snapshot"),
            4: ("audit", PUBLIC_GUIDANCE, "--snapshot"),
            5: ("audit", AUDIT, "--rule", APPROVAL, "--snapshot"),
        }[attempt]
        add("audit", attempt, audit_args,
            entry=("positional snapshot", "--context snapshot", "positional plus --against Conformance", "granted positional snapshot", "positional plus --rule alias snapshot")[attempt - 1],
            target=(PERSONAL_2024, PERSONAL_2026, LOCAL, PUBLIC_GUIDANCE, AUDIT)[attempt - 1],
            scope=("direct quality frame", "direct quality frame", "quality plus privacy Conformance", "granted direct quality frame", "quality plus approval Conformance")[attempt - 1],
            provenance=f"{state}; fixed pre-destructive healthcare evidence frame",
            consumer="saved read-only quality evidence for later Review",
            expected="Save a complete evidence-linked Audit without mutating content or treating quality as disclosure approval.")

        checkpoint_args = {
            1: ("checkpoint", target, "task-3 transform round 1 direct recovery", "--direct"),
            2: ("checkpoint", "task-3 transform round 2 option-target recovery", "--context", target, "--direct"),
            3: ("checkpoint", target, "--message", "task-3 transform round 3 message-option recovery", "--direct"),
            4: ("checkpoint", "-c", target, "-m", "task-3 transform round 4 short-option recovery", "-d"),
            5: ("checkpoint", target, "task-3 transform round 5 default-direct recovery"),
        }[attempt]
        add("checkpoint", attempt, checkpoint_args,
            entry=("two positionals plus --direct", "message positional plus --context", "Context positional plus --message", "short -c/-m/-d options", "two positionals with default direct scope")[attempt - 1],
            target=target,
            scope="exact direct scratch Context at its pre-destructive byte-equivalent content boundary",
            provenance=f"{state}; actual checkpoint argv freezes this round's target",
            consumer="same-round Clear/Delete/semantic/structural recovery",
            expected="Create one reusable exact checkpoint UID before any destructive mutation.")

        conformance_args = {
            1: ("check-conformance", subject, "--against", rules),
            2: ("check-conformance", "--example", subject, "--from", rules),
            3: ("check-conformance", "--to", subject, "--rule", "text:Never disclose a third party's private information as the user's healthcare fact."),
            4: ("check-conformance", subject, "--rule", rules),
            5: ("check-conformance", "--case", subject, "--against", rules),
        }[attempt]
        add("check-conformance", attempt, conformance_args,
            entry=("Target positional plus --against", "--example plus --from aliases", "--to plus forced text: Rule", "Target positional plus --rule alias", "--case plus --against aliases")[attempt - 1],
            target=f"{subject} against {rules if attempt != 3 else 'literal privacy rule'}",
            scope=("Context subjects and Context rules" if attempt != 3 else "Context subjects against one process-local INSTRUCTION Rule"),
            provenance=f"{state}; argv explicitly separates Subject from Rules",
            consumer="candidate safety and policy conformance report",
            expected="Report all applicable judgments without mutation or unsupported factual acceptance.")

        if attempt in {1, 2}:
            clear_args = ("clear", target, "--force" if attempt == 1 else "-f")
            clear_target = target
            clear_scope = "all direct items in the checkpointed scratch target"
        elif attempt == 3:
            clear_args = ("clear", "task-3/local/transform-missing-r3")
            clear_target = "task-3/local/transform-missing-r3"
            clear_scope = "deliberately absent local Context boundary; checkpointed real target remains available"
        elif attempt == 4:
            clear_args = ("clear", "--force", target)
            clear_target = target
            clear_scope = "all direct items in checkpointed local scratch; children remain untouched"
        else:
            clear_args = ("clear", "task-3/local/transform-missing-r5", "-f")
            clear_target = "task-3/local/transform-missing-r5"
            clear_scope = "deliberately absent local Context boundary after real-target checkpoint"
        add("clear", attempt, clear_args,
            entry=("Context then --force", "Context then -f compatibility flag", "missing positional Context", "--force before Context", "missing Context then -f")[attempt - 1],
            target=clear_target, scope=clear_scope,
            provenance=f"{state}; checkpoint {artifact('checkpoint', attempt)} must already exist by sequence order",
            consumer="destructive/no-partial-state recovery trial",
            expected="Clear only the exact checkpointed direct scope, or reject an absent Context before mutation.",
            recovery=f"Revert#{attempt} restores checkpoint {artifact('checkpoint', attempt)} later in this round.")

        if attempt in {3, 5}:
            delete_args: tuple[str, ...] | Callable[[], tuple[str, ...]] = (
                lambda a=attempt, t=target: ("delete", ROUND_TARGET_UIDS.get(a, "deadbeef")[:8], "--context", t)
            )
            delete_target = f"one exact pre-round direct Memory in {target}"
            delete_scope = "single existing direct Memory inside the checkpoint window"
        elif attempt == 2:
            delete_args = ("delete", f"{target}:dead0002")
            delete_target = f"{target}:dead0002"
            delete_scope = "qualified unavailable Memory after direct Clear"
        elif attempt == 4:
            delete_args = ("delete", "dead0004", "-c", target)
            delete_target = f"{target}:dead0004"
            delete_scope = "short-option unavailable Memory after direct Clear"
        else:
            delete_args = ("delete", "dead0001", "--context", target)
            delete_target = f"{target}:dead0001"
            delete_scope = "explicit unavailable Memory after direct Clear"
        add("delete", attempt, delete_args,
            entry=("UID plus --context", "qualified Context:UID", "existing UID plus --context", "UID plus short -c", "late existing UID plus --context")[attempt - 1],
            target=delete_target, scope=delete_scope,
            provenance=f"{state}; actual UID is captured before Checkpoint for existing-item rounds",
            consumer="exact item deletion and missing-selector boundary",
            expected="Delete only the exact selected scratch item, or fail without a second mutation.",
            recovery="The same-round Diff exposes the delta and Revert restores any deleted item.")

        diff_flags = ("--stat", "--raw", "--verbose", "--raw", "--stat")
        diff_args: Callable[[], tuple[str, ...]]
        if attempt == 2:
            diff_args = lambda a=attempt, t=target: ("diff", "--checkpoint", artifact("checkpoint", a), "--context", t, "--raw")
        elif attempt == 3:
            diff_args = lambda a=attempt, t=target: ("diff", artifact("checkpoint", a), "--context", t, "--verbose")
        elif attempt == 4:
            diff_args = lambda a=attempt, t=target: ("diff", "--context", t, "--checkpoint", artifact("checkpoint", a), "--raw")
        elif attempt == 5:
            diff_args = lambda a=attempt, t=target: ("diff", artifact("checkpoint", a), "--context", t, "--stat")
        else:
            diff_args = lambda a=attempt, t=target: ("diff", artifact("checkpoint", a), "--context", t, "--stat")
        add("diff", attempt, diff_args,
            entry=("checkpoint positional plus --stat", "--checkpoint option plus --raw", "checkpoint positional plus --verbose", "owner then --checkpoint plus --raw", "checkpoint positional plus late --stat")[attempt - 1],
            target=f"checkpoint {attempt} ↔ current {target}",
            scope=f"post-Clear/Delete exact delta rendered with {diff_flags[attempt - 1]}",
            provenance=f"{state}; UID comes from the immediately preceding counted Checkpoint receipt",
            consumer="pre-transformation destructive delta inspection",
            expected="Render the exact checkpoint difference noninteractively without changing state.")

        goals = (
            "Distill only disclosure-selection rules; preserve necessity, currency, third-party exclusion, and explicit approval boundaries.",
            "Distill only minimum-necessary redaction rules without selecting or transmitting personal facts.",
            "Distill candidate-review rules from personal evidence while marking every fact unapproved and potentially stale.",
            "Distill public transmission guidance into local review rules while preserving Grant provenance and no-send status.",
            "Distill only exact approval and delivery gates; do not infer recipient, purpose, channel, retention, or consent.",
        )
        distill_args = (
            "distill", "--from", source, "--to", target, "--goal", goals[attempt - 1],
            "--recursive" if attempt == 2 else "--direct", "--plain",
        )
        add("distill", attempt, distill_args,
            entry=("--from/--to direct", "--from/--to recursive", "personal Source to audit target", "granted Source to local target", "approval Source to audit target")[attempt - 1],
            target=f"{source} → {target}",
            scope=("recursive Source traversal" if attempt == 2 else "exact direct Source frame") + "; automatic local Add is inside checkpoint window",
            provenance=f"{state}; explicit Goal in argv forbids disclosure and unsupported acceptance",
            consumer="temporary derived disclosure-review Rules",
            expected="Add only source-grounded review Rules; do not mark any personal fact approved or sent.",
            recovery="Same-round Revert removes every temporary derived Rule from the scratch target.")

        elaborate_args = {
            1: ("elaborate", "--rule", "A disclosed item must be necessary, current, user-owned, and explicitly approved for the exact recipient and purpose.", "--to", target, "--number", "1", "--plain"),
            2: ("elaborate", "--from", source, "--to", target, "--as", "rules", "--number", "2", "--plain"),
            3: ("elaborate", "--goal", "Create only hypothetical review questions, never healthcare facts or approvals.", "--to", target, "--number", "2", "--plain"),
            4: ("elaborate", "--rule", "Public guidance may inform a local checklist but cannot prove a user's fact is current or approved.", "--rule", "No example may claim external transmission occurred.", "--to", target, "--number", "2", "--strict", "--plain"),
            5: ("elaborate", "--from", source, "--to", target, "--as", "goal", "--number", "1", "--strict", "--plain"),
        }[attempt]
        add("elaborate", attempt, elaborate_args,
            entry=("one inline Rule", "Context Source as rules", "one inline Goal", "two inline Rules with --strict", "Context Source as one goal with --strict")[attempt - 1],
            target=target,
            scope=("one proposed Case" if attempt in {1, 5} else "two proposed review Cases/Rules") + " in checkpointed scratch",
            provenance=f"{state}; argv carries hypothetical/no-transmission constraints",
            consumer="unsupported-generation safety test",
            expected="Generate only clearly hypothetical, source-grounded review material; never assert a personal healthcare fact or approval.",
            recovery="Any automatically added output is temporary evidence and is removed by same-round Revert.")

        resolve_args = {
            1: ("resolve", target, "--guidance", "Preserve explicit unapproved status and do not add personal facts.", "--no-create", "--plain"),
            2: ("resolve", "--context", target, "--guidance", "Remove only unsupported generated review text; preserve grounded constraints.", "--allow-delete", "--plain"),
            3: lambda t=target: ("resolve", "--context", t, "--memory", memory_uid(t)[:8], "--guidance", "Keep uncertainty and provenance explicit; do not broaden the selected statement.", "--no-create", "--plain"),
            4: lambda t=target: ("resolve", qualified(t), "--guidance", "Do not convert public guidance into user-specific factual acceptance.", "--no-create", "--plain"),
            5: ("resolve", target, "--guidance", "Retain the exact human approval gate; do not infer recipient, purpose, or consent.", "--allow-delete", "--plain"),
        }[attempt]
        add("resolve", attempt, resolve_args,
            entry=("Context positional with --no-create", "--context with --allow-delete", "--context plus --memory", "qualified Memory positional", "late Context with --allow-delete")[attempt - 1],
            target=target, scope="checkpointed temporary direct review frame",
            provenance=f"{state}; exact argv guidance denies factual or disclosure approval",
            consumer="repair-plan review gate",
            expected="Expose proposed repairs without applying an unreviewed semantic candidate.",
            recovery="If unexpected automatic mutation occurs, same-round Revert restores the target.")

        dedup_args = {
            1: ("dedup", target, "--direct"),
            2: ("dedup", target, "-d"),
            3: ("dedup", target),
            4: ("dedup", target, "--direct"),
            5: ("dedup", target, "-d"),
        }[attempt]
        add("dedup", attempt, dedup_args,
            entry=("positional plus --direct", "positional plus -d", "positional default-direct", "late local --direct", "late audit -d")[attempt - 1],
            target=target, scope=f"exact duplicate groups in round-{attempt} temporary direct frame",
            provenance=f"{state}; only deterministic equality is authorized inside recovery window",
            consumer="exact duplicate hygiene",
            expected="Remove only proven exact duplicates with complete survivor evidence.",
            recovery="Same-round Revert restores the pre-round target regardless of cleanup effects.")

        dedun_args = {
            1: ("dedun", target, "--direct", "--plain"),
            2: ("dedun", "--context", target, "-d", "--plain"),
            3: ("dedun", target, "-d", "--plain"),
            4: ("dedun", "-c", target, "--direct", "--plain"),
            5: ("dedun", target, "--direct", "--plain"),
        }[attempt]
        add("dedun", attempt, dedun_args,
            entry=("positional direct", "--context with -d", "positional with -d", "short -c plus --direct", "late positional --direct")[attempt - 1],
            target=target, scope=f"complete semantic redundancy analysis of round-{attempt} temporary direct frame",
            provenance=f"{state}; local semantic cleanup remains checkpoint-contained",
            consumer="semantic redundancy review",
            expected="Apply only complete evidence-linked redundancy groups and retain distinct safety boundaries.",
            recovery="Same-round Revert restores the exact pre-round frame.")

        forget_instructions = (
            "Remove only temporary items that imply disclosure approval; preserve explicit decision gates and exclusions.",
            "Remove generated examples that invent user facts; preserve minimum-necessary and redaction rules.",
            "Remove only personal statements that are stale, third-party, or unsupported as current; preserve explicit uncertainty.",
            "Remove any local output that claims public guidance proves a user fact or that transmission occurred.",
            "Remove any temporary item that infers recipient, purpose, consent, channel, or retention; preserve the human decision gate.",
        )
        forget_args = ("forget", forget_instructions[attempt - 1], "--context", target)
        add("forget", attempt, forget_args,
            entry=f"round-{attempt} process-local INSTRUCTION plus --context",
            target=target, scope="whole checkpointed direct Source frame in one provider turn",
            provenance=f"{state}; criterion text is argv input, never a durable fabricated Memory",
            consumer="selective curation safety trial",
            expected="Return exactly one keep/transform/drop disposition per Source Memory and preserve the human decision boundary.",
            recovery="Same-round Revert restores all pre-round content after the curation trial.")

        ground_requests = (
            "Review which healthcare-disclosure facts still require human decisions; do not create a Ground or transmit anything.",
            "Prepare a minimization checklist without creating a Ground, selecting personal facts, or approving disclosure.",
            "Identify stale and third-party evidence boundaries without creating a Ground or accepting facts as current.",
            "Explain how public guidance informs review without creating a Ground or claiming transmission.",
            "Summarize the remaining recipient, purpose, item, channel, retention, and consent decisions without creating a Ground.",
        )
        ground_args = ("ground", "--request", ground_requests[attempt - 1])
        add("ground", attempt, ground_args,
            entry=f"explicit unsaved --request wording variant {attempt}",
            target="process-local blank unsaved Ground frame",
            scope=f"one bounded provider turn for round-{attempt}; no durable Ground name or approval key",
            provenance=f"{state}; natural-language request explicitly forbids creation and disclosure",
            consumer="agent-mediated planning boundary",
            expected="Print the stable unsaved proposal frame and create no Ground without exact human approval.")

        impact_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: ("impact", "atomize", PURPOSE),
            2: ("impact", "--from", source, "--to", target, "--direct"),
            3: ("impact", "update", source, target, "--direct"),
            4: lambda: ("impact", "atomize", "--context", PUBLIC_GUIDANCE, "--memory", memory_uid(PUBLIC_GUIDANCE, ("stale", "current"))[:8], "--all"),
            5: lambda: ("impact", "meld", "--session", artifact("meld", 5)),
        }
        add("impact", attempt, impact_args[attempt],
            entry=("named Atomize Context preview", "root directional Update preview", "named Update positional preview", "named focused granted Atomize preview", "saved Meld session preview")[attempt - 1],
            target=(PURPOSE, f"{source} → {target}", f"{source} → {target}", PUBLIC_GUIDANCE, "round-5 saved Meld artifact")[attempt - 1],
            scope="read-only projected effects with operation-specific actual argv",
            provenance=f"{state}; live Source/target or saved session is explicitly named",
            consumer="pre-Apply effect inspection",
            expected="Preview effects without applying them; unavailable sessions must fail atomically.")

        meld_result = f"task-3/local/transform-meld-r{attempt}"
        meld_args = {
            1: ("meld", source, target, meld_result, "--direct"),
            2: ("meld", "--memory", "Minimum necessary does not establish currentness or approval.", "--into", target, "--direct"),
            3: ("meld", "--from", source, "--to", target, "--direct"),
            4: ("meld", source, target, "--direct"),
            5: ("meld", source, target, "--to", meld_result, "--direct"),
        }[attempt]
        add("meld", attempt, meld_args,
            entry=("three positional symmetric plan", "inline --memory directional plan", "--from/--to directional plan", "two positional directional plan", "two positionals plus --to symmetric Result")[attempt - 1],
            target=(f"{source} + {target} → {meld_result}" if attempt in {1, 5} else f"{source} → {target}"),
            scope="complete direct peer/baseline frames; saved review only",
            provenance=f"{state}; all endpoints are explicit and Result is lane-local when supplied",
            consumer="relation/conflict review session",
            expected="Save a source-bound Meld review and stop before --accept or unresolved meaning choices.")

        merge_args = {
            1: ("merge", source, target, "--direct", "--keep-target-all"),
            2: ("merge", "--from", source, "--into", target, "-d", "--keep-target-all"),
            3: ("merge", source, "--to", target, "--direct", "--take-source-all"),
            4: ("merge", "--from", source, "--to", target, "-d", "--keep-target-all"),
            5: ("merge", source, target, "-d", "--take-source-all"),
        }[attempt]
        add("merge", attempt, merge_args,
            entry=("two positionals keep Target", "--from/--into keep Target", "Source positional plus --to take Source", "--from/--to granted Source keep Target", "two positionals take Source")[attempt - 1],
            target=f"{source} → checkpointed {target}",
            scope="direct structural merge only; no descendant or external target mutation",
            provenance=f"{state}; explicit conflict policy and same-round target checkpoint",
            consumer="temporary structural integration trial",
            expected="Merge atomically into local scratch with explicit effects; never export personal Memories.",
            recovery="Same-round Revert restores the exact pre-round target after structural integration.")

        rationale_args = {
            1: lambda: ("rationale", qualified(source)),
            2: lambda: ("rationale", qualified(source), "--verbose", "--limit", "40", "--unit", "words"),
            3: lambda: ("rationale", "--context", source, "--limit", "160", "--unit", "characters", "--json"),
            4: lambda: ("rationale", qualified(source, ("stale", "current")), "-v", "-n", "240", "-u", "bytes"),
            5: lambda: ("rationale", qualified(source), "--json", "--limit", "60"),
        }[attempt]
        add("rationale", attempt, rationale_args,
            entry=("qualified Memory default limit", "qualified Memory verbose word limit", "Context option JSON character limit", "granted Memory short flags byte limit", "qualified Memory JSON late limit")[attempt - 1],
            target=source,
            scope=("one exact Memory provenance" if attempt != 3 else "Context selection/provenance boundary") + f"; round-{attempt} limit grammar",
            provenance=f"{state}; durable source and actual output-limit argv",
            consumer="why/provenance inspection",
            expected="Explain recorded lineage and limitations without claiming that provenance proves healthcare relevance or approval.")

        revert_args: dict[int, Callable[[], tuple[str, ...]]] = {
            1: lambda a=attempt, t=target: ("revert", artifact("checkpoint", a), "--context", t, "--keep"),
            2: lambda a=attempt, t=target: ("revert", artifact("checkpoint", a), "-c", t, "-k"),
            3: lambda a=attempt, t=target: ("revert", artifact("checkpoint", a), "--context", t),
            4: lambda a=attempt, t=target: ("revert", "--context", t, artifact("checkpoint", a), "--keep"),
            5: lambda a=attempt, t=target: ("revert", "-c", t, artifact("checkpoint", a)),
        }
        add("revert", attempt, revert_args[attempt],
            entry=("UID positional plus --context --keep", "UID plus short -c/-k", "UID plus owner with default keep", "owner option before UID plus --keep", "short owner option before UID default keep")[attempt - 1],
            target=target,
            scope="restore the exact same-round direct checkpoint while retaining recovery history",
            provenance=f"{state}; checkpoint UID is consumed from counted Checkpoint#{attempt}",
            consumer="mandatory recovery before post-trial evidence operations",
            expected="Restore the target's pre-round content exactly and leave every Source unchanged.",
            recovery="This command is the mandatory recovery action; later Review/Trace/Translate/Update verify continued availability.")

        review_args: dict[int, Callable[[], tuple[str, ...]]] = {
            1: lambda a=attempt: ("review", "audit", "--session", artifact("audit", a), "--snapshot"),
            2: lambda a=attempt: ("review", "audit", "--session", artifact("audit", a)[:8], "--snapshot"),
            3: lambda s=LOCAL: ("review", "audit", "--context", s, "--snapshot"),
            4: lambda a=attempt, s=PUBLIC_GUIDANCE: ("review", "audit", "--session", artifact("audit", a), "--context", s, "--snapshot"),
            5: lambda a=attempt: ("review", "audit", "--snapshot", "--session", artifact("audit", a)),
        }
        add("review", attempt, review_args[attempt],
            entry=("full saved Audit session", "Audit session prefix", "latest Audit by Context", "session plus granted Context", "snapshot before session option")[attempt - 1],
            target=(f"Audit session from round {attempt}" if attempt != 3 else "latest local Audit artifact"),
            scope="provider-free complete review snapshot after scratch recovery",
            provenance=f"{state}; saved artifact comes from counted Audit#{attempt}",
            consumer="post-recovery evidence verification",
            expected="Reopen exact saved evidence without rerunning inference or mutating Context content.")

        sever_result = f"task-3/local/transform-sever-r{attempt}"
        sever_source = PERSONAL_2024 if attempt in {1, 3, 4} else PERSONAL_2026
        sever_criteria = rules
        sever_args = {
            1: ("sever", sever_source, sever_criteria, sever_result, "--direct"),
            2: ("sever", "--source", sever_source, "--criteria", sever_criteria, "--save-as", sever_result, "-d"),
            3: ("sever", "--from", sever_source, "--against", sever_criteria, "--to", sever_result, "--source-root-only", "--criteria-root-only"),
            4: ("sever", sever_source, sever_criteria, "--to", sever_result, "--direct"),
            5: ("sever", "--source", sever_source, "--against", sever_criteria, "--save-as", sever_result, "--direct"),
        }[attempt]
        add("sever", attempt, sever_args,
            entry=("three positionals direct", "--source/--criteria/--save-as", "--from/--against/--to root-only axes", "two positionals plus --to", "--source/--against/--save-as")[attempt - 1],
            target=f"{sever_source} × {sever_criteria} → fresh {sever_result}",
            scope="whole direct Source and Criteria frames; saved proposal only",
            provenance=f"{state}; post-Revert Sources and criteria are explicit in argv",
            consumer="personal-Memory inclusion/exclusion review session",
            expected="Leave Source unchanged, save a proposal, and stop before --accept or unresolved meaning/disclosure choices.")

        trace_args = {
            1: lambda: ("trace", qualified(source), "--limit", "3"),
            2: lambda: ("trace", memory_uid(source)[:8], "--context", source, "--limit", "4", "--verbose"),
            3: lambda: ("trace", qualified(source), "--limit", "5", "--json"),
            4: lambda: ("trace", qualified(source, ("stale", "current")), "--limit", "6", "--plain"),
            5: lambda: ("trace", qualified(source), "--all", "--verbose"),
        }[attempt]
        add("trace", attempt, trace_args,
            entry=("qualified Memory bounded trace", "bare UID plus --context verbose", "qualified Memory JSON", "granted Memory plain", "qualified Memory --all verbose")[attempt - 1],
            target=source,
            scope=f"exact retained lineage route with round-{attempt} output/depth modifier",
            provenance=f"{state}; durable post-Revert Source UID",
            consumer="lineage and ownership verification",
            expected="Render typed provenance without confusing copied content, Grant ownership, or semantic output with approval.")

        translate_args = {
            1: lambda: ("translate", qualified(source), "--to", LANGUAGES[0]),
            2: lambda: ("translate", "--to", LANGUAGES[1], qualified(source)),
            3: lambda: ("translate", qualified(source), "-t", LANGUAGES[2], "--refresh"),
            4: lambda: ("translate", "-t", LANGUAGES[3], qualified(source, ("stale", "current"))),
            5: lambda: ("translate", qualified(source), "--to", LANGUAGES[4], "--refresh"),
        }[attempt]
        add("translate", attempt, translate_args,
            entry=("selector then --to", "--to before selector", "selector with -t and --refresh", "-t before granted selector", "late selector --to --refresh")[attempt - 1],
            target=f"{source} exact Memory → {LANGUAGES[attempt - 1]} view",
            scope="one read-only provider translation view; no --save-as, --in-place, or --export",
            provenance=f"{state}; exact post-Revert Source digest and language argv",
            consumer="cross-language understanding without materialization",
            expected="Return a source-bound translation view and leave every Context Memory unchanged.")

        update_args = {
            1: ("update", source, target, "--direct"),
            2: ("update", "--from", source, "--to", target, "-d", "--replace-stage"),
            3: lambda: ("update", source, target, "--source-memory", memory_uid(source, ("medication", "back discomfort"))[:8], "--direct", "--replace-stage"),
            4: ("update", "--memory", "Public guidance can inform review but cannot prove a user fact or approval.", "--to", target, "--direct", "--replace-stage"),
            5: ("update", source, target, "--goal", "Preserve explicit recipient, purpose, item, channel, retention, and consent gates; do not apply unsupported facts.", "--direct", "--replace-stage"),
        }[attempt]
        add("update", attempt, update_args,
            entry=("two positional endpoints", "--from/--to with replace-stage", "positional endpoints plus focused Source Memory", "process-local --memory plus --to", "positional endpoints plus explicit Goal")[attempt - 1],
            target=f"{source if attempt != 4 else 'process-local Rule'} → {target}",
            scope="direct Source/Target review plan; no accept/apply route exists in this invocation",
            provenance=f"{state}; post-Revert target and explicit no-approval Goal/guidance",
            consumer="directional update review session",
            expected="Stage or report typed changes but stop before unsupported meaning acceptance or disclosure.")

    return result


def new_ledger(initial_digest: str, core_digest: str) -> dict:
    return {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": "task-3",
        "phase": "transform",
        "status": "running",
        "world_goal": (
            "Decide which personal Memories a healthcare agent should receive, exclude the rest, "
            "and transfer only explicitly selected information."
        ),
        "contract": {"operations": 24, "attempts_per_operation": 5, "attempts": 120},
        "execution_identity": {
            "code_snapshot_sha256": CODE_SHA256,
            "catalog_sha256": CATALOG_SHA256,
            "profile_uid": PROFILE_UID,
            "store_root": str(STORE),
            "provider_policy_sha256": PROVIDER_SHA256,
            "launcher": f"python {RUNNER} task-3 ...",
        },
        "starting_boundary": {
            "cumulative_from_core": True,
            "core_final_digest": core_digest,
            "transform_initial_digest": initial_digest,
            "matches_core_final_digest": core_digest == initial_digest,
            "no_reset": True,
            "recovery_policy": (
                "Every round creates an exact direct checkpoint before Clear/Delete and restores "
                "that target through Revert before Review/Sever/Trace/Translate/Update."
            ),
        },
        "digest_semantics": "SHA-256 over lane-local task-3 Context subtree context.json files, matching CORE.",
        "safety_boundary": {
            "external_disclosure": "No Share, export, clipboard, external Target, or accepted Meld/Sever/Update result.",
            "healthcare_facts": "No unsupported factual acceptance; semantic outputs remain local and checkpoint-recovered.",
            "decision_gate": "Recipient, purpose, exact items, channel, retention, currency, necessity, and consent remain human decisions.",
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
        "operations": {operation: {"attempts": []} for operation in OPERATIONS},
    }


def save(ledger: dict) -> None:
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")


def restore_artifacts(ledger: dict) -> None:
    records = sorted(
        (record for payload in ledger["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    for record in records:
        raw = AUDIT_ROOT / record["raw_output"]
        if raw.exists():
            capture_artifact(record["operation"], record["attempt"], raw.read_text())


def main() -> None:
    WORLD_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    core = json.loads(CORE_LEDGER.read_text())
    core_records = sorted(
        (record for payload in core["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    core_digest = core_records[-1]["post_target_digest"]["sha256"]
    initial_digest = task_digest()
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else new_ledger(initial_digest, core_digest)
    if not ledger["starting_boundary"]["matches_core_final_digest"]:
        raise RuntimeError("Transform initial Store does not match CORE final digest")
    restore_artifacts(ledger)
    completed = {
        record["sequence"]
        for payload in ledger["operations"].values()
        for record in payload["attempts"]
    }
    prior_records = sorted(
        (record for payload in ledger["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    prior_post = prior_records[-1]["post_target_digest"]["sha256"] if prior_records else core_digest
    all_specs = specs()
    if len(all_specs) != 120 or tuple(dict.fromkeys(spec.operation for spec in all_specs)) != OPERATIONS:
        raise RuntimeError("Transform specification does not match the 24×5 catalog contract")

    for sequence, spec in enumerate(all_specs, 1):
        if sequence in completed:
            continue
        # Existing-item Delete routes consume a UID captured before the round's
        # checkpoint/clear sequence, so the harness itself never discovers via
        # an uncounted mem invocation.
        if spec.operation == "atomize":
            round_target = TARGETS[spec.attempt - 1]
            uids = ordinary_uids(round_target)
            ROUND_TARGET_UIDS[spec.attempt] = uids[0] if uids else "deadbeef"

        args = spec.args() if callable(spec.args) else spec.args
        argv = ["python", str(RUNNER), "task-3", *args]
        command = shlex.join(argv)
        pre = task_digest()
        started = time.monotonic()
        timed_out = False
        try:
            completed_run = subprocess.run(
                argv,
                cwd=REPO,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=360,
                check=False,
            )
            exit_code = completed_run.returncode
            output = completed_run.stdout
        except subprocess.TimeoutExpired as error:
            timed_out = True
            exit_code = 124
            partial = error.stdout or ""
            output = partial if isinstance(partial, str) else partial.decode("utf-8", "replace")
            output += "\nAUDIT HARNESS TIMEOUT after 360 seconds; child process terminated.\n"
        elapsed = time.monotonic() - started
        post = task_digest()
        capture_artifact(spec.operation, spec.attempt, output)
        raw_path = RAW_DIR / f"{sequence:03d}-{spec.operation}-a{spec.attempt}.txt"
        raw_path.write_text(f"COMMAND\n{command}\n\nEXIT\n{exit_code}\n\nOUTPUT\n{output}")
        record = {
            "operation": spec.operation,
            "attempt": spec.attempt,
            "sequence": sequence,
            "command": command,
            "exit": exit_code,
            "starting_state": (
                f"Cumulative no-reset Store at transform sequence {sequence}; pre-command "
                f"task-3 digest {pre}; immediately follows prior post digest {prior_post}."
            ),
            "entry_route": spec.entry_route,
            "target_route": spec.target_route,
            "scope": spec.scope + f"; actual argv `{shlex.join(args)}`",
            "input_provenance": spec.input_provenance,
            "consumer": spec.consumer,
            "expected": spec.expected,
            "actual": actual_summary(output, exit_code),
            "defect_ids": [],
            "cost": {
                "wall_seconds": round(elapsed, 3),
                "output_bytes": len(output.encode()),
                "timed_out": timed_out,
                "terminal_screens": None,
                "tui": False,
            },
            "pre_target_digest": {"scope": "lane-local task-3 Context subtree", "sha256": pre},
            "post_target_digest": {"scope": "lane-local task-3 Context subtree", "sha256": post},
            "recovery_evidence": spec.recovery_evidence,
            "state_continuity": {
                "same_as_previous_post": prior_post == pre,
                "task_tree_changed": pre != post,
                "one_cumulative_store": True,
            },
            "raw_output": str(raw_path.relative_to(AUDIT_ROOT)),
        }
        ledger["operations"][spec.operation]["attempts"].append(record)
        ledger["last_completed_sequence"] = sequence
        ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
        save(ledger)
        prior_post = post
        print(
            f"[{sequence:03d}/120] {spec.operation}#{spec.attempt} "
            f"exit={exit_code} {elapsed:.2f}s changed={pre != post}",
            flush=True,
        )

    records = [record for payload in ledger["operations"].values() for record in payload["attempts"]]
    ledger["status"] = "executed_pending_issue_review"
    ledger["attempt_count"] = len(records)
    ledger["completed_at"] = datetime.now(timezone.utc).isoformat()
    ledger["summary"] = {
        "attempts": len(records),
        "successful_exits": sum(record["exit"] == 0 for record in records),
        "nonzero_exits": sum(record["exit"] != 0 for record in records),
        "task_tree_mutations": sum(record["state_continuity"]["task_tree_changed"] for record in records),
        "continuity_breaks": sum(not record["state_continuity"]["same_as_previous_post"] for record in records),
        "wall_seconds": round(sum(record["cost"]["wall_seconds"] for record in records), 3),
    }
    save(ledger)


if __name__ == "__main__":
    main()
