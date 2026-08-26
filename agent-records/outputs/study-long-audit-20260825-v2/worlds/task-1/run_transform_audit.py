#!/usr/bin/env python3
"""Run task-1's counted TRANSFORM phase on its cumulative CORE Store.

The runner deliberately confines destructive trials to task-1's ordinary local
scratch Contexts.  Each round checkpoints the scratch target, clears and uses
it for transform evidence, and then restores it before the post-recovery
operations.  Verified construction Sources and contributed campus-wiki areas
are read-only throughout this phase.
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


REPOSITORY = Path("/Users/KimMunyeong/Github/memcommit")
AUDIT_ROOT = REPOSITORY / "agent-records/outputs/study-long-audit-20260825-v2"
WORLD_ROOT = AUDIT_ROOT / "worlds/task-1"
RAW_ROOT = WORLD_ROOT / "raw/transform"
WORLD_RUNNER = AUDIT_ROOT / "run_world_mem.py"
STORE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-1/profile-control/"
    "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
LANE_ROOT = STORE_ROOT.parents[1]
CONTEXTS_ROOT = STORE_ROOT / "contexts"
LEDGER_PATH = WORLD_ROOT / "phase-transform.json"
CORE_LEDGER_PATH = WORLD_ROOT / "phase-core.json"

CODE_SHA256 = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA256 = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROVIDER_SHA256 = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"

P = "task-1/participant"
C = "task-1/participant/construction-updates"
F = f"{C}/facility-updates"
E = f"{C}/event-relocations"
A = f"{C}/building-access"
R = f"{C}/route-changes"
S = f"{C}/shop-updates"
T = f"{C}/temporary-parking"
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


def _tree_digest() -> str:
    """Match CORE's boundary digest over the whole pinned profile-control lane."""
    digest = hashlib.sha256()
    for path in sorted(path for path in LANE_ROOT.rglob("*") if path.is_file()):
        if path.suffix == ".lock" or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(LANE_ROOT).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _context_data(name: str) -> dict:
    path = CONTEXTS_ROOT / name / "context.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _memory_uid(context: str, needles: tuple[str, ...]) -> str:
    data = _context_data(context)
    ordered = data.get("order", [])
    memories = data.get("memories", {})
    for needle in needles:
        for uid in ordered:
            item = memories.get(uid, {})
            if item.get("type") == "memory" and needle.lower() in item.get("content", "").lower():
                return uid
    for uid in ordered:
        if memories.get(uid, {}).get("type") == "memory":
            return uid
    return "missing0000000000000000000000000000"


def _memory_target(context: str, needles: tuple[str, ...]) -> str:
    return f"{context}:{_memory_uid(context, needles)[:8]}"


def _artifact(kind: str, attempt: int) -> str:
    return ARTIFACTS.get((kind, attempt), "deadbeef")


def _capture_artifacts(operation: str, attempt: int, output: str) -> None:
    patterns = {
        "checkpoint": [r"\[([0-9a-f]{8})\]"],
        "audit": [
            r"SESSION\s*\[([0-9a-f-]{8,36})\]",
            r"mem review audit --session ([0-9a-f-]{8,36})",
        ],
        "distill": [r"mem review distill --receipt ([0-9a-f-]{8,36})"],
        "forget": [r"mem review forget --receipt ([0-9a-f-]{8,36})"],
        "atomize": [
            r"mem review atomize --session ([0-9a-f-]{8,36})",
            r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})",
        ],
        "meld": [r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})"],
        "sever": [r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})"],
        "update": [r"SESSION\s*[·:]\s*([0-9a-f-]{8,36})"],
    }
    for pattern in patterns.get(operation, []):
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            ARTIFACTS[(operation, attempt)] = match.group(1)
            break


def _summary(text: str) -> str:
    clean = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text).replace("\r", "")
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if not lines:
        return "No stdout/stderr text was emitted."
    value = " | ".join(lines[:8])
    if len(lines) > 8:
        value += f" | … ({len(lines)} non-empty lines; see raw output)"
    return value[:2400]


def _specs() -> list[Spec]:
    specs: list[Spec] = []

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
        recovery: str = "Later interleaved operations verify continuity; no separate recovery is expected.",
    ) -> None:
        specs.append(Spec(op, attempt, args, entry, target, scope, provenance, consumer, expected, recovery))

    sources = {1: F, 2: E, 3: A, 4: T, 5: S}
    source_needles = {
        1: ("major facility improvement", "elevators operate alternately"),
        2: ("Viewing in the tenth-floor", "Do not accept new reservations"),
        3: ("third-floor rear entrance", "temporary accessible route"),
        4: ("underground parking garage", "physical access card"),
        5: ("ATM on the first floor", "24-hour unattended store"),
    }

    for attempt in range(1, 6):
        # P carries four disposable CORE evidence Memories. C has no direct
        # Memories, so both are safe local scratch endpoints while descendants
        # remain intact verified Sources.  Alternation exercises both an
        # ordinary leaf-like target and a lexical parent target.
        target = P if attempt % 2 else C
        source = sources[attempt]
        needles = source_needles[attempt]
        other_source = {1: E, 2: A, 3: T, 4: R, 5: F}[attempt]
        round_state = (
            f"transform round {attempt} on the cumulative CORE Store; checkpointed lane-local scratch "
            f"target is {target}, verified construction Source is {source}, and no Store reset occurs"
        )
        route_tag = {
            1: "whole facility Context",
            2: "focused event Memory via split operands",
            3: "focused access Memory via combined locator",
            4: "whole parking Context",
            5: "focused shop Memory with neighbor coverage",
        }[attempt]

        atomize_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: ("atomize", F),
            2: lambda: ("atomize", "--context", E, "--memory", _memory_uid(E, source_needles[2])[:8]),
            3: lambda: ("atomize", _memory_target(A, source_needles[3])),
            4: ("atomize", T),
            5: lambda: ("atomize", "--context", S, "--memory", _memory_uid(S, source_needles[5])[:8], "--all"),
        }[attempt]
        add("atomize", attempt, atomize_args, entry=f"pinned CLI · {route_tag}",
            target=source, scope=("complete direct construction frame" if attempt in {1, 4} else "one exact construction Memory with evidence neighbors"),
            provenance=f"{round_state}; durable selector recovered from verified construction input; route={route_tag}",
            consumer="atomicity review session", expected="Analyze atomicity without applying edits or inventing campus facts.")

        audit_args = {
            1: ("audit", F, "--snapshot"),
            2: ("audit", E, "--snapshot"),
            3: ("audit", A, "--against", R, "--snapshot"),
            4: ("audit", T, "--against", A, "--snapshot"),
            5: ("audit", S, "--snapshot"),
        }[attempt]
        add("audit", attempt, audit_args, entry=f"pinned CLI · saved audit route {attempt}",
            target=source, scope=("three quality checks" if attempt in {1, 2, 5} else f"quality plus cross-area conformance against {other_source}"),
            provenance=f"{round_state}; immutable pre-destructive construction frame; audit-route={shlex.join(audit_args)}",
            consumer="saved read-only quality evidence", expected="Save a source-linked Audit without changing verified construction content.")

        checkpoint_args = ("checkpoint", target, f"task-1 transform round {attempt} scratch recovery", "--direct")
        add("checkpoint", attempt, checkpoint_args, entry=f"pinned CLI · exact recovery checkpoint r{attempt}",
            target=target, scope=f"direct scratch snapshot before round {attempt}",
            provenance=f"{round_state}; exact pre-Clear durable target; checkpoint-route={shlex.join(checkpoint_args)}",
            consumer="same-round destructive recovery", expected="Create one named checkpoint whose UID feeds Diff and Revert.")

        conformance_args = {
            1: ("check-conformance", F, "--against", "text:Every published construction claim must state its effective period and source."),
            2: ("check-conformance", E, "--against", A),
            3: ("check-conformance", A, "--against", "text:Accessible-route claims must retain temporary alternatives and construction dates."),
            4: ("check-conformance", T, "--against", R),
            5: ("check-conformance", S, "--against", F),
        }[attempt]
        add("check-conformance", attempt, conformance_args, entry=f"pinned CLI · target/rule frame r{attempt}",
            target=source, scope=("literal construction publication rule" if attempt in {1, 3} else f"cross-area rule frame against {other_source}"),
            provenance=f"{round_state}; verified pre-Clear facts plus explicit rule source; conformance-route={shlex.join(conformance_args)}",
            consumer="rule-fit report", expected="Return evidence-linked dispositions without mutating either frame.")

        add("clear", attempt, ("clear", target, "--force"), entry=f"pinned CLI · force-confirmed scratch r{attempt}",
            target=target, scope="all direct Memories in checkpointed lane-local scratch only",
            provenance=f"{round_state}; same-round checkpoint UID is resolved before execution; clear-route={target} --force",
            consumer="destructive recovery trial", expected="Clear only the checkpointed scratch target atomically; descendants and public areas stay unchanged.",
            recovery=f"Revert#{attempt} must restore checkpoint {_artifact('checkpoint', attempt)} before the round ends.")

        add("delete", attempt, ("delete", f"dead{attempt:04x}", "--context", target),
            entry=f"pinned CLI · unavailable selector boundary r{attempt}", target=target,
            scope=f"one missing direct selector dead{attempt:04x} after Clear",
            provenance=f"{round_state}; deliberately empty checkpointed target; delete-route=dead{attempt:04x}@{target}",
            consumer="safe missing-item boundary", expected="Reject the unavailable selector without a second mutation.",
            recovery="Diff and Revert later in this round verify no partial Delete effect.")

        diff_flag = {1: "--stat", 2: "--raw", 3: "--verbose", 4: "--stat", 5: "--raw"}[attempt]
        add("diff", attempt, lambda a=attempt, t=target, f=diff_flag: ("diff", _artifact("checkpoint", a), "--context", t, f),
            entry=f"pinned CLI · checkpoint Diff {diff_flag} r{attempt}", target=target,
            scope=f"post-Clear checkpoint difference rendered with {diff_flag}",
            provenance=f"{round_state}; checkpoint receipt from sequence-local Checkpoint; diff-view={diff_flag}",
            consumer="destructive-change inspection", expected="Show exact scratch removal relative to the same-round checkpoint without mutation.")

        goals = {
            1: "Distill dated facility changes for publication; retain source attribution and all verified qualifications.",
            2: "Distill event relocation rules while keeping reservation limits and alternative venues distinct.",
            3: "Distill access changes while preserving accessible alternatives, hours, dates, and exceptions.",
            4: "Distill parking controls while keeping general, staff, and construction access roles separate.",
            5: "Distill shop closures and alternatives without inventing hours, services, or locations.",
        }
        add("distill", attempt, ("distill", "--from", source, "--to", target, "--goal", goals[attempt]),
            entry=f"pinned CLI · Source→scratch Distill r{attempt}", target=f"{source} → {target}",
            scope=f"complete {source} direct frame into cleared scratch",
            provenance=f"{round_state}; verified construction inputs only; bounded-goal={goals[attempt]}",
            consumer="temporary derived Rules under recovery checkpoint", expected="Add only source-bound Rules with a reusable receipt; require no unsupported approval.",
            recovery="Same-round Revert removes all temporary derived material after review trials.")

        elaborate_args = {
            1: ("elaborate", "--from", F, "--goal", "Explain only verified facility changes and their dates.", "--to", target),
            2: ("elaborate", "--rule", "Event relocation examples must use only verified venues, dates, and reservation status.", "--to", target),
            3: ("elaborate", "--goal", "Explain only verified accessible-route alternatives and access-hour changes.", "--to", target),
            4: ("elaborate", "--rule", "Parking examples must distinguish general, staff, and controlled construction access.", "--to", target),
            5: ("elaborate", "--goal", "Give only verified closure and alternative-service examples already in the shop evidence.", "--to", target),
        }[attempt]
        add("elaborate", attempt, elaborate_args, entry=f"pinned CLI · bounded elaborate form r{attempt}",
            target=target, scope=f"temporary {route_tag} examples in checkpointed scratch",
            provenance=f"{round_state}; no-invention boundary; elaborate-route={shlex.join(elaborate_args)}",
            consumer="unsupported-generation safety test",
            expected=("Reject incompatible --from plus --goal form before mutation." if attempt == 1 else "Generate only source-supported examples and avoid implying approval."),
            recovery="Any temporary output remains scratch-only and is removed by same-round Revert.")

        add("resolve", attempt, ("resolve", "--context", target), entry=f"pinned CLI · scratch coherence route r{attempt}",
            target=target, scope=f"complete post-Distill/Elaborate scratch frame r{attempt}",
            provenance=f"{round_state}; generated frame is inside the checkpoint recovery window; resolve-context={target}",
            consumer="coherence repair proposal", expected="Stage reviewable repairs without silently choosing between verified distinctions.",
            recovery="Any direct scratch mutation is rolled back by same-round Revert and logged as evidence.")

        add("dedup", attempt, ("dedup", target, "--direct"), entry=f"pinned CLI · exact duplicate cleanup r{attempt}",
            target=target, scope=f"exact direct duplicate groups in scratch round {attempt}",
            provenance=f"{round_state}; post-Resolve scratch only; dedup-route={target} --direct",
            consumer="exact duplicate recovery trial", expected="Apply only proven exact duplicate absorptions or report no groups.",
            recovery="Same-round Revert restores the pre-Clear scratch snapshot.")

        add("dedun", attempt, ("dedun", target, "--direct"), entry=f"pinned CLI · semantic redundancy cleanup r{attempt}",
            target=target, scope=f"semantic direct redundancy groups in scratch round {attempt}",
            provenance=f"{round_state}; post-Dedup scratch only; dedun-route={target} --direct",
            consumer="semantic redundancy recovery trial", expected="Apply only complete evidence-linked redundancy groups and retain real distinctions.",
            recovery="Same-round Revert restores the pre-Clear scratch snapshot.")

        forget_instructions = {
            1: "remove temporary facility rules that lack a verified date or source",
            2: "remove temporary event claims that invent a venue, date, or reservation status",
            3: "remove temporary access claims that omit a verified accessible alternative or exception",
            4: "remove temporary parking claims that collapse general, staff, and construction access roles",
            5: "remove temporary shop claims that invent operating hours, services, or locations",
        }
        add("forget", attempt, ("forget", forget_instructions[attempt], "--context", target),
            entry=f"pinned CLI · process-local Forget criterion r{attempt}", target=target,
            scope=f"whole temporary direct scratch frame under criterion {attempt}",
            provenance=f"{round_state}; checkpointed post-curation frame; instruction={forget_instructions[attempt]}",
            consumer="selective curation safety trial", expected="Return one decision per Memory and apply atomically without fabricating provenance.",
            recovery="Same-round Revert restores all pre-round scratch content regardless of curation outcome.")

        ground_requests = {
            1: "Review how verified facility changes should update the campus wiki without creating a Ground.",
            2: "Review event relocations and reservation limits without creating a Ground.",
            3: "Review accessible-route updates and exceptions without creating a Ground.",
            4: "Review temporary parking roles and controls without creating a Ground.",
            5: "Review shop closures and alternative services without creating a Ground.",
        }
        add("ground", attempt, ("ground", "--request", ground_requests[attempt]),
            entry=f"pinned CLI · natural-language unsaved Ground request r{attempt}", target="blank unsaved Ground frame",
            scope=f"one provider turn about {route_tag}; no durable Ground",
            provenance=f"{round_state}; explicit no-create boundary; request={ground_requests[attempt]}",
            consumer="agent-mediated planning boundary", expected="Return an unsaved proposal frame and create nothing without exact command approval.")

        impact_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: ("impact", "atomize", F),
            2: ("impact", "--from", E, "--to", target, "--direct"),
            3: lambda: ("impact", "audit", "--session", _artifact("audit", 3)),
            4: ("impact", "update", T, target, "--direct"),
            5: ("impact", "meld", "--session", "deadbeef"),
        }
        add("impact", attempt, impact_args[attempt], entry=f"pinned CLI · operation-specific Impact route r{attempt}",
            target=(source if attempt == 1 else (f"{source} → {target}" if attempt in {2, 4} else "saved analysis artifact")),
            scope=f"read-only projected effects via Impact form {attempt}",
            provenance=f"{round_state}; live/saved analysis route unique to attempt {attempt}",
            consumer="pre-Apply effect inspection", expected="Preview typed effects without applying; unavailable artifacts fail atomically.")

        meld_result = f"task-1/participant/transform-meld-r{attempt}"
        add("meld", attempt, ("meld", source, target, meld_result), entry=f"pinned CLI · symmetric Meld plan r{attempt}",
            target=f"{source} + {target} → {meld_result}", scope=f"verified {route_tag} plus temporary scratch frame",
            provenance=f"{round_state}; fresh world-local Result plan {meld_result}",
            consumer="saved merge-resolution session", expected="Save a source-bound review session or reject invalid provider relations; never --accept.")

        conflict_policy = "--keep-target-all" if attempt % 2 else "--take-source-all"
        merge_args = ("merge", source, target, "--direct", conflict_policy)
        add("merge", attempt, merge_args, entry=f"pinned CLI · structural Merge {conflict_policy} r{attempt}",
            target=f"{source} → {target}", scope=f"direct items only with explicit policy {conflict_policy}",
            provenance=f"{round_state}; target is within recovery checkpoint; merge-route={shlex.join(merge_args)}",
            consumer="temporary structural integration", expected="Apply one atomic scratch merge with explicit source/target effects and checkpoint provenance.",
            recovery="Same-round Revert restores the exact scratch snapshot made before Clear.")

        add("rationale", attempt,
            lambda s=source, n=needles, a=attempt: ("rationale", _memory_target(s, n), "--verbose") if a in {3, 5} else ("rationale", _memory_target(s, n)),
            entry=f"pinned CLI · durable {route_tag} rationale r{attempt}", target=source,
            scope=f"one exact verified construction Memory; verbose={attempt in {3, 5}}",
            provenance=f"{round_state}; intact non-scratch source selector from {source}",
            consumer="why/provenance review", expected="Explain durable lineage only; do not infer unsupported campus rationale.")

        add("revert", attempt, lambda a=attempt, t=target: ("revert", _artifact("checkpoint", a), "--context", t, "--keep"),
            entry=f"pinned CLI · mandatory checkpoint Revert r{attempt}", target=target,
            scope=f"restore round {attempt} pre-Clear direct scratch snapshot and retain history",
            provenance=f"{round_state}; same-round checkpoint is the reviewed recovery boundary",
            consumer="mandatory destructive-trial recovery", expected="Restore scratch content to the checkpointed snapshot and keep recovery history.",
            recovery="This is the recovery action; later read-only operations verify restored source availability.")

        review_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: lambda: ("review", "audit", "--session", _artifact("audit", 1), "--snapshot"),
            2: lambda: ("review", "distill", "--receipt", _artifact("distill", 2), "--snapshot"),
            3: lambda: ("review", "forget", "--receipt", _artifact("forget", 3), "--snapshot"),
            4: lambda: ("review", "audit", "--session", _artifact("audit", 4), "--snapshot"),
            5: lambda: ("review", "distill", "--receipt", _artifact("distill", 5), "--snapshot"),
        }
        add("review", attempt, review_args[attempt], entry=f"pinned CLI · immutable saved artifact review r{attempt}",
            target=f"round {attempt} Audit/Distill/Forget artifact",
            scope=f"read-only complete review snapshot using artifact family {review_args[attempt]}",
            provenance=f"{round_state}; UID consumed from an earlier counted receipt in this round",
            consumer="post-recovery evidence verification", expected="Render saved evidence without re-running inference or applying changes.")

        sever_result = f"task-1/participant/transform-sever-r{attempt}"
        add("sever", attempt, ("sever", source, target, sever_result, "--direct"),
            entry=f"pinned CLI · Source/Criteria/Result Sever r{attempt}", target=f"{source} × {target} → {sever_result}",
            scope=f"whole direct {route_tag} Source and restored scratch Criteria",
            provenance=f"{round_state}; fresh world-local Result plan {sever_result}",
            consumer="saved selective-curation session", expected="Save a reviewed Result proposal, leave Source unchanged, and never --accept.")

        add("trace", attempt,
            lambda s=source, n=needles, a=attempt: ("trace", _memory_target(s, n), "--limit", str(a + 2), "--verbose") if a in {3, 5} else ("trace", _memory_target(s, n), "--limit", str(a + 2)),
            entry=f"pinned CLI · bounded durable trace r{attempt}", target=source,
            scope=f"exact {route_tag} provenance depth {attempt + 2}; verbose={attempt in {3, 5}}",
            provenance=f"{round_state}; restored post-Revert state and exact verified UID",
            consumer="lineage verification", expected="Render typed source/checkpoint lineage without confusing copy with ownership.")

        language = {1: "Korean", 2: "French", 3: "Japanese", 4: "Spanish", 5: "German"}[attempt]
        add("translate", attempt, lambda s=source, n=needles, lang=language: ("translate", _memory_target(s, n), "--to", lang),
            entry=f"pinned CLI · exact Memory translation to {language}", target=source,
            scope=f"one read-only {language} translation view of {route_tag}",
            provenance=f"{round_state}; restored source content and exact UID; target-language={language}",
            consumer="cross-language campus update understanding", expected="Return a digest-bound translation view without altering the Memory.")

        update_args = {
            1: ("update", F, F, "--direct"),
            2: ("update", E, target, "--direct", "--replace-stage"),
            3: ("update", A, target, "--direct", "--replace-stage"),
            4: ("update", T, target, "--direct", "--replace-stage", "--goal", "Preserve access-role distinctions and construction dates."),
            5: ("update", S, target, "--direct", "--replace-stage", "--goal", "Keep closure and alternative-service facts explicit; add nothing unsupported."),
        }[attempt]
        add("update", attempt, update_args, entry=f"pinned CLI · directional staged Update r{attempt}",
            target=(F if attempt == 1 else f"{source} → {target}"),
            scope=f"direct Source/Target frames; replace-stage={attempt != 1}; bounded-goal={attempt in {4, 5}}",
            provenance=f"{round_state}; post-Revert durable endpoints; update-route={shlex.join(update_args)}",
            consumer="review-only directional update plan",
            expected=("Reject same-Context Update without mutation." if attempt == 1 else "Stage typed changes only; do not Apply unsupported additions."))

    return specs


def _new_ledger(initial_digest: str, core_digest: str) -> dict:
    operations = (
        "atomize", "audit", "checkpoint", "check-conformance", "clear", "delete",
        "diff", "distill", "elaborate", "resolve", "dedup", "dedun", "forget",
        "ground", "impact", "meld", "merge", "rationale", "revert", "review",
        "sever", "trace", "translate", "update",
    )
    return {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": "task-1",
        "phase": "transform",
        "status": "running",
        "contract": {"operations": 24, "attempts_per_operation": 5, "attempts": 120},
        "sequence_semantics": "Phase-local transform sequence 1..120; CORE used its own phase-local sequence 1..105.",
        "execution_identity": {
            "code_sha": CODE_SHA256,
            "code_sha256": CODE_SHA256,
            "catalog_sha": CATALOG_SHA256,
            "catalog_sha256": CATALOG_SHA256,
            "profile_uid": PROFILE_UID,
            "lane_store_root": str(STORE_ROOT),
            "store_root": str(STORE_ROOT),
            "provider_digest": PROVIDER_SHA256,
            "provider_policy_sha256": PROVIDER_SHA256,
            "runner": f"python {WORLD_RUNNER} task-1",
        },
        "starting_boundary": {
            "cumulative_from_core": True,
            "core_final_digest": core_digest,
            "transform_initial_digest": initial_digest,
            "matches_core_final_digest": core_digest == initial_digest,
            "no_reset": True,
            "same_profile_uid": PROFILE_UID,
            "same_lane_store": str(STORE_ROOT),
            "recovery_policy": (
                "Each round checkpoints only its lane-local scratch Clear target, then Revert restores "
                "that exact target before post-recovery operations; verified Sources and public wiki remain read-only."
            ),
        },
        "digest_semantics": "CORE-compatible SHA-256 over all files in the pinned profile-control lane except locks and __pycache__, with length-delimited relative paths and contents.",
        "launcher": f"python {WORLD_RUNNER} task-1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "operations": {operation: {"attempts": []} for operation in operations},
    }


def _save(ledger: dict) -> None:
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")


def _restore_artifacts(ledger: dict) -> None:
    records = sorted(
        (record for payload in ledger["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    for record in records:
        raw = AUDIT_ROOT / record["raw_output"]
        if raw.exists():
            output = raw.read_text().split("\nOUTPUT\n", 1)[-1]
            _capture_artifacts(record["operation"], record["attempt"], output)


def main() -> None:
    WORLD_ROOT.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    core = json.loads(CORE_LEDGER_PATH.read_text())
    core_records = sorted(
        (record for payload in core["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    core_digest = core_records[-1]["post_target_digest"]
    initial_digest = _tree_digest()
    ledger = json.loads(LEDGER_PATH.read_text()) if LEDGER_PATH.exists() else _new_ledger(initial_digest, core_digest)
    if not ledger["starting_boundary"]["matches_core_final_digest"]:
        raise RuntimeError("Transform initial Store does not match CORE final digest")
    _restore_artifacts(ledger)
    completed = {
        record["sequence"]
        for payload in ledger["operations"].values()
        for record in payload["attempts"]
    }
    previous = sorted(
        (record for payload in ledger["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    prior_post = previous[-1]["post_target_digest"] if previous else core_digest
    specs = _specs()
    if len(specs) != 120 or {spec.operation for spec in specs} != set(ledger["operations"]):
        raise RuntimeError("Transform spec does not match 24×5 catalog contract")

    for sequence, spec in enumerate(specs, 1):
        if sequence in completed:
            continue
        args = spec.args() if callable(spec.args) else spec.args
        command_argv = ["python", str(WORLD_RUNNER), "task-1", *args]
        command = shlex.join(command_argv)
        pre = _tree_digest()
        began = time.monotonic()
        timed_out = False
        try:
            result = subprocess.run(
                command_argv,
                cwd=REPOSITORY,
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
        post = _tree_digest()
        _capture_artifacts(spec.operation, spec.attempt, output)
        raw_path = RAW_ROOT / f"{sequence:03d}-{spec.operation}-{spec.attempt}.txt"
        raw_path.write_text(f"COMMAND\n{command}\n\nEXIT\n{exit_code}\n\nOUTPUT\n{output}")
        no_reset = f"no reset; same pinned Profile UID {PROFILE_UID} and lane Store {STORE_ROOT}"
        record = {
            "operation": spec.operation,
            "attempt": spec.attempt,
            "sequence": sequence,
            "command": command,
            "exit": exit_code,
            "starting_state": (
                f"Cumulative no-reset Store at phase-local transform sequence {sequence}; "
                f"pre-command Context-tree digest {pre}; immediately follows prior post digest {prior_post}."
            ),
            "entry_route": spec.entry_route + f" · argv={shlex.join(args)}",
            "target_route": spec.target_route,
            "scope": spec.scope,
            "input_provenance": spec.input_provenance + f"; actual argv `{shlex.join(args)}`",
            "consumer": spec.consumer,
            "expected": spec.expected,
            "actual": _summary(output),
            "defect_ids": [],
            "cost": {"wall_seconds": round(elapsed, 3), "output_bytes": len(output.encode()), "timed_out": timed_out},
            "pre_target_digest": pre,
            "post_target_digest": post,
            "recovery_evidence": spec.recovery_evidence,
            "state_continuity": (
                f"{no_reset}; pre digest {'equals' if prior_post == pre else 'DOES NOT EQUAL'} prior phase-local "
                f"post digest; durable Context tree {'changed' if pre != post else 'unchanged'} during this attempt."
            ),
            "state_continuity_facts": {
                "reset": False,
                "same_as_previous_post": prior_post == pre,
                "durable_context_tree_changed": pre != post,
                "one_cumulative_store": True,
            },
            "raw_output": str(raw_path.relative_to(AUDIT_ROOT)),
            "evidence_id": f"T1-V2-TRANSFORM-{sequence:03d}",
        }
        ledger["operations"][spec.operation]["attempts"].append(record)
        ledger["last_completed_sequence"] = sequence
        ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save(ledger)
        prior_post = post
        print(f"[{sequence:03d}/120] {spec.operation}#{spec.attempt} exit={exit_code} {elapsed:.2f}s changed={pre != post}", flush=True)

    records = [record for payload in ledger["operations"].values() for record in payload["attempts"]]
    ledger["status"] = "complete"
    ledger["attempt_count"] = len(records)
    ledger["completed_at"] = datetime.now(timezone.utc).isoformat()
    ledger["coverage"] = {
        "operations": 24,
        "attempts_per_operation": 5,
        "counted_actual_mem_commands": len(records),
        "exit_zero": sum(record["exit"] == 0 for record in records),
        "nonzero_boundary_or_failure": sum(record["exit"] != 0 for record in records),
        "wall_seconds": round(sum(record["cost"]["wall_seconds"] for record in records), 3),
        "tui_attempts": 0,
        "continuity_breaks": sum(not record["state_continuity_facts"]["same_as_previous_post"] for record in records),
        "durable_context_tree_mutations": sum(record["state_continuity_facts"]["durable_context_tree_changed"] for record in records),
    }
    _save(ledger)


if __name__ == "__main__":
    main()
