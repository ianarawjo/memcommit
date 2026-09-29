"""Describe the exact first-item retention choice for DUP and DUN findings."""

from ...model import AuditResolutionIssue


def build_fixed_suggestion(item: AuditResolutionIssue) -> str:
    if item.item_kind == "MEMORY":
        return (
            f"Keep the first Memory [{item.item_uids[0][:8]}] unchanged and delete "
            "the duplicate "
            + ", ".join(f"[{uid[:8]}]" for uid in item.item_uids[1:])
            + "."
        )
    return (
        f"Keep {item.item_kind} [{item.item_uids[0][:8]}] and remove only the duplicate "
        "placements "
        + ", ".join(f"[{uid[:8]}]" for uid in item.item_uids[1:])
        + ". Referenced Source content stays unchanged."
    )
