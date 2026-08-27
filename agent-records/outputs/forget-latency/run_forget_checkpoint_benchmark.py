"""Evaluation-only Task 3 whole-frame Forget latency and agreement runner."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
import glob
import hashlib
import json
from pathlib import Path
import statistics
import time

from memcommit.core.context import Context
from memcommit.application.evaluation.semantic_campaign import _atomic_write_json
from memcommit.ops import analyze_forget
from memcommit.provider_types import CODEX_REASONING_EFFORTS
from memcommit.query_provider import CodexChatGPTProvider


DEFAULT_CHECKPOINTS = Path(
    "/Users/KimMunyeong/.mem-profiles/stores/"
    "fb248286-3986-47a5-8700-d721e9b234a8/"
    "contexts/task-3/participant/forget-working/checkpoints"
)
LABELS = ("KEEP", "EDIT", "DELETE")


class CapturingProvider:
    def __init__(self, provider: CodexChatGPTProvider) -> None:
        self.provider = provider
        self.identity = provider.identity
        self.prompt: str | None = None
        self.output_schema: dict[str, object] | None = None
        self.response: str | None = None
        self.provider_seconds: float | None = None
        self.operation: str | None = None

    @property
    def last_run(self):
        return self.provider.last_run

    def complete(self, prompt, *, operation, output_schema=None):
        self.prompt = prompt
        self.output_schema = output_schema
        self.operation = operation
        started = time.monotonic()
        try:
            self.response = self.provider.complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            return self.response
        finally:
            self.provider_seconds = time.monotonic() - started


def _load_reference(checkpoints: Path):
    loaded = []
    for raw_path in glob.glob(str(checkpoints / "*.json")):
        path = Path(raw_path)
        with path.open(encoding="utf-8") as handle:
            loaded.append((json.load(handle), path))
    before_record, before_path = max(
        (
            (record, path)
            for record, path in loaded
            if record.get("command") == "merge"
        ),
        key=lambda pair: len(pair[0]["snapshot"].get("memories", {})),
    )
    after_record, after_path = next(
        (record, path)
        for record, path in loaded
        if "T003217-Forgot" in path.name
    )
    before = before_record["snapshot"]
    after = after_record["snapshot"]
    if len(before["memories"]) != 300 or len(after["memories"]) != 251:
        raise RuntimeError("historical 300-to-251 comparison frame is not intact")
    return before, after, after_record["args"]["query"], before_path, after_path


def _reference(before, after):
    labels = {}
    contents = {}
    for uid, item in before["memories"].items():
        if uid not in after["memories"]:
            label, content = "DELETE", ""
        elif after["memories"][uid]["content"] != item["content"]:
            label, content = "EDIT", after["memories"][uid]["content"]
        else:
            label, content = "KEEP", item["content"]
        labels[uid] = label
        contents[uid] = content
    return labels, contents


def _prf(confusion, label):
    tp = confusion[label][label]
    fp = sum(confusion[expected][label] for expected in LABELS if expected != label)
    fn = sum(confusion[label][observed] for observed in LABELS if observed != label)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": sum(confusion[label].values()),
    }


def run(args) -> dict[str, object]:
    before, after, query, before_path, after_path = _load_reference(args.checkpoints)
    reference_labels, reference_contents = _reference(before, after)
    context = Context.from_dict(before)
    print(
        f"START {args.model} reasoning={args.reasoning} source=300 ",
        f"reference={dict(Counter(reference_labels.values()))}",
        flush=True,
    )
    connection_started = time.monotonic()
    provider = CodexChatGPTProvider.connect(
        timeout=args.timeout,
        model=args.model,
        reasoning_effort=args.reasoning,
    )
    connection_seconds = time.monotonic() - connection_started
    wrapped = CapturingProvider(provider)
    analysis_started = time.monotonic()
    analysis, _history = analyze_forget(context, query, wrapped)
    analysis_seconds = time.monotonic() - analysis_started

    observed_labels = {
        decision.source_uid: decision.variant for decision in analysis.decisions
    }
    observed_contents = {
        decision.source_uid: decision.proposed_content
        for decision in analysis.decisions
    }
    decisions = {decision.source_uid: decision for decision in analysis.decisions}
    if set(observed_labels) != set(reference_labels):
        raise RuntimeError("decoded result does not cover the exact 300 UIDs")

    confusion = {
        expected: {observed: 0 for observed in LABELS} for expected in LABELS
    }
    for uid, expected in reference_labels.items():
        confusion[expected][observed_labels[uid]] += 1
    correct = sum(confusion[label][label] for label in LABELS)

    change_tp = change_fp = change_fn = change_tn = 0
    for uid, expected in reference_labels.items():
        expected_change = expected != "KEEP"
        observed_change = observed_labels[uid] != "KEEP"
        if expected_change and observed_change:
            change_tp += 1
        elif not expected_change and observed_change:
            change_fp += 1
        elif expected_change and not observed_change:
            change_fn += 1
        else:
            change_tn += 1
    change_precision = change_tp / (change_tp + change_fp) if change_tp + change_fp else 0.0
    change_recall = change_tp / (change_tp + change_fn) if change_tp + change_fn else 0.0
    change_f1 = (
        2 * change_precision * change_recall / (change_precision + change_recall)
        if change_precision + change_recall
        else 0.0
    )

    edit_ratios = []
    edit_exact = 0
    for uid, expected in reference_labels.items():
        if expected == "EDIT" and observed_labels[uid] == "EDIT":
            expected_content = reference_contents[uid]
            observed_content = observed_contents[uid]
            edit_exact += observed_content == expected_content
            edit_ratios.append(
                SequenceMatcher(None, expected_content, observed_content).ratio()
            )

    mismatches = []
    for uid, expected in reference_labels.items():
        observed = observed_labels[uid]
        if observed != expected:
            mismatches.append(
                {
                    "uid": uid,
                    "expected": expected,
                    "observed": observed,
                    "source_content": before["memories"][uid]["content"],
                    "historical_content": reference_contents[uid],
                    "model_content": observed_contents[uid],
                    "model_rationale": decisions[uid].rationale,
                }
            )

    prompt = wrapped.prompt or ""
    response = wrapped.response or ""
    schema_json = json.dumps(
        wrapped.output_schema, ensure_ascii=False, sort_keys=True
    )
    return {
        "kind": "memcommit.semantic-eval.forget-latency-quality-v1",
        "schema_version": 1,
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
        "status": "VALID",
        "production_behavior_changed": False,
        "source_mutated": False,
        "provider": asdict(provider.identity),
        "condition": {
            "model": args.model,
            "reasoning_effort": args.reasoning,
            "operation": wrapped.operation,
            "contract": "production exhaustive whole-frame Forget",
            "calls": 1,
        },
        "corpus": {
            "profile": "study-alt-20260810-t3-forget",
            "before_checkpoint": str(before_path),
            "after_checkpoint": str(after_path),
            "source_count": 300,
            "historical_after_count": 251,
            "instruction": query,
            "source_digest": hashlib.sha256(
                json.dumps(before, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        },
        "timing": {
            "provider_connection_seconds": connection_seconds,
            "provider_seconds": wrapped.provider_seconds,
            "analysis_and_validation_seconds": analysis_seconds,
        },
        "sizes": {
            "prompt_chars": len(prompt),
            "output_schema_chars": len(schema_json),
            "response_chars": len(response),
        },
        "contract_validation": {
            "decoded_decisions": len(analysis.decisions),
            "exact_uid_coverage": len(observed_labels),
            "missing_uids": [],
            "extra_uids": [],
        },
        "historical_reference": {
            "label_counts": dict(Counter(reference_labels.values())),
            "note": (
                "Prior applied production run on the same checkpoint; "
                "agreement is not ground-truth accuracy."
            ),
        },
        "model_result": {
            "overview": analysis.overview,
            "label_counts": dict(Counter(observed_labels.values())),
        },
        "agreement": {
            "exact_label_accuracy": correct / len(reference_labels),
            "exact_label_matches": correct,
            "total": len(reference_labels),
            "confusion_expected_rows_observed_columns": confusion,
            "per_label": {
                label: _prf(confusion, label) for label in LABELS
            },
            "change_vs_keep": {
                "precision": change_precision,
                "recall": change_recall,
                "f1": change_f1,
                "tp": change_tp,
                "fp": change_fp,
                "fn": change_fn,
                "tn": change_tn,
            },
            "historical_edit_overlap": {
                "both_edit_count": len(edit_ratios),
                "exact_content_matches": edit_exact,
                "mean_character_sequence_ratio": (
                    statistics.mean(edit_ratios) if edit_ratios else None
                ),
                "median_character_sequence_ratio": (
                    statistics.median(edit_ratios) if edit_ratios else None
                ),
            },
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
        },
        "raw": {
            "prompt": prompt,
            "output_schema": wrapped.output_schema,
            "response": response,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning", choices=CODEX_REASONING_EFFORTS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoints", type=Path, default=DEFAULT_CHECKPOINTS)
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite {args.output}")
    record = run(args)
    _atomic_write_json(args.output, record)
    print(
        "VALID "
        f"provider_seconds={record['timing']['provider_seconds']:.3f} "
        f"labels={record['model_result']['label_counts']} "
        f"agreement={record['agreement']['exact_label_matches']}/300 "
        f"change_f1={record['agreement']['change_vs_keep']['f1']:.3f} "
        f"mismatches={record['agreement']['mismatch_count']} "
        f"ledger={args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
