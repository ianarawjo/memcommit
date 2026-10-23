"""Normalize retained checkpoint field names at the persistence boundary."""

from __future__ import annotations

import copy


def normalize_checkpoint_record(record: dict) -> dict:
    """Read historical records without publishing old names or generated prose.

    Structured recovery evidence and explicit human notes survive the rename.
    Revert embeds the same record format, so its retained history follows the
    same conversion rather than a separate compatibility path.
    """

    normalized = copy.deepcopy(record)
    legacy_details = normalized.pop("args", None)
    if "command_details" not in normalized:
        normalized["command_details"] = legacy_details
    elif legacy_details is not None and normalized["command_details"] != legacy_details:
        raise ValueError("Checkpoint contains conflicting command details.")
    legacy_message = normalized.pop("message", None)
    normalized.pop("description", None)
    if normalized.get("auto"):
        normalized.pop("checkpoint_message", None)
    elif "checkpoint_message" not in normalized and legacy_message:
        normalized["checkpoint_message"] = legacy_message
    details = normalized.get("command_details")
    if isinstance(details, dict) and isinstance(details.get("log_snapshot"), list):
        details["log_snapshot"] = [
            normalize_checkpoint_record(entry) if isinstance(entry, dict) else entry
            for entry in details["log_snapshot"]
        ]
    return normalized
