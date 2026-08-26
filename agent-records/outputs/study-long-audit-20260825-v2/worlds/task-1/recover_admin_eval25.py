#!/usr/bin/env python3
"""Recover counted ADMIN Eval#2 evidence lost after child exit, without rerun."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex


ROOT = Path(__file__).resolve().parent
PHASE = ROOT / "phase-admin.json"
HOST = ROOT / "admin-host-reads.json"
RAW = ROOT / "raw/admin/025-eval-m2.txt"
RUNNER = ROOT.parents[1] / "run_world_mem.py"
LANE = Path("/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/worlds/task-1")
PROFILE_CONTROL = LANE / "profile-control"
STORE = PROFILE_CONTROL / "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
EVAL = LANE / "admin-eval-ledger"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"


def lane_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in PROFILE_CONTROL.rglob("*") if path.is_file()):
        if path.suffix == ".lock" or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(PROFILE_CONTROL).as_posix().encode()
        digest.update(len(rel).to_bytes(8, "big")); digest.update(rel)
        data = path.read_bytes(); digest.update(len(data).to_bytes(8, "big")); digest.update(data)
    return digest.hexdigest()


def main() -> None:
    phase = json.loads(PHASE.read_text())
    existing = sorted((item for values in phase["operations"].values() for item in values["attempts"]), key=lambda item: item["sequence"])
    if len(existing) != 24 or existing[-1]["sequence"] != 24:
        raise SystemExit("Expected exactly 24 persisted ADMIN records before recovery.")
    host = json.loads(HOST.read_text())
    identity = [item for item in host["host_reads"] if item.get("kind") == "identity_assertion" and item.get("after_counted_sequence") == 25]
    if len(identity) != 1 or identity[0].get("result") != "PASS":
        raise SystemExit("Missing exact post-child identity PASS for counted sequence 25.")
    runs = sorted((EVAL / "runs").glob("*.json"))
    if len(runs) != 1:
        raise SystemExit(f"Expected one Eval M2 run, found {runs}")
    run = json.loads(runs[0].read_text())
    if run.get("status") != "COMPLETED" or not run.get("summary", {}).get("campaign_passed"):
        raise SystemExit("Eval M2 durable run is not a completed pass.")
    args = ["eval", "semantic", "run", "ambiguity", "--provider", "codex_chatgpt", "--model", "gpt-5.6-sol", "--reasoning", "none", "--pipeline", "v2", "--corpus", "calibration", "--runs", "1", "--case", "single-none-main-entrance-hours", "--ledger-dir", str(EVAL)]
    command = shlex.join(["python", str(RUNNER), "task-1", *args])
    pre = existing[-1]["post_target_digest"]
    post = lane_digest()
    actual = (
        f"Recovered from durable Eval ledger after child exit: run_id={run['run_id']} · "
        f"status={run['status']} · cases={run['summary']['cases']['passed']}/{run['summary']['cases']['total']} PASS · "
        f"provider={run['provider']['provider']}:{run['provider']['model']} · "
        f"completion_seconds={run['attempts'][0]['completion_seconds']:.6f}. "
        "Original captured stdout was lost when the audit harness was interrupted during post-call digesting."
    )
    RAW.write_text(
        f"COMMAND\n{command}\n\nEXIT\n0 (host-inferred from durable COMPLETED 1/1 PASS run and post-child identity evidence)\n\n"
        f"OUTPUT_RECOVERY\n{actual}\n\nDURABLE_EVAL_LEDGER\n{runs[0]}\n"
    )
    record = {
        "attempt": 2, "sequence": 25, "command": command, "exit": 0,
        "starting_state": f"One cumulative no-reset Store; ADMIN orchestration round 2; phase-local sequence 25; pre-lane-digest={pre}; previous-post={pre}.",
        "entry_route": f"pinned noninteractive ADMIN CLI · M2 · one-case ambiguity Eval · argv={shlex.join(args)}",
        "target_route": str(EVAL), "scope": "ADMIN method M2 exact argv · one calibration case, one provider run",
        "input_provenance": f"cumulative CORE+TRANSFORM+ADMIN Store; protocol M2; actual argv `{shlex.join(args)}`; durable run {run['run_id']}",
        "consumer": "admin safety, recoverability, orientation, and exact-identity audit",
        "expected": "Keep Eval evidence lane-local, run one declared case, and validate its full run ID. ADMIN method M2.",
        "actual": actual, "defect_ids": ["T1-V2-ADMIN-HARNESS-POST-DIGEST-INTERRUPTION"],
        "cost": {"wall_seconds": round(run["timing"]["total_seconds"], 6), "output_bytes": None, "output_lines": None,
                 "timed_out": False, "tui": False, "terminal_screens": 0, "extra_manual_steps": 1,
                 "cost_provenance": "durable Eval run timing; process wrapper overhead unavailable"},
        "pre_target_digest": pre, "post_target_digest": post,
        "pre_selected_target_digest": hashlib.sha256().hexdigest(), "post_selected_target_digest": hashlib.sha256().hexdigest(),
        "pre_registry_digest": None, "post_registry_digest": hashlib.sha256((PROFILE_CONTROL / "registry.json").read_bytes()).hexdigest(),
        "pre_config_digest": None, "post_config_digest": hashlib.sha256((PROFILE_CONTROL / "authoring-store/config.json").read_bytes()).hexdigest(),
        "recovery_evidence": f"Durable Eval ledger {runs[0]} plus admin-host-reads identity assertion at counted sequence 25; command was not rerun.",
        "state_continuity": f"no reset; same pinned Profile UID {PROFILE_UID} and lane Store {STORE}; pre digest equals sequence 24 post digest; post-child identity PASS; post digest recovered by host read.",
        "state_continuity_facts": {"reset": False, "same_as_previous_post": True, "lane_digest_changed": pre != post,
                                   "one_cumulative_store": True, "source_digest_preserved": True,
                                   "post_call_identity_asserted": True, "recovered_without_replay": True},
        "raw_output": "raw/admin/025-eval-m2.txt", "evidence_id": "T1-V2-ADMIN-025",
    }
    phase["operations"]["eval"]["attempts"].append(record)
    host["host_reads"].append({
        "index": len(host["host_reads"]) + 1, "after_counted_sequence": 25,
        "kind": "harness_interruption_recovery", "result": "PASS",
        "run_id": run["run_id"], "durable_eval_ledger": str(runs[0]),
        "note": "Recovered evidence only; no mem replay.",
    })
    host["counted_mem_calls"] = 25
    HOST.write_text(json.dumps(host, ensure_ascii=False, indent=2) + "\n")
    records = sorted((item for values in phase["operations"].values() for item in values["attempts"]), key=lambda item: item["sequence"])
    phase["coverage"]["counted_actual_mem_commands"] = len(records)
    phase["coverage"]["exit_zero"] = sum(item["exit"] == 0 for item in records)
    phase["coverage"]["nonzero_boundary_or_failure"] = sum(item["exit"] != 0 for item in records)
    phase["coverage"]["wall_seconds"] = round(sum(item["cost"]["wall_seconds"] for item in records), 6)
    phase["coverage"]["continuity_breaks"] = 0
    PHASE.write_text(json.dumps(phase, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
