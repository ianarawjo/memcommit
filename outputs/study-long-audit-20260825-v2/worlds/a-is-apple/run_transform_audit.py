#!/usr/bin/env python3
"""Run the counted a-is-apple TRANSFORM phase on the cumulative CORE Store."""

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
AUDIT_ROOT = REPOSITORY / "outputs/study-long-audit-20260825-v2"
WORLD_ROOT = AUDIT_ROOT / "worlds/a-is-apple"
RAW_ROOT = WORLD_ROOT / "raw/transform"
WORLD_RUNNER = AUDIT_ROOT / "run_world_mem.py"
STORE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/a-is-apple/profile-control/"
    "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
CONTEXTS_ROOT = STORE_ROOT / "contexts"
LEDGER_PATH = WORLD_ROOT / "phase-transform.json"
CORE_LEDGER_PATH = WORLD_ROOT / "phase-core.json"

CODE_SHA256 = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA256 = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROVIDER_SHA256 = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"

P = "practice"
S = "practice/source"
D = "practice/description"
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
    digest = hashlib.sha256()
    for path in sorted(CONTEXTS_ROOT.rglob("context.json")):
        digest.update(path.relative_to(STORE_ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(b"state.json\0")
    digest.update((STORE_ROOT / "state.json").read_bytes())
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
            if item.get("type") == "memory" and needle in item.get("content", ""):
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
        "audit": [r"mem review audit --session ([0-9a-f-]{8,36})"],
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

    for attempt in range(1, 6):
        # Alternate the destructive scratch endpoint. The other endpoint remains
        # the evidence Source, and Revert later in the same round restores the
        # checkpointed endpoint before Sever/Trace/Translate/Update continue.
        target = S if attempt % 2 else P
        source = P if target == S else S
        source_needles = (
            ("a is apple", "a maps to apple", "Preferred set")
            if source == P
            else ("b is banana", "b is blueberry", "a maps to")
        )
        target_needles = (
            ("b is banana", "b is blueberry", "a maps to")
            if target == S
            else ("a is apple", "a maps to apple", "Preferred set")
        )
        round_state = (
            f"transform round {attempt} on the cumulative CORE Store; checkpointed scratch target "
            f"will be {target}, evidence Source is {source}, and no Store reset occurs"
        )

        atomize_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: ("atomize", P),
            2: lambda n=source_needles: ("atomize", "--context", S, "--memory", _memory_uid(S, n)[:8]),
            3: lambda: ("atomize", _memory_target(P, ("Preferred set", "a is apple"))),
            4: ("atomize", S),
            5: lambda: ("atomize", "--context", P, "--memory", _memory_uid(P, ("a maps to apricot", "a is apple"))[:8], "--all"),
        }[attempt]
        add("atomize", attempt, atomize_args, entry="Context or focused-Memory analysis",
            target=P if attempt in {1, 3, 5} else S,
            scope=("whole direct frame" if attempt in {1, 4} else "one actionable Memory with neighbors as evidence"),
            provenance=f"{round_state}; direct CORE Memory selector recovered from durable state",
            consumer="atomicity review session",
            expected="Analyze without applying or inventing replacement facts; save a reviewable source-bound session.")

        audit_args = {
            1: ("audit", P, "--snapshot"),
            2: ("audit", S, "--snapshot"),
            3: ("audit", P, "--against", S, "--snapshot"),
            4: ("audit", S, "--against", P, "--snapshot"),
            5: ("audit", P, "--snapshot"),
        }[attempt]
        add("audit", attempt, audit_args, entry="explicit audit snapshot",
            target=(P if attempt in {1, 3, 5} else S),
            scope=("three quality checks" if attempt in {1, 2, 5} else "quality plus cross-Context conformance"),
            provenance=f"{round_state}; pre-destructive cumulative Source frame",
            consumer="saved read-only quality evidence",
            expected="Save and print a complete evidence-linked Audit without changing Context content.")

        checkpoint_args = (
            "checkpoint", target,
            f"a-is-apple transform round {attempt} recovery before destructive scratch trials",
            "--direct",
        )
        add("checkpoint", attempt, checkpoint_args, entry="explicit Context plus recovery message",
            target=target, scope="direct checkpoint",
            provenance=f"{round_state}; exact pre-clear durable target",
            consumer="same-round destructive recovery",
            expected="Create one named checkpoint whose UID can feed Diff and Revert.")

        conformance_args = {
            1: ("check-conformance", P, "--against", "text:Each letter maps to at most one preferred word."),
            2: ("check-conformance", S, "--against", P),
            3: ("check-conformance", S, "--against", "text:Alternatives must remain explicit and source-grounded."),
            4: ("check-conformance", P, "--against", D),
            5: ("check-conformance", S, "--against", P),
        }[attempt]
        add("check-conformance", attempt, conformance_args, entry="Target plus literal/Context rules",
            target=(P if attempt in {1, 4} else S),
            scope=("literal INSTRUCTION rule" if attempt in {1, 3} else "cross-Context rule frame"),
            provenance=f"{round_state}; pre-clear claims and explicit rule source",
            consumer="rule-fit report",
            expected="Return complete source-linked dispositions without mutating either frame.")

        add("clear", attempt, ("clear", target, "--force"), entry="explicit force-confirmed lane-local target",
            target=target, scope="all direct items in checkpointed Context",
            provenance=f"{round_state}; checkpoint {_artifact('checkpoint', attempt)} is required before execution",
            consumer="destructive recovery trial",
            expected="Remove the checkpointed target's direct items atomically and leave the checkpoint available.",
            recovery=f"Revert#{attempt} must restore checkpoint {_artifact('checkpoint', attempt)} before the round ends.")

        add("delete", attempt, ("delete", f"dead{attempt:04x}", "--context", target),
            entry="explicit unavailable Memory selector", target=target,
            scope="single missing selector after Clear",
            provenance=f"{round_state}; deliberately empty checkpointed target after Clear",
            consumer="safe missing-item boundary",
            expected="Reject the unavailable selector without publishing a second mutation.",
            recovery="Diff and Revert later in this round verify no partial Delete effect.")

        diff_flag = {1: "--stat", 2: "--raw", 3: "--verbose", 4: "--stat", 5: "--raw"}[attempt]
        add("diff", attempt,
            lambda a=attempt, t=target, f=diff_flag: ("diff", _artifact("checkpoint", a), "--context", t, f),
            entry="checkpoint UID plus exact owning Context", target=target,
            scope=f"post-Clear checkpoint difference {diff_flag}",
            provenance=f"{round_state}; checkpoint receipt from sequence-local Checkpoint",
            consumer="destructive-change inspection",
            expected="Show the exact removal relative to the same-round recovery checkpoint without mutation.")

        goal = {
            1: "Distill only source-supported alphabet mappings and preserve unresolved alternatives.",
            2: "Distill explicit provenance rules for apple and the unresolved b alternatives.",
            3: "Distill a compact recovery rule set without inventing new letter mappings.",
            4: "Distill source-grounded preferred mappings while retaining conflicts as conflicts.",
            5: "Distill final a-is-apple evidence with every alternative and provenance boundary explicit.",
        }[attempt]
        add("distill", attempt, ("distill", "--from", source, "--to", target, "--goal", goal),
            entry="explicit Source, target, and bounded Goal", target=f"{source} → {target}",
            scope="complete direct Source frame into cleared checkpointed target",
            provenance=f"{round_state}; source-supported CORE mappings only",
            consumer="temporary derived Rules under recovery checkpoint",
            expected="Add only evidence-bound Rules with a reusable receipt; unsupported facts must not be approved.",
            recovery="Same-round Revert removes this temporary derived material after review trials.")

        elaborate_args = {
            1: ("elaborate", "--from", source, "--goal", "Explain only the existing mapping provenance.", "--to", target),
            2: ("elaborate", "--rule", "a is apple; examples must preserve this exact supported mapping.", "--to", target),
            3: ("elaborate", "--goal", "Explain only how provenance distinguishes preferred mappings from unresolved alternatives.", "--to", target),
            4: ("elaborate", "--rule", "Every alphabet example must cite an existing mapping and must not introduce a new word.", "--to", target),
            5: ("elaborate", "--goal", "Give only source-grounded examples already present in the a-is-apple evidence.", "--to", target),
        }[attempt]
        add("elaborate", attempt, elaborate_args, entry="bounded Goal/Rule elaboration",
            target=target, scope="temporary derived examples in checkpointed target",
            provenance=f"{round_state}; explicit no-invention boundary",
            consumer="unsupported-generation safety test",
            expected=("Reject incompatible --from plus --goal forms before mutation." if attempt == 1 else "Generate only supported, explicitly unverified examples; do not require or imply approval."),
            recovery="Any automatically published unsupported output is evidence, not approval, and is removed by same-round Revert.")

        add("resolve", attempt, ("resolve", "--context", target),
            entry="explicit temporary result Context", target=target,
            scope="complete post-Distill/Elaborate direct frame",
            provenance=f"{round_state}; generated frame remains inside checkpoint recovery window",
            consumer="coherence repair proposal",
            expected="Report or stage reviewable repairs; do not silently choose between deliberate alternatives.",
            recovery="Any automatic direct mutation is rolled back by same-round Revert and logged as a safety finding.")

        add("dedup", attempt, ("dedup", target, "--direct"), entry="exact direct cleanup",
            target=target, scope="exact duplicate groups in temporary frame",
            provenance=f"{round_state}; post-Resolve checkpointed target",
            consumer="exact duplicate recovery trial",
            expected="Apply only proven exact duplicate absorptions with a checkpoint, or report no groups.",
            recovery="Same-round Revert restores the pre-clear target after cleanup evidence is collected.")

        add("dedun", attempt, ("dedun", target, "--direct"), entry="semantic direct cleanup",
            target=target, scope="complete semantic redundancy groups in temporary frame",
            provenance=f"{round_state}; post-Dedup checkpointed target",
            consumer="semantic redundancy recovery trial",
            expected="Apply only complete evidence-linked DUN groups; retain distinctions that are not proven redundant.",
            recovery="Same-round Revert restores the pre-clear target after cleanup evidence is collected.")

        forget_instruction = {
            1: "remove any temporary rule not directly supported by the exact alphabet Source",
            2: "remove examples that introduce a word absent from the Source evidence",
            3: "remove rules that erase unresolved alternatives or their provenance",
            4: "remove generated claims unrelated to the a-is-apple mappings",
            5: "remove any temporary alphabet claim that cannot be traced to the Source",
        }[attempt]
        add("forget", attempt, ("forget", forget_instruction, "--context", target),
            entry="process-local instruction criterion", target=target,
            scope="whole temporary direct Source frame",
            provenance=f"{round_state}; checkpointed post-curation frame",
            consumer="selective curation safety trial",
            expected="Return exactly one keep/transform/drop decision per Memory and apply atomically without fabricating provenance.",
            recovery="Same-round Revert restores all pre-round target content regardless of curation outcome.")

        ground_request = {
            1: "Review how to preserve the a-is-apple mapping evidence without creating a Ground.",
            2: "Explain the recovery checkpoint boundary without creating or selecting a Ground.",
            3: "Review unresolved b alternatives without creating a Ground.",
            4: "Check provenance safety for apple and apricot without creating a Ground.",
            5: "Summarize the final transform evidence without creating a Ground.",
        }[attempt]
        add("ground", attempt, ("ground", "--request", ground_request),
            entry="natural-language starting request", target="blank unsaved Ground frame",
            scope="one provider turn, no durable Ground",
            provenance=f"{round_state}; explicit no-create boundary and no pre-existing a-is-apple Ground",
            consumer="agent-mediated planning boundary",
            expected="Return the stable unsaved proposal frame and create nothing without exact command approval.")

        impact_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: ("impact", "atomize", P),
            2: ("impact", "--from", source, "--to", target, "--direct"),
            3: lambda: ("impact", "audit", "--session", _artifact("audit", 3)),
            4: ("impact", "update", source, target, "--direct"),
            5: ("impact", "meld", "--session", "deadbeef"),
        }
        add("impact", attempt, impact_args[attempt], entry="named analysis or directional Update preview",
            target=(P if attempt == 1 else (f"{source} → {target}" if attempt in {2, 4} else "saved analysis artifact")),
            scope="read-only projected effects",
            provenance=f"{round_state}; operation-specific live or saved analysis route",
            consumer="pre-Apply effect inspection",
            expected="Preview typed effects without applying them; unavailable artifacts must fail atomically.")

        meld_result = f"practice/aia-meld-r{attempt}"
        add("meld", attempt, ("meld", source, target, meld_result),
            entry="symmetric two-source plus fresh Result plan", target=f"{source} + {target} → {meld_result}",
            scope="complete direct peer frames",
            provenance=f"{round_state}; temporary transformed target plus intact source",
            consumer="saved merge-resolution session",
            expected="Save a source-bound review session or reject invalid provider relations; do not apply without --accept.")

        merge_args = (
            "merge", source, target, "--direct",
            "--keep-target-all" if attempt % 2 else "--take-source-all",
        )
        add("merge", attempt, merge_args, entry="structural direct merge with explicit conflict policy",
            target=f"{source} → {target}", scope="direct items only",
            provenance=f"{round_state}; both endpoints covered by target recovery checkpoint",
            consumer="temporary structural integration",
            expected="Apply one atomic structural merge with explicit source/target effects and checkpoint provenance.",
            recovery="Same-round Revert restores the exact target snapshot made before Clear.")

        add("rationale", attempt,
            lambda s=source, n=source_needles, a=attempt: ("rationale", _memory_target(s, n), "--verbose") if a in {3, 5} else ("rationale", _memory_target(s, n)),
            entry="direct durable Memory selector", target=source,
            scope="one source Memory provenance explanation",
            provenance=f"{round_state}; intact non-scratch Source UID",
            consumer="why/provenance review",
            expected="Explain only durable checkpoint and source lineage; do not infer an unsupported semantic rationale.")

        add("revert", attempt,
            lambda a=attempt, t=target: ("revert", _artifact("checkpoint", a), "--context", t, "--keep"),
            entry="same-round checkpoint UID plus exact owner", target=target,
            scope="restore pre-Clear direct snapshot and retain newer history",
            provenance=f"{round_state}; checkpoint receipt is the reviewed recovery boundary",
            consumer="mandatory destructive-trial recovery",
            expected="Restore the target byte-for-byte at the Context-content level and keep the recovery history.",
            recovery="This is the recovery action; subsequent Review/Sever/Trace verify restored availability.")

        review_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: lambda: ("review", "audit", "--session", _artifact("audit", 1), "--snapshot"),
            2: lambda: ("review", "distill", "--receipt", _artifact("distill", 2), "--snapshot"),
            3: lambda: ("review", "forget", "--receipt", _artifact("forget", 3), "--snapshot"),
            4: lambda: ("review", "audit", "--session", _artifact("audit", 4), "--snapshot"),
            5: lambda: ("review", "distill", "--receipt", _artifact("distill", 5), "--snapshot"),
        }
        add("review", attempt, review_args[attempt], entry="saved session or applied receipt",
            target="round-local Audit/Distill/Forget artifact",
            scope="read-only complete review snapshot",
            provenance=f"{round_state}; UID consumed from an earlier operation receipt",
            consumer="post-recovery evidence verification",
            expected="Render the immutable saved evidence without re-running inference or applying changes.")

        sever_result = f"practice/aia-sever-r{attempt}"
        add("sever", attempt, ("sever", source, target, sever_result, "--direct"),
            entry="Source, Criteria, and fresh Result plan", target=f"{source} × {target} → {sever_result}",
            scope="whole direct Source and Criteria frames",
            provenance=f"{round_state}; restored target and intact source",
            consumer="saved selective-curation session",
            expected="Save a reviewed Result proposal while leaving Source unchanged; do not materialize without --accept.")

        add("trace", attempt,
            lambda s=source, n=source_needles, a=attempt: ("trace", _memory_target(s, n), "--limit", str(a + 2), "--verbose") if a in {3, 5} else ("trace", _memory_target(s, n), "--limit", str(a + 2)),
            entry="direct durable Memory selector", target=source,
            scope=f"bounded provenance trace depth {attempt + 2}",
            provenance=f"{round_state}; restored post-Revert state",
            consumer="lineage verification",
            expected="Render typed source/checkpoint lineage without confusing copied content with ownership.")

        language = {1: "Korean", 2: "French", 3: "Japanese", 4: "Spanish", 5: "German"}[attempt]
        add("translate", attempt,
            lambda s=source, n=source_needles, lang=language: ("translate", _memory_target(s, n), "--to", lang),
            entry="direct Memory selector plus language", target=source,
            scope=f"one read-only {language} translation view",
            provenance=f"{round_state}; restored source content and exact UID",
            consumer="cross-language understanding",
            expected="Return a translation view bound to the source digest without altering the Memory.")

        update_args = {
            1: ("update", P, P, "--direct"),
            2: ("update", S, P, "--direct", "--replace-stage"),
            3: ("update", P, S, "--direct", "--replace-stage"),
            4: ("update", S, P, "--direct", "--replace-stage", "--goal", "Preserve only source-supported alphabet mappings."),
            5: ("update", P, S, "--direct", "--replace-stage", "--goal", "Keep unresolved alternatives explicit; do not apply unsupported facts."),
        }[attempt]
        add("update", attempt, update_args, entry="directional exact endpoints with staged-review policy",
            target=(P if attempt == 1 else (f"{S} → {P}" if attempt in {2, 4} else f"{P} → {S}")),
            scope="direct Source and Target frames",
            provenance=f"{round_state}; post-Revert durable endpoints and explicit goal where supplied",
            consumer="review-only directional update plan",
            expected=("Reject same-Context Update without mutation." if attempt == 1 else "Stage or report typed changes; do not apply unsupported additions without explicit reviewed action."))

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
        "world": "a-is-apple",
        "phase": "transform",
        "status": "running",
        "contract": {"operations": 24, "attempts_per_operation": 5, "attempts": 120},
        "execution_identity": {
            "code_snapshot_sha256": CODE_SHA256,
            "catalog_sha256": CATALOG_SHA256,
            "profile_uid": PROFILE_UID,
            "store_root": str(STORE_ROOT),
            "provider_policy_sha256": PROVIDER_SHA256,
        },
        "starting_boundary": {
            "cumulative_from_core": True,
            "core_final_digest": core_digest,
            "transform_initial_digest": initial_digest,
            "matches_core_final_digest": core_digest == initial_digest,
            "no_reset": True,
            "recovery_policy": (
                "Each round checkpoints its Clear target before destructive trials, then "
                "Revert restores that exact target before post-recovery operations."
            ),
        },
        "digest_semantics": "SHA-256 over all active-Profile context.json files plus state.json in sorted path order.",
        "launcher": f"python {WORLD_RUNNER} a-is-apple",
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
        command_argv = ["python", str(WORLD_RUNNER), "a-is-apple", *args]
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
        record = {
            "operation": spec.operation,
            "attempt": spec.attempt,
            "sequence": sequence,
            "command": command,
            "exit": exit_code,
            "starting_state": (
                f"Cumulative no-reset Store at transform sequence {sequence}; "
                f"pre-command Context-tree digest {pre}; immediately follows prior post digest {prior_post}."
            ),
            "entry_route": spec.entry_route,
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
            "state_continuity": {
                "same_as_previous_post": prior_post == pre,
                "durable_context_tree_changed": pre != post,
                "one_cumulative_store": True,
            },
            "raw_output": str(raw_path.relative_to(AUDIT_ROOT)),
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
    ledger["summary"] = {
        "attempts": len(records),
        "successful_exits": sum(record["exit"] == 0 for record in records),
        "nonzero_exits": sum(record["exit"] != 0 for record in records),
        "durable_context_tree_mutations": sum(record["state_continuity"]["durable_context_tree_changed"] for record in records),
        "continuity_breaks": sum(not record["state_continuity"]["same_as_previous_post"] for record in records),
        "wall_seconds": round(sum(record["cost"]["wall_seconds"] for record in records), 3),
    }
    _save(ledger)


if __name__ == "__main__":
    main()
