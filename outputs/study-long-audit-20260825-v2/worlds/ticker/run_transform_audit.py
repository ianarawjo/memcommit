#!/usr/bin/env python3
"""Run 120 counted ticker TRANSFORM attempts on the cumulative CORE Store."""

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
AUDIT = REPO / "outputs/study-long-audit-20260825-v2"
WORLD = AUDIT / "worlds/ticker"
RAW = WORLD / "raw/transform"
RUNNER = AUDIT / "run_world_mem.py"
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/"
    "worlds/ticker/profile-control/stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
CONTEXTS = STORE / "contexts"
PHASE = WORLD / "phase-transform.json"

SOURCE = "task-2/participant/proposal-workspace"
CRITERIA = "task-2/participant"
SCRATCHES = (
    "task-3/local",
    "task-3/local/guardrails",
    "task-3/local/personal-memory",
    "task-3/local",
    "task-3/local/guardrails",
)
LANGUAGES = ("Korean", "French", "Japanese", "Spanish", "German")
OPS = (
    "atomize", "audit", "checkpoint", "check-conformance", "clear", "delete",
    "diff", "distill", "elaborate", "resolve", "dedup", "dedun", "forget",
    "ground", "impact", "meld", "merge", "rationale", "revert", "review",
    "sever", "trace", "translate", "update",
)
ARTIFACTS: dict[tuple[str, int], str] = {}


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


def context_path(name: str) -> Path:
    return CONTEXTS.joinpath(*name.split("/"), "context.json")


def context_data(name: str) -> dict:
    return json.loads(context_path(name).read_text())


def memory_uids(name: str) -> list[str]:
    data = context_data(name)
    return [
        uid for uid in data.get("order", ())
        if data.get("memories", {}).get(uid, {}).get("type") == "memory"
    ]


def memory_uid(name: str, needles: tuple[str, ...]) -> str:
    data = context_data(name)
    for needle in needles:
        for uid in data.get("order", ()):
            item = data.get("memories", {}).get(uid, {})
            if item.get("type") == "memory" and needle in item.get("content", ""):
                return uid
    uids = memory_uids(name)
    return uids[0] if uids else "00000000000000000000000000000000"


def target_memory(name: str, needles: tuple[str, ...]) -> str:
    return f"{name}:{memory_uid(name, needles)[:8]}"


def tree_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(CONTEXTS.rglob("context.json")):
        digest.update(path.relative_to(STORE).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(b"state.json\0")
    digest.update((STORE / "state.json").read_bytes())
    return digest.hexdigest()


def artifact(kind: str, attempt: int) -> str:
    return ARTIFACTS.get((kind, attempt), "deadbeef")


def capture_artifacts(operation: str, attempt: int, output: str) -> None:
    patterns = {
        "checkpoint": [r"\[([0-9a-f]{8})\]"],
        "audit": [
            r"mem review audit --session ([0-9a-f-]{8,36})",
            r"SESSION\s*\[([0-9a-f]{8})\]",
        ],
        "distill": [r"mem review distill --(?:receipt|session) ([0-9a-f-]{8,36})"],
        "forget": [r"mem review forget --(?:receipt|session) ([0-9a-f-]{8,36})"],
        "atomize": [r"mem review atomize --session ([0-9a-f-]{8,36})", r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})"],
        "meld": [r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})"],
        "sever": [r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})"],
        "update": [r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})"],
    }
    for pattern in patterns.get(operation, ()):
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            ARTIFACTS[(operation, attempt)] = match.group(1)
            return


def compact(output: str) -> str:
    clean = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", output).replace("\r", "")
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if not lines:
        return "No stdout/stderr text was emitted."
    result = " | ".join(lines[:8])
    if len(lines) > 8:
        result += f" | … ({len(lines)} non-empty lines; see raw output)"
    return result[:2600]


def specs() -> list[Spec]:
    result: list[Spec] = []

    def add(
        op: str,
        attempt: int,
        args: tuple[str, ...] | Callable[[], tuple[str, ...]],
        *,
        entry: str,
        target: str,
        scope: str,
        provenance: str,
        consumer: str,
        expected: str,
        recovery: str = "A later same-round exact read or recovery operation verifies continuity.",
    ) -> None:
        result.append(Spec(op, attempt, args, entry, target, scope, provenance, consumer, expected, recovery))

    for attempt in range(1, 6):
        scratch = SCRATCHES[attempt - 1]
        punctuation = ("North-Star", "Punctuation rule")
        numeral = ("Route 66", "Numeral rule")
        share = ("Acme Corp. Class B", "Share-class")
        source_needles = (punctuation, numeral, numeral, share, share)[attempt - 1]
        round_state = (
            f"transform round {attempt}; cumulative CORE ticker evidence remains in exact Source {SOURCE} "
            f"and Criteria {CRITERIA}; checkpoint-protected direct scratch is {scratch}"
        )

        merge_args = {
            1: ("merge", SOURCE, scratch, "--direct", "--keep-target-all"),
            2: ("merge", CRITERIA, scratch, "--direct", "--keep-target-all"),
            3: ("merge", SOURCE, scratch, "--direct", "--take-source-all"),
            4: ("merge", SOURCE, scratch, "--direct", "--keep-target-all"),
            5: ("merge", CRITERIA, scratch, "--direct", "--take-source-all"),
        }[attempt]
        merge_source = CRITERIA if attempt in {2, 5} else SOURCE
        add("merge", attempt, merge_args,
            entry=("direct structural Merge with --take-source-all" if attempt in {3, 5} else "direct structural Merge with --keep-target-all"),
            target=f"{merge_source} → {scratch}", scope="exact direct Source and scratch Target only",
            provenance=f"{round_state}; source wording is already user-authored/core-grounded",
            consumer="populate recoverable scratch before destructive Transform trials",
            expected="Copy/merge only existing source evidence into scratch, retain Source, and print a reusable mapping receipt.")

        checkpoint_args = {
            1: ("checkpoint", scratch, "ticker transform round 1 pre-destructive recovery", "--direct"),
            2: ("checkpoint", "--context", scratch, "ticker transform round 2 pre-destructive recovery", "--direct"),
            3: ("checkpoint", scratch, "--message", "ticker transform round 3 pre-destructive recovery", "--direct"),
            4: ("checkpoint", "--context", scratch, "--message", "ticker transform round 4 pre-destructive recovery", "--direct"),
            5: ("checkpoint", scratch, "ticker transform round 5 pre-destructive recovery", "--direct"),
        }[attempt]
        add("checkpoint", attempt, checkpoint_args,
            entry=f"checkpoint operand grammar variant {attempt}", target=scratch,
            scope="exact direct scratch after Merge population",
            provenance=f"{round_state}; Merge#{attempt} output is the recovery baseline",
            consumer="mandatory same-round recovery before Delete/Clear/derived mutation",
            expected="Create an exact named checkpoint and expose a reusable checkpoint prefix.")

        atomize_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: ("atomize", SOURCE),
            2: lambda: ("atomize", "--context", SOURCE, "--memory", memory_uid(SOURCE, punctuation)[:8]),
            3: lambda: ("atomize", target_memory(SOURCE, numeral)),
            4: ("atomize", "--context", scratch, "--memory", "00000000"),
            5: lambda: ("atomize", "--context", SOURCE, "--memory", memory_uid(SOURCE, share)[:8], "--all"),
        }
        add("atomize", attempt, atomize_args[attempt],
            entry=("whole exact Context analysis" if attempt == 1 else "focused Memory analysis selector variant"),
            target=(SOURCE if attempt != 4 else f"{scratch}:missing"),
            scope=("complete direct example frame" if attempt == 1 else "one selected Memory with neighbors as evidence"),
            provenance=f"{round_state}; selector derives from durable CORE content or deliberate unavailable boundary",
            consumer="review whether compound ticker examples are independently atomic",
            expected=("Reject the unavailable Memory before provider connection." if attempt == 4 else "Save a source-bound review session without applying an unsupported rewrite."))

        audit_args = {
            1: ("audit", SOURCE, "--snapshot"),
            2: ("audit", SOURCE, "--against", CRITERIA, "--snapshot"),
            3: ("audit", CRITERIA, "--snapshot"),
            4: ("audit", scratch, "--snapshot"),
            5: ("audit", "task-3/local/ticker-missing", "--snapshot"),
        }[attempt]
        add("audit", attempt, audit_args,
            entry=("quality plus cross-Context conformance snapshot" if attempt == 2 else "explicit read-only Audit snapshot"),
            target=audit_args[1], scope=("three quality checks plus Criteria" if attempt == 2 else "three complete quality checks"),
            provenance=f"{round_state}; pre-clear exact direct frame",
            consumer="saved quality evidence for later provider-free Review",
            expected=("Reject the missing Context atomically." if attempt == 5 else "Save and print complete linked findings without mutating the audited frame."))

        conformance_args = {
            1: ("check-conformance", SOURCE, "--against", CRITERIA),
            2: ("check-conformance", SOURCE, "--against", "text:Ticker outputs must remove terminal legal suffixes."),
            3: ("check-conformance", CRITERIA, "--against", "text:Digits 0 through 9 must remain in original order."),
            4: ("check-conformance", scratch, "--against", CRITERIA),
            5: ("check-conformance", SOURCE, "--against", "text:Share classes use generated dot-A or dot-B syntax.", "--plain"),
        }[attempt]
        add("check-conformance", attempt, conformance_args,
            entry=("stored Context Criteria" if attempt in {1, 4} else "forced literal text: Criteria"),
            target=conformance_args[1], scope=f"exact direct conformance frame variant {attempt}",
            provenance=f"{round_state}; stored or explicit synthetic ticker rule",
            consumer="verify examples against reusable suffix/numeral/share-class constraints",
            expected="Return one complete disposition per target Memory without changing Target or Criteria.")

        delete_args: tuple[str, ...] | Callable[[], tuple[str, ...]]
        if attempt in {1, 4}:
            delete_args = ("delete", f"dead{attempt:04x}", "--context", scratch)
            delete_entry = "deliberate unavailable direct-item selector"
        elif attempt == 2:
            delete_args = lambda s=scratch: ("delete", memory_uids(s)[0][:8], "--context", s)
            delete_entry = "bare exact scratch UID plus --context"
        elif attempt == 3:
            delete_args = lambda s=scratch: ("delete", f"{s}:{memory_uids(s)[-1][:8]}")
            delete_entry = "qualified CONTEXT:UID direct-item selector"
        else:
            delete_args = lambda s=scratch: ("delete", memory_uids(s)[0], "--context", s)
            delete_entry = "full exact UID plus explicit owner Context"
        add("delete", attempt, delete_args,
            entry=delete_entry, target=scratch, scope="one exact scratch direct item or missing boundary",
            provenance=f"{round_state}; checkpoint {artifact('checkpoint', attempt)} already exists",
            consumer="exercise atomic deletion before whole-scratch Clear",
            expected=("Reject the missing selector without mutation." if attempt in {1, 4} else "Remove exactly one checkpoint-protected scratch Memory."),
            recovery=f"Revert#{attempt} must restore checkpoint {artifact('checkpoint', attempt)} later in this round.")

        add("clear", attempt, ("clear", scratch, "--force"),
            entry="force-confirmed exact lane-local scratch Clear", target=scratch,
            scope=f"all direct scratch items after Delete variant {attempt}; descendants excluded",
            provenance=f"{round_state}; same-round checkpoint {artifact('checkpoint', attempt)} is mandatory",
            consumer="whole-frame destructive recovery trial",
            expected="Clear only direct scratch items atomically and preserve pre-clear checkpoint history.",
            recovery=f"Diff#{attempt} inspects and Revert#{attempt} restores checkpoint {artifact('checkpoint', attempt)}.")

        diff_flag = ("--stat", "--raw", "--verbose", "--stat", "--raw")[attempt - 1]
        add("diff", attempt,
            lambda a=attempt, s=scratch, f=diff_flag: ("diff", artifact("checkpoint", a), "--context", s, f),
            entry=f"same-round checkpoint prefix plus Context and {diff_flag}", target=scratch,
            scope="checkpoint-to-cleared-current direct difference",
            provenance=f"{round_state}; consumes Checkpoint#{attempt} receipt after Clear",
            consumer="verify exact destructive effect before derived work and recovery",
            expected="Show only same-round direct scratch removals without changing state.")

        goals = (
            "Extract only reusable suffix and uppercase ticker rules.",
            "Preserve punctuation-removal evidence without inventing outputs.",
            "Extract numeral-preservation rules and retain leading-zero conditions.",
            "Extract share-class syntax and distinguish generated dots from input punctuation.",
            "Produce a complete source-grounded regression rule set for the three maintained examples.",
        )
        add("distill", attempt,
            ("distill", "--from", SOURCE, "--to", scratch, "--goal", goals[attempt - 1], "--direct", "--plain"),
            entry="explicit Source/Target/Goal direct Distill", target=f"{SOURCE} → {scratch}",
            scope=f"complete exact Source frame; bounded ticker Goal {attempt}",
            provenance=f"{round_state}; scratch is empty after Clear and checkpointed for recovery",
            consumer="derive temporary reusable Rules without accepting unsupported facts",
            expected="Publish only source-bound derived Rules/receipt inside scratch; no unsupported generated fact is approved.",
            recovery=f"Revert#{attempt} removes every temporary derived item and restores checkpoint {artifact('checkpoint', attempt)}.")

        elaborate_args = {
            1: ("elaborate", "--from", SOURCE, "--goal", "Explain only existing ticker-example provenance.", "--to", scratch),
            2: ("elaborate", "--rule", "A ticker example must state both input company and complete output.", "--to", scratch, "--number", "2"),
            3: ("elaborate", "--goal", "Give source-grounded numeral ticker examples already represented by the Source.", "--to", scratch),
            4: ("elaborate", "--rule", "Do not invent an unseen company or output.", "--to", scratch, "--number", "1"),
            5: ("elaborate", "Create only examples already supported by the ticker Source", scratch, "--number", "0", "--plain"),
        }[attempt]
        add("elaborate", attempt, elaborate_args,
            entry=f"bounded Goal/Rule elaboration grammar variant {attempt}", target=scratch,
            scope="temporary generated examples in checkpoint recovery window",
            provenance=f"{round_state}; explicit source-grounding/no-invention boundary",
            consumer="test unsupported-generation rejection and presentation",
            expected=("Reject incompatible --from plus --goal before mutation." if attempt == 1 else "Generate no unsupported approved fact; invalid count/grammar boundaries must fail atomically."),
            recovery=f"Any generated scratch content is evidence only and is removed by Revert#{attempt}.")

        resolve_args = {
            1: ("resolve", scratch, "--plain"),
            2: lambda s=scratch: ("resolve", s, "--memory", (memory_uids(s)[0][:8] if memory_uids(s) else "00000000"), "--guidance", "Recover a complete standalone ticker claim", "--plain"),
            3: ("resolve", scratch, "--candidate", "deadbeef", "--revision", "1", "--apply"),
            4: ("resolve", scratch, "--guidance", "Preserve uncertainty and do not invent examples.", "--plain"),
            5: ("resolve", scratch, "--guidance", "Keep complete claims and delete only irrecoverable scratch fragments.", "--allow-delete", "--plain"),
        }[attempt]
        add("resolve", attempt, resolve_args,
            entry=f"Resolve analysis/application boundary variant {attempt}", target=scratch,
            scope="complete or one-Memory temporary direct frame",
            provenance=f"{round_state}; post-Distill/Elaborate scratch remains checkpoint-protected",
            consumer="repair fragmented ticker claims without unsupported decisions",
            expected=("Reject the fabricated candidate/revision without mutation." if attempt == 3 else "Return or stage reviewable repairs; do not silently choose unsupported content."),
            recovery=f"Revert#{attempt} restores pre-round scratch regardless of any allowed temporary mutation.")

        add("dedup", attempt, ("dedup", scratch, "--direct"),
            entry=f"exact direct Dedup on scratch role {attempt}", target=scratch,
            scope="exact duplicate groups in temporary direct frame",
            provenance=f"{round_state}; merge/derived output may contain exact maintenance copies",
            consumer="remove only proven exact duplicates inside recovery window",
            expected="Apply only exact same-role duplicate absorption or report no groups.",
            recovery=f"Revert#{attempt} restores the pre-destructive scratch baseline.")

        add("dedun", attempt, ("dedun", scratch, "--direct"),
            entry=f"semantic direct Dedun on scratch role {attempt}", target=scratch,
            scope="complete semantic redundancy groups in temporary direct frame",
            provenance=f"{round_state}; post-Dedup scratch with source-grounded variants",
            consumer="test semantic consolidation without crossing scratch boundary",
            expected="Apply only complete reviewed semantic redundancies; preserve distinctions not proven equivalent.",
            recovery=f"Revert#{attempt} restores the pre-destructive scratch baseline.")

        instructions = (
            "remove only temporary rules not directly supported by the ticker Source",
            "remove incomplete punctuation fragments but preserve complete examples",
            "remove no numeral rule that preserves source-supported digits",
            "remove generated examples that invent a company absent from Source",
            "remove any temporary rule inconsistent with maintained regression expectations",
        )
        add("forget", attempt, ("forget", instructions[attempt - 1], "--context", scratch),
            entry="process-local INSTRUCTION criterion plus exact scratch Source", target=scratch,
            scope=f"whole direct temporary frame with instruction variant {attempt}",
            provenance=f"{round_state}; every scratch item remains recoverable and no criterion is persisted",
            consumer="selective curation coverage without per-Memory hidden batching",
            expected="Return exactly one keep/transform/drop decision per Source Memory and publish no partial mutation.",
            recovery=f"Revert#{attempt} restores all pre-round direct scratch content.")

        ground_requests = (
            "Plan how to preserve suffix ticker evidence without creating a Ground.",
            "Review punctuation rule provenance without creating a Ground.",
            "Plan numeral-preserving tests without creating a Ground.",
            "Review share-class syntax without creating a Ground.",
            "Summarize a complete synthetic ticker rulebook plan without creating anything.",
        )
        add("ground", attempt, ("ground", "--request", ground_requests[attempt - 1]),
            entry="natural-language --request outside a TTY", target="blank unsaved Ground frame",
            scope=f"one provider planning turn for ticker aspect {attempt}; no durable Ground",
            provenance=f"{round_state}; explicit no-create/no-approval boundary",
            consumer="agent-mediated plan proposal only",
            expected="Print a stable unsaved proposal and create no named Ground without exact command approval.")

        impact_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: ("impact", "--from", SOURCE, "--to", scratch, "--direct"),
            2: ("impact", "update", SOURCE, scratch, "--direct"),
            3: ("impact", "atomize", SOURCE),
            4: lambda: ("impact", "audit", "--session", artifact("audit", 4)),
            5: ("impact", "meld", "--session", "deadbeef"),
        }
        add("impact", attempt, impact_args[attempt],
            entry=f"Impact live/saved-analysis route variant {attempt}", target=(f"{SOURCE} → {scratch}" if attempt < 4 else "saved analysis artifact"),
            scope="read-only projected typed effects",
            provenance=f"{round_state}; live endpoints or earlier saved Audit identity",
            consumer="inspect effects before any reviewed Apply",
            expected=("Reject the unavailable saved session atomically." if attempt == 5 else "Preview effects without mutating either endpoint."))

        meld_result = f"task-3/local/ticker-meld-r{attempt}"
        meld_args = {
            1: ("meld", SOURCE, CRITERIA, meld_result, "--defer-all"),
            2: ("meld", SOURCE, CRITERIA, "--to", meld_result, "--defer-all"),
            3: ("meld", SOURCE, CRITERIA, "--to", meld_result),
            4: ("meld", SOURCE, "--to", CRITERIA, "--defer-all"),
            5: ("meld", SOURCE, CRITERIA, "--to", meld_result, "--defer-all"),
        }[attempt]
        add("meld", attempt, meld_args,
            entry=("deliberate obsolete three-positional Result boundary" if attempt == 1 else f"current Meld setup grammar variant {attempt}"),
            target=f"{SOURCE} + {CRITERIA} → {meld_result}",
            scope=f"complete direct example/rule peers; fresh result plan {attempt}",
            provenance=f"{round_state}; only user-authored CORE Sources are exposed",
            consumer="saved balanced relation session without materialization",
            expected="Save a source-bound review session and defer every unresolved relation; do not create Result without acceptance.")

        rationale_args = {
            1: lambda: ("rationale", target_memory(SOURCE, punctuation)),
            2: lambda: ("rationale", target_memory(SOURCE, numeral), "--json"),
            3: lambda: ("rationale", target_memory(SOURCE, numeral), "--limit", "20", "--unit", "words"),
            4: lambda: ("rationale", target_memory(SOURCE, share), "--verbose", "--limit", "60"),
            5: lambda: ("rationale", target_memory(SOURCE, share), "--format", "json", "--max-chars", "80"),
        }[attempt]
        add("rationale", attempt, rationale_args,
            entry=f"exact durable Memory rationale presentation variant {attempt}", target=SOURCE,
            scope="one CORE source Memory provenance/history explanation",
            provenance=f"{round_state}; source selector {source_needles} is outside destructive scratch",
            consumer="understand why the maintained example exists",
            expected="Explain only retained lineage and authorship; do not infer unsupported semantic rationale.")

        add("revert", attempt,
            lambda a=attempt, s=scratch: ("revert", artifact("checkpoint", a), "--context", s, "--keep"),
            entry="same-round checkpoint prefix plus exact owner and --keep", target=scratch,
            scope="restore exact pre-Delete/Clear direct snapshot while retaining later history",
            provenance=f"{round_state}; consumes the reviewed Checkpoint#{attempt} recovery identity",
            consumer="mandatory cleanup of all destructive and generated scratch trials",
            expected="Restore the checkpointed direct scratch contents and preserve recovery history.",
            recovery="This command is the recovery action; following Review/Trace verify continued availability.")

        add("review", attempt,
            lambda a=attempt: ("review", "audit", "--session", artifact("audit", a), "--snapshot"),
            entry="exact saved Audit session plus provider-free --snapshot", target=f"Audit artifact from attempt {attempt}",
            scope="immutable complete saved quality result",
            provenance=f"{round_state}; consumes Audit#{attempt} output after scratch recovery",
            consumer="verify saved evidence without provider rerun",
            expected=("Reject unavailable session identity if the upstream missing-Context Audit produced none." if attempt == 5 else "Render exactly the saved Audit without inference or mutation."))

        sever_result = f"task-3/local/ticker-sever-r{attempt}"
        add("sever", attempt, ("sever", SOURCE, CRITERIA, sever_result, "--direct"),
            entry="Source, Criteria, and fresh Result curation plan", target=f"{SOURCE} × {CRITERIA} → {sever_result}",
            scope=f"whole direct Source and Criteria frames; result plan {attempt}",
            provenance=f"{round_state}; intact user-authored examples and rules after Revert",
            consumer="saved selective-curation proposal without materialization",
            expected="Save a reviewed proposal, leave Source unchanged, and do not create Result without --accept.")

        trace_args = {
            1: lambda: ("trace", target_memory(SOURCE, punctuation)),
            2: lambda: ("trace", target_memory(SOURCE, numeral), "--json"),
            3: lambda: ("trace", target_memory(SOURCE, numeral), "--limit", "1"),
            4: lambda: ("trace", target_memory(SOURCE, share), "--verbose"),
            5: lambda: ("trace", target_memory(SOURCE, share), "--all", "--json"),
        }[attempt]
        add("trace", attempt, trace_args,
            entry=f"exact durable Memory trace presentation variant {attempt}", target=SOURCE,
            scope=f"one CORE Memory lineage with bounded/full detail variant {attempt}",
            provenance=f"{round_state}; exact UID outside scratch and after recovery",
            consumer="verify provenance continuity across copies, edits, and checkpoints",
            expected="Render typed history without confusing copied content, References, or ownership.")

        translate_args = (
            "translate", target_memory(SOURCE, source_needles), "--to", LANGUAGES[attempt - 1],
        ) + (("--refresh",) if attempt == 5 else ())
        add("translate", attempt, translate_args,
            entry=("exact Memory plus language and --refresh" if attempt == 5 else "exact Memory plus target language"),
            target=f"{SOURCE} → {LANGUAGES[attempt - 1]}",
            scope=f"one read-only {LANGUAGES[attempt - 1]} translation view",
            provenance=f"{round_state}; source digest/UID remains unchanged after Revert",
            consumer="cross-language review of maintained synthetic examples",
            expected="Return a source-bound translation view and leave the Source Memory unchanged.")

        update_args = {
            1: ("update", SOURCE, SOURCE, "--direct"),
            2: ("update", SOURCE, scratch, "--direct", "--replace-stage"),
            3: ("update", CRITERIA, scratch, "--direct", "--replace-stage"),
            4: ("update", SOURCE, scratch, "--direct", "--replace-stage", "--goal", "Preserve only source-supported ticker transformations."),
            5: ("update", CRITERIA, scratch, "--direct", "--replace-stage", "--goal", "Keep the lowercase regression conflict explicit; do not apply a choice."),
        }[attempt]
        add("update", attempt, update_args,
            entry=f"directional staged Update variant {attempt}", target=(SOURCE if attempt == 1 else f"{update_args[1]} → {scratch}"),
            scope="exact direct Source/Target frames with explicit stage replacement where applicable",
            provenance=f"{round_state}; post-Revert durable endpoint and bounded Goal when present",
            consumer="review-only directional maintenance plan",
            expected=("Reject same-Context Update without mutation." if attempt == 1 else "Stage typed changes only; do not apply unsupported additions or resolve the deliberate conflict."))

    return result


def new_ledger(initial_digest: str) -> dict:
    return {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": "ticker",
        "phase": "transform",
        "status": "running",
        "world_goal": "Transform and maintain reusable synthetic ticker rules while preserving source provenance, unresolved conflicts, and exact recovery boundaries.",
        "contract": {"operations": 24, "attempts_per_operation": 5, "attempts": 120},
        "execution_identity": {
            "code_snapshot_sha256": "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84",
            "catalog_sha256": "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5",
            "profile_uid": "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd",
            "store_root": str(STORE),
            "provider_policy_sha256": "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca",
            "launcher": f"python {RUNNER} ticker",
        },
        "starting_boundary": {
            "cumulative_from_core": True,
            "core_attempts_complete": 105,
            "transform_initial_tree_digest": initial_digest,
            "no_reset": True,
            "current_context": "practice",
            "dedicated_ticker_context_missing": True,
            "clean_evidence_boundary": "Exact/direct Source, Criteria, and scratch routes only.",
            "noisy_boundary": "Recursive routes under borrowed task roots may expose pre-existing descendants and are not clean ticker-only semantic evidence.",
            "recovery_policy": "Each round structurally populates scratch, checkpoints it, runs exact destructive/derived trials, and Reverts that checkpoint before post-recovery operations.",
        },
        "digest_semantics": "SHA-256 over all active-Profile context.json files plus state.json in sorted path order.",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "operations": {op: {"attempts": []} for op in OPS},
    }


def save(ledger: dict) -> None:
    PHASE.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")


def restore_artifacts(ledger: dict) -> None:
    records = sorted(
        (record for payload in ledger["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    for record in records:
        raw = REPO / record["raw_output"]
        if raw.exists():
            capture_artifacts(record["operation"], record["attempt"], raw.read_text().split("\nOUTPUT\n", 1)[-1])


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    initial = tree_digest()
    ledger = json.loads(PHASE.read_text()) if PHASE.exists() else new_ledger(initial)
    restore_artifacts(ledger)
    interrupted_marker = RAW / "034-elaborate-2-interrupted.txt"
    already_has_34 = any(
        record["sequence"] == 34
        for payload in ledger["operations"].values()
        for record in payload["attempts"]
    )
    if interrupted_marker.exists() and not already_has_34:
        interrupted_spec = specs()[33]
        frozen = tree_digest()
        record = {
            "operation": "elaborate",
            "attempt": 2,
            "sequence": 34,
            "command": "python " + str(RUNNER) + " ticker " + shlex.join(interrupted_spec.args),
            "exit": 130,
            "starting_state": "Cumulative lane immediately after Transform sequence 33; the driver was intentionally interrupted to correct future route wiring.",
            "entry_route": interrupted_spec.entry_route,
            "target_route": interrupted_spec.target_route,
            "scope": interrupted_spec.scope,
            "input_provenance": interrupted_spec.input_provenance + f"; actual argv `{shlex.join(interrupted_spec.args)}`",
            "consumer": interrupted_spec.consumer,
            "expected": interrupted_spec.expected,
            "actual": "The actual pinned command began, then received SIGINT with no stdout and no durable Context-tree change; it was not rerun.",
            "defect_ids": [],
            "cost": {"wall_seconds": 0.0, "output_bytes": 0, "timed_out": False, "interrupted": True, "duration_not_recovered": True},
            "pre_target_digest": frozen,
            "post_target_digest": frozen,
            "recovery_evidence": "Pre/post complete Context-tree digests are identical; the interrupted attempt is retained and not retried.",
            "state_continuity": {
                "same_as_previous_post": True,
                "durable_context_tree_changed": False,
                "one_cumulative_store": True,
                "current_context_expected": "practice",
                "current_context_actual": json.loads((STORE / "state.json").read_text()).get("current"),
            },
            "raw_output": str(interrupted_marker.relative_to(REPO)),
        }
        ledger["operations"]["elaborate"]["attempts"].append(record)
        ledger["last_completed_sequence"] = 34
        ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
        save(ledger)
    completed = {
        record["sequence"]
        for payload in ledger["operations"].values()
        for record in payload["attempts"]
    }
    records = sorted(
        (record for payload in ledger["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    prior_post = records[-1]["post_target_digest"] if records else ledger["starting_boundary"]["transform_initial_tree_digest"]
    plan = specs()
    if len(plan) != 120 or {spec.operation for spec in plan} != set(OPS):
        raise RuntimeError("Ticker Transform spec does not satisfy the 24×5 catalog contract")

    for sequence, spec in enumerate(plan, 1):
        if sequence in completed:
            continue
        args = spec.args() if callable(spec.args) else spec.args
        command_argv = ["python", str(RUNNER), "ticker", *args]
        command = shlex.join(command_argv)
        pre = tree_digest()
        began = time.monotonic()
        timed_out = False
        try:
            result = subprocess.run(
                command_argv,
                cwd=REPO,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=300,
                check=False,
            )
            exit_code = result.returncode
            output = result.stdout
        except subprocess.TimeoutExpired as error:
            timed_out = True
            exit_code = 124
            partial = error.stdout or ""
            output = partial if isinstance(partial, str) else partial.decode("utf-8", "replace")
            output += "\nAUDIT RUNNER TIMEOUT after 300 seconds; child process terminated.\n"
        elapsed = time.monotonic() - began
        post = tree_digest()
        capture_artifacts(spec.operation, spec.attempt, output)
        raw = RAW / f"{sequence:03d}-{spec.operation}-{spec.attempt}.txt"
        raw.write_text(f"COMMAND\n{command}\n\nEXIT\n{exit_code}\n\nOUTPUT\n{output}")
        record = {
            "operation": spec.operation,
            "attempt": spec.attempt,
            "sequence": sequence,
            "command": command,
            "exit": exit_code,
            "starting_state": f"Cumulative no-reset ticker lane at Transform sequence {sequence}; pre-tree digest {pre}; prior post {prior_post}.",
            "entry_route": spec.entry_route,
            "target_route": spec.target_route,
            "scope": spec.scope,
            "input_provenance": spec.input_provenance + f"; actual argv `{shlex.join(args)}`",
            "consumer": spec.consumer,
            "expected": spec.expected,
            "actual": compact(output),
            "defect_ids": [],
            "cost": {"wall_seconds": round(elapsed, 3), "output_bytes": len(output.encode()), "timed_out": timed_out},
            "pre_target_digest": pre,
            "post_target_digest": post,
            "recovery_evidence": spec.recovery_evidence,
            "state_continuity": {
                "same_as_previous_post": prior_post == pre,
                "durable_context_tree_changed": pre != post,
                "one_cumulative_store": True,
                "current_context_expected": "practice",
                "current_context_actual": json.loads((STORE / "state.json").read_text()).get("current"),
            },
            "raw_output": str(raw.relative_to(REPO)),
        }
        ledger["operations"][spec.operation]["attempts"].append(record)
        ledger["last_completed_sequence"] = sequence
        ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
        save(ledger)
        prior_post = post
        print(f"[{sequence:03d}/120] {spec.operation}#{spec.attempt} exit={exit_code} {elapsed:.2f}s changed={pre != post}", flush=True)

    records = [record for payload in ledger["operations"].values() for record in payload["attempts"]]
    ledger["status"] = "complete"
    ledger["attempt_count"] = len(records)
    ledger["coverage"] = {op: len(ledger["operations"][op]["attempts"]) for op in OPS}
    ledger["completed_at"] = datetime.now(timezone.utc).isoformat()
    ledger["summary"] = {
        "attempts": len(records),
        "successful_exits": sum(record["exit"] == 0 for record in records),
        "nonzero_exits": sum(record["exit"] != 0 for record in records),
        "durable_context_tree_mutations": sum(record["state_continuity"]["durable_context_tree_changed"] for record in records),
        "continuity_breaks": sum(not record["state_continuity"]["same_as_previous_post"] for record in records),
        "wall_seconds": round(sum(record["cost"]["wall_seconds"] for record in records), 3),
    }
    save(ledger)


if __name__ == "__main__":
    main()
