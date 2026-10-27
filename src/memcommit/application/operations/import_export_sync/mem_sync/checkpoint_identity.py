"""Shared operation identity for one explicit Sync's Context checkpoints."""

from uuid import UUID


def validate_sync_checkpoint_identity(command_details):
    record = command_details.get("sync_operation")
    if not isinstance(record, dict) or record.get("action") not in {
        "ADD",
        "EDIT",
        "REMOVE",
        "RENAME",
        "UNCHANGED",
    }:
        raise ValueError("Invalid Sync checkpoint identity.")
    uid = record.get("uid")
    try:
        if str(UUID(uid)) != uid:
            raise ValueError("Invalid Sync checkpoint identity.")
    except (TypeError, AttributeError) as error:
        raise ValueError("Invalid Sync checkpoint identity.") from error
    return uid
