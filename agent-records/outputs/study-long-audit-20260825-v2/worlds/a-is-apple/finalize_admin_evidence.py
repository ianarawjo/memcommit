#!/usr/bin/env python3
"""Finalize ADMIN issues and re-render actual visible PTY prefixes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import runpy

import pyte


ROOT = Path(__file__).resolve().parent
AUDIT = ROOT.parents[1]
REPO = AUDIT.parents[1]
LEDGER = ROOT / "phase-admin.json"
AGENT_RECORDS = REPO / "agent-records/docs/screenshots/six-world-audit-v2-20260825/a-is-apple-admin"


def visible_text(data: bytes) -> str:
    screen = pyte.Screen(180, 52)
    pyte.Stream(screen).feed(data.decode("utf-8", "replace"))
    return "\n".join(line.rstrip() for line in screen.display if line.rstrip())


def visible_prefixes(data: bytes) -> list[bytes]:
    positions = [m.start() for m in re.finditer(br"\x1b\[J", data)][1:]
    positions.extend(m.end() for m in re.finditer(br"\x1b\[\?7h", data))
    positions.append(len(data))
    found: list[tuple[str, bytes]] = []
    for end in sorted(set(positions)):
        prefix = data[:end]
        text = visible_text(prefix)
        if text and text not in {item[0] for item in found}:
            found.append((text, prefix))
    return [item[1] for item in found]


def main() -> None:
    helper = runpy.run_path(str(ROOT / "run_admin_audit.py"), run_name="admin_helpers")
    render = helper["_render"]
    ledger = json.loads(LEDGER.read_text())
    tui_records = sorted(
        (r for payload in ledger["operations"].values() for r in payload["attempts"] if r["cost"].get("tui")),
        key=lambda r: r["sequence"],
    )
    for record in tui_records:
        evidence = record["tui_evidence"]
        raw = AUDIT / evidence["raw_pty_path"]
        data = raw.read_bytes()
        prefixes = visible_prefixes(data)
        screenshots = [AUDIT / value for value in evidence["screenshots"]]
        # The final image is already the actual post-exit receipt (or the
        # still-visible frame when an externally terminated TUI had no receipt).
        interactive = screenshots[:-1]
        if prefixes:
            for index, screenshot in enumerate(interactive):
                prefix = prefixes[min(index, len(prefixes) - 1)]
                render(prefix, screenshot)
        log_path = AUDIT / evidence["interaction_log_path"]
        log = json.loads(log_path.read_text())
        if record["sequence"] == 54 and screenshots[-1].name.endswith("cancel-or-failure-receipt.png"):
            # Bare Help exits read-only on Q without emitting any post-exit
            # receipt.  The former all-black canvas represented absence, not a
            # terminal state, so do not publish it as a screenshot.
            blank = screenshots[-1]
            blank_record = AGENT_RECORDS / blank.name
            if blank.exists():
                blank.unlink()
            if blank_record.exists():
                blank_record.unlink()
            evidence["screenshots"] = evidence["screenshots"][:-1]
            log["steps"] = [step for step in log["steps"] if Path(step["screenshot"]).name != blank.name]
            log["no_post_exit_receipt"] = "Bare read-only Help closed on Q and emitted no terminal text."
        log["capture_finalization"] = {
            "renderer": "actual color-preserving cumulative PTY byte-stream replay",
            "visible_prefix_count": len(prefixes),
            "limitation": (
                "Keys were pre-buffered before the frozen launcher completed on some attempts. "
                "When only one visible prompt-toolkit flush survived, multiple ordered labels refer "
                "to that same actual visible frame; no synthetic state was invented."
            ),
        }
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n")
        record_log = AGENT_RECORDS / log_path.name
        if record_log.exists():
            record_log.unlink()
        os.link(log_path, record_log)

    # Repair the host byte-equality assertion across harness restarts from the
    # immutable counted raw outputs, excluding only the audit wrapper header.
    def output_bytes(sequence: int, name: str) -> bytes:
        path = ROOT / f"raw/admin/{sequence:03d}-{name}.txt"
        return path.read_bytes().split(b"\nOUTPUT\n", 1)[1]
    shell_check = {
        "host_comparison": "counted stdout payload after raw audit wrapper OUTPUT marker",
        "M1_raw": "worlds/a-is-apple/raw/admin/020-shell-init-1.txt",
        "M2_raw": "worlds/a-is-apple/raw/admin/042-shell-init-2.txt",
        "byte_equal_to_M1": output_bytes(20, "shell-init-1") == output_bytes(42, "shell-init-2"),
        "earlier_false_value_cause": "Harness process restart lost its in-memory M1 bytes; corrected from immutable raw evidence.",
    }
    (ROOT / "host_reads/admin/shell-init-2-host-check.json").write_text(
        json.dumps(shell_check, indent=2) + "\n"
    )

    issue_id = "AIA-V2-A-RENAME-COMMAND-STACK-01"
    issues = {
        "world": "a-is-apple",
        "phase": "admin",
        "issues": [
            {
                "id": issue_id,
                "title": "Renaming a Branch/checkout target corrupts the global Undo/Redo stack",
                "expected": (
                    "After a successful Rename of a Context created by Branch or checkout -b, "
                    "the retained producer unit remains reconstructible under the new canonical name, "
                    "so later Undo/Redo can host-read and restore its exact UID/member set."
                ),
                "actual": (
                    "Rename#1, #2, and #3 succeeded. Thereafter every global stack build and each "
                    "counted Undo/Redo control failed closed with `Branch checkpoint owner is outside "
                    "its creation membership.` The renamed checkpoint owner uses the new Context name "
                    "while the branch receipt's creation membership retains the old target name."
                ),
                "workaround": (
                    "Do not Rename a Branch/checkout-created Context while its producer remains in "
                    "command history. Use explicit per-Context checkpoints/revert for recovery; there "
                    "is no global Undo workaround once this mismatch exists."
                ),
                "severity": "HIGH",
                "classification": "SAFETY_RECOVERY_GLOBAL_STACK_CORRUPTION_FAIL_CLOSED",
                "reproduction": "3 successful renames followed by 8/8 Undo/Redo failures across rounds 2-5",
                "evidence": [
                    "worlds/a-is-apple/raw/admin/004-rename-1.txt",
                    "worlds/a-is-apple/raw/admin/024-undo-2.txt",
                    "worlds/a-is-apple/raw/admin/025-redo-2.txt",
                    "worlds/a-is-apple/raw/admin/046-undo-3.txt",
                    "worlds/a-is-apple/raw/admin/047-redo-3.txt",
                    "worlds/a-is-apple/raw/admin/083-undo-4.txt",
                    "worlds/a-is-apple/raw/admin/085-undo-5.txt",
                    "worlds/a-is-apple/raw/admin/086-redo-5.txt",
                    "worlds/a-is-apple/host_reads/admin/stack-pre-undo-2-seq-024.json",
                ],
            }
        ],
        "limitations": [
            {
                "id": "AIA-V2-A-TUI-PREBUFFER-CAPTURE",
                "classification": "AUDIT_HARNESS_INTERACTION_LIMITATION",
                "actual": (
                    "Help --emit-selection and Branch M5 received scripted keys before the frozen "
                    "launcher completed. They remained open until terminated and are recorded as exit "
                    "124; their actual PTY streams/screens are retained. Other nine TUI attempts "
                    "completed, including the final Switch restoration to practice."
                ),
                "evidence": [
                    "worlds/a-is-apple/raw/admin/068-help-4.txt",
                    "worlds/a-is-apple/raw/admin/101-branch-5.txt",
                    "worlds/a-is-apple/screenshots/admin/068-help-4-pty.bin",
                    "worlds/a-is-apple/screenshots/admin/101-branch-5-pty.bin",
                ],
            },
            {
                "id": "AIA-V2-A-LOCK-M3-SELECTOR",
                "classification": "AUDIT_INPUT_ASSUMPTION_LIMITATION",
                "actual": (
                    "Lock/Unlock M3 used the Source Memory prefix f1c940a1 after branching; Branch "
                    "remapped Memory UIDs, so both exact-Memory commands safely rejected the missing "
                    "target instead of exercising a successful exact lock pair."
                ),
                "evidence": [
                    "worlds/a-is-apple/raw/admin/048-lock-3.txt",
                    "worlds/a-is-apple/raw/admin/049-unlock-3.txt",
                ],
            },
            {
                "id": "AIA-V2-A-LOG-M3-POST-RENAME",
                "classification": "AUDIT_ORDERING_LIMITATION",
                "actual": (
                    "Log M3 named the pre-Rename checkout target `.../co3` after Rename M3 had "
                    "already moved it to `.../renamed-3`, so the exact-Memory history route safely "
                    "failed at Context resolution instead of rendering a five-row Memory log."
                ),
                "evidence": [
                    "worlds/a-is-apple/raw/admin/050-rename-3.txt",
                    "worlds/a-is-apple/raw/admin/058-log-3.txt",
                ],
            },
        ],
    }
    (ROOT / "issues-admin.json").write_text(json.dumps(issues, ensure_ascii=False, indent=2) + "\n")
    world_registry_path = ROOT / "issues.json"
    world_registry = json.loads(world_registry_path.read_text())
    world_registry["phase"] = "multi-phase"
    existing = {item["id"] for item in world_registry.get("issues", [])}
    for item in issues["issues"]:
        if item["id"] not in existing:
            world_registry.setdefault("issues", []).append(item)
    world_registry_path.write_text(json.dumps(world_registry, ensure_ascii=False, indent=2) + "\n")
    markdown = """# a-is-apple ADMIN findings\n\n## AIA-V2-A-RENAME-COMMAND-STACK-01 · HIGH\n\nRenaming a Context created by Branch or `checkout -b` leaves its retained creation membership under the old target name. Global command-stack reconstruction then fails closed with `Branch checkpoint owner is outside its creation membership`, and every later Undo/Redo is unavailable. Avoid Rename while the producer remains in history; use explicit checkpoints/revert for recovery.\n\n## Audit limitations\n\n- Two interactive attempts (`help --emit-selection`, bare Branch) received pre-buffered keys before launcher startup and were terminated after their actual PTY state was captured.\n- Exact-Memory Lock/Unlock M3 used the pre-Branch Source UID; Branch remapped the target UID, so both controls rejected the missing selector.\n- Log M3 named the pre-Rename `co3` target after it had moved to `renamed-3`, so Context resolution failed safely.\n"""
    (ROOT / "issues-admin.md").write_text(markdown)

    # Attach issue IDs only to directly supporting counted attempts.
    for operation, attempts in (("rename", {1, 2, 3}), ("undo", {2, 3, 4, 5}), ("redo", {2, 3, 5})):
        for record in ledger["operations"][operation]["attempts"]:
            if record["attempt"] in attempts:
                record["defect_ids"] = [issue_id]
    ledger["negative_control"] = {
        "classification": "RENAME_INDUCED_GLOBAL_COMMAND_STACK_CORRUPTION",
        "supplemental_recovery_mem_calls": 0,
        "continued_fail_closed": True,
    }
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")

    images = sorted(AGENT_RECORDS.glob("*.png"))
    logs = sorted(AGENT_RECORDS.glob("*-interaction.json"))
    readme = AGENT_RECORDS / "README.md"
    readme.write_text(
        "# a-is-apple ADMIN interactive evidence\n\n"
        "Actual 180×52 xterm-256color PTY captures. Interaction logs record keys, visible state, "
        "mutation status, and the pre-buffer limitation.\n\n## Images\n\n"
        + "\n".join(f"- `{p.name}`" for p in images)
        + "\n\n## Interaction logs\n\n"
        + "\n".join(f"- `{p.name}`" for p in logs)
        + "\n"
    )


if __name__ == "__main__":
    main()
