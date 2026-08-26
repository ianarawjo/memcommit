#!/usr/bin/env python3
"""Finalize task-2 ADMIN metadata without invoking or replaying mem."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


OUT = Path(
    "/Users/KimMunyeong/Github/memcommit/outputs/"
    "study-long-audit-20260825-v2/worlds/task-2"
)
PHASE = OUT / "phase-admin.json"
HOST = OUT / "admin-host-reads.json"
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-2/profile-control/"
    "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
SOURCE_STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-2/profile-control/"
    "stores/51fa256d-3e5e-4c18-836e-54832b6b4236"
)
ISSUE_HISTORY = "T2V2-BRANCH-NESTED-HISTORY-01"
ISSUE_IMPORT = "T2V2-IMPORT-CONTEXT-UID-COLLISION-01"
EXPECTED_BUILDER_ERROR = (
    "CommandHistoryError: Branch checkpoint owner is outside its creation "
    "membership."
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_context(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def add_defect(attempt: dict[str, object], issue_id: str) -> None:
    ids = attempt.setdefault("defect_ids", [])
    if issue_id not in ids:
        ids.append(issue_id)


phase = json.loads(PHASE.read_text(encoding="utf-8"))
host = json.loads(HOST.read_text(encoding="utf-8"))
attempts = sorted(
    (
        attempt
        for record in phase["operations"].values()
        for attempt in record["attempts"]
    ),
    key=lambda item: item["sequence"],
)
assert len(attempts) == 105
assert [item["sequence"] for item in attempts] == list(range(1, 106))
assert all(
    [item["attempt"] for item in phase["operations"][operation]["attempts"]]
    == [1, 2, 3, 4, 5]
    for operation in phase["operations"]
)
assert host["counted_mem_calls"] == 105
assert len(host["identity_reads"]) == 106
assert sum(
    item.get("moment") == "immediately-after-counted-call"
    for item in host["identity_reads"]
) == 105
assert all(item.get("asserted_expected_identity") for item in host["identity_reads"])

# The initial Rename/Branch defect also explains every later fail-closed
# Undo/Redo negative control; label those attempts so the failure is traceable.
for operation in ("undo", "redo"):
    for attempt in phase["operations"][operation]["attempts"]:
        if attempt["attempt"] >= 2:
            assert attempt["exit"] != 0
            assert "Branch checkpoint owner" in attempt["actual"]
            add_defect(attempt, ISSUE_HISTORY)

history_issue = next(item for item in phase["issues"] if item["id"] == ISSUE_HISTORY)
history_issue.update(
    {
        "actual": (
            "Rename M1 changed Branch1's owner name from b1 to renamed-1 "
            "without rebasing its retained Branch membership. Branch M2 then "
            "succeeded and copied that invalid history into a seven-Context "
            "subtree. The prescribed counted inverse Rename M2 restored the "
            "original owner, but the cloned checkpoint still had a different "
            "owner UID/name; build_command_stacks continued to fail with "
            "'Branch checkpoint owner is outside its creation membership.' "
            "All eight remaining counted Undo/Redo attempts reproduced that "
            "builder error before Context mutation, and their complete "
            "scratch Context-tree/state digests were unchanged."
        ),
        "workaround": (
            "There is no safe in-phase recovery. Preserve the malformed history "
            "for diagnosis, avoid recursive Branch over a subtree containing "
            "renamed Branch history, and rely only on the observed fail-closed "
            "Undo/Redo behavior until Rename rebases recovery metadata or "
            "Branch rejects/isolates the invalid history before mutation."
        ),
        "evidence_ids": [
            "admin:rename:1",
            "admin:branch:2",
            "admin:rename:2",
            "admin:undo:2-5",
            "admin:redo:2-5",
            "admin-host:undo-redo-fail-closed-negative-control:8",
            "admin-host:final-malformed-history-builder-negative-control",
            "admin-stack-blocker.json",
        ],
    }
)

# Import M1 copied the source Context UID into a new local name even though an
# existing granted Context reference in the active Profile already used that
# UID with the source name. Rename M3 then enforced the resulting mismatch.
parent_path = STORE / "contexts/task-2/participant/context.json"
imported_path = STORE / (
    "contexts/task-2/participant/admin-v2-scratch/import-direct/context.json"
)
source_path = SOURCE_STORE / "contexts/advisor1/style/context.json"
parent = read_context(parent_path)
imported = read_context(imported_path)
source = read_context(source_path)
uid = "a759f597-4f26-5782-828b-55f1c90076bf"
reference = parent["memories"][uid]
assert imported["uid"] == source["uid"] == reference["uid"] == uid
assert reference["name"] == "task-2/advisor1/style"
assert imported["name"] == (
    "task-2/participant/admin-v2-scratch/import-direct"
)
collision_event = {
    "kind": "imported-context-uid-reference-collision-host-read",
    "after_phase_sequence": 105,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "uid": uid,
    "source_context_name": source["name"],
    "existing_reference_type": reference["type"],
    "existing_reference_name": reference["name"],
    "imported_context_name": imported["name"],
    "source_context_sha256": sha256(source_path),
    "existing_reference_container_sha256": sha256(parent_path),
    "imported_context_sha256": sha256(imported_path),
    "rename_attempt": 3,
    "rename_error": phase["operations"]["rename"]["attempts"][2]["actual"],
    "read_only": True,
}
host["safety_reads"] = [
    item
    for item in host["safety_reads"]
    if item.get("kind") != "imported-context-uid-reference-collision-host-read"
]
host["safety_reads"].append(collision_event)
for operation, index in (("import", 0), ("rename", 2), ("rename", 4)):
    add_defect(phase["operations"][operation]["attempts"][index], ISSUE_IMPORT)
phase["operations"]["rename"]["attempts"][2]["recovery_evidence"] = (
    "Read-only collision evidence is retained in admin-host-reads.json: the "
    "source Context, imported Context, and an existing granted Context "
    "reference share UID a759f597 while the latter two store different names."
)
phase["operations"]["rename"]["attempts"][4]["recovery_evidence"] = (
    "The intended cancellation prompt was not reached because Rename M3 had "
    "already failed closed and therefore never created renamed-3-import; no "
    "supplemental or replay attempt was allowed."
)
import_issue = {
    "id": ISSUE_IMPORT,
    "title": "Context Import publishes a UID/name collision that blocks Rename",
    "expected": (
        "A successful Context import into a new local name must preserve a "
        "consistent identity graph so later world-local Rename can update "
        "references, or the import must reject the collision before mutation."
    ),
    "actual": (
        "Import M1 succeeded and stored advisor1/style as import-direct with "
        "the source UID a759f597. The active Profile already had a granted "
        "Context reference with that UID and the source name "
        "task-2/advisor1/style. Rename M3 then failed with 'Context reference "
        "identity and stored target name disagree'; consequently Rename M5's "
        "planned cancel target was never created."
    ),
    "workaround": (
        "Do not rename a Context imported under a new name when the active "
        "Profile already contains a reference with the source UID. Inspect the "
        "UID/name graph first and keep the imported Context at its initial "
        "name; no in-phase repair was attempted."
    ),
    "severity": "high",
    "classification": "import/reference-identity-integrity",
    "evidence_ids": [
        "admin:import:1",
        "admin:rename:3",
        "admin:rename:5",
        "admin-host:imported-context-uid-reference-collision-host-read",
    ],
}
phase["issues"] = [
    item for item in phase["issues"] if item["id"] != ISSUE_IMPORT
] + [import_issue]

# Confirm after all 105 counted calls that the retained negative-control state
# still fails in the same frozen builder. This is a read only host diagnostic.
sys.path.insert(0, str(OUT))
import run_admin  # noqa: E402

try:
    run_admin.build_command_stacks(run_admin.MemoryStore(create=False))
except Exception as error:
    rendered = f"{type(error).__name__}: {error}"
else:
    raise AssertionError("Malformed command history unexpectedly became buildable")
assert rendered == EXPECTED_BUILDER_ERROR
host["safety_reads"] = [
    item
    for item in host["safety_reads"]
    if item.get("kind") != "final-malformed-history-builder-negative-control"
]
host["safety_reads"].append(
    {
        "kind": "final-malformed-history-builder-negative-control",
        "after_phase_sequence": 105,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual": rendered,
        "expected": EXPECTED_BUILDER_ERROR,
        "matched": True,
        "read_only": True,
    }
)

summary = phase["execution_summary"]
summary["identity_host_reads_after_counted_calls"] = 105
summary["phase_entry_identity_host_reads"] = 1
summary["identity_host_reads_total"] = 106
phase["recovery_negative_control"]["final_builder_failure_after_sequence_105"] = (
    EXPECTED_BUILDER_ERROR
)
phase["recovery_negative_control"]["all_eight_context_state_digests_unchanged"] = True

PHASE.write_text(
    json.dumps(phase, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
HOST.write_text(
    json.dumps(host, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
