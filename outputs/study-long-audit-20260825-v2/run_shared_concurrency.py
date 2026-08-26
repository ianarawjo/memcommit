"""Focused supplemental shared-Profile concurrency regression.

This lane is intentionally excluded from the 1,980-attempt coverage contract.
It uses one fresh clone of the frozen Study template and records every command.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "run_shared_mem.py"
OUT = ROOT / "shared-concurrency"
CONTROL = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/shared-concurrency/profile-control"
)
STORE = CONTROL / "stores" / "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
ACTORS = (
    "task-1",
    "task-2",
    "task-3",
    "ticker",
    "a-is-apple",
    "practice-source",
)
RECEIPT_RE = re.compile(r"RECEIPT\s+[·:]?\s*([0-9a-f-]{36})", re.IGNORECASE)


@dataclass
class Call:
    actor: str
    phase: str
    argv: list[str]
    exit: int
    wall_seconds: float
    stdout: str
    stderr: str


def _sha(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(actor: str, phase: str, args: list[str], timeout: int = 360) -> Call:
    command = [sys.executable, str(RUNNER), actor, *args]
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return Call(
            actor=actor,
            phase=phase,
            argv=command,
            exit=result.returncode,
            wall_seconds=round(time.monotonic() - started, 6),
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except subprocess.TimeoutExpired as error:
        return Call(
            actor=actor,
            phase=phase,
            argv=command,
            exit=124,
            wall_seconds=round(time.monotonic() - started, 6),
            stdout=(error.stdout or "") if isinstance(error.stdout, str) else "",
            stderr=(error.stderr or "") if isinstance(error.stderr, str) else "",
        )


async def _run_async(
    actor: str, phase: str, args: list[str], timeout: int = 360
) -> Call:
    return await asyncio.to_thread(_run, actor, phase, args, timeout)


def _context(actor: str, leaf: str) -> str:
    return f"audit/shared-v2/{actor}/{leaf}"


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    calls: list[Call] = []
    initial = {
        "registry_sha256": _sha(CONTROL / "registry.json"),
        "state_sha256": _sha(STORE / "state.json"),
        "staged_update_sha256": _sha(STORE / "staged-update.json"),
    }

    # Fresh-clone setup is serialized and included as supplemental evidence.
    for actor in ACTORS:
        for leaf in ("source", "target"):
            calls.append(
                _run(actor, "setup", ["init", _context(actor, leaf), "--parents"])
            )
        calls.append(
            _run(
                actor,
                "setup",
                [
                    "add",
                    f"SHARED-CANARY::{actor} source assertion.",
                    "--context",
                    _context(actor, "source"),
                ],
            )
        )
        calls.append(
            _run(
                actor,
                "setup",
                [
                    "add",
                    f"SHARED-BASELINE::{actor} target assertion.",
                    "--context",
                    _context(actor, "target"),
                ],
            )
        )

    # Global-current contention: all writers complete before all readers.
    current_rounds: list[dict[str, object]] = []
    for round_index in range(1, 6):
        switch_calls = await asyncio.gather(
            *(
                _run_async(
                    actor,
                    f"current-r{round_index}-switch",
                    ["switch", _context(actor, "source")],
                )
                for actor in ACTORS
            )
        )
        calls.extend(switch_calls)
        pwd_calls = await asyncio.gather(
            *(
                _run_async(actor, f"current-r{round_index}-pwd", ["pwd"])
                for actor in ACTORS
            )
        )
        calls.extend(pwd_calls)
        observations = {
            call.actor: call.stdout.strip().splitlines()[-1]
            if call.stdout.strip()
            else ""
            for call in pwd_calls
        }
        current_rounds.append(
            {
                "round": round_index,
                "observations": observations,
                "own_context_matches": {
                    actor: observations.get(actor) == _context(actor, "source")
                    for actor in ACTORS
                },
            }
        )

    # Six explicit endpoint Updates race for the one Profile-owned active record.
    update_calls = await asyncio.gather(
        *(
            _run_async(
                actor,
                "update-race",
                [
                    "update",
                    _context(actor, "source"),
                    _context(actor, "target"),
                    "--direct",
                    "--replace-stage",
                    "--goal",
                    f"Preserve only SHARED-CANARY::{actor} in this actor target.",
                ],
            )
            for actor in ACTORS
        )
    )
    calls.extend(update_calls)
    receipts: dict[str, str | None] = {}
    for call in update_calls:
        match = RECEIPT_RE.search(call.stdout)
        receipts[call.actor] = match.group(1) if match else None

    # Implicit Diff is intentionally actor-unbound; exact Review uses each receipt.
    diff_calls = await asyncio.gather(
        *(_run_async(actor, "implicit-diff", ["diff", "--raw"]) for actor in ACTORS)
    )
    calls.extend(diff_calls)
    review_calls: list[Call] = []
    for actor in ACTORS:
        receipt = receipts.get(actor)
        if receipt:
            review_calls.append(
                _run(
                    actor,
                    "exact-review",
                    ["review", "update", "--session", receipt, "--snapshot"],
                )
            )
    calls.extend(review_calls)

    # Disjoint checkpoint-producing mutations start together. The shared
    # command publication lock should serialize without receipt misattribution.
    branch_calls = await asyncio.gather(
        *(
            _run_async(
                actor,
                "branch-race",
                [
                    "branch",
                    _context(actor, "branch-copy"),
                    "--from",
                    _context(actor, "source"),
                    "--direct",
                ],
            )
            for actor in ACTORS
        )
    )
    calls.extend(branch_calls)

    final = {
        "registry_sha256": _sha(CONTROL / "registry.json"),
        "state_sha256": _sha(STORE / "state.json"),
        "staged_update_sha256": _sha(STORE / "staged-update.json"),
    }
    diff_canaries = {
        call.actor: sorted(set(re.findall(r"SHARED-CANARY::[a-z0-9-]+", call.stdout)))
        for call in diff_calls
    }
    review_canaries = {
        call.actor: sorted(set(re.findall(r"SHARED-CANARY::[a-z0-9-]+", call.stdout)))
        for call in review_calls
    }
    result = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "excluded_from_1980": True,
        "code_snapshot_sha256": "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84",
        "profile_uid": "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd",
        "store_root": str(STORE),
        "initial": initial,
        "final": final,
        "current_rounds": current_rounds,
        "update_receipts": receipts,
        "implicit_diff_canaries": diff_canaries,
        "exact_review_canaries": review_canaries,
        "branch_exit_codes": {call.actor: call.exit for call in branch_calls},
        "calls": [asdict(call) for call in calls],
    }
    (OUT / "supplemental-report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = [
        "# Shared-Profile concurrency supplemental lane",
        "",
        "This lane is excluded from the 1,980-attempt contract.",
        "",
        f"- Calls: {len(calls)}",
        f"- Update exits: {dict((c.actor, c.exit) for c in update_calls)}",
        f"- Implicit Diff canaries: {diff_canaries}",
        f"- Exact Review canaries: {review_canaries}",
        f"- Branch exits: {dict((c.actor, c.exit) for c in branch_calls)}",
        "",
        "See `supplemental-report.json` for exact argv, stdout, stderr, timing,",
        "current observations, identities, and hashes.",
        "",
    ]
    (OUT / "README.md").write_text("\n".join(summary), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
