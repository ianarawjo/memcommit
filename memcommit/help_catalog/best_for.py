"""Reviewed use cases shown beside every public operation in Help."""

from __future__ import annotations


BEST_FOR_BY_OPERATION = {
    "add": "Adding one or more facts, instructions, or notes directly to a Context.",
    "atomize": (
        "Separating a composite Memory into independently reviewable requirements."
    ),
    "audit": "Performing a combined quality review before revising a Context.",
    "branch": (
        "Editing a Context or subtree independently while preserving the original."
    ),
    "check-conformance": ("Checking a Context or saved Ground against explicit Rules."),
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
    "config": "Inspecting or changing persistent MemCommit settings.",
    "contexts": "Exploring every Context currently available to the Profile.",
    "delete": "Removing a specific Context or item that is no longer needed.",
    "dedup": (
        "Collapsing confirmed equivalent Memories while preserving one existing "
        "UID and its exact wording."
    ),
    "diff": "Verifying exactly what a recorded operation changed.",
    "distill": "Extracting reusable rules from evidence-rich source material.",
    "elaborate": (
        "An abstract Goal needs starter Rule candidates, or existing Rules need "
        "additional concrete Case propositions for review."
    ),
    "edit": (
        "Directly correcting or replacing the content of specific existing Memories."
    ),
    "embed": (
        "Reusing a Memory or Context in another Context while following later "
        "Source changes."
    ),
    "eval": "Measuring operation behavior against repeatable fixtures.",
    "find": (
        "Locating exact words, identifiers, or text patterns within a selected "
        "Context scope."
    ),
    "search": (
        "Finding relevant Memories through meaning and context, including related "
        "content expressed in different words."
    ),
    "find-ambiguities": (
        "Finding Memories that permit unclear or multiple interpretations."
    ),
    "find-conflicts": "Finding mutually incompatible claims or instructions.",
    "find-duplicates": ("Locating semantically redundant Memories before cleanup."),
    "fit": "Checking whether Memories, Rules, Goals, or other propositions can coexist without contradiction.",
    "resolve": (
        "Turning one non-fitting direct-Memory frame into a grounded, independently "
        "verified Fit-YES post-image before exact Apply."
    ),
    "forget": (
        "Removing or rewriting Memories according to a natural-language "
        "instruction whose meaning must be interpreted."
    ),
    "ground": "Building a reviewed evaluation or behavior contract from evidence.",
    "help": "Discovering available operations and their invocation forms.",
    "impact": "Checking expected consequences before accepting a transformation.",
    "import": ("Bringing externally supplied material into a locally managed store."),
    "init": (
        "Starting a separate workspace for a new topic, task, or group of Memories."
    ),
    "init-study": "Preparing a reproducible, isolated user-study environment.",
    "list": "Inspecting the structure and direct contents of a Context.",
    "lock": "Preventing accidental modification of stable material.",
    "log": "Investigating previous operations, checkpoints, or Memory history.",
    "meld": (
        "Combining separately developed Contexts into a shared Result, or "
        "incorporating proposed changes into an existing Baseline."
    ),
    "merge": (
        "Bringing work from a copied or branched Context back into the current Context."
    ),
    "profile": "Managing separate users, environments, or Memory stores.",
    "provider": "Selecting and validating the semantic execution backend.",
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
    "review": "Resolving issues in a saved analysis before a later Apply.",
    "sever": (
        "Selecting or transforming part of a Source according to reusable criteria."
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
    "translate": "Translating material while preserving the original source.",
    "undo": "Reversing the latest recorded mutation as one operation.",
    "unlock": "Reopening protected material for intentional revision.",
    "update": "Updating an existing Context using newly verified Memories.",
}
