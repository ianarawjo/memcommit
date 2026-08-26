"""Launch the frozen mem CLI against one audit-owned Profile registry.

This harness is deliberately outside the product snapshot.  It changes only
the process-local path resolvers before importing the CLI; product code and the
participant's live Profile registry remain untouched.
"""

from __future__ import annotations

import os
from pathlib import Path


def _required_path(name: str) -> Path:
    raw = os.environ.get(name)
    if not raw:
        raise SystemExit(f"{name} is required")
    try:
        return Path(raw).resolve(strict=True)
    except OSError as error:
        raise SystemExit(f"{name} is not a readable existing path: {raw}") from error


def main() -> None:
    code_root = _required_path("MEMCOMMIT_AUDIT_CODE_ROOT")
    profile_control = _required_path("MEMCOMMIT_AUDIT_PROFILE_CONTROL")

    import memcommit

    imported_root = Path(memcommit.__file__).resolve().parent.parent
    if imported_root != code_root:
        raise SystemExit(
            "Frozen-code assertion failed: "
            f"expected {code_root}, imported {imported_root}"
        )

    import memcommit.profile_config as profile_config

    # The CLI has no root-level explicit Profile/Store option.  Pin both path
    # families before store.py or the CLI is imported, so every adapter sees
    # one immutable process-local selection without racing the live active_uid.
    profile_config.profile_control_dir = lambda: profile_control
    profile_config.default_store_dir = lambda: profile_control / "authoring-store"

    import memcommit.config as mem_config

    # Provider/config commands otherwise retain the process user's real
    # ~/.mem/config.json even though the active MemoryStore is isolated.
    mem_config.CONFIG_FILE = profile_control / "authoring-store" / "config.json"

    registry = profile_config.load_profile_registry()
    expected_name = os.environ.get("MEMCOMMIT_AUDIT_EXPECTED_PROFILE_NAME")
    expected_uid = os.environ.get("MEMCOMMIT_AUDIT_EXPECTED_PROFILE_UID")
    if expected_name and registry.active.name != expected_name:
        raise SystemExit(
            "Pinned Profile name changed: "
            f"expected {expected_name}, got {registry.active.name}"
        )
    if expected_uid and registry.active.uid != expected_uid:
        raise SystemExit(
            "Pinned Profile uid changed: "
            f"expected {expected_uid}, got {registry.active.uid}"
        )

    resolved_store = profile_config.resolve_active_store_dir().resolve()
    expected_store = os.environ.get("MEMCOMMIT_AUDIT_EXPECTED_STORE_ROOT")
    if expected_store and resolved_store != Path(expected_store).resolve():
        raise SystemExit(
            "Pinned Store root changed: "
            f"expected {Path(expected_store).resolve()}, got {resolved_store}"
        )

    from memcommit.cli import app

    app()


if __name__ == "__main__":
    main()
