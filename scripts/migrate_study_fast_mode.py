#!/usr/bin/env python3
"""Repin visible pilot Study pairs to the Study-only Codex Fast policy."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from memcommit.providers.policy import (  # noqa: E402
    LEGACY_STUDY_PROVIDER_POLICY_VERSION,
    STUDY_PROVIDER_POLICY_DIGEST,
    STUDY_PROVIDER_POLICY_VERSION,
    study_provider_config,
)
from memcommit.application.operations.profile.model import migrate_visible_study_provider_policy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Atomically migrate visible pilot Study pairs to the current "
            "Study-only Codex Fast policy."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="publish the migration; without this flag only show the target",
    )
    args = parser.parse_args()

    legacy = study_provider_config(LEGACY_STUDY_PROVIDER_POLICY_VERSION)
    current = study_provider_config(STUDY_PROVIDER_POLICY_VERSION)
    print(f"target_version: {current.version}")
    print(f"target_digest: {current.digest}")
    print(f"service_tier: {current.service_tier or 'standard'}")
    if not args.apply:
        print("status: dry_run")
        return 0

    result = migrate_visible_study_provider_policy(
        target_version=STUDY_PROVIDER_POLICY_VERSION,
        target_digest=STUDY_PROVIDER_POLICY_DIGEST,
        accepted_sources=frozenset(
            {
                (None, None),
                (LEGACY_STUDY_PROVIDER_POLICY_VERSION, legacy.digest),
            }
        ),
    )
    print(f"migrated_studies: {result.migrated_study_count}")
    print(f"migrated_profiles: {result.migrated_profile_count}")
    print(f"registry_generation: {result.generation}")
    print("status: applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
