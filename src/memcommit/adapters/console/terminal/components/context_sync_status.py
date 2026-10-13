"""Common active automatic-Sync label; plain text remains the full signal."""


def context_sync_status_text(status):
    if status is None:
        return ""
    if status not in {"SYNC", "SYNC PENDING", "SYNC ERROR"}:
        raise ValueError("Invalid Context Sync status.")
    return "  " + status
