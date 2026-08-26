"""Retry only the shared Update/Diff regression with locator-safe canaries."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
import re

from run_shared_concurrency import ACTORS, OUT, RECEIPT_RE, _context, _run, _run_async


async def main() -> None:
    updates = await asyncio.gather(
        *(
            _run_async(
                actor,
                "update-race-safe-canary",
                [
                    "update",
                    "--from",
                    _context(actor, "source"),
                    "--to",
                    _context(actor, "target"),
                    "--direct",
                    "--replace-stage",
                    "--goal",
                    f"Preserve only SHARED_CANARY_{actor.replace('-', '_')} in this target.",
                ],
            )
            for actor in ACTORS
        )
    )
    receipts: dict[str, str | None] = {}
    for call in updates:
        match = RECEIPT_RE.search(call.stdout)
        receipts[call.actor] = match.group(1) if match else None

    diffs = await asyncio.gather(
        *(
            _run_async(actor, "implicit-diff-after-update-race", ["diff", "--raw"])
            for actor in ACTORS
        )
    )
    reviews = []
    for actor in ACTORS:
        receipt = receipts.get(actor)
        if receipt:
            reviews.append(
                _run(
                    actor,
                    "exact-review-after-update-race",
                    ["review", "update", "--session", receipt, "--snapshot"],
                )
            )

    canary_re = re.compile(r"SHARED_CANARY_[A-Za-z0-9_]+")
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "excluded_from_1980": True,
        "receipts": receipts,
        "update_exits": {call.actor: call.exit for call in updates},
        "update_canaries": {
            call.actor: sorted(set(canary_re.findall(call.stdout))) for call in updates
        },
        "diff_exits": {call.actor: call.exit for call in diffs},
        "implicit_diff_canaries": {
            call.actor: sorted(set(canary_re.findall(call.stdout))) for call in diffs
        },
        "review_exits": {call.actor: call.exit for call in reviews},
        "exact_review_canaries": {
            call.actor: sorted(set(canary_re.findall(call.stdout))) for call in reviews
        },
        "calls": [asdict(call) for call in (*updates, *diffs, *reviews)],
    }
    (OUT / "update-race-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
