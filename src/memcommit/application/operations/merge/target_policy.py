"""Frozen Target authority for choice availability and final effect validation."""

from dataclasses import dataclass

from memcommit.models.context import Context


@dataclass(frozen=True, slots=True)
class MergeTargetPolicy:
    """Verified destination facts for Merge choices and final Apply validation."""

    allowed_effects: tuple[str, ...] = ("CREATE", "UPDATE", "DELETE")

    def __post_init__(self):
        if (
            not isinstance(self.allowed_effects, tuple)
            or len(set(self.allowed_effects)) != len(self.allowed_effects)
            or not set(self.allowed_effects) <= {"CREATE", "UPDATE", "DELETE"}
        ):
            raise ValueError(
                "Target effects must be distinct CREATE/UPDATE/DELETE values."
            )


def validate_target_result(
    policy: MergeTargetPolicy | None, before: Context, after: Context
) -> None:
    """Check the proposed effects against the original destination authority."""
    if policy is None:
        return
    for uid in set(before.memories) | set(after.memories):
        old, new = before.memories.get(uid), after.memories.get(uid)
        if old is not None and new is not None and old.to_dict() == new.to_dict():
            continue
        effect = "CREATE" if old is None else "DELETE" if new is None else "UPDATE"
        if effect not in policy.allowed_effects:
            raise ValueError(
                f"Merge Target does not permit {effect} in the reviewed result."
            )
