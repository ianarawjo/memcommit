"""Execute the counted task-3 core audit against the frozen world runner.

This is audit harness code, not product code. It deliberately invokes exactly
five interleaved attempts for each of the 21 core operations and records every
stdout/stderr byte plus a digest of the lane-local task-3 Context subtree.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any


REPO = Path("/Users/KimMunyeong/Github/memcommit")
WORLD_DIR = REPO / "outputs/study-long-audit-20260825-v2/worlds/task-3"
RAW_DIR = WORLD_DIR / "raw/core"
RUNNER = REPO / "outputs/study-long-audit-20260825-v2/run_world_mem.py"
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-3/profile-control/"
    "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
TASK_TREE = STORE / "contexts/task-3"
RUN_RECORD = WORLD_DIR / "core-run-record.json"

PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
CODE_DIGEST = "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84"
CATALOG_DIGEST = "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5"
PROVIDER_DIGEST = "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca"

OPERATIONS = (
    "contexts",
    "list",
    "show",
    "find",
    "search",
    "query",
    "summarize",
    "add",
    "copy",
    "reference",
    "embed",
    "edit",
    "move",
    "replace",
    "chunk",
    "compare",
    "find-duplicates",
    "find-redundancies",
    "find-ambiguities",
    "find-conflicts",
    "fit",
)

PUBLIC_GUIDANCE = (
    "task-3/remote/government/healthcare-agent/info-request/"
    "transmission-guidance/public-guidance"
)
PUBLIC_QUERY = (
    "task-3/remote/government/healthcare-agent/info-request/"
    "questions-and-answers"
)


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("context.json"), key=lambda item: str(item)):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def command_display(args: list[str]) -> str:
    def quote(value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9_./:@=-]+", value):
            return value
        return "'" + value.replace("'", "'\\''") + "'"

    return " ".join(
        quote(value)
        for value in ["python", str(RUNNER), "task-3", *args]
    )


def add_uid(record: dict[str, Any]) -> str:
    match = re.search(r"Added \[([0-9a-f]{8})\]", record["stdout"])
    if match is None:
        raise RuntimeError(
            f"counted Add attempt {record['attempt']} did not return a reusable UID"
        )
    return match.group(1)


def copied_uids(record: dict[str, Any]) -> list[str]:
    values = re.findall(r"→ \[([0-9a-f]{8})\]", record["stdout"])
    if not values:
        raise RuntimeError(
            f"counted Copy attempt {record['attempt']} did not return reusable UIDs"
        )
    return values


def entry(
    args: list[str],
    *,
    starting_state: str,
    entry_route: str,
    target_route: str,
    scope: str,
    input_provenance: str,
    consumer: str,
    expected: str,
    recovery_evidence: str = "not required",
) -> dict[str, Any]:
    return {
        "args": args,
        "starting_state": starting_state,
        "entry_route": entry_route,
        "target_route": target_route,
        "scope": scope,
        "input_provenance": input_provenance,
        "consumer": consumer,
        "expected": expected,
        "recovery_evidence": recovery_evidence,
    }


def build_round(round_number: int, variables: dict[str, Any]) -> dict[str, dict[str, Any]]:
    state = f"round {round_number}; accumulated lane-local task-3 state"
    add_uid_value = variables.get(f"add_{round_number}", "{ADD_UID}")
    copy_values = variables.get(f"copy_{round_number}", ["{COPY_UID}"])
    copy_uid_value = copy_values[0]

    if round_number == 1:
        return {
            "contexts": entry(["contexts"], starting_state=state, entry_route="bare discovery", target_route="Profile readable catalog", scope="all ordinary and granted public names", input_provenance="fixed Profile registry", consumer="discover local, READ/EMBED, QUERY-only, and SHARE routes", expected="Show the complete readable namespace with current and Grant annotations."),
            "list": entry(["list", "task-3/description", "--direct"], starting_state=state, entry_route="explicit canonical Context plus direct preset", target_route="task-3/description", scope="exact local Context", input_provenance="fixed Study goal fixture", consumer="anchor the healthcare-disclosure goal", expected="List the one goal Memory with a reusable UID."),
            "show": entry(["show", "task-3/description:77ea44c9", "--direct"], starting_state=state, entry_route="qualified direct-Memory locator", target_route="task-3/description:77ea44c9", scope="one exact local Memory", input_provenance="UID from fixed goal fixture", consumer="read the full task requirement", expected="Render only the selected goal Memory."),
            "find": entry(["find", "healthcare", "--context", "task-3/description", "--direct", "--all-results"], starting_state=state, entry_route="literal text search", target_route="task-3/description", scope="exact local Context; all matches", input_provenance="world-goal keyword", consumer="locate the task language", expected="Return the matching goal Memory without broadening scope."),
            "search": entry(["search", "Which rules determine what personal information must be excluded from the healthcare agent?", "--context", "task-3/local/guardrails", "--descendants", "--exclude-embeds", "--limit", "5"], starting_state=state, entry_route="semantic search with explicit traversal axes", target_route="task-3/local/guardrails", scope="lexical descendants; no embeds; top 5", input_provenance="world-goal question", consumer="derive an exclusion checklist", expected="Rank minimization, purpose, approval, and third-party safeguards."),
            "query": entry(["query", PUBLIC_QUERY, "What information may the healthcare-support process request, and what remains outside this Q&A endpoint's authority?"], starting_state=state, entry_route="query-only public name as selector", target_route=PUBLIC_QUERY, scope="authorized opaque QUERY interface", input_provenance="recipient-scope question", consumer="learn the endpoint boundary before candidate review", expected="Use the named QUERY-only Source and explain its information-sharing boundary without opening personal Memories."),
            "summarize": entry(["summarize", "task-3/local/guardrails", "--recursive", "--plain"], starting_state=state, entry_route="explicit Context plus recursive preset", target_route="task-3/local/guardrails", scope="full local guardrail subtree", input_provenance="fixed local policy Memories", consumer="orient the disclosure review", expected="Summarize purpose, minimization, third-party, currency, and approval constraints without mutating state."),
            "add": entry(["add", "Healthcare candidate (pending): limit disclosure to facts necessary for current care, exclude unrelated history, and require explicit user approval.", "--context", "task-3/local/guardrails/purpose-and-scope"], starting_state=state, entry_route="single inline Memory with compatibility target flag", target_route="task-3/local/guardrails/purpose-and-scope", scope="one local scratch Memory", input_provenance="agent synthesis of fixed guardrails", consumer="stage a purpose-bound rule", expected="Add one local Memory and print its reusable UID."),
            "copy": entry(["copy", "75944d44", "--from", "task-3/local/guardrails/purpose-and-scope", "--into", "task-3/local"], starting_state=state, entry_route="bare UID plus explicit Source and Target", target_route="purpose-and-scope → task-3/local", scope="one local Memory copy", input_provenance="fixed purpose-exclusion Memory", consumer="reuse a policy in the review workspace", expected="Create an independent local copy and identify Source and new UID."),
            "reference": entry(["reference", "9d626b1a", "--from", "task-3/local/guardrails/minimization-and-redaction", "--into", "task-3/local"], starting_state=state, entry_route="bare UID plus explicit Source and Target", target_route="minimization-and-redaction → task-3/local", scope="one local Memory snapshot", input_provenance="fixed redaction Memory", consumer="retain provenance-preserving review evidence", expected="Create one snapshot Reference in local scratch."),
            "embed": entry(["embed", "task-3/local/guardrails/channel-and-format", "--into", "task-3/local"], starting_state=state, entry_route="Context positional plus explicit Target", target_route="channel-and-format → task-3/local", scope="one local Context Embed", input_provenance="fixed local channel policy", consumer="make delivery rules visible without copying them", expected="Create a live Context Embed in local scratch."),
            "edit": entry(["edit", add_uid_value, "Healthcare candidate (pending, not approved): limit disclosure to facts necessary for current care, exclude unrelated history, and require explicit user approval.", "--context", "task-3/local/guardrails/purpose-and-scope"], starting_state=state, entry_route="prior Add UID plus explicit owner", target_route="task-3/local/guardrails/purpose-and-scope", scope="one newly added local Memory", input_provenance="UID from this round's Add receipt", consumer="make the review state explicit", expected="Edit the staged Memory in place and preserve its UID."),
            "move": entry(["move", copy_uid_value, "--from", "task-3/local", "--into", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="prior Copy UID plus explicit Source and Target", target_route="task-3/local → audit-and-recovery", scope="one newly copied local Memory", input_provenance="UID from this round's Copy receipt", consumer="place reused policy with audit evidence", expected="Move the Memory atomically and preserve its UID."),
            "replace": entry(["replace", "pending", "review-pending", "--context", "task-3/local/guardrails/purpose-and-scope"], starting_state=state, entry_route="literal replacement in exact Context", target_route="task-3/local/guardrails/purpose-and-scope", scope="direct Memories only", input_provenance="wording from staged candidate", consumer="test bounded bulk wording change", expected="Report the exact replacement count without crossing Context boundaries."),
            "chunk": entry(["chunk", add_uid_value, "--context", "task-3/local/guardrails/purpose-and-scope", "--method", "sentence"], starting_state=state, entry_route="invalid singular strategy boundary", target_route="task-3/local/guardrails/purpose-and-scope", scope="one staged local Memory", input_provenance="UID from this round's Add receipt", consumer="test option discoverability before any split", expected="Reject the unsupported method before mutation and identify valid choices.", recovery_evidence="round 3 uses the valid 'sentences' spelling on a later staged Memory"),
            "compare": entry(["compare", "task-3/local/guardrails/purpose-and-scope", "task-3/local/guardrails/minimization-and-redaction", "--direct", "--snapshot"], starting_state=state, entry_route="two explicit Context endpoints", target_route="purpose-and-scope ↔ minimization-and-redaction", scope="direct peer frames", input_provenance="fixed guardrail branches", consumer="relate purpose limitation to minimization", expected="Produce a stable read-only comparison with the two roles identifiable."),
            "find-duplicates": entry(["find-duplicates", "task-3/local/guardrails/purpose-and-scope", "--direct"], starting_state=state, entry_route="exact Context positional", target_route="task-3/local/guardrails/purpose-and-scope", scope="direct exact-duplicate analysis", input_provenance="fixed plus staged purpose rules", consumer="prevent duplicated disclosure constraints", expected="Report all exact duplicate groups or a compact zero result."),
            "find-redundancies": entry(["find-redundancies", "task-3/local/guardrails/purpose-and-scope", "--direct"], starting_state=state, entry_route="exact Context positional", target_route="task-3/local/guardrails/purpose-and-scope", scope="one direct semantic frame", input_provenance="fixed plus staged purpose rules", consumer="identify overlapping review constraints", expected="Report complete semantic redundancy evidence without mutation."),
            "find-ambiguities": entry(["find-ambiguities", "task-3/local/guardrails/purpose-and-scope"], starting_state=state, entry_route="exact Context positional", target_route="task-3/local/guardrails/purpose-and-scope", scope="one direct semantic frame", input_provenance="fixed plus staged purpose rules", consumer="identify underspecified sharing criteria", expected="Classify every direct Memory and foreground ambiguous items."),
            "find-conflicts": entry(["find-conflicts", "task-3/local/guardrails/purpose-and-scope"], starting_state=state, entry_route="exact Context positional", target_route="task-3/local/guardrails/purpose-and-scope", scope="all direct Memory pairs", input_provenance="fixed plus staged purpose rules", consumer="identify contradictory disclosure criteria", expected="Classify every pair and publish no partial result on failure."),
            "fit": entry(["fit", "task-3/local/personal-memory", "task-3/local/guardrails/purpose-and-scope"], starting_state=state, entry_route="two auto-typed Context operands", target_route="personal root + purpose rules", scope="direct Memories from each operand", input_provenance="fixed local Contexts", consumer="test empty-root handling before fit judgment", expected="Fail clearly if the personal root contributes no direct propositions; do not imply approval."),
        }

    if round_number == 2:
        return {
            "contexts": entry(["contexts"], starting_state=state, entry_route="bare rediscovery after first mutations", target_route="Profile readable catalog", scope="all ordinary and granted public names", input_provenance="Profile registry plus accumulated local state", consumer="reorient after staging", expected="Preserve the same complete namespace and current marker."),
            "list": entry(["list", "task-3/local/personal-memory/2026/06", "--direct"], starting_state=state, entry_route="exact leaf Context", target_route="task-3/local/personal-memory/2026/06", scope="one month, direct", input_provenance="fixed recent personal Memories", consumer="establish an exclusion-heavy comparison set", expected="List all and only the month-owned Memories."),
            "show": entry(["show", "task-3/local/personal-memory/2026/06:e682f0fd"], starting_state=state, entry_route="qualified personal-Memory locator", target_route="task-3/local/personal-memory/2026/06:e682f0fd", scope="one exact Memory", input_provenance="fixed restaurant/hearing detail", consumer="inspect an irrelevant candidate", expected="Render the exact personal detail without siblings."),
            "find": entry(["find", "appointment", "--context", "task-3/local/personal-memory", "--recursive", "--all-results"], starting_state=state, entry_route="literal recursive search", target_route="task-3/local/personal-memory", scope="lexical descendants plus embeds; all matches", input_provenance="healthcare-adjacent keyword", consumer="enumerate scheduling mentions for manual disposition", expected="Return complete scoped matches while preserving source Context names."),
            "search": entry(["search", "Which personal details could help with medication timing, clinic access, waiting, or transport?", "--context", "task-3/local/personal-memory", "--descendants", "--exclude-embeds", "--limit", "5"], starting_state=state, entry_route="semantic recursive candidate search", target_route="task-3/local/personal-memory", scope="all lexical descendants; no embeds; top 5", input_provenance="candidate-category question", consumer="observe whether relevance mixes personal and third-party facts", expected="Rank relevant Memories with owners but make no approval or safety claim."),
            "query": entry(["query", "What exact information-sharing actions can this endpoint perform?", "--context", PUBLIC_QUERY], starting_state=state, entry_route="question plus --context QUERY-only Source", target_route=PUBLIC_QUERY, scope="authorized opaque QUERY interface", input_provenance="capability-boundary question", consumer="cross-check positional query-only targeting", expected="Use the named QUERY-only Source and explain it cannot select or transmit personal Memories."),
            "summarize": entry(["summarize", "task-3/local/personal-memory/2024/03", "--direct", "--plain"], starting_state=state, entry_route="exact month direct summary", target_route="task-3/local/personal-memory/2024/03", scope="ten direct personal Memories", input_provenance="fixed healthcare-adjacent month", consumer="test whether narrative mixes distinct disclosure dispositions", expected="Summarize faithfully while retaining uncertainty and third-party distinctions where material."),
            "add": entry(["add", "DRAFT ONLY: medication timing is a candidate; verify the medication identity, current prescription, recipient, purpose, and relevance before approval.", "--to", "task-3/local"], starting_state=state, entry_route="single inline Memory with preferred target flag", target_route="task-3/local", scope="one local scratch Memory", input_provenance="personal Memory plus currency guardrails", consumer="stage a withheld medication candidate", expected="Add one local draft and print its reusable UID."),
            "copy": entry(["copy", "task-3/local/personal-memory/2024/03:12ba4249", "--into", "task-3/local"], starting_state=state, entry_route="qualified Memory locator plus Target", target_route="2024/03 → task-3/local", scope="one local personal Memory copy", input_provenance="fixed historical medication instruction", consumer="make a reviewable independent candidate", expected="Copy locally with a new UID and retain Source provenance in the receipt."),
            "reference": entry(["reference", "task-3/local/personal-memory/2024/03:3069baac", "--into", "task-3/local"], starting_state=state, entry_route="qualified Memory locator", target_route="2024/03 → task-3/local", scope="one third-party snapshot", input_provenance="fixed brother transport preference", consumer="retain explicit excluded evidence", expected="Create a local Reference without changing Source."),
            "embed": entry(["embed", "task-3/local/guardrails/approval-and-delivery", "--into", "task-3/local"], starting_state=state, entry_route="local Context embed", target_route="approval-and-delivery → task-3/local", scope="one Context link", input_provenance="fixed approval policy", consumer="keep approval boundaries live in scratch", expected="Embed the policy Context once."),
            "edit": entry(["edit", add_uid_value, "DRAFT ONLY: medication timing is a candidate; verify the medication identity, current status, recipient, purpose, and relevance before approval.", "--context", "task-3/local"], starting_state=state, entry_route="prior Add UID", target_route="task-3/local", scope="one local draft", input_provenance="this round's Add receipt", consumer="clarify that current status must be checked", expected="Edit only the staged draft in place."),
            "move": entry(["move", copy_uid_value, "--from", "task-3/local", "--into", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="prior Copy UID", target_route="task-3/local → audit-and-recovery", scope="one copied candidate", input_provenance="this round's Copy receipt", consumer="quarantine historical medication evidence with audit records", expected="Move locally and preserve UID."),
            "replace": entry(["replace", "medication identity", "specific medication identity", "--context", "task-3/local"], starting_state=state, entry_route="exact direct replacement", target_route="task-3/local", scope="direct local scratch Memories", input_provenance="staged draft wording", consumer="test a bounded clarification", expected="Change only exact matches and report count."),
            "chunk": entry(["chunk", add_uid_value, "--context", "task-3/local", "--method", "clauses"], starting_state=state, entry_route="valid clause strategy", target_route="task-3/local", scope="one safety-gated draft", input_provenance="this round's Add receipt", consumer="test whether splitting preserves the not-approved safety frame", expected="Either preserve status/conditions with every chunk or make the semantic risk explicit; identify every created UID."),
            "compare": entry(["compare", "task-3/local/personal-memory/2024/03", "task-3/local/personal-memory/2024/12", "--direct", "--snapshot"], starting_state=state, entry_route="two month Contexts", target_route="2024/03 ↔ 2024/12", scope="two direct ten-Memory frames", input_provenance="fixed personal history", consumer="compare recurring healthcare-adjacent patterns", expected="Produce role-clear, read-only comparison evidence."),
            "find-duplicates": entry(["find-duplicates", "task-3/local", "--direct"], starting_state=state, entry_route="local scratch direct", target_route="task-3/local", scope="direct exact duplicate analysis", input_provenance="accumulated copied/referenced/embedded items", consumer="check exact duplication in scratch", expected="Separate ordinary Memories from References/Embeds and report exact groups compactly."),
            "find-redundancies": entry(["find-redundancies", "task-3/local", "--direct"], starting_state=state, entry_route="local scratch direct", target_route="task-3/local", scope="one accumulated semantic frame", input_provenance="staged drafts and copied/reference evidence", consumer="detect overlapping candidates", expected="Produce exhaustive DUN evidence without treating link objects as unowned facts."),
            "find-ambiguities": entry(["find-ambiguities", "task-3/local"], starting_state=state, entry_route="local scratch direct", target_route="task-3/local", scope="one accumulated semantic frame", input_provenance="staged candidates plus clause chunks", consumer="check whether curation artifacts are self-contained", expected="Flag missing identity/currentness/approval qualifiers and classify the complete frame."),
            "find-conflicts": entry(["find-conflicts", "task-3/local"], starting_state=state, entry_route="local scratch direct", target_route="task-3/local", scope="all direct ordinary-Memory pairs", input_provenance="accumulated scratch", consumer="ensure excluded evidence does not contradict staged decisions", expected="Classify every pair without applying a resolution."),
            "fit": entry(["fit", "task-3/local/personal-memory/2024/03", "task-3/local/guardrails/purpose-and-scope"], starting_state=state, entry_route="two exact Context operands", target_route="2024/03 + purpose rules", scope="two direct proposition frames", input_provenance="fixed month and guardrails", consumer="test whether all propositions jointly hold", expected="Return a receipt with enough evidence to avoid mistaking fit for disclosure approval."),
        }

    if round_number == 3:
        return {
            "contexts": entry(["contexts"], starting_state=state, entry_route="bare rediscovery after links and chunks", target_route="Profile readable catalog", scope="all ordinary and granted public names", input_provenance="fixed registry and accumulated scratch", consumer="reorient before provenance-driven round", expected="Show stable catalog identity despite changed direct items."),
            "list": entry(["list", "task-3/local", "--recursive"], starting_state=state, entry_route="recursive local workspace list", target_route="task-3/local", scope="lexical descendants and embedded Contexts", input_provenance="all accumulated local review state", consumer="discover created chunk UIDs and linked evidence", expected="List every effective item with owner/provenance without hiding generated UIDs."),
            "show": entry(["show", "task-3/local", "--recursive"], starting_state=state, entry_route="recursive Context inspection", target_route="task-3/local", scope="lexical descendants and embedded Contexts", input_provenance="accumulated local workspace", consumer="inspect source/link distinctions after mutation", expected="Render a readable hierarchical view preserving item kinds and owners."),
            "find": entry(["find", "third[- ]party", "--regex", "--context", "task-3/local/personal-memory", "--recursive", "--all-results"], starting_state=state, entry_route="regex recursive enumeration", target_route="task-3/local/personal-memory", scope="all descendant matches", input_provenance="privacy policy language", consumer="enumerate third-party-related personal Memories", expected="Return all scoped matches with exact owners for manual exclusion review."),
            "search": entry(["search", "What is the minimum necessary health information and which third-party details must be excluded?", "--context", "task-3/local/personal-memory/2024/03", "--context", "task-3/local/guardrails/privacy-and-others", "--context-only", "--exclude-embeds", "--limit", "5"], starting_state=state, entry_route="repeatable multi-root semantic search", target_route="2024/03 + privacy-and-others", scope="two direct roots; no embeds; top 5 aggregate", input_provenance="candidate and exclusion question", consumer="inspect multi-root coverage under a global limit", expected="Identify owners and make source coverage visible even if one root contributes no top result."),
            "query": entry(["query", "Which guardrails require excluding unrelated or third-party information and withholding transfer until explicit approval?", "--context", "task-3/local/guardrails/purpose-and-scope", "--context", "task-3/local/guardrails/privacy-and-others", "--context", "task-3/local/guardrails/approval-and-delivery", "--context-only", "--exclude-embeds"], starting_state=state, entry_route="ordinary multi-root Query", target_route="three local guardrail branches", scope="direct roots; no embeds", input_provenance="fixed policy synthesis question", consumer="ground the local review criteria", expected="Answer only from the three named ordinary Sources and cite used Memories."),
            "summarize": entry(["summarize", PUBLIC_GUIDANCE, "--direct", "--plain"], starting_state=state, entry_route="granted descendant direct summary", target_route=PUBLIC_GUIDANCE, scope="25 public guidance Memories", input_provenance="READ/DERIVE granted Source", consumer="orient external-boundary review", expected="Summarize only the readable granted Source with Grant provenance and no mutation."),
            "add": entry(["add", "NOT SHARED: exclude relatives, contacts, and unrelated third-party details unless the user separately approves a necessary support role.", "--context", "task-3/local"], starting_state=state, entry_route="single local scratch Add", target_route="task-3/local", scope="one exclusion decision draft", input_provenance="privacy guardrails plus retrieved evidence", consumer="record a local exclusion rule", expected="Create one local Memory with reusable UID."),
            "copy": entry(["copy", "e6023aed", "--from", "task-3/local/personal-memory/2024/03", "--into", "task-3/local"], starting_state=state, entry_route="bare UID and explicit endpoints", target_route="2024/03 → task-3/local", scope="one clinic-condition copy", input_provenance="fixed prior Find/Search candidate", consumer="prepare an independently editable candidate", expected="Copy locally and report the new UID."),
            "reference": entry(["reference", "task-3/local/personal-memory/2024/12:e9515d6b", "--into", "task-3/local"], starting_state=state, entry_route="qualified cross-month locator", target_route="2024/12 → task-3/local", scope="one local Memory snapshot", input_provenance="fixed prior-month evidence", consumer="retain a provenance-bearing comparison item", expected="Create one snapshot Reference without Source mutation."),
            "embed": entry(["embed", "task-3/local/guardrails/evidence-and-uncertainty", "--into", "task-3/local"], starting_state=state, entry_route="third local Context Embed", target_route="evidence-and-uncertainty → task-3/local", scope="one Context link", input_provenance="fixed uncertainty guardrails", consumer="keep currency rules live beside candidates", expected="Embed once and identify its position."),
            "edit": entry(["edit", copy_uid_value, "DRAFT ONLY candidate: the user waited because seats were unavailable; verify the current accommodation need before any approval.", "--context", "task-3/local"], starting_state=state, entry_route="prior Copy UID as consumer input", target_route="task-3/local", scope="one copied clinic detail", input_provenance="this round's Copy receipt", consumer="generalize a facility claim into a review candidate", expected="Edit the copy only; preserve original Source."),
            "move": entry(["move", add_uid_value, "--from", "task-3/local", "--into", "task-3/local/guardrails/privacy-and-others"], starting_state=state, entry_route="prior Add UID as consumer input", target_route="task-3/local → privacy-and-others", scope="one exclusion rule", input_provenance="this round's Add receipt", consumer="place exclusion decision beside source policy", expected="Move locally, preserving UID and checkpoints."),
            "replace": entry(["replace", "NOT SHARED", "DRAFT ONLY", "--context", "task-3/local", "--context", "task-3/local/guardrails/privacy-and-others"], starting_state=state, entry_route="repeatable exact Context targets", target_route="task-3/local + privacy-and-others", scope="two direct local roots", input_provenance="staged status labels", consumer="normalize pre-approval terminology", expected="Replace only matching direct Memories in both frozen roots and report per-target results."),
            "chunk": entry(["chunk", add_uid_value, "--context", "task-3/local/guardrails/privacy-and-others", "--method", "sentences"], starting_state=state, entry_route="recovered valid plural strategy", target_route="task-3/local/guardrails/privacy-and-others", scope="one moved one-sentence draft", input_provenance="round 1 parser recovery plus this round's Move", consumer="verify safe one-chunk no-op behavior", expected="Accept the valid strategy and leave a one-sentence Memory semantically whole.", recovery_evidence="recovery from round 1 singular-method rejection"),
            "compare": entry(["compare", "task-3/local/personal-memory/2024/03:18d58666", "task-3/local/personal-memory/2024/03:e6023aed", "--snapshot"], starting_state=state, entry_route="two auto-typed direct-Memory endpoints", target_route="back discomfort Memory ↔ clinic seating Memory", scope="two direct Memories with neighbors as context", input_provenance="fixed personal evidence", consumer="test evidence-level relation clarity", expected="Name both exact Memories and explain their relationship without elevating either to an approved fact."),
            "find-duplicates": entry(["find-duplicates", "task-3/local/guardrails", "--recursive"], starting_state=state, entry_route="recursive quality scope", target_route="task-3/local/guardrails", scope="each lexical descendant as an exact duplicate frame", input_provenance="fixed guardrail tree plus staged additions", consumer="find repeated policy wording across branches", expected="Foreground actionable groups and summarize empty descendant frames compactly."),
            "find-redundancies": entry(["find-redundancies", "task-3/local/personal-memory/2024/11", "--direct", "--evidence-json"], starting_state=state, entry_route="exact month plus machine evidence", target_route="task-3/local/personal-memory/2024/11", scope="one ten-Memory semantic frame", input_provenance="fixed month with known mother-privacy overlap", consumer="obtain reusable redundancy evidence", expected="Return complete human report plus canonical evidence JSON for every finding."),
            "find-ambiguities": entry(["find-ambiguities", "task-3/local/personal-memory/2024/03"], starting_state=state, entry_route="exact personal month", target_route="task-3/local/personal-memory/2024/03", scope="one ten-Memory semantic frame", input_provenance="fixed healthcare-adjacent facts", consumer="separate stale or underspecified candidates", expected="Classify all ten and identify medication/currentness/deictic ambiguities."),
            "find-conflicts": entry(["find-conflicts", "task-3/local/personal-memory/2024/03", "--handoff-json"], starting_state=state, entry_route="exact month plus canonical handoff", target_route="task-3/local/personal-memory/2024/03", scope="all 45 direct pairs", input_provenance="fixed healthcare-adjacent facts", consumer="obtain reusable conflict evidence", expected="Classify every pair and print handoffs only for findings."),
            "fit": entry(["fit", "--memory", "task-3/local/personal-memory/2024/03:18d58666", "--context", "task-3/local/guardrails/minimization-and-redaction"], starting_state=state, entry_route="typed direct Memory plus Context Source", target_route="back discomfort fact + minimization rules", scope="one exact Memory plus one direct policy frame", input_provenance="fixed candidate and policy", consumer="test mixed typed-source evidence", expected="Produce a traceable Fit receipt without implying external approval."),
        }

    if round_number == 4:
        return {
            "contexts": entry(["contexts"], starting_state=state, entry_route="late bare discovery", target_route="Profile readable catalog", scope="all ordinary and granted public names", input_provenance="fixed registry plus accumulated state", consumer="locate granted scopes before regression checks", expected="Keep the task-3 Grant names and capabilities discoverable."),
            "list": entry(["list", PUBLIC_GUIDANCE, "--direct"], starting_state=state, entry_route="granted descendant direct list", target_route=PUBLIC_GUIDANCE, scope="25 READ-granted Memories", input_provenance="granted-memory Store", consumer="select one stale-information warning", expected="List all public guidance Memories with public owner and reusable UIDs."),
            "show": entry(["show", f"{PUBLIC_GUIDANCE}:dcf1b441"], starting_state=state, entry_route="qualified granted-Memory locator", target_route=f"{PUBLIC_GUIDANCE}:dcf1b441", scope="one exact granted Memory", input_provenance="UID from fixed granted guidance", consumer="inspect the currency warning", expected="Render the granted Memory under its public name."),
            "find": entry(["find", "third[- ]party", "--regex", "--context", "task-3/local/personal-memory", "--recursive", "--all-results"], starting_state=state, entry_route="high-volume regex boundary", target_route="task-3/local/personal-memory", scope="all descendant occurrences", input_provenance="privacy classification keyword", consumer="quantify exhaustive manual-review cost", expected="Return complete results or a clear display boundary without silently truncating semantics."),
            "search": entry(["search", "What current Memories mention problems during or after a medical visit?", "--context", "task-3/local/personal-memory/2024/03", "--context-only", "--exclude-embeds", "--limit", "5"], starting_state=state, entry_route="bounded exact-month semantic search", target_route="task-3/local/personal-memory/2024/03", scope="direct only; no embeds; top 5", input_provenance="candidate refinement question", consumer="recover from broad retrieval with a precise frame", expected="Return only retained current month Memories with owners."),
            "query": entry(["query", "Which exact categories can the institution process, what information may be routed to third parties, and what can this Q&A endpoint not verify or transmit?", "--context", PUBLIC_QUERY], starting_state=state, entry_route="exact QUERY-only --context regression", target_route=PUBLIC_QUERY, scope="authorized opaque Source", input_provenance="recipient-boundary checklist", consumer="verify targeting before any transfer decision", expected="Label and use the named public query Source; never silently substitute local personal Memory."),
            "summarize": entry(["summarize", "task-3/local", "--direct", "--plain"], starting_state=state, entry_route="accumulated scratch direct summary", target_route="task-3/local", scope="direct drafts, copies, references, and embeds", input_provenance="rounds 1-3 outputs", consumer="assess review state", expected="Distinguish item kinds and draft/approval state in a read-only summary."),
            "add": entry(["add", "REVIEW STATE: no healthcare disclosure is approved; candidates remain subject to recipient, purpose, currency, necessity, third-party, and exact-item checks.", "--to", "task-3/local"], starting_state=state, entry_route="late local review marker", target_route="task-3/local", scope="one local scratch Memory", input_provenance="accumulated findings", consumer="record the fail-closed decision state", expected="Add one local review Memory and print its UID."),
            "copy": entry(["copy", "18d58666", "d7f215c6", "--from", "task-3/local/personal-memory/2024/03", "--into", "task-3/local"], starting_state=state, entry_route="ordered batch UIDs with shared Source", target_route="2024/03 → task-3/local", scope="two local Memories copied atomically", input_provenance="candidate plus uncertainty evidence", consumer="stage a paired review packet", expected="Copy both in order as one operation and print both new UIDs."),
            "reference": entry(["reference", "dcf1b441", "--from", PUBLIC_GUIDANCE, "--into", "task-3/local"], starting_state=state, entry_route="selective granted Memory Reference", target_route=f"{PUBLIC_GUIDANCE} → task-3/local", scope="one READ/EXPORT-granted Memory snapshot", input_provenance="granted stale-information warning", consumer="regress previously failing selective Grant route", expected="Create one local Reference or state the exact missing authority; must not misreport the granted Context as absent."),
            "embed": entry(["embed", PUBLIC_GUIDANCE, "--into", "task-3/local"], starting_state=state, entry_route="whole granted descendant Embed", target_route=f"{PUBLIC_GUIDANCE} → task-3/local", scope="one readable public Context link", input_provenance="READ/EMBED Grant", consumer="contrast whole-Context route with selective Reference", expected="Embed the public Context once without copying its Memories."),
            "edit": entry(["edit", copy_uid_value, "Candidate INCLUDE (DRAFT ONLY): the user stood for 20 minutes when no waiting chair was available and experienced back discomfort; verify current accommodation relevance before approval.", "--context", "task-3/local"], starting_state=state, entry_route="first UID from batch Copy", target_route="task-3/local", scope="one copied candidate", input_provenance="this round's batch receipt", consumer="turn evidence into an explicit draft candidate", expected="Edit only the first copy and retain DRAFT ONLY status."),
            "move": entry(["move", *copy_values, "--from", "task-3/local", "--into", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="ordered batch from prior Copy", target_route="task-3/local → audit-and-recovery", scope="two newly copied Memories", input_provenance="this round's batch Copy receipt", consumer="quarantine candidate and uncertainty evidence together", expected="Move both atomically in order and preserve UIDs."),
            "replace": entry(["replace", "current accommodation relevance", "current accommodation necessity", "--context", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="late exact replacement", target_route="task-3/local/guardrails/audit-and-recovery", scope="direct audit Memories", input_provenance="this round's moved edited candidate", consumer="test post-move target continuity", expected="Find the moved Memory under the canonical Target and change only the reviewed phrase."),
            "chunk": entry(["chunk", add_uid_value, "--context", "task-3/local", "--method", "paragraphs"], starting_state=state, entry_route="paragraph strategy on one paragraph", target_route="task-3/local", scope="one review-state Memory", input_provenance="this round's Add UID", consumer="verify safe no-op chunking", expected="Leave one-paragraph safety state whole and report no semantic split."),
            "compare": entry(["compare", "task-3/local", PUBLIC_GUIDANCE, "--recursive", "--snapshot", "--refresh"], starting_state=state, entry_route="mixed local/granted comparison", target_route=f"task-3/local ↔ {PUBLIC_GUIDANCE}", scope="recursive local frame and readable granted frame", input_provenance="accumulated candidates plus public guidance", consumer="compare concrete review state to external guidance", expected="Preserve Source roles, Grant provenance, exclusions, and uncertainty in fresh analysis."),
            "find-duplicates": entry(["find-duplicates", "task-3/local/personal-memory/2024/11", "--direct"], starting_state=state, entry_route="bounded exact month", target_route="task-3/local/personal-memory/2024/11", scope="ten direct Memories", input_provenance="fixed month", consumer="recover from recursive report breadth", expected="Compactly report exact duplicate groups or zero."),
            "find-redundancies": entry(["find-redundancies", "task-3/local/guardrails", "--recursive"], starting_state=state, entry_route="recursive policy analysis", target_route="task-3/local/guardrails", scope="each guardrail child as an independent frame", input_provenance="fixed policy tree plus local additions", consumer="test broad report density and planner behavior", expected="Cover every frame once, foreground findings, and compact empty frames."),
            "find-ambiguities": entry(["find-ambiguities", PUBLIC_GUIDANCE], starting_state=state, entry_route="granted READ/DERIVE Source", target_route=PUBLIC_GUIDANCE, scope="25 direct granted Memories", input_provenance="public guidance Grant", consumer="test quality analysis across Grant boundary", expected="Analyze the complete readable frame or fail before provider connection with the exact authority reason."),
            "find-conflicts": entry(["find-conflicts", "task-3/local/guardrails/privacy-and-others"], starting_state=state, entry_route="exact policy branch after moved addition", target_route="task-3/local/guardrails/privacy-and-others", scope="all direct pairs", input_provenance="fixed privacy rules plus staged exclusion", consumer="check local policy consistency", expected="Classify every pair and preserve Source unchanged."),
            "fit": entry(["fit", "task-3/local", PUBLIC_GUIDANCE], starting_state=state, entry_route="local plus granted auto operands", target_route=f"task-3/local + {PUBLIC_GUIDANCE}", scope="direct propositions from both Sources", input_provenance="accumulated scratch and READ/DERIVE Grant", consumer="test mixed-authority Fit evidence", expected="Preserve Source ownership and explain support; never treat YES as approval."),
        }

    if round_number == 5:
        moved_candidate = variables.get("copy_4", ["{ROUND4_COPY_UID}"])[0]
        return {
            "contexts": entry(["contexts"], starting_state=state, entry_route="final bare discovery", target_route="Profile readable catalog", scope="all ordinary and granted public names", input_provenance="final accumulated lane state", consumer="verify navigation continuity", expected="Retain the same readable routes and unchanged current marker."),
            "list": entry(["list", "task-3/local/guardrails/audit-and-recovery", "--direct"], starting_state=state, entry_route="final bounded audit list", target_route="task-3/local/guardrails/audit-and-recovery", scope="direct audit records and moved candidates", input_provenance="all prior mutation receipts", consumer="inspect the final local review packet", expected="List every audit item with reusable IDs and kinds."),
            "show": entry(["show", f"task-3/local/guardrails/audit-and-recovery:{moved_candidate}"], starting_state=state, entry_route="prior round Move UID", target_route=f"audit-and-recovery:{moved_candidate}", scope="one moved candidate", input_provenance="round 4 Copy/Edit/Move chain", consumer="verify state continuity", expected="Resolve the canonical post-move owner and show the edited draft."),
            "find": entry(["find", "clinic|medication|back|appointment", "--regex", "--context", "task-3/local/personal-memory/2024/03", "--direct", "--all-results"], starting_state=state, entry_route="final bounded regex", target_route="task-3/local/personal-memory/2024/03", scope="one direct month", input_provenance="candidate category terms", consumer="produce a bounded exact evidence set", expected="Return all seven-ish month matches without broadening."),
            "search": entry(["search", "Which staged healthcare candidates are safe, current, necessary, non-third-party, and explicitly approved?", "--context", "task-3/local", "--context", "task-3/local/guardrails/audit-and-recovery", "--context-only", "--exclude-embeds", "--limit", "8"], starting_state=state, entry_route="late accumulated multi-root search", target_route="task-3/local + audit-and-recovery", scope="two direct roots; no embeds; top 8", input_provenance="all staged artifacts", consumer="test whether relevance becomes a safe disposition", expected="Rank candidates and review-state evidence but make no unsupported approval claim."),
            "query": entry(["query", PUBLIC_QUERY, "State the recipient scope, purpose categories, transmitted-unit rule, possible downstream uses, and what this endpoint cannot do."], starting_state=state, entry_route="final exact QUERY-only selector", target_route=PUBLIC_QUERY, scope="authorized opaque QUERY interface", input_provenance="final decision checklist", consumer="establish remaining unknowns at the decision gate", expected="Answer from the exact public Source with References and no local personal substitution."),
            "summarize": entry(["summarize", "task-3/local", "--recursive", "--plain"], starting_state=state, entry_route="final recursive local summary", target_route="task-3/local", scope="local descendants and all embedded Contexts", input_provenance="complete accumulated local review state", consumer="assess what remains before approval", expected="Separate candidates, exclusions, uncertainty, and approval state; do not claim transfer."),
            "add": entry(["add", "AUDIT RESULT: no transfer was executed and no approval was inferred; candidate facts remain stale or underspecified and require the user's exact recipient, purpose, item, and channel decision.", "--context", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="final audit record Add", target_route="task-3/local/guardrails/audit-and-recovery", scope="one local decision record", input_provenance="complete core-phase evidence", consumer="persist the genuine decision gate locally", expected="Add one local fail-closed record with reusable UID."),
            "copy": entry(["copy", "dcf1b441", "--from", PUBLIC_GUIDANCE, "--into", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="selective granted Memory Copy", target_route=f"{PUBLIC_GUIDANCE} → audit-and-recovery", scope="one READ/EXPORT-granted Memory", input_provenance="granted currency warning", consumer="regress the second previously failing selective Grant route", expected="Copy one public Memory locally or identify the exact authority failure; never say the readable Grant is absent."),
            "reference": entry(["reference", moved_candidate, "--from", "task-3/local/guardrails/audit-and-recovery", "--into", "task-3/local"], starting_state=state, entry_route="post-move UID with explicit canonical Source", target_route="audit-and-recovery → task-3/local", scope="one local snapshot", input_provenance="round 4 state-continuity chain", consumer="retain a final candidate reference in scratch", expected="Create a snapshot under local while Source remains unchanged."),
            "embed": entry(["embed", f"task-3/local/guardrails/audit-and-recovery:{add_uid_value}", "--into", "task-3/local"], starting_state=state, entry_route="qualified live Memory Embed", target_route="audit-and-recovery Memory → task-3/local", scope="one newly added decision record", input_provenance="this round's Add receipt", consumer="keep final decision state live in the workspace", expected="Create one live Memory Embed and identify its UID and placement."),
            "edit": entry(["edit", add_uid_value, "AUDIT RESULT: no transfer was executed and no approval was inferred; candidate facts remain stale or underspecified and require the user's exact recipient, purpose, item, channel, and retention decision.", "--context", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="final Add UID", target_route="task-3/local/guardrails/audit-and-recovery", scope="one local audit record", input_provenance="this round's Add receipt", consumer="add the missing retention decision", expected="Edit in place; any live Memory Embed must continue resolving to the same UID."),
            "move": entry(["move", add_uid_value, "--from", "task-3/local/guardrails/audit-and-recovery", "--into", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="same-Source/same-Target boundary", target_route="audit-and-recovery → itself", scope="one final audit Memory", input_provenance="this round's Add/Edit chain", consumer="test no-op protection", expected="Reject the meaningless move before mutation and preserve the record.", recovery_evidence="the following Replace/Chunk/quality operations successfully resolve the same Source and UID"),
            "replace": entry(["replace", "APPROVED AND SHARED", "SENT", "--context", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="no-match safety boundary", target_route="task-3/local/guardrails/audit-and-recovery", scope="direct audit Memories", input_provenance="prohibited state label", consumer="verify no false sent-state exists", expected="Report zero matches and leave state unchanged."),
            "chunk": entry(["chunk", add_uid_value, "--context", "task-3/local/guardrails/audit-and-recovery", "--method", "sentences"], starting_state=state, entry_route="final valid sentence strategy", target_route="task-3/local/guardrails/audit-and-recovery", scope="one single-sentence audit record", input_provenance="this round's Add/Edit chain", consumer="confirm safety state remains whole", expected="Produce one semantic chunk/no split and preserve the final record."),
            "compare": entry(["compare", "task-3/local/guardrails/audit-and-recovery", "task-3/local/guardrails/approval-and-delivery", "--direct", "--snapshot", "--refresh"], starting_state=state, entry_route="final fresh policy comparison", target_route="audit-and-recovery ↔ approval-and-delivery", scope="two direct local frames", input_provenance="accumulated audit records and fixed approval rules", consumer="explain the remaining human decision", expected="State why approval cannot be inferred and what must be reviewed."),
            "find-duplicates": entry(["find-duplicates", "task-3/local/guardrails/audit-and-recovery", "--direct"], starting_state=state, entry_route="final exact audit frame", target_route="task-3/local/guardrails/audit-and-recovery", scope="direct exact duplicates", input_provenance="all moved/copied/audit evidence", consumer="check packet hygiene", expected="Compactly report exact groups or zero."),
            "find-redundancies": entry(["find-redundancies", "task-3/local/guardrails/audit-and-recovery", "--direct", "--evidence-json"], starting_state=state, entry_route="final semantic frame plus JSON", target_route="task-3/local/guardrails/audit-and-recovery", scope="one direct accumulated frame", input_provenance="final local packet", consumer="identify overlapping records before user review", expected="Return complete reusable evidence without changing the packet."),
            "find-ambiguities": entry(["find-ambiguities", "task-3/local/guardrails/audit-and-recovery"], starting_state=state, entry_route="final exact audit frame", target_route="task-3/local/guardrails/audit-and-recovery", scope="one direct accumulated frame", input_provenance="final local packet", consumer="identify remaining verification gaps", expected="Classify every ordinary Memory and foreground stale/currentness/recipient gaps."),
            "find-conflicts": entry(["find-conflicts", "task-3/local/guardrails/audit-and-recovery", "--handoff-json"], starting_state=state, entry_route="final exact audit frame plus handoff", target_route="task-3/local/guardrails/audit-and-recovery", scope="all direct ordinary-Memory pairs", input_provenance="final local packet", consumer="ensure no unresolved contradictions are hidden", expected="Classify every pair and provide canonical handoffs only for findings."),
            "fit": entry(["fit", "task-3/local/guardrails/audit-and-recovery", "task-3/local/guardrails/approval-and-delivery"], starting_state=state, entry_route="final accumulated Context operands", target_route="audit-and-recovery + approval-and-delivery", scope="two direct proposition frames", input_provenance="final audit packet plus approval rules", consumer="test final consistency without authorizing transfer", expected="Return traceable evidence and keep approval as a separate user decision."),
        }

    raise AssertionError(round_number)


def main() -> None:
    if RUN_RECORD.exists():
        raise SystemExit(
            f"Refusing to rerun counted attempts because {RUN_RECORD} already exists"
        )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    variables: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    document: dict[str, Any] = {
        "schema_version": 1,
        "world": "task-3",
        "phase": "core",
        "execution_identity": {
            "code_sha256": CODE_DIGEST,
            "catalog_sha256": CATALOG_DIGEST,
            "profile_uid": PROFILE_UID,
            "store_root": str(STORE),
            "provider_policy_sha256": PROVIDER_DIGEST,
        },
        "attempts": records,
    }

    sequence = 0
    for round_number in range(1, 6):
        # Add and Copy outputs are required by later operations in the same
        # round, so rebuild the remaining round entries after each of them.
        for operation in OPERATIONS:
            sequence += 1
            spec = build_round(round_number, variables)[operation]
            args = spec.pop("args")
            pre_digest = digest_tree(TASK_TREE)
            start = time.monotonic()
            completed = subprocess.run(
                ["python", str(RUNNER), "task-3", *args],
                cwd=REPO,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            elapsed = time.monotonic() - start
            post_digest = digest_tree(TASK_TREE)
            raw_path = RAW_DIR / f"{sequence:03d}-{operation}-a{round_number}.txt"
            raw_path.write_text(
                "COMMAND\n"
                + command_display(args)
                + "\n\nSTDOUT\n"
                + completed.stdout
                + "\nSTDERR\n"
                + completed.stderr,
                encoding="utf-8",
            )
            record = {
                "attempt": round_number,
                "sequence": sequence,
                "operation": operation,
                "command": command_display(args),
                "exit": completed.returncode,
                **spec,
                "actual": "pending evidence review",
                "defect_ids": [],
                "cost": {
                    "wall_seconds": round(elapsed, 3),
                    "terminal_screens": None,
                    "extra_manual_steps": 0,
                    "tui": False,
                },
                "pre_target_digest": {
                    "scope": "lane-local task-3 Context subtree",
                    "sha256": pre_digest,
                },
                "post_target_digest": {
                    "scope": "lane-local task-3 Context subtree",
                    "sha256": post_digest,
                },
                "state_continuity": {
                    "task_tree_changed": pre_digest != post_digest,
                    "review": "pending evidence review",
                },
                "raw_output": str(raw_path.relative_to(REPO)),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
            records.append(record)
            if operation == "add":
                variables[f"add_{round_number}"] = add_uid(record)
            if operation == "copy" and completed.returncode == 0:
                variables[f"copy_{round_number}"] = copied_uids(record)
            RUN_RECORD.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(
                f"{sequence:03d}/105 r{round_number} {operation} "
                f"exit={completed.returncode} {elapsed:.2f}s",
                flush=True,
            )

    assert len(records) == 105
    assert {record["operation"] for record in records} == set(OPERATIONS)
    for operation in OPERATIONS:
        assert sum(record["operation"] == operation for record in records) == 5


if __name__ == "__main__":
    main()
