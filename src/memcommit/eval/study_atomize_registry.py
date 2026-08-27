"""Publish one retained Tutorial Atomize analysis into its Study baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from memcommit.infrastructure.config import Config
from memcommit.operations.profile.config import (
    load_profile_registry,
    profile_store_dir,
    study_run_identity,
)
from memcommit.persistence.store import MemoryStore
from memcommit.study_prewarm.atomize import build_atomize_prewarm_artifact
from memcommit.study_prewarm.registry import publish_artifact


class StudyAtomizeRegistryError(RuntimeError):
    """A retained analysis cannot safely become the tutorial fixture."""


def publish_active_tutorial_analysis(
    *,
    baseline_profile_name: str,
    offline_provider_seconds: float,
) -> dict[str, object]:
    registry = load_profile_registry()
    active = registry.active
    identity = study_run_identity(active)
    if identity is None or identity.role != "PARTICIPANT":
        raise StudyAtomizeRegistryError(
            "Active Profile is not a participant Study run."
        )
    baseline = registry.by_name(baseline_profile_name)
    if baseline is None or baseline.uid != identity.baseline_profile_uid:
        raise StudyAtomizeRegistryError(
            "Study baseline identity does not match the active run."
        )
    store = MemoryStore(create=False)
    source = store.load_direct("practice/source")
    description = store.load_direct("practice/description")
    analysis = store.load_atomize_analysis(source.uid)
    if analysis is None:
        raise StudyAtomizeRegistryError(
            "The active Study run has no retained practice Atomize analysis."
        )
    config = Config()
    provider = config.semantic_provider()
    model = config.model_for_provider(provider)
    reasoning = (
        config.codex_reasoning_effort()
        if provider == "codex_chatgpt"
        else None
    )
    key, artifact = build_atomize_prewarm_artifact(
        task_description=description,
        analysis=analysis,
        provider=provider,
        model=model,
        reasoning=reasoning,
        offline_provider_seconds=offline_provider_seconds,
    )
    entry = publish_artifact(
        profile_store_dir(baseline),
        baseline_profile_uid=baseline.uid,
        operation="ATOMIZE",
        task="tutorial",
        key=key,
        artifact=artifact,
    )
    return {
        "kind": "STUDY_ATOMIZE_PREWARM_PUBLICATION_RECEIPT",
        "schema_version": 1,
        "baseline_profile_name": baseline.name,
        "task": "tutorial",
        "operation": "ATOMIZE",
        "entry_key": entry.key,
        "analysis_uid": analysis.uid,
        "provider_calls": 0,
        "semantic_content_in_receipt": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish the active exact Tutorial Atomize analysis."
    )
    parser.add_argument("--baseline-profile", default="study-baseline")
    parser.add_argument("--offline-provider-seconds", type=float, required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = publish_active_tutorial_analysis(
            baseline_profile_name=args.baseline_profile,
            offline_provider_seconds=args.offline_provider_seconds,
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
            print(
                f"Refusing to overwrite publication receipt: {args.output}",
                file=sys.stderr,
            )
            return 1
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
