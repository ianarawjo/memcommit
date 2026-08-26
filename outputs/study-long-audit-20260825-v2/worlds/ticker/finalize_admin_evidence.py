#!/usr/bin/env python3
"""Finalize ticker ADMIN issue and verifier evidence without invoking mem."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPO = Path("/Users/KimMunyeong/Github/memcommit")
AUDIT = REPO / "outputs/study-long-audit-20260825-v2"
WORLD = AUDIT / "worlds/ticker"
PHASE = WORLD / "phase-admin.json"
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/"
    "worlds/ticker/profile-control/stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
CODE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-snapshots/"
    "memcommit-six-world-v2-20260825-code"
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    return str(path.relative_to(AUDIT))


def status_diagnostic() -> str:
    sys.path.insert(0, str(CODE_ROOT))
    from memcommit.context_snapshot import ContextSnapshotRef
    from memcommit.store import MemoryStore

    store = MemoryStore(root=STORE, create=False, resolve_granted_links=False)
    root = store.load_direct("task-2/participant")
    snapshot = next(
        item for item in root.iter_items() if isinstance(item, ContextSnapshotRef)
    )
    live = store.load_direct(snapshot.name)
    evidence = {
        "kind": "host-only frozen-code diagnosis; no mem call",
        "status_attempt": 3,
        "status_sequence": 49,
        "current_context": {"name": root.name, "uid": root.uid},
        "embedded_item": {
            "runtime_type": type(snapshot).__name__,
            "occurrence_uid": snapshot.uid,
            "public_name": snapshot.name,
            "target_context_uid": snapshot.target_context_uid,
        },
        "live_target": {"name": live.name, "uid": live.uid},
        "identity_comparisons": {
            "occurrence_uid_equals_live_uid": snapshot.uid == live.uid,
            "target_context_uid_equals_live_uid": snapshot.target_context_uid == live.uid,
        },
        "inference": (
            "Frozen Status recursive traversal treats ContextSnapshotRef as Context and "
            "passes the occurrence UID as expected_uid; the live target correctly matches "
            "target_context_uid instead, so the read fails with an identity-change error."
        ),
    }
    path = WORLD / "host_reads/admin/status-3-context-snapshot-identity-diagnostic.json"
    write_json(path, evidence)
    return relative(path)


def init_diagnostic() -> str:
    parent = STORE / "contexts/audit/ticker/admin-v2-scratch/missing-parent/context.json"
    leaf = STORE / "contexts/audit/ticker/admin-v2-scratch/missing-parent/leaf/context.json"
    evidence = {
        "kind": "host-only post-attempt namespace read; no mem call",
        "init_attempt": 5,
        "init_sequence": 95,
        "parent_context_exists": parent.is_file(),
        "leaf_context_exists": leaf.is_file(),
        "leaf_identity": read_json(leaf).get("uid") if leaf.is_file() else None,
        "interpretation": (
            "Default Init creates only the exact requested leaf Context and filesystem "
            "namespace directories; --parents is the mode that creates parent Context objects. "
            "The campaign's expected missing-parent failure was incorrect."
        ),
    }
    path = WORLD / "host_reads/admin/init-5-leaf-without-parent-diagnostic.json"
    write_json(path, evidence)
    return relative(path)


def main() -> None:
    ledger = read_json(PHASE)
    if ledger.get("status") != "complete" or ledger.get("attempt_count") != 105:
        raise SystemExit("Ticker ADMIN phase is not complete")
    status_host = status_diagnostic()
    init_host = init_diagnostic()
    issues = [
        {
            "id": "TICK-V2-A-STATUS-SNAPSHOT-UID-01",
            "title": "Recursive Status compares a ContextSnapshotRef occurrence UID to the live target UID",
            "expected": (
                "`status --recursive` on `task-2/participant` follows its retained "
                "Context snapshot using the snapshot's target Context identity and renders a read-only frame."
            ),
            "actual": (
                "Status exited 1 with `An embedded Context identity changed during Status.` "
                "Host diagnosis shows occurrence UID c458ab18 differs from the live target UID "
                "b839b146, while the snapshot's explicit target_context_uid correctly equals b839b146."
            ),
            "workaround": (
                "Use `status --short`, default direct Status, or an exact direct read that does not "
                "follow embedded snapshot occurrences."
            ),
            "severity": "HIGH",
            "classification": "FUNCTIONAL_READ_FAILURE_CONTEXT_SNAPSHOT_IDENTITY",
            "reproduction": "1/1 recursive Status on the snapshot-bearing task-2/participant Context",
            "evidence": [
                "worlds/ticker/raw/admin/049-status-3.txt",
                status_host,
            ],
        },
        {
            "id": "TICK-V2-A-IMPORT-FIXTURE-01",
            "title": "Cumulative ticker identity collisions invalidated the Admin import/Rename fixture",
            "expected": (
                "Admin Context import M1/M2 creates fresh by-value scratch fixtures that positive-control "
                "Rename M1/M2 can rename without touching Branch/Checkout targets."
            ),
            "actual": (
                "The cumulative ticker Profile already contained the task-1 Context stable UIDs, so both "
                "imports rejected aliasing the same identities and both dependent Renames found no Source. "
                "Branch3 consequently succeeded; the harness stopped before unsafe Checkout3 cloning and "
                "continued with an explicit clean-O target-collision route and exact Branch3 Undo/Redo."
            ),
            "workaround": (
                "Preflight imported stable identities host-side and choose a source Context whose UID is "
                "absent from the active cumulative Profile, or reserve init-created scratch fixtures for all positive Renames."
            ),
            "severity": "CAMPAIGN_LIMITATION",
            "classification": "CAMPAIGN_FIXTURE_STABLE_IDENTITY_COLLISION",
            "reproduction": "2/2 Context imports and their 2/2 dependent positive Renames",
            "evidence": [
                "worlds/ticker/raw/admin/012-import-1.txt",
                "worlds/ticker/raw/admin/013-rename-1.txt",
                "worlds/ticker/raw/admin/027-import-2.txt",
                "worlds/ticker/raw/admin/041-rename-2.txt",
                "worlds/ticker/raw/admin/043-branch-3.txt",
                "worlds/ticker/host_reads/admin/source-precondition-046-checkout-3-source.json",
                "worlds/ticker/host_reads/admin/stack-round3-resume-actual-branch3-producer.json",
                "worlds/ticker/raw/admin/045-rename-3.txt",
                "worlds/ticker/raw/admin/046-checkout-3.txt",
            ],
        },
        {
            "id": "TICK-V2-A-INIT-EXPECTATION-01",
            "title": "Admin protocol incorrectly expected default Init to reject a missing lexical parent",
            "expected": (
                "The campaign protocol expected `init C/missing-parent/leaf` without `--parents` to fail."
            ),
            "actual": (
                "Init correctly created only the exact leaf Context and switched to it; no parent Context "
                "object exists. The current operation contract reserves parent-Context creation for `--parents`."
            ),
            "workaround": (
                "Use a collision, invalid UID-shaped name, or another documented validation failure for a "
                "negative Init method; treat a missing lexical parent as a valid exact-leaf route."
            ),
            "severity": "CAMPAIGN_LIMITATION",
            "classification": "CAMPAIGN_PROTOCOL_EXPECTATION_MISMATCH",
            "reproduction": "1/1 default exact-leaf Init with an absent parent Context",
            "evidence": [
                "worlds/ticker/raw/admin/095-init-5.txt",
                init_host,
            ],
        },
    ]
    registry = {"world": "ticker", "phase": "admin", "issues": issues}
    write_json(WORLD / "issues-admin.json", registry)
    lines = ["# Ticker ADMIN issues", ""]
    for issue in issues:
        lines.extend(
            [
                f"## {issue['id']} — {issue['title']}", "",
                f"- Severity: `{issue['severity']}`", f"- Classification: `{issue['classification']}`",
                f"- Expected: {issue['expected']}", f"- Actual: {issue['actual']}",
                f"- Workaround: {issue['workaround']}", f"- Reproduction: {issue['reproduction']}", "",
            ]
        )
    (WORLD / "issues-admin.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    by_id = {issue["id"]: issue for issue in issues}
    assignments = {
        ("status", 3): ["TICK-V2-A-STATUS-SNAPSHOT-UID-01"],
        ("import", 1): ["TICK-V2-A-IMPORT-FIXTURE-01"],
        ("rename", 1): ["TICK-V2-A-IMPORT-FIXTURE-01"],
        ("import", 2): ["TICK-V2-A-IMPORT-FIXTURE-01"],
        ("rename", 2): ["TICK-V2-A-IMPORT-FIXTURE-01"],
        ("branch", 3): ["TICK-V2-A-IMPORT-FIXTURE-01"],
        ("rename", 3): ["TICK-V2-A-IMPORT-FIXTURE-01"],
        ("checkout", 3): ["TICK-V2-A-IMPORT-FIXTURE-01"],
        ("undo", 3): ["TICK-V2-A-IMPORT-FIXTURE-01"],
        ("redo", 3): ["TICK-V2-A-IMPORT-FIXTURE-01"],
        ("init", 5): ["TICK-V2-A-INIT-EXPECTATION-01"],
    }
    for operation, payload in ledger["operations"].items():
        for attempt in payload["attempts"]:
            ids = assignments.get((operation, attempt["attempt"]), [])
            if any(issue_id not in by_id for issue_id in ids):
                raise RuntimeError("Unknown issue assignment")
            attempt["defect_ids"] = ids
    ledger["issue_registry"] = relative(WORLD / "issues-admin.json")
    ledger["issues"] = issues
    ledger["issue_summary"] = {
        "product_defects": 1,
        "campaign_limitations": 2,
        "provider_infrastructure_failures": 0,
    }
    ledger["interleave_exception"] = {
        "operation": "switch",
        "attempt_ids": [1, 2],
        "sequences": [21, 22],
        "commands": ["mem switch --previous", "mem switch --next"],
        "rationale": (
            "The ADMIN protocol requires round 1 last `mem switch --previous`, then "
            "round 2 first `mem switch --next` with no intervening mem call so the "
            "navigation transaction itself is preserved."
        ),
    }
    ledger["starting_boundary"]["admin_initial_digest"] = ledger["starting_boundary"]["admin_initial_tree_digest"]
    ledger["starting_boundary"]["transform_final_digest"] = ledger["starting_boundary"]["transform_final_tree_digest"]
    ledger["starting_boundary"]["matches_transform_final_digest"] = ledger["starting_boundary"]["matching_boundary_digest"]
    write_json(PHASE, ledger)


if __name__ == "__main__":
    main()
