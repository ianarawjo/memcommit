"""Reviewed use cases shown beside every public operation in Help."""

from __future__ import annotations


BEST_FOR_BY_OPERATION = {
    "add": "Adding one or more facts, instructions, or notes directly to a Context.",
    "atomize": (
        "Untangling requirements or claims that were written together so each "
        "can be reviewed and revised independently."
    ),
    "audit": "Performing a combined quality review before revising a Context.",
    "branch": (
        "Editing a Context or subtree independently while preserving the original."
    ),
    "check-conformance": (
        "Verifying whether existing Memories or Examples satisfy stated Rules "
        "or condition propositions."
    ),
    "checkout": "Using a Git-like workflow to switch or create a branch.",
    "checkpoint": "Creating a recovery point before risky work.",
    "chunk": (
        "A Memory already has clear text boundaries that should become "
        "separate Memories."
    ),
    "clear": "Emptying a Context while retaining the Context itself.",
    "compare": (
        "Comparing two Contexts as a whole to understand where they align and differ."
    ),
    "config": (
        "Inspecting or changing stored global settings through the legacy "
        "low-level interface."
    ),
    "contexts": "Exploring every Context currently available to the Profile.",
    "delete": "Removing a specific Context or item that is no longer needed.",
    "dedup": (
        "Removing confirmed semantic duplicates while preserving one exact "
        "existing Memory and its UID."
    ),
    "diff": "Verifying exactly what a recorded operation changed.",
    "distill": (
        "Inferring more general Rules or condition propositions from several "
        "concrete cases or examples."
    ),
    "elaborate": (
        "Generating several more concrete candidate Rules or Cases from an "
        "abstract concept or condition."
    ),
    "edit": (
        "Directly correcting or replacing the content of specific existing Memories."
    ),
    "embed": (
        "Reusing a Memory or Context in another Context while following later "
        "Source changes."
    ),
    "eval": (
        "Using the existing research evaluation harness while the general "
        "evaluation interface is redesigned."
    ),
    "find": (
        "Locating exact words, identifiers, or text patterns within a selected "
        "Context scope."
    ),
    "search": (
        "Finding relevant Memories through meaning and context, including related "
        "content without obvious keyword overlap."
    ),
    "find-ambiguities": (
        "Finding Memories that permit unclear or multiple interpretations."
    ),
    "find-conflicts": "Finding mutually incompatible claims or instructions.",
    "find-duplicates": ("Locating semantically redundant Memories before cleanup."),
    "fit": (
        "Checking whether a defined set of Memories, Rules, Goals, Examples, "
        "or other propositions can jointly hold."
    ),
    "resolve": (
        "Deciding how to repair semantic conflicts or ambiguities within a "
        "bounded Context frame."
    ),
    "forget": (
        "Removing or rewriting Memories according to a natural-language "
        "instruction whose meaning must be interpreted."
    ),
    "ground": (
        "Working out how an abstract goal should operate in practice through "
        "jointly revised Rules and concrete Examples."
    ),
    "help": "Discovering available operations and their invocation forms.",
    "impact": (
        "Verifying an operation's proposed effects before its separate Apply action."
    ),
    "import": ("Bringing externally supplied material into a locally managed store."),
    "init": (
        "Starting a separate workspace for a new topic, task, or group of Memories."
    ),
    "init-study": "Preparing a reproducible, isolated user-study environment.",
    "list": "Inspecting the structure and direct contents of a Context.",
    "lock": "Preventing accidental modification of stable material.",
    "log": "Investigating previous operations, checkpoints, or Memory history.",
    "meld": (
        "Combining two bodies of work when overlap, conflicts, and newly "
        "synthesized content must be reviewed semantically."
    ),
    "merge": (
        "Appending Source-only items or bringing a copied or branched Context "
        "back into the current Context without semantic synthesis."
    ),
    "profile": "Managing separate users, environments, or Memory stores.",
    "provider": (
        "Choosing which backend semantic operations should use, or checking "
        "that it is ready before durable work."
    ),
    "pwd": "Confirming the active Context in a script or terminal.",
    "query": (
        "Getting a grounded natural-language answer instead of a list of matching "
        "Memories."
    ),
    "rationale": "Understanding why a Memory exists or reached its current form.",
    "redo": "Reapplying a command that was undone accidentally.",
    "reference": (
        "Retaining one exact Memory version even if its Source later changes "
        "or disappears."
    ),
    "replace": (
        "Correcting, renaming, or redacting exact text throughout a known local "
        "Context scope."
    ),
    "rename": "Giving an existing managed Profile a clearer name.",
    "revert": "Restoring a Context to a deliberately saved recovery point.",
    "review": "Revisiting a saved analysis, proposal, or result state.",
    "sever": (
        "Selecting or transforming Source content according to defined criteria."
    ),
    "share": "Delivering an owned Context to an authorized receiver.",
    "shell-init": "Enabling optional shell-specific conveniences.",
    "show": "Reading the complete content of a known item or Context.",
    "status": (
        "Getting oriented to what the current Context contains, how it is "
        "connected, and which operations were recently applied."
    ),
    "summarize": "Obtaining a concise overview of a Context or subtree.",
    "switch": "Moving the working position to another existing Context.",
    "trace": "Determining where a Memory came from and how it changed.",
    "translate": (
        "Reading or reusing Memory content in another language without replacing "
        "the original."
    ),
    "undo": "Reversing the latest recorded mutation as one operation.",
    "unlock": "Reopening protected material for intentional revision.",
    "update": "Updating an existing Context using newly verified Memories.",
}
