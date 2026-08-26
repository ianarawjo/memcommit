#!/usr/bin/env python3
"""Run and checkpoint the counted a-is-apple CORE audit lane.

This campaign script is evidence infrastructure, not product code.  It invokes
every counted command through the frozen world runner and writes after every
attempt so an interrupted lane can resume without replaying mutations.
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
AUDIT_ROOT = REPOSITORY / "outputs/study-long-audit-20260825-v2"
WORLD_ROOT = AUDIT_ROOT / "worlds/a-is-apple"
RAW_ROOT = WORLD_ROOT / "raw/core"
WORLD_RUNNER = AUDIT_ROOT / "run_world_mem.py"
STORE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/a-is-apple/profile-control/"
    "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
CONTEXTS_ROOT = STORE_ROOT / "contexts"
LEDGER_PATH = WORLD_ROOT / "phase-core.json"

CODE_SHA256 = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA256 = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROVIDER_SHA256 = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"

P = "practice"
S = "practice/source"
D = "practice/description"


@dataclass(frozen=True)
class CommandSpec:
    operation: str
    attempt: int
    args: tuple[str, ...] | Callable[[], tuple[str, ...]]
    starting_state: str
    entry_route: str
    target_route: str
    scope: str
    input_provenance: str
    consumer: str
    expected: str
    recovery_evidence: str


def _context_data(name: str) -> dict:
    path = CONTEXTS_ROOT / name / "context.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _selector(
    context: str,
    needle: str,
    *,
    exact: bool = False,
    last: bool = True,
) -> str:
    data = _context_data(context)
    matches: list[str] = []
    for uid in data.get("order", []):
        item = data.get("memories", {}).get(uid, {})
        if item.get("type") != "memory":
            continue
        content = item.get("content", "")
        if (content == needle) if exact else (needle in content):
            matches.append(uid)
    uid = matches[-1 if last else 0] if matches else "missing0000000000000000000000000000"
    return f"{context}:{uid[:8]}"


def _context_tree_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(CONTEXTS_ROOT.rglob("context.json")):
        digest.update(path.relative_to(STORE_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    state_path = STORE_ROOT / "state.json"
    digest.update(b"state.json\0")
    digest.update(state_path.read_bytes())
    return digest.hexdigest()


def _clean_output(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
    text = text.replace("\r", "")
    lines = [line.rstrip() for line in text.splitlines()]
    nonempty = [line for line in lines if line.strip()]
    if not nonempty:
        return "No stdout/stderr text was emitted."
    head = " | ".join(nonempty[:4])
    if len(nonempty) > 4:
        head += f" | … ({len(nonempty)} non-empty lines total)"
    return head[:1200]


def _specs() -> list[CommandSpec]:
    specs: list[CommandSpec] = []

    def add(
        operation: str,
        attempt: int,
        args: tuple[str, ...] | Callable[[], tuple[str, ...]],
        *,
        state: str,
        entry: str,
        target: str,
        scope: str,
        provenance: str,
        consumer: str,
        expected: str,
        recovery: str = "No recovery required; later interleaved attempts verify continuity.",
    ) -> None:
        specs.append(
            CommandSpec(
                operation,
                attempt,
                args,
                state,
                entry,
                target,
                scope,
                provenance,
                consumer,
                expected,
                recovery,
            )
        )

    round_states = {
        1: (
            "Round 1 starts at exact `practice`, whose direct Memory set is empty. "
            "The frozen template already has nonempty `practice/description` and "
            "`practice/source` descendants; no a-is-apple Ground exists."
        ),
        2: (
            "Round 2 follows the first a→apple Memory, deliberate same-Context copy "
            "and Reference, edit, and boundary attempts; the Store is not reset."
        ),
        3: (
            "Round 3 follows b→banana placement in `practice/source`, an a→apple "
            "provenance copy, Source Reference, and Source embed into `practice`."
        ),
        4: (
            "Round 4 follows a deliberate b→boat conflict and cross-Context copy, "
            "Reference, edit, move, chunk, comparison, and quality review."
        ),
        5: (
            "Round 5 uses the late cumulative Store after an exact a→apple duplicate, "
            "an a→apricot conflict, a b→blueberry replacement, and added provenance."
        ),
    }

    for attempt in range(1, 6):
        state = round_states[attempt]

        # Read and inference routes appear before the round's mutation so they
        # observe a real cumulative boundary rather than a post-hoc fixture.
        add("contexts", attempt, ("contexts",), state=state,
            entry="global readable-Context inventory", target="Profile readable namespace",
            scope="all readable Contexts", provenance="frozen Study Profile plus cumulative lane state",
            consumer="orientation and current-Context safety",
            expected="List the readable namespace and keep current Context `practice` visible without mutation.")

        list_args = {
            1: ("list", "--direct", P),
            2: ("list", "--recursive", P),
            3: ("list", "--direct", S),
            4: ("list", "--recursive", P),
            5: ("list", "--recursive", P),
        }[attempt]
        add("list", attempt, list_args, state=state,
            entry="explicit Context operand", target=P if attempt != 3 else S,
            scope="direct exact" if attempt in {1, 3} else "recursive lexical and embedded",
            provenance="cumulative durable Context contents", consumer="inventory and UID recovery",
            expected="Render the selected Context scope with stable Memory and provenance identifiers.")

        show_args = {
            1: ("show", "--direct", "--context", P),
            2: ("show", "--recursive", "--context", P),
            3: ("show", "--recursive", "--context", P),
            4: ("show", "--direct", "--context", S),
            5: ("show", "--recursive", "--context", P),
        }[attempt]
        add("show", attempt, show_args, state=state,
            entry="explicit --context", target=P if attempt != 4 else S,
            scope="direct exact" if attempt in {1, 4} else "recursive lexical and embedded",
            provenance="cumulative durable Context contents", consumer="read-only provenance review",
            expected="Display the requested Context and preserve the distinction between direct, descendant, Reference, and embedded content.")

        find_args = {
            1: ("find", "apple", "--direct", "--context", P),
            2: ("find", "apple", "--recursive", "--context", P),
            3: ("find", "banana|boat", "--regex", "--context", P, "--context", S),
            4: ("find", "apple|apricot|banana|boat", "--regex", "--recursive", "--context", P),
            5: ("find", "^[abc] (is|maps)", "--regex", "--recursive", "--context", P, "--all-results"),
        }[attempt]
        add("find", attempt, find_args, state=state,
            entry="literal search" if attempt in {1, 2} else "regex search",
            target=P if attempt not in {3} else f"{P} + {S}",
            scope="direct exact" if attempt == 1 else ("multiple exact" if attempt == 3 else "recursive"),
            provenance="typed query over frozen-at-command-start Context scope", consumer="mapping and conflict discovery",
            expected="Return only matching visible Memories, with zero-result behavior explicit and recursive provenance retained.")

        search_args = {
            1: ("search", "alphabet letter to word mapping", "--context", P, "--limit", "5"),
            2: ("search", "current a to apple mapping and its provenance", "--context", P, "--context", S, "--limit", "6"),
            3: ("search", "conflicting mappings for the letter b", "--context", P, "--context", S, "--limit", "8"),
            4: ("search", "evidence and provenance for alphabet mapping conflicts", "--context", P, "--context", S, "--limit", "8"),
            5: ("search", "preferred final alphabet mappings and unresolved alternatives", "--context", P, "--context", S, "--limit", "10"),
        }[attempt]
        add("search", attempt, search_args, state=state,
            entry="semantic retrieval", target=P if attempt == 1 else f"{P} + {S}",
            scope="exact top-k" if attempt == 1 else "multiple exact top-k",
            provenance="query text plus frozen visible candidate set", consumer="semantic evidence retrieval",
            expected="Return ranked visible evidence without inventing absent mappings or mutating the Store.")

        query_args = {
            1: ("query", "What alphabet-to-word mappings are stored?", "--context", P),
            2: ("query", "What is mapped to the letter a, and what uncertainty remains?", "--recursive", "--context", P),
            3: ("query", "Which mappings are established, provisional, or conflicting?", "--recursive", "--context", P),
            4: ("query", "What conflicts and provenance records are visible?", "--recursive", "--context", P),
            5: ("query", "State the best-supported mappings for a, b, and c while preserving unresolved alternatives and provenance.", "--recursive", "--context", P),
        }[attempt]
        add("query", attempt, query_args, state=state,
            entry="ordinary provider-backed query", target=P,
            scope="exact" if attempt == 1 else "recursive lexical and embedded",
            provenance="question plus typed readable Source frame", consumer="grounded answer",
            expected="Answer only from visible Memories, explicitly report empty or conflicting evidence, and retain citations.")

        summarize_args = {
            1: ("summarize", P, "--plain"),
            2: ("summarize", P, "--recursive", "--plain"),
            3: ("summarize", S, "--plain"),
            4: ("summarize", P, "--recursive", "--plain"),
            5: ("summarize", S, "--plain"),
        }[attempt]
        add("summarize", attempt, summarize_args, state=state,
            entry="explicit Context operand", target=P if attempt in {1, 2, 4} else S,
            scope="direct exact" if attempt in {1, 3, 5} else "recursive",
            provenance="complete visible Source frame", consumer="compact world understanding",
            expected="Produce a bounded source-grounded summary, or a clear empty result, without durable mutation.")

        add_args = {
            1: ("add", "a is apple.", "--context", P),
            2: ("add", "b is banana.", "--context", S),
            3: ("add", "b is boat.", "--context", S),
            4: ("add", "a is apple.", "--context", S),
            5: ("add", "Canonical set: a is apple; b is banana; c is cedar; unresolved alternatives remain explicit.", "--context", P),
        }[attempt]
        add("add", attempt, add_args, state=state,
            entry="single exact CLI Memory", target=P if attempt in {1, 5} else S,
            scope="one direct target Context", provenance="world-authored exact statement",
            consumer="cumulative alphabet knowledge set",
            expected="Atomically add exactly one Memory and return its target, UID, and checkpoint provenance.")

        copy_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: lambda: ("copy", _selector(P, "a is apple.", exact=True), "--into", P),
            2: lambda: ("copy", _selector(P, "a is apple.", exact=True, last=False), "--into", S),
            3: lambda: ("copy", _selector(S, "b is banana.", exact=True, last=False), "--into", P),
            4: lambda: ("copy", _selector(S, "b is boat.", exact=True, last=False), "--into", S),
            5: lambda: ("copy", _selector(P, "Canonical set:", last=False), "--into", S),
        }
        add("copy", attempt, copy_args[attempt], state=state,
            entry="direct Memory selector", target=(P if attempt in {1, 3} else S),
            scope="single Memory transfer", provenance="UID from immediately prior cumulative Store state",
            consumer="duplicate and provenance experiment",
            expected="Create an independent Memory copy in the exact destination while preserving traceable source identity.")

        reference_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: lambda: ("reference", _selector(P, "a is apple.", exact=True, last=False), "--into", P),
            2: lambda: ("reference", _selector(S, "b is banana.", exact=True, last=False), "--into", P),
            3: lambda: ("reference", _selector(S, "b is boat.", exact=True, last=False), "--into", P),
            4: lambda: ("reference", _selector(S, "a is apple.", exact=True, last=False), "--into", P),
            5: lambda: ("reference", _selector(P, "Canonical set:", last=False), "--into", S),
        }
        add("reference", attempt, reference_args[attempt], state=state,
            entry="direct Memory selector", target=P if attempt in {1, 2, 3, 4} else S,
            scope="single immutable snapshot Reference", provenance="UID from prior Add/Copy state",
            consumer="provenance-preserving evidence trail",
            expected="Create a snapshot Reference without changing or duplicating the source Memory itself.")

        embed_args = {
            1: ("embed", P, "--into", P),
            2: ("embed", S, "--into", P),
            3: ("embed", S, "--into", P),
            4: ("embed", D, "--into", P),
            5: ("embed", S, "--into", P),
        }[attempt]
        embed_expected = (
            "Reject the self-embed before mutation and explain the cycle boundary."
            if attempt == 1
            else (
                "Reject the already-present embed without duplicating it and leave the prior projection usable."
                if attempt in {3, 5}
                else "Add one Context embed with visible source ownership and no copied Memory bodies."
            )
        )
        add("embed", attempt, embed_args, state=state,
            entry="explicit source and --into Contexts", target=P,
            scope="single Context projection", provenance="existing local Context identity",
            consumer="recursive working view", expected=embed_expected,
            recovery="Expected safe boundary; later Show/List/Find attempts verify no partial embed and existing projections remain usable.")

        edit_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: lambda: ("edit", _selector(P, "a is apple.", exact=True, last=True), "a maps to apple; this edited duplicate retains the original assertion."),
            2: lambda: ("edit", _selector(S, "a is apple.", exact=True, last=True), "a maps to apple; copied from the original direct Memory for provenance."),
            3: lambda: ("edit", _selector(P, "b is banana.", exact=True, last=True), "b is banana; this copied mapping is provisional while boat remains visible."),
            4: lambda: ("edit", _selector(S, "a is apple.", exact=True, last=True), "a maps to apricot; this is a deliberate conflicting alternative for recovery testing."),
            5: lambda: ("edit", _selector(S, "Canonical set:", last=True), "Preferred set: a is apple; b is banana; c is cedar; unresolved alternatives remain explicit."),
        }
        add("edit", attempt, edit_args[attempt], state=state,
            entry="direct Memory selector plus replacement body", target=P if attempt in {1, 3} else S,
            scope="one exact Memory", provenance="UID recovered from prior Copy/Add",
            consumer="edit and conflict history",
            expected="Replace exactly one selected Memory, preserve its UID, and create a reviewable checkpoint.")

        move_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: lambda: ("move", _selector(P, "edited duplicate", last=True), "--into", P),
            2: lambda: ("move", _selector(S, "copied from the original", last=True), "--into", P),
            3: lambda: ("move", _selector(P, "copied mapping is provisional", last=True), "--into", S),
            4: lambda: ("move", _selector(S, "deliberate conflicting alternative", last=True), "--into", P),
            5: lambda: ("move", _selector(S, "Preferred set:", last=True), "--into", P),
        }
        add("move", attempt, move_args[attempt], state=state,
            entry="direct Memory selector plus --into", target=P if attempt in {1, 2, 4, 5} else S,
            scope="single Memory relocation", provenance="UID from prior Edit",
            consumer="provenance-preserving organization",
            expected=("Reject a same-Context move as a safe no-op without mutation." if attempt == 1 else "Move exactly one Memory atomically, retaining its UID and recording both endpoints."),
            recovery=("Expected safe boundary; the next round verifies the edited Memory remains in `practice`." if attempt == 1 else "No recovery required; later List/Show verifies source and destination continuity."))

        replace_args = {
            1: ("replace", "banana", "boat", "--direct", "--context", P, "--plain"),
            2: ("replace", "canonical", "preferred", "--direct", "--context", S, "--plain"),
            3: ("replace", "cherry", "cedar", "--direct", "--context", S, "--plain"),
            4: ("replace", "boat", "blueberry", "--direct", "--context", S, "--plain"),
            5: ("replace", "Canonical set", "Preferred set", "--direct", "--context", P, "--plain"),
        }[attempt]
        add("replace", attempt, replace_args, state=state,
            entry="literal old/new text", target=P if attempt in {1, 5} else S,
            scope="direct exact Context", provenance="cumulative Memory bodies",
            consumer="bulk correction and no-match boundary",
            expected=("Report zero matches and publish no checkpoint for an absent literal." if attempt in {1, 2, 3} else "Replace every direct exact occurrence, report affected UIDs, and publish one atomic checkpoint."),
            recovery="Later exact Find/List attempts verify whether the replacement did or did not publish changes.")

        chunk_args: dict[int, tuple[str, ...] | Callable[[], tuple[str, ...]]] = {
            1: lambda: ("chunk", _selector(P, "edited duplicate", last=True), "--method", "clauses", "--max-chars", "45"),
            2: lambda: ("chunk", _selector(P, "copied from the original", last=True), "--method", "clauses", "--max-chars", "45"),
            3: lambda: ("chunk", _selector(S, "copied mapping is provisional", last=True), "--method", "clauses", "--max-chars", "42"),
            4: lambda: ("chunk", _selector(P, "deliberate conflicting alternative", last=True), "--method", "clauses", "--max-chars", "42"),
            5: lambda: ("chunk", _selector(P, "Preferred set:", last=True), "--method", "clauses", "--max-chars", "48"),
        }
        add("chunk", attempt, chunk_args[attempt], state=state,
            entry="direct Memory selector with clause method", target=P if attempt in {1, 2, 4, 5} else S,
            scope="one Memory, bounded chunk size", provenance="UID from earlier Edit/Move/Replace",
            consumer="atomic statement decomposition",
            expected="Split the selected Memory without silent content loss, return created UIDs, and keep checkpoint provenance.")

        compare_args = {
            1: ("compare", P, P, "--snapshot"),
            2: ("compare", P, S, "--snapshot"),
            3: ("compare", S, P, "--snapshot"),
            4: ("compare", P, S, "--snapshot"),
            5: ("compare", P, S, "--snapshot"),
        }[attempt]
        add("compare", attempt, compare_args, state=state,
            entry="two explicit Context operands", target=P if attempt == 1 else f"{P} ↔ {S}",
            scope="snapshot analysis", provenance="frozen Context snapshots after round mutations",
            consumer="difference and provenance review",
            expected=("Explain or represent identical-input comparison without inventing differences." if attempt == 1 else "Compare both complete direct frames and retain source-linked evidence without applying changes."))

        quality_context = P if attempt in {1, 4, 5} else S
        for operation, purpose in (
            ("find-duplicates", "exact or semantic duplicate review"),
            ("find-redundancies", "overlap and subsumption review"),
            ("find-ambiguities", "underspecification review"),
            ("find-conflicts", "contradiction review"),
        ):
            args = (operation, quality_context, "--direct") if operation in {"find-duplicates", "find-redundancies"} else (operation, quality_context)
            add(operation, attempt, args, state=state,
                entry="explicit Context operand", target=quality_context,
                scope="direct exact Context", provenance="post-mutation cumulative Source frame",
                consumer=purpose,
                expected="Analyze the complete frozen direct frame, expose evidence-linked findings or an explicit none result, and make no unreviewed Apply.")

        fit_args = {
            1: ("fit", "--context", P, "--context", P),
            2: ("fit", "--context", P, "--context", S),
            3: ("fit", "--context", S, "--context", P),
            4: ("fit", "--context", P, "--context", S),
            5: ("fit", "--context", P, "--context", S),
        }[attempt]
        add("fit", attempt, fit_args, state=state,
            entry="repeatable explicit --context", target=P if attempt == 1 else f"{P} + {S}",
            scope="whole selected direct frames", provenance="frozen post-round Context snapshots",
            consumer="global coherence judgment",
            expected=("Handle the same Context supplied twice without double-counting or invented mismatch." if attempt == 1 else "Judge combined coherence while preserving conflicts, provenance, and the distinction between source frames."))

    return specs


def _new_ledger() -> dict:
    return {
        "schema_version": 2,
        "world": "a-is-apple",
        "phase": "core",
        "status": "running",
        "contract": {"operations": 21, "attempts_per_operation": 5, "attempts": 105},
        "execution_identity": {
            "code_snapshot_sha256": CODE_SHA256,
            "catalog_sha256": CATALOG_SHA256,
            "profile_uid": PROFILE_UID,
            "store_root": str(STORE_ROOT),
            "provider_policy_sha256": PROVIDER_SHA256,
        },
        "starting_boundary": {
            "world_context": P,
            "direct_memory_count": 0,
            "dedicated_a_is_apple_context_present": False,
            "ground_present": False,
            "limitation": (
                "The frozen template has no dedicated audit/a-is-apple Context and "
                "uncounted initialization is forbidden. Exact `practice` is therefore "
                "the empty starting namespace. Existing nonempty description/source "
                "descendants are disclosed and used only as lane-local provenance and "
                "conflict scratch in later attempts."
            ),
        },
        "digest_semantics": (
            "pre_target_digest and post_target_digest are SHA-256 over every active-Profile "
            "context.json plus state.json, in sorted relative-path order. This catches all "
            "durable Context-tree mutations while excluding caches, analysis artifacts, and locks."
        ),
        "launcher": f"python {WORLD_RUNNER} a-is-apple",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "operations": {op: {"attempts": []} for op in (
            "contexts", "list", "show", "find", "search", "query", "summarize",
            "add", "copy", "reference", "embed", "edit", "move", "replace",
            "chunk", "compare", "find-duplicates", "find-redundancies",
            "find-ambiguities", "find-conflicts", "fit",
        )},
    }


def _save(ledger: dict) -> None:
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    WORLD_ROOT.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8")) if LEDGER_PATH.exists() else _new_ledger()
    completed_sequences = {
        attempt["sequence"]
        for operation in ledger["operations"].values()
        for attempt in operation["attempts"]
    }
    prior_records = sorted(
        (
            attempt
            for operation in ledger["operations"].values()
            for attempt in operation["attempts"]
        ),
        key=lambda item: item["sequence"],
    )
    prior_post = prior_records[-1]["post_target_digest"] if prior_records else None

    specs = _specs()
    if len(specs) != 105:
        raise RuntimeError(f"CORE spec must contain 105 attempts, found {len(specs)}")
    counts: dict[str, int] = {}
    for spec in specs:
        counts[spec.operation] = counts.get(spec.operation, 0) + 1
    if set(counts.values()) != {5} or len(counts) != 21:
        raise RuntimeError(f"CORE spec operation count mismatch: {counts}")

    for sequence, spec in enumerate(specs, start=1):
        if sequence in completed_sequences:
            continue
        args = spec.args() if callable(spec.args) else spec.args
        command_argv = ["python", str(WORLD_RUNNER), "a-is-apple", *args]
        command = shlex.join(command_argv)
        pre_digest = _context_tree_digest()
        began = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(
                command_argv,
                cwd=REPOSITORY,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=300,
                check=False,
            )
            exit_code = completed.returncode
            output = completed.stdout
        except subprocess.TimeoutExpired as error:
            timed_out = True
            exit_code = 124
            partial = error.stdout or ""
            output = partial if isinstance(partial, str) else partial.decode("utf-8", "replace")
            output += "\nAUDIT RUNNER TIMEOUT after 300 seconds; child process was terminated.\n"
        elapsed = time.monotonic() - began
        post_digest = _context_tree_digest()
        raw_path = RAW_ROOT / f"{sequence:03d}-{spec.operation}-{spec.attempt}.txt"
        raw_path.write_text(
            f"COMMAND\n{command}\n\nEXIT\n{exit_code}\n\nOUTPUT\n{output}",
            encoding="utf-8",
        )
        record = {
            "attempt": spec.attempt,
            "sequence": sequence,
            "command": command,
            "exit": exit_code,
            "starting_state": spec.starting_state,
            "entry_route": spec.entry_route,
            "target_route": spec.target_route,
            "scope": spec.scope,
            "input_provenance": spec.input_provenance,
            "consumer": spec.consumer,
            "expected": spec.expected,
            "actual": _clean_output(output),
            "defect_ids": [],
            "cost": {
                "wall_seconds": round(elapsed, 3),
                "output_bytes": len(output.encode("utf-8")),
                "timed_out": timed_out,
            },
            "pre_target_digest": pre_digest,
            "post_target_digest": post_digest,
            "recovery_evidence": spec.recovery_evidence,
            "state_continuity": {
                "same_as_previous_post": prior_post is None or prior_post == pre_digest,
                "durable_context_tree_changed": pre_digest != post_digest,
                "one_cumulative_store": True,
            },
            "raw_output": str(raw_path.relative_to(AUDIT_ROOT)),
        }
        ledger["operations"][spec.operation]["attempts"].append(record)
        ledger["last_completed_sequence"] = sequence
        ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save(ledger)
        prior_post = post_digest
        print(
            f"[{sequence:03d}/105] {spec.operation}#{spec.attempt} "
            f"exit={exit_code} {elapsed:.2f}s changed={pre_digest != post_digest}",
            flush=True,
        )

    ledger["status"] = "complete"
    ledger["completed_at"] = datetime.now(timezone.utc).isoformat()
    ledger["attempt_count"] = sum(
        len(operation["attempts"]) for operation in ledger["operations"].values()
    )
    _save(ledger)


if __name__ == "__main__":
    main()
