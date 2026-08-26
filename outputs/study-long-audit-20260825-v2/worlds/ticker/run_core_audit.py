#!/usr/bin/env python3
"""Run the ticker lane's 105 counted core attempts against the frozen CLI."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time


REPO = Path("/Users/KimMunyeong/Github/memcommit")
WORLD_DIR = REPO / "outputs/study-long-audit-20260825-v2/worlds/ticker"
RAW_DIR = WORLD_DIR / "raw/core"
WRAPPER = REPO / "outputs/study-long-audit-20260825-v2/run_world_mem.py"
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/ticker/profile-control/"
    "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
CONTEXTS = STORE / "contexts"

# The template contains no pre-created ticker namespace. These empty, local,
# lane-isolated fixture Contexts are reused without changing the global current.
WORKSPACE = "task-2"
RULES = "task-2/participant"
EXAMPLES = "task-2/participant/proposal-workspace"
TESTS = "task-1"
ARCHIVE = "task-3"

OPS = (
    "contexts", "list", "show", "find", "search", "query", "summarize",
    "add", "copy", "reference", "embed", "edit", "move", "replace",
    "chunk", "compare", "find-duplicates", "find-redundancies",
    "find-ambiguities", "find-conflicts", "fit",
)


def context_file(name: str) -> Path:
    return CONTEXTS.joinpath(*name.split("/"), "context.json")


def load_context(name: str) -> dict:
    return json.loads(context_file(name).read_text())


def memory_items(name: str) -> list[dict]:
    data = load_context(name)
    return [data["memories"][uid] for uid in data.get("order", ())]


def find_uid(name: str, needle: str, *, newest: bool = True) -> str:
    items = memory_items(name)
    if newest:
        items.reverse()
    for item in items:
        if item.get("type") == "memory" and needle in item.get("content", ""):
            return item["uid"]
    raise RuntimeError(f"No direct Memory containing {needle!r} in {name}")


def direct_memory_uids(name: str) -> set[str]:
    return {
        item["uid"] for item in memory_items(name) if item.get("type") == "memory"
    }


def newest_uid_not_in(name: str, before: set[str]) -> str:
    for item in reversed(memory_items(name)):
        if item.get("type") == "memory" and item["uid"] not in before:
            return item["uid"]
    raise RuntimeError(f"No newly created direct Memory in {name}")


def digest_targets(targets: list[str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(set(targets)):
        path = context_file(name)
        digest.update(name.encode())
        digest.update(b"\0")
        if path.exists():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def output_excerpt(stdout: str, stderr: str, limit: int = 900) -> str:
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    combined = " ".join(combined.split())
    if len(combined) > limit:
        return combined[: limit - 1] + "…"
    return combined or "No stdout or stderr."


ATTEMPTS_PATH = WORLD_DIR / "attempts-core.jsonl"
attempts: list[dict] = (
    [json.loads(line) for line in ATTEMPTS_PATH.read_text().splitlines() if line.strip()]
    if ATTEMPTS_PATH.exists()
    else []
)
sequence = len(attempts)


def run(
    operation: str,
    attempt: int,
    args: list[str],
    *,
    targets: list[str],
    starting_state: str,
    entry_route: str,
    target_route: str,
    scope: str,
    provenance: str,
    consumer: str,
    expected: str,
    mutating: bool = False,
    recovery_evidence: str = "Not required.",
) -> subprocess.CompletedProcess[str]:
    global sequence
    assert operation in OPS
    command = ["python", str(WRAPPER), "ticker", *args]
    prior = next(
        (
            item for item in attempts
            if item["operation"] == operation and item["attempt"] == attempt
        ),
        None,
    )
    if prior is not None:
        # Resuming never reruns a counted command, but it does let the driver
        # refine ledger-only route descriptions from the already frozen argv.
        prior.update(
            {
                "starting_state": starting_state,
                "entry_route": entry_route,
                "target_route": target_route,
                "scope": scope,
                "input_provenance": provenance,
                "consumer": consumer,
                "expected": expected,
                "recovery_evidence": recovery_evidence,
            }
        )
        ATTEMPTS_PATH.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in attempts)
        )
        stdout = (REPO / prior["raw_stdout"]).read_text()
        stderr = (REPO / prior["raw_stderr"]).read_text()
        print(
            f"[{prior['sequence']:03d}/105] {operation} {attempt}: already recorded; not rerun",
            flush=True,
        )
        return subprocess.CompletedProcess(command, prior["exit"], stdout, stderr)
    sequence += 1
    pre = digest_targets(targets)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO,
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        completed = subprocess.CompletedProcess(
            command,
            124,
            stdout=error.stdout or "",
            stderr=(error.stderr or "") + "\nAUDIT DRIVER TIMEOUT after 240 seconds",
        )
    wall = round(time.monotonic() - started, 3)
    post = digest_targets(targets)
    stem = f"{sequence:03d}-{operation}-attempt-{attempt}"
    stdout_path = RAW_DIR / f"{stem}.stdout.txt"
    stderr_path = RAW_DIR / f"{stem}.stderr.txt"
    stdout_path.write_text(completed.stdout)
    stderr_path.write_text(completed.stderr)
    line_count = max(completed.stdout.count("\n"), completed.stderr.count("\n"), 1)
    record = {
        "attempt": attempt,
        "sequence": sequence,
        "command": " ".join(command),
        "exit": completed.returncode,
        "starting_state": starting_state,
        "entry_route": entry_route,
        "target_route": target_route,
        "scope": scope,
        "input_provenance": provenance,
        "consumer": consumer,
        "expected": expected,
        "actual": f"Exit {completed.returncode}. {output_excerpt(completed.stdout, completed.stderr)}",
        "defect_ids": [],
        "cost": {
            "wall_seconds": wall,
            "terminal_screens": max(1, math.ceil(line_count / 52)),
            "extra_manual_steps": 0,
            "tui": False,
        },
        "pre_target_digest": pre,
        "post_target_digest": post,
        "recovery_evidence": recovery_evidence,
        "state_continuity": {
            "current_context_expected": "practice",
            "current_context_actual": json.loads((STORE / "state.json").read_text()).get("current"),
            "target_changed": pre != post,
            "mutation_expected": mutating,
            "preserved": (
                json.loads((STORE / "state.json").read_text()).get("current") == "practice"
                and (mutating or pre == post)
            ),
        },
        "raw_stdout": str(stdout_path.relative_to(REPO)),
        "raw_stderr": str(stderr_path.relative_to(REPO)),
    }
    attempts.append({"operation": operation, **record})
    ATTEMPTS_PATH.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in attempts)
    )
    print(f"[{sequence:03d}/105] {operation} {attempt}: exit {completed.returncode} ({wall:.3f}s)", flush=True)
    return completed


def run_round(round_number: int) -> None:
    state = f"round {round_number}; cumulative ticker corpus in lane-local fixture Contexts"
    catalog_checkpoint = {
        1: "fixed initial Profile catalog before any ticker Memory is authored",
        2: "catalog re-entry after direct rules, one copied/chunked test, and first live Embed",
        3: "catalog re-entry after punctuation evidence, cross-Context snapshots, and nested test views",
        4: "catalog re-entry after numeral evidence, recursive comparison, and archive-to-test reorganization",
        5: "catalog re-entry after share-class evidence, asymmetric comparison, and cross-tree Archive Embed",
    }[round_number]

    run("contexts", round_number, ["contexts"], targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route="global catalog", target_route="Profile-readable namespace",
        scope="all readable Context names", provenance=catalog_checkpoint,
        consumer="confirm stable Context identity and unchanged current Context",
        expected="Print the readable catalog without changing any Context or current pointer.")

    list_args = {
        1: ["list", WORKSPACE, "--direct"],
        2: ["list", WORKSPACE, "--recursive"],
        3: ["list", EXAMPLES, "--direct"],
        4: ["list", TESTS, "--direct"],
        5: ["list", ARCHIVE, "--recursive"],
    }[round_number]
    list_route = {
        1: ("positional Context plus --direct", "exact local root task-2", "direct items only", "initial empty workspace-root baseline before ticker authoring"),
        2: ("positional Context plus --recursive", "task-2 readable semantic subtree", "38 lexical local/granted Context frames plus live Embeds", "post-round-1 rules, chunks, archive move, and rules Embed; deliberate noisy descendant boundary"),
        3: ("positional exact child plus --direct", "exact local examples child", "direct items only", "punctuation source after immutable snapshot, edit, and literal normalization"),
        4: ("positional cross-tree test root plus --direct", "exact local tests root", "direct typed Memories/Embeds only", "numeral-era copied/chunked test state after a break-links move"),
        5: ("positional archive root plus --recursive", "archive root and reachable semantic descendants/Embeds", "recursive lexical and live-Embed expansion", "late archive graph after rules/examples/tests and cross-tree live links accumulated"),
    }[round_number]
    run("list", round_number, list_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route=list_route[0], target_route=list_route[1],
        scope=list_route[2], provenance=list_route[3],
        consumer="inspect typed items and recover UIDs for later commands",
        expected="Render the selected Context scope without mutation.")

    if round_number == 1:
        add_args = [
            "add", "--to", RULES,
            "--memory", "Base ticker rule: remove a terminal legal suffix such as Inc., Corp., Ltd., or LLC before constructing the ticker. Preserve the remaining alphanumeric characters.",
            "--memory", "Base ticker rule: uppercase the remaining company-name letters in their original order. Do not invent letters.",
        ]
        add_target, entry = RULES, "repeatable --memory batch"
    elif round_number == 2:
        add_args = ["add", "Punctuation example: North-Star, Inc. becomes NORTHSTAR after removing the comma, hyphen, space, and Inc. suffix. The output contains no punctuation.", "--to", EXAMPLES]
        add_target, entry = EXAMPLES, "single positional INFO"
    elif round_number == 3:
        input_path = WORLD_DIR / "inputs" / "round-3-numerals.txt"
        input_path.write_text(
            "Numeral rule: preserve digits 0-9, including leading zeroes, in their original positions while removing spaces and punctuation.\n"
            "Numeral example: Route 66, LLC becomes ROUTE66 after removing the comma, space, and LLC suffix while preserving 66.\n"
        )
        add_args = ["add", "--input", str(input_path), "--to", EXAMPLES]
        add_target, entry = EXAMPLES, "UTF-8 --input file"
    elif round_number == 4:
        add_args = [
            "add", "--to", EXAMPLES,
            "-m", "Share-class rule: if a legal suffix immediately precedes terminal Class A or Class B, remove the suffix and append .A or .B to the derived base ticker.",
            "-m", "Share-class example: Acme Corp. Class B becomes ACME.B after removing Corp. and mapping Class B to the .B suffix. The dot is generated share-class syntax.",
        ]
        add_target, entry = EXAMPLES, "short -m batch alias"
    else:
        add_args = [
            "add", "--context", RULES,
            "--memory", "Regression expectation: every maintained example must preserve digits, remove input punctuation, and encode a terminal share class with generated dot syntax.",
            "--memory", "Conflicting regression draft: derived ticker letters must remain lowercase.",
        ]
        add_target, entry = RULES, "compatibility --context plus repeatable --memory"
    run("add", round_number, add_args, targets=[add_target], starting_state=state,
        entry_route=entry, target_route=add_target, scope="direct target",
        provenance=f"authored ticker round {round_number} evidence", consumer="grow reusable rule and example corpus",
        expected="Add the supplied non-empty Memories atomically and print their exact UIDs.", mutating=True)

    suffix_uid = find_uid(RULES, "terminal legal suffix")
    uppercase_uid = find_uid(RULES, "company-name letters")
    punctuation_uid = find_uid(EXAMPLES, "North-Star") if round_number >= 2 else suffix_uid
    numeral_uid = find_uid(EXAMPLES, "Route 66") if round_number >= 3 else punctuation_uid
    share_uid = find_uid(EXAMPLES, "Acme Corp. Class B") if round_number >= 4 else numeral_uid

    show_args = {
        1: ["show", WORKSPACE, "--direct"],
        2: ["show", f"{EXAMPLES}:{punctuation_uid[:12]}"],
        3: ["show", numeral_uid[:12]],
        4: ["show", WORKSPACE, "--recursive"],
        5: ["show", f"{TESTS}:00000000"],
    }[round_number]
    show_route = {
        1: ("auto-typed existing Context plus --direct", "exact workspace Context task-2", "direct Context items only", "post-add rules remain below the empty root; verifies exact root isolation"),
        2: ("qualified CONTEXT:UID positional selector", "exact punctuation Memory in examples", "one directly owned Memory", "UID recovered from Add attempt 2"),
        3: ("bare UID positional selector", "globally unique numeral Memory", "one auto-resolved local direct Memory", "UID recovered from UTF-8 Add attempt 3"),
        4: ("auto-typed existing Context plus --recursive", "workspace task-2 semantic subtree", "lexical descendants and live Embeds", "share-class-era recursive inspection with deliberate pre-existing descendant noise"),
        5: ("qualified CONTEXT:missing-prefix positional selector", "unavailable direct item under tests", "one exact missing direct-item boundary", "synthetic 00000000 unavailable selector after final List exposed valid rows"),
    }[round_number]
    run("show", round_number, show_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS],
        starting_state=state, entry_route=show_route[0], target_route=show_route[1],
        scope=show_route[2], provenance=show_route[3],
        consumer="inspect exact ticker evidence and selector boundaries",
        expected=("Fail clearly without mutation for the unavailable direct-item prefix."
                  if round_number == 5 else "Show the selected Context or direct item without mutation."),
        recovery_evidence=("The immediately preceding exact List provides current valid test UIDs; no retry hides this boundary."
                           if round_number == 5 else "Not required."))

    find_args = {
        1: ["find", "ticker rule", "--context", RULES, "--context-only"],
        2: ["find", "north-star", "--context", EXAMPLES, "--context-only", "--ignore-case"],
        3: ["find", r"Route\s+66", "--regex", "--context", EXAMPLES, "--direct"],
        4: ["find", "Class B", "--context", RULES, "--context", EXAMPLES, "--context-only"],
        5: ["find", "generated dot", "--context", WORKSPACE, "--descendants", "--follow-embeds", "--all-results"],
    }[round_number]
    find_route = {
        1: ("literal pattern plus single --context and --context-only", "rules root task-2/participant", "case-sensitive literal; exact root; no descendants or Embeds", "authored suffix/uppercase rule batch from Add attempt 1"),
        2: ("literal pattern plus --ignore-case", "examples root task-2/participant/proposal-workspace", "case-insensitive literal; exact root", "new punctuation example after Add attempt 2"),
        3: ("--regex pattern plus --direct", "examples root task-2/participant/proposal-workspace", "regular expression Route\\s+66; exact root", "numeral lines ingested from round-3 UTF-8 file"),
        4: ("literal pattern plus repeated --context", "two exact roots: rules and examples", "multiple roots; exact Contexts only", "share-class rule/example batch plus maintained direct rules"),
        5: ("literal pattern plus --descendants --follow-embeds --all-results", "workspace task-2 with live graph reach", "lexical descendants and Embed traversal with unbounded result rendering", "late generated-dot evidence after cross-tree Archive Embed and conflict draft"),
    }[round_number]
    run("find", round_number, find_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route=find_route[0], target_route=find_route[1],
        scope=find_route[2], provenance=find_route[3],
        consumer="locate exact reusable evidence and verify traversal controls",
        expected="Return every matching literal span in the declared frozen scope without mutation.")

    search_args = {
        1: ["search", "How should a company name become a ticker?", "--context", RULES, "--context-only"],
        2: ["search", "company name with punctuation and a legal suffix", "--context", EXAMPLES, "--direct"],
        3: ["search", "ticker example that keeps a number", "--context", RULES, "--context", EXAMPLES, "--context-only"],
        4: ["search", "ticker for a company with a share class", "--context", WORKSPACE, "--descendants", "--exclude-embeds"],
        5: ["search", "final regression rules for suffix punctuation numeral and share class", "--context", ARCHIVE, "--context-only", "--follow-embeds", "--limit", "10"],
    }[round_number]
    search_route = {
        1: ("natural-language Search plus one --context --context-only", "exact rules root", "one direct Context; descendants and Embeds excluded", "two initial ticker rules only"),
        2: ("natural-language Search plus one --context --direct", "exact examples root", "one direct Context after punctuation Add", "punctuation example before numeral/share-class evidence exists"),
        3: ("natural-language Search plus repeated --context", "two roots: rules and examples", "multiple exact roots; Context-only reach", "suffix, punctuation, and numeral evidence jointly frozen"),
        4: ("natural-language Search plus --descendants --exclude-embeds", "workspace task-2 readable semantic subtree", "lexical descendants included; live Embeds excluded", "share-class state with deliberate granted descendant noise boundary"),
        5: ("natural-language Search plus --follow-embeds --limit 10", "archive task-3 exact root with live graph", "Context-only lexical reach; Embeds followed; ten-result cap", "final archive-to-tests-to-rules/examples graph after regression draft"),
    }[round_number]
    run("search", round_number, search_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route=search_route[0], target_route=search_route[1],
        scope=search_route[2], provenance=search_route[3],
        consumer="retrieve relevant rule/example evidence for later Query and Compare",
        expected="Rank relevant Memories from the declared scope and preserve the corpus.")

    query_args = {
        1: ["query", "What ticker-construction rules are currently known?", "--context", RULES, "--direct"],
        2: ["query", "What ticker should North-Star, Inc. receive and why?", "--context", WORKSPACE, "--recursive"],
        3: ["query", "What ticker should Route 66, LLC receive under the current rules?", "--context", RULES, "--context", EXAMPLES, "--context-only"],
        4: ["query", "How should Acme Corp. Class B be encoded, and is its dot retained punctuation?", "--context", WORKSPACE, "--descendants", "--exclude-embeds"],
        5: ["query", "State the maintained algorithm and evaluate North-Star, Inc., Route 66, LLC, and Acme Corp. Class B.", "--context", ARCHIVE, "--context-only", "--follow-embeds"],
    }[round_number]
    query_route = {
        1: ("ordinary Query plus one --context --direct", "exact rules root", "direct rules only", "initial two-rule source frame"),
        2: ("ordinary Query plus one --context --recursive", "workspace task-2 readable semantic subtree", "lexical descendants and live Embeds", "North-Star example plus initial rules; includes deliberate descendant noise boundary"),
        3: ("ordinary Query plus repeated --context --context-only", "two exact roots: rules and examples", "multiple direct roots without descendants/Embeds", "Route 66 rule/example frame produced by prior Search"),
        4: ("ordinary Query plus --descendants --exclude-embeds", "workspace task-2 semantic descendants", "descendants included; live Embeds excluded", "Acme Class B source after share-class Add and Replace"),
        5: ("ordinary Query plus --context-only --follow-embeds", "archive task-3 live graph", "exact archive root with Embed traversal only", "final regression graph and three held examples"),
    }[round_number]
    run("query", round_number, query_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route=query_route[0], target_route=query_route[1],
        scope=query_route[2], provenance=query_route[3],
        consumer="apply the synthetic ticker rules to held examples",
        expected="Answer from only the declared source frame with typed References and no mutation.")

    summarize_args = {
        1: ["summarize", RULES, "--direct"],
        2: ["summarize", EXAMPLES, "--direct"],
        3: ["summarize", WORKSPACE, "--recursive"],
        4: ["summarize", TESTS],
        5: ["summarize", ARCHIVE, "--recursive"],
    }[round_number]
    run("summarize", round_number, summarize_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route="Summarize CLI", target_route=summarize_args[1],
        scope="direct or recursive", provenance="round-specific rule/example/test frame",
        consumer="compress current knowledge for maintenance review",
        expected="Produce a faithful English summary without changing source state.")

    # Each copy is followed by Chunk, so retain the exact new target UID.
    if round_number == 1:
        copy_source = (RULES, suffix_uid, TESTS)
    elif round_number == 2:
        copy_source = (EXAMPLES, punctuation_uid, TESTS)
    elif round_number == 3:
        copy_source = (EXAMPLES, numeral_uid, ARCHIVE)
    elif round_number == 4:
        copy_source = (EXAMPLES, share_uid, TESTS)
    else:
        copy_source = (RULES, find_uid(RULES, "Regression expectation"), ARCHIVE)
    source_context, source_uid, copy_target = copy_source
    before_copy = direct_memory_uids(copy_target)
    if round_number in (1, 3):
        copy_args = ["copy", f"{source_context}:{source_uid[:12]}", "--into", copy_target]
        copy_entry = "qualified positional Memory"
    elif round_number == 2:
        copy_args = ["copy", "--memory", source_uid[:12], "--from", source_context, "--to", copy_target]
        copy_entry = "repeatable --memory plus --from"
    elif round_number == 4:
        anchor = next(iter(direct_memory_uids(TESTS)), None)
        copy_args = ["copy", source_uid[:12], "--from", source_context, "--into", copy_target]
        if anchor:
            copy_args += ["--before", anchor[:12]]
        copy_entry = "ordered insertion before existing item"
    else:
        copy_args = ["copy", source_uid[:12], "--from", source_context, "--into", copy_target]
        copy_entry = "later accumulated test-to-archive handoff"
    copy_result = run("copy", round_number, copy_args, targets=[source_context, copy_target],
        starting_state=state, entry_route=copy_entry, target_route=copy_target, scope="one exact direct Memory",
        provenance=f"{source_context}:{source_uid}", consumer="preserve a mutable test/archive copy for Chunk and Move",
        expected="Create one independent Memory in the target and report source-to-copy UID mapping.", mutating=True)
    if copy_result.returncode == 0:
        new_copy_uids = direct_memory_uids(copy_target) - before_copy
        if new_copy_uids:
            copied_uid = next(iter(new_copy_uids))
        else:
            # A metadata-only resume reads the immutable prior receipt instead
            # of issuing another Copy merely to rediscover its new prefix.
            copied_matches = re.findall(r"→ \[([0-9a-f]+)\]", copy_result.stdout)
            copied_uid = copied_matches[-1] if copied_matches else source_uid
    else:
        copied_uid = source_uid

    if round_number == 1:
        reference_args, reference_target, reference_entry = (
            ["reference", f"{RULES}:{uppercase_uid[:12]}", "--into", WORKSPACE],
            WORKSPACE,
            "Memory snapshot",
        )
    elif round_number == 2:
        reference_args, reference_target, reference_entry = (
            ["reference", EXAMPLES, "--into", RULES, "--direct"],
            RULES,
            "direct Context snapshot",
        )
    elif round_number == 3:
        reference_args, reference_target, reference_entry = (
            ["reference", WORKSPACE, "--into", ARCHIVE, "--recursive"],
            ARCHIVE,
            "recursive Context snapshot",
        )
    elif round_number == 4:
        reference_args, reference_target, reference_entry = (
            ["reference", f"{EXAMPLES}:00000000", "--into", TESTS],
            TESTS,
            "unavailable Memory boundary",
        )
    else:
        reference_args, reference_target, reference_entry = (
            ["reference", f"{RULES}:{find_uid(RULES, 'Regression expectation')[:12]}", "--into", WORKSPACE],
            WORKSPACE,
            "later exact Memory snapshot",
        )
    run("reference", round_number, reference_args, targets=[RULES, EXAMPLES, WORKSPACE, TESTS, ARCHIVE],
        starting_state=state, entry_route=reference_entry, target_route=reference_target,
        scope="exact Memory or direct/recursive Context snapshot", provenance="current immutable evidence handoff",
        consumer="retain historical ticker evidence while mutable sources evolve",
        expected=("Reject the unavailable source without changing the target."
                  if round_number == 4 else "Create an immutable Reference in the target with source provenance."),
        mutating=round_number != 4,
        recovery_evidence=("Round 5 references a valid test Memory after the deliberate unavailable selector."
                           if round_number == 4 else "Not required."))

    embed_cases = {
        1: (["embed", RULES, "--into", TESTS], TESTS, "Context live link"),
        2: (["embed", EXAMPLES, "--into", TESTS], TESTS, "second peer Context live link"),
        3: (["embed", TESTS, "--into", ARCHIVE], ARCHIVE, "nested live link"),
        4: (["embed", ARCHIVE, "--into", WORKSPACE], WORKSPACE, "cross-tree live link"),
        5: (["embed", RULES, "--into", TESTS], TESTS, "duplicate live-link boundary"),
    }
    embed_args, embed_target, embed_entry = embed_cases[round_number]
    run("embed", round_number, embed_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route=embed_entry, target_route=embed_target, scope="one exact live Source",
        provenance="lane-local Context identity", consumer="compose live maintenance views across rules/examples/tests/archive",
        expected=("Reject the duplicate live link without mutation and explain the boundary."
                  if round_number == 5 else "Add one live Embed without copying the Source content."),
        mutating=round_number != 5,
        recovery_evidence=("The existing round-1 Embed remains available and later recursive reads verify it."
                           if round_number == 5 else "Not required."))

    if round_number == 1:
        edit_uid, edit_context = uppercase_uid, RULES
        edit_args = ["edit", f"{RULES}:{edit_uid[:12]}", "Core ticker rule: uppercase remaining company-name letters in their original order. Do not invent letters."]
        edit_route = "qualified CONTEXT:UID positional selector without --context"
    elif round_number == 2:
        edit_uid, edit_context = punctuation_uid, EXAMPLES
        edit_args = ["edit", edit_uid[:12], "Punctuation rule and example: remove punctuation before constructing a ticker. North-Star, Inc. becomes NORTHSTAR after removing the comma, hyphen, space, and Inc. suffix.", "--context", EXAMPLES]
        edit_route = "bare UID positional selector qualified by --context"
    elif round_number == 3:
        edit_uid, edit_context = find_uid(EXAMPLES, "Numeral rule"), EXAMPLES
        edit_file = WORLD_DIR / "inputs" / "round-3-edit.tsv"
        edit_file.write_text(f"{edit_uid}\tNumeral rule: preserve digits 0-9, including leading zeroes, in original positions while removing spaces and punctuation.\n")
        edit_args = ["edit", "--input", str(edit_file), "--context", EXAMPLES]
        edit_route = "batch TSV --input with explicit owner Context"
    elif round_number == 4:
        edit_uid, edit_context = "00000000", EXAMPLES
        edit_args = ["edit", edit_uid, "This edit must not be applied.", "--context", EXAMPLES]
        edit_route = "unavailable bare UID prefix qualified by --context"
    else:
        edit_uid, edit_context = uppercase_uid, RULES
        edit_args = ["edit", edit_uid[:12], "Intentionally conflicting draft: lowercase remaining company-name letters in their original order. Do not invent letters.", "--context", RULES]
        edit_route = "late bare UID plus --context conflict-staging rewrite"
    run("edit", round_number, edit_args, targets=[edit_context], starting_state=state,
        entry_route=edit_route,
        target_route=edit_context, scope="one exact directly owned Memory", provenance=f"selected UID {edit_uid}",
        consumer="clarify rules, probe stale selection, and stage a detectable conflict",
        expected=("Reject the unavailable selector without mutation." if round_number == 4 else "Replace exactly one Memory while preserving its UID."),
        mutating=round_number != 4,
        recovery_evidence=("Round 5 edits a valid rule UID after the deliberate unavailable-selector attempt."
                           if round_number == 4 else "Not required."))

    replace_cases = {
        1: (["replace", "Base ticker rule", "Core ticker rule", "--context", RULES, "--direct"], [RULES], "literal direct replacement"),
        2: (["replace", "REMOVE PUNCTUATION", "strip punctuation", "--ignore-case", "--context", EXAMPLES, "--context-only"], [EXAMPLES], "case-insensitive replacement"),
        3: (["replace", r"digits 0-9", "digits 0 through 9", "--regex", "--context", RULES, "--context", EXAMPLES, "--context-only"], [RULES, EXAMPLES], "multi-Context regex replacement"),
        4: (["replace", "append .A or .B", "append dot-A (.A) or dot-B (.B)", "--context", EXAMPLES, "--direct"], [EXAMPLES], "share-class syntax clarification"),
        5: (["replace", "Intentionally conflicting draft: lowercase", "Core ticker rule: uppercase", "--context", RULES, "--direct"], [RULES], "conflict recovery replacement"),
    }
    replace_args, replace_targets, replace_entry = replace_cases[round_number]
    run("replace", round_number, replace_args, targets=replace_targets, starting_state=state,
        entry_route=replace_entry, target_route=", ".join(replace_targets), scope="declared exact/regex target roots",
        provenance="authored rule terminology and round-5 conflict draft", consumer="normalize evolving rule wording atomically",
        expected="Replace every declared match atomically and report affected Contexts/Memories.", mutating=True)

    chunk_args = {
        1: ["chunk", f"{TESTS}:{copied_uid[:12]}", "--method", "sentences"],
        2: ["chunk", copied_uid[:12], "--context", TESTS, "--method", "clauses"],
        3: ["chunk", f"{ARCHIVE}:{copied_uid[:12]}", "--method", "sentences", "--break-on", ","],
        4: ["chunk", f"{TESTS}:{copied_uid[:12]}", "--method", "paragraphs", "--max-chars", "90"],
        5: ["chunk", f"{ARCHIVE}:00000000", "--method", "sentences"],
    }[round_number]
    run("chunk", round_number, chunk_args, targets=[copy_target], starting_state=state,
        entry_route="qualified or Context-qualified direct Memory", target_route=copy_target,
        scope="one copied scratch Memory", provenance=f"Copy attempt {round_number} output {copied_uid}",
        consumer="test sentence/clause/punctuation/length splitting and UID handoff",
        expected=("Reject the unavailable selector without mutation."
                  if round_number == 5 else "Replace the copied Memory with complete ordered chunks and print old-to-new UID mapping."),
        mutating=round_number != 5,
        recovery_evidence=("The round-5 List and valid original regression Memory preserve a usable source."
                           if round_number == 5 else "Not required."))

    # Move a surviving non-chunked Memory or a chunk discovered from the target.
    if round_number == 1:
        move_source, move_target = TESTS, ARCHIVE
        move_uid = next(iter(direct_memory_uids(TESTS)))
        move_args = ["move", f"{TESTS}:{move_uid[:12]}", "--into", ARCHIVE]
        move_entry = "qualified CONTEXT:UID positional plus preferred --into target"
    elif round_number == 2:
        move_source, move_target = TESTS, ARCHIVE
        move_uid = next(iter(direct_memory_uids(TESTS)))
        move_args = ["move", "--memory", move_uid[:12], "--from", TESTS, "--to", ARCHIVE]
        move_entry = "--memory selector plus explicit --from and compatibility --to"
    elif round_number == 3:
        move_source, move_target = ARCHIVE, TESTS
        move_uid = next(iter(direct_memory_uids(ARCHIVE)))
        move_args = ["move", move_uid[:12], "--from", ARCHIVE, "--into", TESTS, "--break-links"]
        move_entry = "bare positional selector plus --from/--into and explicit --break-links"
    elif round_number == 4:
        move_source, move_target = TESTS, EXAMPLES
        move_uid = next(iter(direct_memory_uids(TESTS)))
        anchor = next(iter(direct_memory_uids(EXAMPLES)))
        move_args = ["move", move_uid[:12], "--from", TESTS, "--into", EXAMPLES, "--after", anchor[:12]]
        move_entry = "bare positional selector with explicit ordered --after insertion"
    else:
        move_source, move_target = ARCHIVE, RULES
        move_uid = "00000000"
        move_args = ["move", move_uid, "--from", ARCHIVE, "--into", RULES]
        move_entry = "unavailable bare selector with explicit Source and Target"
    run("move", round_number, move_args, targets=[move_source, move_target], starting_state=state,
        entry_route=move_entry, target_route=f"{move_source} -> {move_target}",
        scope="one exact lane-local scratch Memory", provenance=f"post-Copy/Chunk accumulated item {move_uid}",
        consumer="reorganize test/archive evidence while exercising link/order boundaries",
        expected=("Reject the unavailable selector without changing either Context."
                  if round_number == 5 else "Move one Memory atomically and report the preserved/retargeted identity."),
        mutating=round_number != 5,
        recovery_evidence=("Earlier successful moves and the final recursive Archive read verify no partial move."
                           if round_number == 5 else "Not required."))

    compare_cases = {
        1: (["compare", RULES, EXAMPLES, "--snapshot", "--direct"], "two direct Context endpoints"),
        2: (["compare", f"{RULES}:{suffix_uid[:12]}", f"{EXAMPLES}:{punctuation_uid[:12]}", "--snapshot"], "two auto-typed Memory endpoints"),
        3: (["compare", WORKSPACE, TESTS, "--snapshot", "--recursive"], "two recursive Context roots"),
        4: (["compare", WORKSPACE, ARCHIVE, "--snapshot", "--reference-descendants", "--compared-root-only"], "asymmetric descendant reach"),
        5: (["compare", RULES, TESTS, "--snapshot", "--refresh"], "fresh late-state comparison"),
    }
    compare_args, compare_entry = compare_cases[round_number]
    run("compare", round_number, compare_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route=compare_entry, target_route="explicit peer endpoints",
        scope="direct, Memory-focused, recursive, asymmetric, or refreshed",
        provenance="current rule/example/test snapshots", consumer="assess coverage and divergence between reusable rules and examples",
        expected="Return a complete comparison report/session identity without changing Context content.")

    duplicate_args = {
        1: ["find-duplicates", RULES, "--direct"],
        2: ["find-duplicates", TESTS, "--direct"],
        3: ["find-duplicates", WORKSPACE, "--recursive"],
        4: ["find-duplicates", EXAMPLES, "--direct"],
        5: ["find-duplicates", ARCHIVE, "--recursive"],
    }[round_number]
    run("find-duplicates", round_number, duplicate_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route="exact duplicate report", target_route=duplicate_args[1],
        scope="direct or per-descendant recursive frames", provenance="copies and post-Chunk artifacts",
        consumer="locate exact redundant maintenance copies",
        expected="Report every exact duplicate group in each declared frame without mutation.")

    redundancy_args = {
        1: ["find-redundancies", RULES, "--direct", "--evidence-json"],
        2: ["find-redundancies", TESTS, "--direct"],
        3: ["find-redundancies", WORKSPACE, "--recursive"],
        4: ["find-redundancies", EXAMPLES, "--direct", "--evidence-json"],
        5: ["find-redundancies", ARCHIVE, "--recursive"],
    }[round_number]
    run("find-redundancies", round_number, redundancy_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route="semantic redundancy report", target_route=redundancy_args[1],
        scope="direct or per-descendant recursive frames", provenance="semantically overlapping rule/example copies",
        consumer="identify consolidation candidates without applying them",
        expected="Return exhaustive redundancy evidence for each declared direct frame without mutation.")

    ambiguity_args = {
        1: ["find-ambiguities", RULES],
        2: ["find-ambiguities", EXAMPLES],
        3: ["find-ambiguities", WORKSPACE],
        4: ["find-ambiguities", TESTS],
        5: ["find-ambiguities", ARCHIVE],
    }[round_number]
    run("find-ambiguities", round_number, ambiguity_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route="single exact Context quality scan", target_route=ambiguity_args[1],
        scope="complete direct Memory frame", provenance="round-specific ticker rules/examples/chunks",
        consumer="find statements with multiple operational readings",
        expected="Judge each direct Memory in complete frame context and report actionable ambiguities only.")

    conflict_args = {
        1: ["find-conflicts", RULES, "--handoff-json"],
        2: ["find-conflicts", EXAMPLES],
        3: ["find-conflicts", WORKSPACE],
        4: ["find-conflicts", TESTS],
        5: ["find-conflicts", RULES, "--handoff-json"],
    }[round_number]
    conflict_provenance = {
        1: "two compatible initial rules before examples or a lowercase draft exists",
        2: "punctuation example frame after edit and normalization",
        3: "empty direct workspace root while evidence remains in descendants",
        4: "test/chunk frame after share-class reorganization",
        5: "rules frame after explicit lowercase regression draft was added; expected uppercase/lowercase conflict",
    }[round_number]
    run("find-conflicts", round_number, conflict_args, targets=[WORKSPACE, RULES, EXAMPLES, TESTS, ARCHIVE],
        starting_state=state, entry_route="single exact Context conflict scan", target_route=conflict_args[1],
        scope="complete direct Memory frame", provenance=conflict_provenance,
        consumer="detect mutually incompatible ticker rules before reuse",
        expected="Report all actionable conflicting pairs and canonical handoff data when requested.")

    if round_number == 1:
        fit_args = ["fit", "--context", RULES]
        fit_entry = "one stored Context source"
    elif round_number == 2:
        fit_args = ["fit", "text:Remove punctuation before ticker construction.", "text:North-Star, Inc. becomes NORTHSTAR."]
        fit_entry = "two forced literal propositions"
    elif round_number == 3:
        fit_args = ["fit", "--context", RULES, "--context", EXAMPLES]
        fit_entry = "multiple stored Context sources"
    elif round_number == 4:
        fit_args = ["fit", "--memory", f"{EXAMPLES}:{share_uid[:12]}", "--memory", f"{EXAMPLES}:{numeral_uid[:12]}"]
        fit_entry = "two exact stored Memory sources"
    else:
        fit_args = ["fit", "--context", RULES, "--context", EXAMPLES, "--context", TESTS,
                    "--background", "A generated class dot is syntax, while input punctuation is removed."]
        fit_entry = "late multi-Context frame plus background"
    run("fit", round_number, fit_args, targets=[RULES, EXAMPLES, TESTS], starting_state=state,
        entry_route=fit_entry, target_route="frozen proposition frame", scope="stored/literal/background propositions",
        provenance="current ticker invariant set", consumer="verify that every supplied rule and example can jointly hold",
        expected="Return a complete Fit receipt covering every proposition without mutating any Context.")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (WORLD_DIR / "inputs").mkdir(parents=True, exist_ok=True)
    for round_number in range(1, 6):
        run_round(round_number)
    assert sequence == 105, sequence
    counts = {op: sum(item["operation"] == op for item in attempts) for op in OPS}
    assert set(counts.values()) == {5}, counts
    phase = {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": "ticker",
        "phase": "core",
        "world_goal": "Grow, test, and maintain reusable synthetic company-ticker rules from varied examples, including punctuation, numerals, and share classes.",
        "execution_identity": {
            "code_snapshot_sha256": "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84",
            "catalog_sha256": "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5",
            "profile_uid": "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd",
            "store_root": str(STORE),
            "provider_policy_sha256": "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca",
            "launcher": str(WRAPPER),
        },
        "workspace_mapping": {
            "reason": "The frozen template has no pre-created ticker namespace; empty lane-local fixture Contexts were reused so no uncounted bootstrap commands were introduced.",
            "workspace": WORKSPACE,
            "rules": RULES,
            "examples": EXAMPLES,
            "tests": TESTS,
            "archive": ARCHIVE,
            "initial_current": "practice",
            "current_mutated_by_worker": False,
        },
        "total_attempts": len(attempts),
        "coverage": counts,
        "operations": {
            op: {"attempts": [
                {key: value for key, value in item.items() if key != "operation"}
                for item in attempts if item["operation"] == op
            ]}
            for op in OPS
        },
    }
    (WORLD_DIR / "phase-core.json").write_text(json.dumps(phase, ensure_ascii=False, indent=2) + "\n")
    print("Completed 105/105 core attempts.", flush=True)


if __name__ == "__main__":
    main()
