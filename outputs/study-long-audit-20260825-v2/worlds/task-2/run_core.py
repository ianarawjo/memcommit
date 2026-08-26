#!/usr/bin/env python3
"""Run the task-2 CORE audit against the pinned world launcher.

This is an audit-only recorder.  It deliberately invokes no CLI discovery or
setup command: the 105 entries below are exactly the five requested attempts
for each of the 21 CORE operations.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import time


WORLD = "task-2"
ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "outputs/study-long-audit-20260825-v2/worlds/task-2"
RAW = OUT / "raw"
WRAPPER = ROOT / "outputs/study-long-audit-20260825-v2/run_world_mem.py"
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-2/profile-control/stores/"
    "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
PHASE = OUT / "phase-core.json"

CODE_SHA = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_SHA = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROVIDER_DIGEST = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"


def context_file(name: str) -> Path:
    return STORE / "contexts" / name / "context.json"


def digest(name: str | None) -> str:
    if name is None:
        return "N/A (no single durable target)"
    path = context_file(name)
    if not path.exists():
        return "N/A (readable grant or absent local Context)"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_actual(output: str, exit_code: int) -> str:
    lines = [line.strip() for line in output.replace("\r", "\n").splitlines() if line.strip()]
    if not lines:
        return f"Exited {exit_code} with no output."
    selected = lines[:3]
    if len(lines) > 6:
        selected.append(f"... ({len(lines)} non-empty lines total) ...")
        selected.extend(lines[-3:])
    elif len(lines) > 3:
        selected.extend(lines[3:])
    text = " | ".join(selected)
    return text[:2400]


def phase_document() -> dict:
    if PHASE.exists():
        return json.loads(PHASE.read_text())
    return {
        "world": WORLD,
        "phase": "core",
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
            "Combine two equal co-advisor policy stores without favoring either; "
            "consolidate duplicates, clarify conditions, and reconcile or explain conflicts."
        ),
        "counted_actual_mem_commands": 0,
        "operations": {},
        "issues": [],
    }


def save(document: dict) -> None:
    PHASE.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")


def attempt(
    document: dict,
    *,
    sequence: int,
    operation: str,
    number: int,
    args: list[str],
    starting_state: str,
    entry_route: str,
    target_route: str,
    target_context: str | None,
    scope: str,
    input_provenance: str,
    consumer: str,
    expected: str,
    cost: str,
    recovery_evidence: str,
    state_continuity: str,
) -> tuple[int, str]:
    command = ["python", str(WRAPPER), WORLD, *args]
    display = " ".join(json.dumps(part) if any(c.isspace() for c in part) else part for part in command)
    pre = digest(target_context)
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=700,
        check=False,
    )
    duration = round(time.monotonic() - started, 3)
    post = digest(target_context)
    raw_path = RAW / f"{sequence:03d}-{operation}-attempt-{number}.txt"
    raw_path.write_text(
        f"COMMAND: {display}\nEXIT: {completed.returncode}\nDURATION_SECONDS: {duration}\n\n"
        + completed.stdout
    )
    record = {
        "attempt": number,
        "sequence": sequence,
        "command": display,
        "exit": completed.returncode,
        "starting_state": starting_state,
        "entry_route": entry_route,
        "target_route": target_route,
        "scope": scope,
        "input_provenance": input_provenance,
        "consumer": consumer,
        "expected": expected,
        "actual": compact_actual(completed.stdout, completed.returncode),
        "defect_ids": [],
        "cost": f"{cost}; {duration:.3f}s wall time",
        "pre_target_digest": pre,
        "post_target_digest": post,
        "recovery_evidence": recovery_evidence,
        "state_continuity": state_continuity,
        "raw_output": str(raw_path.relative_to(ROOT)),
    }
    document["operations"].setdefault(operation, {"attempts": []})["attempts"].append(record)
    document["counted_actual_mem_commands"] += 1
    save(document)
    return completed.returncode, completed.stdout


def args_for(round_number: int, uid: str | None = None) -> dict[str, list[str]]:
    category = ("style", "budget", "methods", "ethics", "evaluation")[round_number - 1]
    add_texts = (
        "Equal-authority synthesis rule: preserve each shared co-advisor requirement once, retain distinct conditions, and explain unresolved conflicts with both provenances.",
        "Equal-authority synthesis rule: preserve each shared co-advisor requirement once, retain distinct conditions, and explain unresolved conflicts with both provenances.",
        "Budget reconciliation: keep totals and major categories in the main text; place quantities, unit rates, assumptions, and arithmetic in a compact cross-referenced appendix.",
        "Recruitment reconciliation: before commitments, use a justified participant target range with separate workload and budget consequences; after confirmation, publish one exact recalculated target.",
        "Final neutral policy: preserve duplicate requirements once, state advisor-specific conditions, retain both provenances, and assign owners to any unresolved conflicts.",
    )
    edited_texts = (
        add_texts[0] + " Apply it category by category.",
        add_texts[1] + " Record why equivalent wording was consolidated.",
        add_texts[2] + " This preserves detail without crowding the two-page narrative.",
        add_texts[3] + " The transition condition is documented explicitly.",
        add_texts[4] + " No source has tie-breaking priority.",
    )
    search_questions = (
        "Which style requirements are shared, and where do the advisors differ?",
        "How can budget detail remain auditable while fitting a two-page proposal?",
        "How should an exact participant target and a justified target range coexist?",
        "Which ethics policies are duplicates, conditional differences, or conflicts?",
        "Which evaluation policies can be consolidated without losing either advisor's conditions?",
    )
    query_questions = (
        "State a neutral combined style policy and cite both advisors.",
        "Reconcile the two budget policies without favoring either advisor.",
        "Explain when to use an exact participant count versus a justified range.",
        "Consolidate the ethics policies and preserve any true conflict with an explanation.",
        "Produce a final equal-authority evaluation policy with source-grounded conditions.",
    )
    embed_sources = (
        "task-2/advisor1/style",
        "task-2/advisor2/style",
        "task-2/description",
        "task-2/proposal-submission-guidelines",
        "task-2/advisor1/budget",
    )
    embed_targets = (
        "task-2/participant",
        "task-2",
        "task-2/participant",
        "task-2/participant",
        "task-2/description",
    )
    replacements = (
        ("nonexistent-policy-token", "normalized-policy-token"),
        ("nonexistent-duplicate-token", "normalized-duplicate-token"),
        ("main text", "proposal body"),
        ("participant target", "recruitment target"),
        ("unresolved conflicts", "owned unresolved conflicts"),
    )
    summaries = (
        ["summarize", "task-2/advisor1/style", "--plain"],
        ["summarize", "task-2/advisor2/style", "--plain"],
        ["summarize", "task-2/advisor1/budget", "--plain"],
        ["summarize", "task-2/advisor2/methods", "--plain"],
        ["summarize", "task-2/participant", "--recursive", "--plain"],
    )
    shows = (
        ["show", "--direct", "--context", "task-2/description"],
        ["show", "--direct", "--context", "task-2/advisor1/style"],
        ["show", "--direct", "--context", "task-2/advisor2/budget"],
        ["show", "--recursive", "--context", "task-2/participant"],
        ["show", "--direct", "--context", "task-2"],
    )
    lists = (
        ["list", "--direct", "task-2/participant"],
        ["list", "--direct", "task-2"],
        ["list", "--direct", "task-2/description"],
        ["list", "--recursive", "task-2/participant"],
        ["list", "--direct", "task-2/advisor2/evaluation"],
    )
    finds = (
        ["find", "equal authority", "--context", "task-2/description", "--direct"],
        ["find", "concise", "--context", "task-2/advisor1/style", "--context", "task-2/advisor2/style"],
        ["find", "budget|appendix", "--regex", "--ignore-case", "--context", "task-2/advisor1/budget", "--context", "task-2/advisor2/budget"],
        ["find", "participant", "--context", "task-2/advisor1/methods", "--context", "task-2/advisor2/methods"],
        ["find", "provenance", "--recursive", "--context", "task-2/participant", "--all-results"],
    )
    compares = (
        ["compare", "task-2/advisor1/style", "task-2/advisor2/style", "--snapshot"],
        ["compare", "task-2/advisor1/budget", "task-2/advisor2/budget", "--snapshot"],
        ["compare", "task-2/advisor1/methods", "task-2/advisor2/methods", "--snapshot"],
        ["compare", "task-2/advisor1/ethics", "task-2/advisor2/ethics", "--snapshot"],
        ["compare", "task-2/advisor1/evaluation", "task-2/advisor2/evaluation", "--snapshot"],
    )
    fit_args = ["fit", "--context", f"task-2/advisor1/{category}", "--context", f"task-2/advisor2/{category}"]
    result = {
        "contexts": ["contexts"],
        "list": lists[round_number - 1],
        "show": shows[round_number - 1],
        "find": finds[round_number - 1],
        "search": ["search", search_questions[round_number - 1], "--context", f"task-2/advisor1/{category}", "--context", f"task-2/advisor2/{category}", "--limit", str(5 + round_number)],
        "query": ["query", query_questions[round_number - 1], "--context", f"task-2/advisor1/{category}", "--context", f"task-2/advisor2/{category}"],
        "summarize": summaries[round_number - 1],
        "add": ["add", add_texts[round_number - 1], "--context", "task-2/participant"],
        "embed": ["embed", embed_sources[round_number - 1], "--into", embed_targets[round_number - 1]],
        "replace": ["replace", replacements[round_number - 1][0], replacements[round_number - 1][1], "--direct", "--context", "task-2", "--plain"],
        "compare": compares[round_number - 1],
        "find-duplicates": ["find-duplicates", "task-2", "--direct"],
        "find-redundancies": ["find-redundancies", "task-2", "--direct"],
        "find-ambiguities": ["find-ambiguities", "task-2"],
        "find-conflicts": ["find-conflicts", "task-2"],
        "fit": fit_args,
    }
    if uid is not None:
        source = f"task-2/participant:{uid}"
        result.update(
            {
                "copy": ["copy", source, "--into", "task-2"],
                "reference": ["reference", source, "--into", "task-2/description"],
                "edit": ["edit", source, edited_texts[round_number - 1]],
                "move": ["move", source, "--into", "task-2"],
                "chunk": ["chunk", f"task-2:{uid}", "--method", "clauses" if round_number > 1 else "sentences", "--max-chars", str(95 + 5 * round_number)],
            }
        )
    return result


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    document = phase_document()
    if document["counted_actual_mem_commands"]:
        raise SystemExit("phase-core.json already contains attempts; refusing to duplicate counted commands")

    operations = (
        "contexts", "list", "show", "find", "search", "query", "summarize",
        "add", "copy", "reference", "embed", "edit", "move", "replace",
        "chunk", "compare", "find-duplicates", "find-redundancies",
        "find-ambiguities", "find-conflicts", "fit",
    )
    sequence = 0
    for round_number in range(1, 6):
        dynamic_uid: str | None = None
        for operation in operations:
            sequence += 1
            command_map = args_for(round_number, dynamic_uid)
            target_context = {
                "add": "task-2/participant",
                "copy": "task-2",
                "reference": "task-2/description",
                "embed": ("task-2/participant", "task-2", "task-2/participant", "task-2/participant", "task-2/description")[round_number - 1],
                "edit": "task-2/participant",
                "move": "task-2",
                "replace": "task-2",
                "chunk": "task-2",
            }.get(operation)
            is_mutation = target_context is not None
            exit_code, output = attempt(
                document,
                sequence=sequence,
                operation=operation,
                number=round_number,
                args=command_map[operation],
                starting_state=f"cumulative round {round_number}; {sequence - 1} counted CORE commands already attempted",
                entry_route="pinned explicit CLI" if operation != "contexts" else "pinned global inventory CLI",
                target_route=(target_context or (f"advisor1/advisor2 {('style','budget','methods','ethics','evaluation')[round_number-1]} or explicit read scope")),
                target_context=target_context,
                scope=("direct world-local mutation" if is_mutation else "explicit read-only exact/multi-root scope as shown by argv"),
                input_provenance=("prior-round world-local synthesis" if is_mutation else "frozen Study fixtures plus cumulative world-local state"),
                consumer="next task-2 synthesis or validation step",
                expected=("Atomic authorized mutation with an attributable receipt and recoverable cumulative state." if is_mutation else "Source-faithful read/analysis of the explicitly requested task-2 scope without mutation."),
                cost="one counted actual mem invocation",
                recovery_evidence=("Pre/post SHA-256 recorded; command receipt/raw output retained." if is_mutation else "Read-only command; no recovery action expected."),
                state_continuity="No reset; same pinned Profile UID and lane Store used before and after this attempt.",
            )
            if operation == "add":
                match = re.search(r"\[([0-9a-f]{8}(?:-[0-9a-f-]{27})?)\]", output, re.IGNORECASE)
                if exit_code == 0 and match:
                    dynamic_uid = match.group(1)
                else:
                    # These still count as actual attempts, but dependent mutation
                    # routes need a concrete non-existent selector to fail safely.
                    dynamic_uid = "00000000"

    document["status"] = "complete"
    save(document)


if __name__ == "__main__":
    main()
