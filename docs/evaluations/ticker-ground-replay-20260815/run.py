#!/usr/bin/env python3
"""Run the frozen ticker Ground replay with the subscription Codex provider."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from memcommit.eval.ticker_ground_replay import (  # noqa: E402
    run_ticker_ground_replay,
)
from memcommit.eval.ticker_ground_workflow import (  # noqa: E402
    load_ticker_workflow,
)
from memcommit.query_provider import CodexChatGPTProvider  # noqa: E402


MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "none"
TIMEOUT_SECONDS = 300


class RecordingProvider:
    """Record content-free provider metadata around the real provider."""

    def __init__(self, provider: CodexChatGPTProvider) -> None:
        self._provider = provider
        self.identity = provider.identity
        self.timeout = provider.timeout
        self.last_run = provider.last_run
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        started = time.monotonic()
        answer = self._provider.complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )
        elapsed = time.monotonic() - started
        self.last_run = self._provider.last_run
        self.calls.append(
            {
                "sequence": len(self.calls) + 1,
                "operation": operation,
                "elapsed_seconds": round(elapsed, 3),
                "prompt_characters": len(prompt),
                "completion_characters": len(answer),
                "completion": (
                    asdict(self.last_run) if self.last_run is not None else None
                ),
            }
        )
        print(
            f"[{len(self.calls):02d}] {operation} completed in {elapsed:.1f}s",
            flush=True,
        )
        return answer


def _evaluation(result: dict[str, Any]) -> dict[str, object]:
    corpus = load_ticker_workflow()
    case_by_proposition = {
        example.proposition: example for example in corpus.examples
    }
    rounds: list[dict[str, object]] = []
    previous: dict[str, str] = {}
    regressions: list[dict[str, object]] = []
    improvements: list[dict[str, object]] = []
    final_statuses: dict[str, str] = {}
    for event in result["events"]:
        if event["kind"] != "FIT_AFTER_DISTILL":
            continue
        judgments = event["payload"]["judgments"]
        statuses: dict[str, str] = {}
        for judgment in judgments:
            example = case_by_proposition[judgment["proposition"]]
            case_id = example.case_id
            status = judgment["status"]
            statuses[case_id] = status
            old = previous.get(case_id)
            transition = {
                "case_id": case_id,
                "round": event["reveal_round"],
                "before": old,
                "after": status,
            }
            if old == "FIT" and status != "FIT":
                regressions.append(transition)
            elif old is not None and old != "FIT" and status == "FIT":
                improvements.append(transition)
        previous.update(statuses)
        final_statuses = statuses
        rounds.append(
            {
                "round": event["reveal_round"],
                "ground_revision": event["payload"]["ground_revision"],
                "example_count": len(judgments),
                "counts": event["payload"]["counts"],
            }
        )
    unresolved_ids = result["explicit_unresolved_case_ids"]
    unresolved = [
        {
            "case_id": case_id,
            "fit_status": final_statuses.get(case_id),
            "proposition_remains_unresolved": (
                "remains unresolved"
                in next(
                    example.proposition
                    for example in corpus.examples
                    if example.case_id == case_id
                )
            ),
        }
        for case_id in unresolved_ids
    ]
    final_counts = rounds[-1]["counts"] if rounds else {}
    return {
        "rounds": rounds,
        "fit_to_non_fit_regressions": regressions,
        "non_fit_to_fit_improvements": improvements,
        "explicit_unresolved_coverage": unresolved,
        "final_all_examples_fit": final_counts.get("FIT", 0) == 50,
        "final_unresolved_boundaries_fit_without_fabricated_outputs": all(
            item["fit_status"] == "FIT"
            and item["proposition_remains_unresolved"]
            for item in unresolved
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("actual-run.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    provider = RecordingProvider(
        CodexChatGPTProvider.connect(
            model=MODEL,
            reasoning_effort=REASONING_EFFORT,
            timeout=TIMEOUT_SECONDS,
        )
    )
    try:
        with TemporaryDirectory(prefix="memcommit-ticker-ground-replay-") as tmp:
            replay = run_ticker_ground_replay(
                load_ticker_workflow(),
                root=Path(tmp) / "store",
                semantic_provider_factory=lambda: provider,
            ).to_dict()
        payload: dict[str, object] = {
            "run": {
                "status": "COMPLETED",
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "model": MODEL,
                "reasoning_effort": REASONING_EFFORT,
                "timeout_seconds": TIMEOUT_SECONDS,
                "provider_identity": asdict(provider.identity),
                "provider_calls": provider.calls,
            },
            "evaluation": _evaluation(replay),
            "replay": replay,
        }
    except Exception as error:
        payload = {
            "run": {
                "status": "FAILED",
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "model": MODEL,
                "reasoning_effort": REASONING_EFFORT,
                "timeout_seconds": TIMEOUT_SECONDS,
                "provider_identity": asdict(provider.identity),
                "provider_calls": provider.calls,
                "error_type": type(error).__name__,
                "error": str(error),
            }
        }
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
