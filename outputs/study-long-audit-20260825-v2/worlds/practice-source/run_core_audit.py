#!/usr/bin/env python3
"""Run and capture the 105 counted practice-source core attempts."""

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
RAW = ROOT / "raw" / "core"
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
PHASE_PATH = ROOT / "phase-core.json"

OPERATIONS = (
    "contexts", "list", "show", "find", "search", "query", "summarize",
    "add", "copy", "reference", "embed", "edit", "move", "replace",
    "chunk", "compare", "find-duplicates", "find-redundancies",
    "find-ambiguities", "find-conflicts", "fit",
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

ADD_CONTENT = {
    1: "AUDIT DRAFT: distinguish review-only requests from authorized editing before changing text.",
    2: "CANDIDATE: preserve structure and citation-needed markers. Change only wording that causes a problem.",
    3: "CANDIDATE: when a shorter fixed limit applies, target approximately 20-30% cuts from redundant or unnecessary material. Preserve every intended point and each claim's original strength and conditions.",
    4: "CANDIDATE: use sentence case for document titles by default, subject only to an explicitly named style guide capitalization override; preserve the intended word for. Use consistent italics for work titles by default, subject only to an explicitly named style guide work-title-format override.",
    5: "AUDIT RESULT: mechanical sentence splitting can detach permissions, triggers, exceptions, and companion safeguards. Future atomize must retain each constraint's complete applicability boundary and provenance.",
}

EDIT_CONTENT = {
    1: "AUDIT DRAFT: classify intent as review-only or authorized editing before changing text; preserve requested scope and source meaning.",
    2: "CANDIDATE: during authorized polishing, preserve overall structure and citation-needed markers. Change only wording that causes a problem.",
    3: "CANDIDATE: if a shorter fixed limit applies, aim to remove approximately 20-30% from redundant or unnecessary material. Preserve all intended points plus every claim's original strength and conditions.",
    4: "CANDIDATE: use sentence case for document titles by default, subject only to an explicitly named style guide capitalization override; preserve the intended word for. Use consistent italics for work titles by default, subject only to an explicitly named style guide work-title-format override.",
    5: "AUDIT RESULT: mechanical sentence splitting detached an editing permission trigger, a protected-word object, and companion safeguards. Future atomize must keep every result independently reviewable with its complete trigger, exception, safeguard, and source provenance.",
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


def memory_prefix_with_text(context_name: str, fragment: str, *, last: bool = False) -> str:
    data = json.loads(context_path(context_name).read_text(encoding="utf-8"))
    matches = [
        uid[:8]
        for uid, item in data.get("memories", {}).items()
        if item.get("type") == "memory" and fragment in item.get("content", "")
    ]
    if not matches:
        raise RuntimeError(f"no Memory containing {fragment!r} in {context_name}")
    return matches[-1] if last else matches[0]


def extract_added_uid(output: str) -> str:
    match = re.search(r"Added \[([0-9a-f]{8})\]", output)
    if not match:
        raise RuntimeError(f"could not extract Add UID from: {output[:500]}")
    return match.group(1)


def extract_copy_uids(output: str) -> list[str]:
    values = re.findall(r"→ \[([0-9a-f]{8})\]", output)
    if not values:
        raise RuntimeError(f"could not extract Copy UID from: {output[:500]}")
    return values


def compact_actual(stdout: str, stderr: str, exit_code: int) -> str:
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return f"Exited {exit_code} with no visible output."
    selected = lines if len(lines) <= 6 else lines[:4] + ["…"] + lines[-2:]
    return f"Exit {exit_code}. " + " | ".join(selected)[:1800]


def expected_for(operation: str, round_number: int) -> str:
    values = {
        "contexts": "Show the frozen readable Profile catalog and retain the growing practice hierarchy without changing state.",
        "list": "Render complete direct-item inventory for the requested Context so later operations can reuse stable UIDs.",
        "show": "Render the complete selected Memory and its owner without mutating it.",
        "find": "Return exact lexical matches with owner, UID, and complete enough content to inspect the constraint boundary.",
        "search": "Semantically search every requested frozen Context and make multi-root coverage or zero-result branches legible.",
        "query": "Answer from the requested source frame while preserving applicability triggers and showing reusable provenance.",
        "summarize": "Summarize the requested visible evidence and disclose any direct-only exclusion of References or Embeds.",
        "add": "Add only the exact audit candidate to scratch and report its reusable UID.",
        "copy": "Copy only selected source Memories into scratch and report complete source-to-new UID mappings.",
        "reference": "Create a read-only snapshot Reference in scratch without altering practice/source and report its identity.",
        "embed": "Create the requested live Context Embed, or reject duplicate/cyclic structure before mutation with a clear recovery path.",
        "edit": "Edit only the exact scratch Memory and report the resulting identity while preserving practice/source.",
        "move": "Move only the exact scratch Memory, preserving/retargeting links atomically and reporting both endpoints.",
        "replace": "Replace only matching scratch text, expose affected Memories, and leave all state unchanged on no-match.",
        "chunk": "Split only the selected scratch candidate and report every resulting full UID/text so semantic loss can be reviewed.",
        "compare": "Compare the complete requested frames and explain coverage, differences, and provenance without mutation.",
        "find-duplicates": "Inspect the declared exact/recursive item scope and state both its corpus cardinality and duplicate disposition.",
        "find-redundancies": "Inspect the declared ordinary-Memory scope and state its corpus cardinality and semantic redundancy disposition.",
        "find-ambiguities": "Identify underspecified applicability, object, exception, or provenance boundaries with source-linked evidence.",
        "find-conflicts": "Identify real or split-induced conflicts and preserve exact participant provenance.",
        "fit": "Explain whether and how source constraints fit the scratch frame, including missing or damaged boundary mappings.",
    }
    suffix = (
        " This is the direct baseline method." if round_number == 1 else
        " This exercises hierarchical or broadened scope." if round_number == 2 else
        " This consumes a prior operation's stored result." if round_number == 3 else
        " This exercises an empty, duplicate, cyclic, ambiguous, or protected boundary." if round_number == 4 else
        " This reopens the operation against later accumulated state."
    )
    return values[operation] + suffix


def route_meta(operation: str, round_number: int, targets: tuple[str, ...]) -> dict[str, str]:
    route = ", ".join(targets) if targets else "Profile readable catalog"
    mutating = operation in {"add", "copy", "reference", "embed", "edit", "move", "replace", "chunk"}
    return {
        "starting_state": f"Frozen v2 lane; cumulative practice scratch at round {round_number}; source guard active.",
        "entry_route": "pinned non-interactive CLI" + (" with exact operand" if targets else " inventory"),
        "target_route": route,
        "scope": "exact declared Context/Memory operands" if targets else "all Profile-readable Context names",
        "input_provenance": "fixed practice/source fixture plus prior counted scratch outputs" if round_number >= 3 else "fixed practice fixture and audit-authored scratch input",
        "consumer": "later atomization safety analysis" if not mutating else "cumulative scratch preparation for later atomization review",
    }


def commands_for(round_number: int, state: dict[str, object]) -> list[tuple[str, list[str], tuple[str, ...], str]]:
    s = SOURCE_UIDS
    added = {**{index: "PENDING" for index in range(1, 6)}, **state["added"]}
    copied = {
        **{index: ["PENDING", "PENDING"] for index in range(1, 6)},
        **state["copied"],
    }
    if round_number == 1:
        return [
            ("contexts", ["contexts"], (), "profile baseline"),
            ("list", ["list", "practice/source"], ("practice/source",), "exact source inventory"),
            ("show", ["show", f"practice/source:{s['review']}"], ("practice/source",), "exact review-intent UID"),
            ("find", ["find", "don't", "--context", "practice/source"], ("practice/source",), "literal boundary search"),
            ("search", ["search", "Which constraints distinguish review from editing and preserve meaning during revision?", "--context", "practice/source", "--context-only", "--exclude-embeds", "--limit", "6"], ("practice/source",), "semantic direct-only retrieval"),
            ("query", ["query", "--context", "practice/source", "What must a reviewer preserve, and when must they avoid editing?"], ("practice/source",), "source-grounded question"),
            ("summarize", ["summarize", "practice/source"], ("practice/source",), "full source summary"),
            ("add", ["add", ADD_CONTENT[1], "--context", "practice"], ("practice",), "audit-authored baseline candidate"),
            ("copy", ["copy", f"practice/source:{s['review']}", "--into", "practice"], ("practice/source", "practice"), "source UID selected by Show"),
            ("reference", ["reference", f"practice/source:{s['citations']}", "--into", "practice"], ("practice/source", "practice"), "source citation snapshot"),
            ("embed", ["embed", "practice/source", "--into", "practice"], ("practice/source", "practice"), "live source edge"),
            ("edit", ["edit", f"practice:{added[1]}", EDIT_CONTENT[1]], ("practice",), "UID returned by Add"),
            ("move", ["move", f"practice:{copied[1][0]}", "--into", "practice/description"], ("practice", "practice/description"), "new UID returned by Copy"),
            ("replace", ["replace", "AUDIT DRAFT", "CANDIDATE", "--context", "practice"], ("practice",), "exact scratch label"),
            ("chunk", ["chunk", f"practice:{added[1]}", "--method", "sentences"], ("practice",), "edited candidate UID"),
            ("compare", ["compare", "practice/source", "practice"], ("practice/source", "practice"), "source versus early scratch"),
            ("find-duplicates", ["find-duplicates", "practice"], ("practice",), "direct structural inventory"),
            ("find-redundancies", ["find-redundancies", "practice", "--direct"], ("practice",), "direct ordinary Memories"),
            ("find-ambiguities", ["find-ambiguities", "practice"], ("practice",), "early scratch"),
            ("find-conflicts", ["find-conflicts", "practice"], ("practice",), "early scratch"),
            ("fit", ["fit", "practice/source", "practice"], ("practice/source", "practice"), "source-to-scratch baseline"),
        ]
    if round_number == 2:
        return [
            ("contexts", ["contexts"], (), "catalog after first mutations"),
            ("list", ["list", "practice"], ("practice",), "mixed Memory/Reference/Embed inventory"),
            ("show", ["show", f"practice/source:{s['polish']}"], ("practice/source",), "polishing UID"),
            ("find", ["find", "strucutre|redundent|titlle|refferences", "--regex", "--context", "practice/source", "--all-results"], ("practice/source",), "regex typo boundary"),
            ("search", ["search", "Which notes constrain structure, wording, citations, and factual verification?", "--context", "practice/source", "--context-only", "--exclude-embeds", "--limit", "7"], ("practice/source",), "broader semantic family"),
            ("query", ["query", "--context", "practice/source", "What are the exact title, terminology, and style-guide override rules?"], ("practice/source",), "conditional override question"),
            ("summarize", ["summarize", "practice"], ("practice",), "mixed direct-item scratch"),
            ("add", ["add", ADD_CONTENT[2], "--context", "practice"], ("practice",), "two-sentence polishing candidate"),
            ("copy", ["copy", f"practice/source:{s['polish']}", "--into", "practice"], ("practice/source", "practice"), "polishing source selected by Show"),
            ("reference", ["reference", f"practice/source:{s['lookup']}", "--into", "practice/description"], ("practice/source", "practice/description"), "original-source lookup snapshot"),
            ("embed", ["embed", "practice/source", "--into", "practice/description"], ("practice/source", "practice/description"), "same source into sibling scratch"),
            ("edit", ["edit", f"practice:{added[2]}", EDIT_CONTENT[2]], ("practice",), "second Add UID"),
            ("move", ["move", f"practice:{copied[2][0]}", "--into", "practice/description"], ("practice", "practice/description"), "second Copy UID"),
            ("replace", ["replace", "CANDIDATE", "REVIEW CANDIDATE", "--context", "practice"], ("practice",), "all matching scratch labels"),
            ("chunk", ["chunk", f"practice:{added[2]}", "--method", "sentences"], ("practice",), "two-sentence edited candidate"),
            ("compare", ["compare", "practice/source", "practice/description"], ("practice/source", "practice/description"), "source versus sibling scratch"),
            ("find-duplicates", ["find-duplicates", "practice", "--recursive"], ("practice", "practice/description", "practice/source"), "recursive practice tree"),
            ("find-redundancies", ["find-redundancies", "practice/description", "--direct"], ("practice/description",), "direct sibling Memories"),
            ("find-ambiguities", ["find-ambiguities", "practice/source"], ("practice/source",), "fixed source ambiguities"),
            ("find-conflicts", ["find-conflicts", "practice/source"], ("practice/source",), "fixed source conflicts"),
            ("fit", ["fit", "practice/source", "practice"], ("practice/source", "practice"), "source to mixed scratch"),
        ]
    if round_number == 3:
        split_uid = memory_prefix_with_text("practice", "authorized polishing")
        return [
            ("contexts", ["contexts"], (), "catalog after split"),
            ("list", ["list", "practice"], ("practice",), "discover generated split UIDs"),
            ("show", ["show", f"practice:{split_uid}"], ("practice",), "UID discovered from prior Chunk/List"),
            ("find", ["find", "default", "--context", "practice/source"], ("practice/source",), "literal defaults"),
            ("search", ["search", "What conditions limit shortening and redundancy removal without strengthening claims?", "--context", "practice/source", "--context", "practice", "--context-only", "--exclude-embeds", "--limit", "6"], ("practice/source", "practice"), "two-root retrieval"),
            ("query", ["query", "--context", "practice/source", "How should shortening preserve claims while meeting a fixed limit?"], ("practice/source",), "cross-Memory synthesis"),
            ("summarize", ["summarize", "practice/description"], ("practice/description",), "prior Copy/Reference/Embed result"),
            ("add", ["add", ADD_CONTENT[3], "--context", "practice"], ("practice",), "fixed-limit compound candidate"),
            ("copy", ["copy", f"practice/source:{s['all_points']}", f"practice/source:{s['strength']}", "--into", "practice"], ("practice/source", "practice"), "two source UIDs from Query"),
            ("reference", ["reference", f"practice/source:{s['fixed_limit']}", "--into", "practice"], ("practice/source", "practice"), "fixed-limit snapshot"),
            ("embed", ["embed", "practice/description", "--into", "practice"], ("practice/description", "practice"), "prior sibling scratch as live input"),
            ("edit", ["edit", f"practice:{added[3]}", EDIT_CONTENT[3]], ("practice",), "third Add UID"),
            ("move", ["move", f"practice:{copied[3][0]}", "--into", "practice/description"], ("practice", "practice/description"), "first UID from batch Copy"),
            ("replace", ["replace", "CANDIDATE", "ATOMIC CANDIDATE", "--context", "practice"], ("practice",), "candidate label after earlier Replace"),
            ("chunk", ["chunk", f"practice:{added[3]}", "--method", "sentences"], ("practice",), "compound fixed-limit candidate"),
            ("compare", ["compare", "practice/source", "practice/description"], ("practice/source", "practice/description"), "source versus accumulated moved copies"),
            ("find-duplicates", ["find-duplicates", "practice", "--recursive"], ("practice", "practice/description", "practice/source"), "recursive accumulated tree"),
            ("find-redundancies", ["find-redundancies", "practice", "--direct"], ("practice",), "direct mixed scratch"),
            ("find-ambiguities", ["find-ambiguities", "practice"], ("practice",), "split candidate outputs"),
            ("find-conflicts", ["find-conflicts", "practice/description"], ("practice/description",), "moved source subset"),
            ("fit", ["fit", "practice/source", "practice"], ("practice/source", "practice"), "source to split candidates"),
        ]
    if round_number == 4:
        guard_uid = memory_prefix_with_text("practice", "Preserve all intended points")
        return [
            ("contexts", ["contexts"], (), "catalog near boundary trials"),
            ("list", ["list", "practice/description"], ("practice/description",), "sibling accumulated inventory"),
            ("show", ["show", f"practice:{guard_uid}"], ("practice",), "detached companion safeguard"),
            ("find", ["find", "style guide", "--context", "practice/source"], ("practice/source",), "literal exception phrase"),
            ("search", ["search", "Which constraints are exceptions, defaults, or conditional overrides rather than unconditional rules?", "--context", "practice/source", "--context", "practice", "--context-only", "--exclude-embeds", "--limit", "8"], ("practice/source", "practice"), "multi-root conditional search"),
            ("query", ["query", "--context", "practice/source", "Which instructions are defaults, which are user-request conditions, and which can a named style guide override?"], ("practice/source",), "default/condition classification"),
            ("summarize", ["summarize", "practice"], ("practice",), "scratch with References and Embeds"),
            ("add", ["add", ADD_CONTENT[4], "--context", "practice"], ("practice",), "title/italics conditional candidate"),
            ("copy", ["copy", f"practice/source:{s['title_case']}", f"practice/source:{s['italics']}", "--into", "practice"], ("practice/source", "practice"), "two conditional source rules"),
            ("reference", ["reference", f"practice/source:{s['terminology']}", "--into", "practice"], ("practice/source", "practice"), "protected terminology snapshot"),
            ("embed", ["embed", "practice/source", "--into", "practice"], ("practice/source", "practice"), "deliberate duplicate live edge"),
            ("edit", ["edit", f"practice:{added[4]}", EDIT_CONTENT[4]], ("practice",), "fourth Add UID"),
            ("move", ["move", f"practice:{added[4]}", "--into", "practice/description"], ("practice", "practice/description"), "edited title candidate"),
            ("replace", ["replace", "CANDIDATE", "DEFAULT CANDIDATE", "--context", "practice/description"], ("practice/description",), "broad substring boundary"),
            ("chunk", ["chunk", f"practice/description:{added[4]}", "--method", "sentences"], ("practice/description",), "moved title candidate"),
            ("compare", ["compare", "practice/source", "practice/description"], ("practice/source", "practice/description"), "source versus damaged split frame"),
            ("find-duplicates", ["find-duplicates", "practice/description"], ("practice/description",), "mixed direct items"),
            ("find-redundancies", ["find-redundancies", "practice/description", "--direct"], ("practice/description",), "same Context ordinary Memories"),
            ("find-ambiguities", ["find-ambiguities", "practice/description"], ("practice/description",), "detached title/polishing parts"),
            ("find-conflicts", ["find-conflicts", "practice/description"], ("practice/description",), "split-induced conflicts"),
            ("fit", ["fit", "practice/source", "practice/description"], ("practice/source", "practice/description"), "source to damaged review frame"),
        ]
    title_uid = memory_prefix_with_text("practice/description", "preserve the intended word for")
    return [
        ("contexts", ["contexts"], (), "late catalog"),
        ("list", ["list", "practice/description"], ("practice/description",), "late mixed inventory"),
        ("show", ["show", f"practice/description:{title_uid}"], ("practice/description",), "damaged title chunk UID"),
        ("find", ["find", "only|before|unless|if|when", "--regex", "--context", "practice/source", "--all-results"], ("practice/source",), "all trigger terms"),
        ("search", ["search", "Which candidate constraints lost their trigger, exception, or companion rule after splitting?", "--context", "practice/source", "--context", "practice", "--context", "practice/description", "--context-only", "--exclude-embeds", "--limit", "10"], ("practice/source", "practice", "practice/description"), "three-root diagnostic"),
        ("query", ["query", "--context", "practice/source", "How should these notes be atomized so each result remains independently reviewable without losing triggers, exceptions, protected wording, or source-verification boundaries?"], ("practice/source",), "final candidate design"),
        ("summarize", ["summarize", "practice/description"], ("practice/description",), "late evidence-rich scratch"),
        ("add", ["add", ADD_CONTENT[5], "--context", "practice"], ("practice",), "audit conclusion"),
        ("copy", ["copy", f"practice/source:{s['citations']}", "--into", "practice"], ("practice/source", "practice"), "citation rule reused late"),
        ("reference", ["reference", f"practice/source:{s['connector']}", "--into", "practice/description"], ("practice/source", "practice/description"), "connector provenance late"),
        ("embed", ["embed", "practice", "--into", "practice/description"], ("practice", "practice/description"), "deliberate live-embed cycle"),
        ("edit", ["edit", f"practice:{added[5]}", EDIT_CONTENT[5]], ("practice",), "fifth Add UID"),
        ("move", ["move", f"practice:{added[5]}", "--into", "practice/description"], ("practice", "practice/description"), "final audit result"),
        ("replace", ["replace", "APPROVED ATOM", "FINAL ATOM", "--context", "practice/description"], ("practice/description",), "deliberate no-match"),
        ("chunk", ["chunk", f"practice/description:{added[5]}", "--method", "paragraphs"], ("practice/description",), "single-paragraph audit result"),
        ("compare", ["compare", "practice", "practice/description"], ("practice", "practice/description"), "two accumulated scratch frames"),
        ("find-duplicates", ["find-duplicates", "practice", "--recursive"], ("practice", "practice/description", "practice/source"), "late recursive tree"),
        ("find-redundancies", ["find-redundancies", "practice/description", "--direct"], ("practice/description",), "late ordinary-Memory corpus"),
        ("find-ambiguities", ["find-ambiguities", "practice/description"], ("practice/description",), "late damaged/evidence-rich frame"),
        ("find-conflicts", ["find-conflicts", "practice"], ("practice",), "late parent scratch"),
        ("fit", ["fit", "practice/source", "practice/description"], ("practice/source", "practice/description"), "late source-to-scratch fit"),
    ]


def write_phase(attempts_by_op: dict[str, list[dict]], source_before: str) -> None:
    total = sum(len(items) for items in attempts_by_op.values())
    phase = {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": WORLD,
        "world_goal": "Atomize editing constraints in practice/source without performing edits or changing intended meaning while surrounding working state grows.",
        "phase": "core",
        "execution_identity": {
            "code_sha256": "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84",
            "catalog_sha256": "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5",
            "profile_uid": "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd",
            "store_root": str(STORE),
            "provider_policy_sha256": "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca",
        },
        "execution_boundary": {
            "runner": str(RUNNER),
            "source_fixture": "practice/source",
            "source_initial_sha256": source_before,
            "source_current_sha256": sha(SOURCE),
            "mutation_boundary": "Only practice and practice/description; practice/source remained guarded read-only.",
            "tui": "No TUI used in core; all attempts used explicit non-interactive pinned routes.",
        },
        "operation_order": list(OPERATIONS),
        "interleaving": "Five rounds; each round executes all 21 operations once before any operation repeats.",
        "total_attempts": total,
        "operations": {operation: {"attempts": attempts_by_op[operation]} for operation in OPERATIONS},
        "outcome": "running" if total < 105 else "core attempt contract complete; interpretation recorded in issues.md",
    }
    PHASE_PATH.write_text(json.dumps(phase, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    source_before = sha(SOURCE)
    attempts_by_op: dict[str, list[dict]] = {operation: [] for operation in OPERATIONS}
    state: dict[str, object] = {"added": {}, "copied": {}}
    sequence = 0

    for round_number in range(1, 6):
        # Add and Copy outputs are needed by later operations in the same round,
        # so construct the prefix through Copy and then rebuild the remaining list.
        for operation_index in range(len(OPERATIONS)):
            command_specs = commands_for(round_number, state)
            operation, mem_args, targets, provenance_detail = command_specs[operation_index]
            assert operation == OPERATIONS[operation_index]
            sequence += 1
            pre = target_digest(targets)
            command_argv = ["python", str(RUNNER), WORLD, *mem_args]
            command = shlex.join(command_argv)
            started = time.monotonic()
            try:
                result = subprocess.run(
                    command_argv, text=True, capture_output=True, timeout=240
                )
            except subprocess.TimeoutExpired as error:
                # A timed-out invocation is still a counted attempt. Preserve
                # its partial evidence and continue without silently retrying.
                result = subprocess.CompletedProcess(
                    command_argv,
                    124,
                    error.stdout or "",
                    (error.stderr or "") + "\nAudit capture timeout after 240 seconds.",
                )
            elapsed = time.monotonic() - started
            post = target_digest(targets)
            if sha(SOURCE) != source_before:
                raise RuntimeError(f"practice/source changed during sequence {sequence}")

            stem = f"{sequence:03d}-{operation}-m{round_number}"
            raw_path = RAW / f"{stem}.txt"
            raw_path.write_text(
                f"COMMAND\n{command}\n\nEXIT\n{result.returncode}\n\n"
                f"WALL_SECONDS\n{elapsed:.6f}\n\nSTDOUT\n{result.stdout}\n\nSTDERR\n{result.stderr}",
                encoding="utf-8",
            )

            if operation == "add" and result.returncode == 0:
                state["added"][round_number] = extract_added_uid(result.stdout)
            if operation == "copy" and result.returncode == 0:
                state["copied"][round_number] = extract_copy_uids(result.stdout)

            meta = route_meta(operation, round_number, targets)
            attempt = {
                "attempt": round_number,
                "sequence": sequence,
                "command": command,
                "exit": result.returncode,
                **meta,
                "input_provenance": meta["input_provenance"] + f"; method: {provenance_detail}",
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
                "recovery_evidence": "No recovery required." if result.returncode == 0 else "The next counted read/analysis attempt verifies continuity; no retry erased this boundary result.",
                "state_continuity": f"practice/source sha256 remained {source_before}; cumulative scratch was retained for sequence {sequence + 1}.",
                "raw_output": str(raw_path.relative_to(ROOT)),
            }
            attempts_by_op[operation].append(attempt)
            write_phase(attempts_by_op, source_before)
            print(f"{sequence:03d}/105 r{round_number} {operation} exit={result.returncode} wall={elapsed:.2f}s", flush=True)

    if sequence != 105 or any(len(attempts_by_op[op]) != 5 for op in OPERATIONS):
        raise RuntimeError("core coverage contract not met")
    print(f"COMPLETE source_sha256={sha(SOURCE)}", flush=True)


if __name__ == "__main__":
    main()
