"""Frozen Target authority for choice availability and final effect validation."""

from dataclasses import dataclass

from memcommit.core.context import Context


@dataclass(frozen=True, slots=True)
class MergeTargetPolicy:
    """Verified destination facts for Merge choices and final Apply validation."""

    allowed_effects: tuple[str, ...] = ("CREATE", "UPDATE", "DELETE")
    context_mutable: bool = True
    protected_uids: frozenset[str] = frozenset()

    def __post_init__(self):
        if (
            not isinstance(self.allowed_effects, tuple)
            or len(set(self.allowed_effects)) != len(self.allowed_effects)
            or not set(self.allowed_effects) <= {"CREATE", "UPDATE", "DELETE"}
        ):
            raise ValueError(
                "Target effects must be distinct CREATE/UPDATE/DELETE values."
            )
        if type(self.context_mutable) is not bool:
            raise TypeError("Target mutability must be a boolean.")
        if not isinstance(self.protected_uids, frozenset) or any(
            not isinstance(uid, str) or not uid for uid in self.protected_uids
        ):
            raise TypeError("Protected Target identities must be frozen text.")


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
        if effect not in policy.allowed_effects or not policy.context_mutable:
            raise ValueError(
                f"Merge Target does not permit {effect} in the reviewed result."
            )
    for uid in policy.protected_uids:
        old, new = before.memories.get(uid), after.memories.get(uid)
        if old is not None and (new is None or old.to_dict() != new.to_dict()):
            raise ValueError("Resolve changed a protected Target item.")
