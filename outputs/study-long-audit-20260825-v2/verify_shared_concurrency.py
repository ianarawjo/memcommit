"""Validate and summarize the supplemental shared-Profile lane."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent / "shared-concurrency"
MAIN = ROOT / "supplemental-report.json"
UPDATE = ROOT / "update-race-report.json"


def main() -> None:
    main_report = json.loads(MAIN.read_text(encoding="utf-8"))
    update_report = json.loads(UPDATE.read_text(encoding="utf-8"))
    current_rounds = main_report["current_rounds"]
    pwd_total = sum(len(row["observations"]) for row in current_rounds)
    own_matches = sum(
        sum(bool(value) for value in row["own_context_matches"].values())
        for row in current_rounds
    )
    single_value_rounds = sum(
        len(set(row["observations"].values())) == 1 for row in current_rounds
    )
    main_calls = main_report["calls"]
    switch_calls = [call for call in main_calls if "-switch" in call["phase"]]
    branch_calls = [call for call in main_calls if call["phase"] == "branch-race"]
    update_calls = [
        call
        for call in update_report["calls"]
        if call["phase"] == "update-race-safe-canary"
    ]
    diff_calls = [
        call
        for call in update_report["calls"]
        if call["phase"] == "implicit-diff-after-update-race"
    ]
    winner = next(call["actor"] for call in update_calls if call["exit"] == 0)
    expected_endpoint = f"audit/shared-v2/{winner}/source"
    diff_winner_matches = sum(
        call["exit"] == 0
        and expected_endpoint in call["stdout"]
        and f"SHARED-CANARY::{winner}" in call["stdout"]
        for call in diff_calls
    )
    checks = {
        "setup_24_success": sum(
            call["phase"] == "setup" and call["exit"] == 0 for call in main_calls
        )
        == 24,
        "five_current_rounds_one_shared_value": single_value_rounds == 5,
        "pwd_observations": pwd_total == 30,
        "only_one_actor_matches_per_round": own_matches == 5,
        "switch_cas_failures": sum(call["exit"] == 1 for call in switch_calls)
        == 19,
        "branch_current_cas_failures": sum(call["exit"] == 1 for call in branch_calls)
        == 5,
        "one_update_winner": sum(call["exit"] == 0 for call in update_calls) == 1,
        "five_update_cas_failures": sum(call["exit"] == 1 for call in update_calls)
        == 5,
        "all_implicit_diffs_show_winner": diff_winner_matches == 6,
        "registry_identity_unchanged": main_report["initial"]["registry_sha256"]
        == main_report["final"]["registry_sha256"],
    }
    status = "complete" if all(checks.values()) else "invalid"
    result = {
        "schema_version": 1,
        "excluded_from_1980": True,
        "status": status,
        "checks": checks,
        "counts": {
            "recorded_calls": len(main_calls) + len(update_report["calls"]),
            "failed_seed_preflight_calls": 102,
            "setup_calls": 24,
            "current_switch_calls": len(switch_calls),
            "current_switch_cas_failures": sum(
                call["exit"] == 1 for call in switch_calls
            ),
            "pwd_calls": pwd_total,
            "pwd_own_matches": own_matches,
            "branch_calls": len(branch_calls),
            "branch_current_cas_failures": sum(
                call["exit"] == 1 for call in branch_calls
            ),
            "update_calls": len(update_calls),
            "update_cas_failures": sum(call["exit"] == 1 for call in update_calls),
            "implicit_diff_calls_showing_winner": diff_winner_matches,
        },
        "update_winner": winner,
        "interpretation": {
            "positive": "Update CAS allowed one explicit-endpoint winner and rejected five stale saves before mutation.",
            "remaining_boundary": "Current and implicit Diff remain Profile-global; explicit disjoint Branch also aborts when unrelated current changes.",
        },
    }
    (ROOT / "verification.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Shared-Profile concurrency supplemental lane",
        "",
        "This focused lane is excluded from the official 1,980 attempts.",
        "",
        f"- Status: `{status}`",
        f"- Recorded product calls: {result['counts']['recorded_calls']}",
        "- Setup: 24/24 succeeded",
        f"- Current: {own_matches}/{pwd_total} actors observed their own Context; every round converged on one last-writer Context",
        f"- Switch: {result['counts']['current_switch_cas_failures']}/30 failed closed on concurrent current change",
        f"- Explicit disjoint Branch: {result['counts']['branch_current_cas_failures']}/6 failed on unrelated current change",
        f"- Update: winner `{winner}`; 5/6 competing saves failed closed via active-record CAS",
        "- Implicit Diff: 6/6 displayed the winner's endpoints and canary",
        "- Registry identity: unchanged",
        "",
        "The old silent Update overwrite is mitigated by CAS, but Profile-global current",
        "and actor-unbound Diff remain shared-state boundaries. Explicit Branch is also",
        "coupled to unrelated current state despite an explicit Source.",
        "",
        "The first 102-call seed preflight never entered product commands because its",
        "active Profile identity was wrong; it is preserved under `failed-seed-preflight/`.",
        "",
    ]
    (ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"shared_concurrency status={status} calls={result['counts']['recorded_calls']}")
    if status != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
