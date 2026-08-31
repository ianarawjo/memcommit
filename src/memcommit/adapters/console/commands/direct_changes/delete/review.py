"""Human-readable review projection for permanent Context deletion."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.direct_changes.delete.application import FrozenContextDeletePlan


def context_delete_warning(plan: FrozenContextDeletePlan) -> str:
    """Describe every irreversible effect before a human CLI approval."""

    return (
        f"This will permanently delete context "
        f"'{display_escape_text(plan.context_name)}' and its checkpoint history, "
        "plus its matching atomize analysis and semantic review artifacts, "
        "including peer Compare analyses. Descendant contexts will be preserved. "
        "A Profile-scoped lifecycle event will retain the deleted Context identity "
        "and digests, but no Memory content or restorable snapshot."
    )


__all__ = ["context_delete_warning"]
