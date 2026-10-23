"""The local Memory-only Task 1–3 Study scenario and its native inputs."""

import hashlib
import json
from pathlib import Path

LEGACY_SCENARIO_ID = "legacy"
# Source provenance only; this identity is never a registered editable Profile.
LEGACY_BASELINE_UID = "b803a4ca-d5de-5ea1-9339-e24df565fb9c"


def _scenario_digest() -> str:
    root = Path(__file__).parent / "data" / "native"
    files = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part.startswith(".") for part in path.relative_to(root).parts)
    ]
    payload = {
        "scenario_id": LEGACY_SCENARIO_ID,
        "scope": "memory-only-local-contexts-v1",
        "files": files,
    }
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


LEGACY_DIGEST = "26f792b0aff331b652446256b84fa0c1cb70f662d5edf5aee1f17bd3c92f1c8d"
if _scenario_digest() != LEGACY_DIGEST:
    raise ValueError(
        "Packaged Legacy Study inputs differ from their pinned fingerprint."
    )

__all__ = ("LEGACY_BASELINE_UID", "LEGACY_DIGEST", "LEGACY_SCENARIO_ID")
