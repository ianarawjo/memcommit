"""Publish one retained exact Study Compare analysis into its baseline fixture.

This setup command never calls a provider. It takes a content-free receipt
from ``study_compare_prewarm``, reloads the corresponding production analysis
from the active Study run, strips the run-specific Grant wrapper, and publishes
one exact portable payload under the run's baseline Profile. Future
``mem init-study`` runs rebind that payload to their own Grant identities.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from memcommit.application.operations.compare.ledger.execution import load_comparison_context
from memcommit.application.authority.access import resolve_context_access
from memcommit.application.operations.compare.ledger.store import load_comparison_analysis
from memcommit.application.operations.compare.ledger.granted_store import load_granted_comparison_artifact
from memcommit.application.operations.profile.config import load_profile_registry, profile_store_dir, study_run_identity
from memcommit.persistence.store import MemoryStore
from memcommit.study_prewarm.compare import build_compare_prewarm_artifact
from memcommit.study_prewarm.registry import publish_artifact


class StudyCompareRegistryError(RuntimeError):
    """A retained analysis cannot safely become a declared Study fixture."""


def _read_receipt(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyCompareRegistryError("Cannot read Compare prewarm receipt.") from error
    if not isinstance(value, dict) or value.get("kind") != "STUDY_COMPARE_PREWARM":
        raise StudyCompareRegistryError("Not a Study Compare prewarm receipt.")
    return value


def _endpoint(receipt: dict[str, object], key: str) -> dict[str, object]:
    value = receipt.get(key)
    if not isinstance(value, dict):
        raise StudyCompareRegistryError(f"Compare receipt has no {key} endpoint.")
    return value


def publish_from_receipt(
    *,
    receipt_path: Path,
    task: str,
    baseline_profile_name: str,
) -> dict[str, object]:
    receipt = _read_receipt(receipt_path)
    registry = load_profile_registry()
    active = registry.active
    identity = study_run_identity(active)
    if identity is None or identity.role != "PARTICIPANT":
        raise StudyCompareRegistryError("Active Profile is not a participant Study run.")
    if receipt.get("profile_name") != active.name:
        raise StudyCompareRegistryError("Receipt belongs to a different Study run.")
    baseline = registry.by_name(baseline_profile_name)
    if baseline is None or baseline.uid != identity.baseline_profile_uid:
        raise StudyCompareRegistryError("Study baseline identity does not match the run.")
    reference = _endpoint(receipt, "reference")
    compared = _endpoint(receipt, "compared")
    reference_uid = reference.get("context_uid")
    compared_uid = compared.get("context_uid")
    if not isinstance(reference_uid, str) or not isinstance(compared_uid, str):
        raise StudyCompareRegistryError("Compare receipt Context identity is invalid.")
    store = MemoryStore(create=False)
    if bool(reference.get("granted")) or bool(compared.get("granted")):
        retained = load_granted_comparison_artifact(store, reference_uid, compared_uid)
        analysis = retained.analysis if retained is not None else None
    else:
        analysis = load_comparison_analysis(reference_uid, compared_uid)
    if analysis is None or analysis.uid != receipt.get("analysis_uid"):
        raise StudyCompareRegistryError("Exact retained Compare analysis is unavailable.")
    description_name = "practice/description" if task == "tutorial" else f"{task}/description"
    current_name = store.current_context_name()
    description_access = resolve_context_access(
        store,
        description_name,
        current_name=current_name,
        required_permission="READ",
        registry=registry,
    )
    description = load_comparison_context(description_access)
    provider = receipt.get("requested_provider")
    model = receipt.get("requested_model")
    reasoning = receipt.get("requested_reasoning")
    provider_seconds = receipt.get("provider_seconds")
    if (
        not isinstance(provider, str)
        or not isinstance(model, str)
        or not isinstance(reasoning, str)
        or not isinstance(provider_seconds, (int, float))
    ):
        raise StudyCompareRegistryError("Compare receipt provider evidence is invalid.")
    key, artifact = build_compare_prewarm_artifact(
        task=task,
        task_description=description,
        analysis=analysis,
        provider=provider,
        model=model,
        reasoning=reasoning,
        offline_provider_seconds=float(provider_seconds),
    )
    entry = publish_artifact(
        profile_store_dir(baseline),
        baseline_profile_uid=baseline.uid,
        operation="COMPARE",
        task=task,
        key=key,
        artifact=artifact,
    )
    return {
        "kind": "STUDY_COMPARE_PREWARM_PUBLICATION_RECEIPT",
        "schema_version": 1,
        "baseline_profile_name": baseline.name,
        "task": task,
        "operation": "COMPARE",
        "entry_key": entry.key,
        "analysis_uid": analysis.uid,
        "provider_calls": 0,
        "semantic_content_in_receipt": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish an exact retained Compare seed into Study baseline setup."
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--task",
        choices=("tutorial", "task-1", "task-2", "task-3"),
        required=True,
    )
    parser.add_argument("--baseline-profile", default="study-baseline")
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = publish_from_receipt(
            receipt_path=args.receipt,
            task=args.task,
            baseline_profile_name=args.baseline_profile,
        )
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as file:
                json.dump(receipt, file, ensure_ascii=False, indent=2, sort_keys=True)
                file.write("\n")
        except FileExistsError:
            print(f"Refusing to overwrite publication receipt: {args.output}", file=sys.stderr)
            return 1
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
