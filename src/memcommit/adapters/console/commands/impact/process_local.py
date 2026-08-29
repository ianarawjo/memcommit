"""Compatibility imports for operation-owned process-local Impact adapters."""

from memcommit.adapters.console.commands.distill.impact import (
    distill_cmd,
    distill_impact_presentation,
)
from memcommit.adapters.console.commands.elaborate.impact import (
    elaborate_cmd,
    elaborate_impact_presentation,
)
from memcommit.adapters.console.commands.forget.impact import (
    forget_cmd,
    forget_impact_presentation,
)
from memcommit.adapters.console.commands.resolve.impact import (
    resolve_cmd,
    resolve_impact_presentation,
)


__all__ = [
    "distill_cmd",
    "distill_impact_presentation",
    "elaborate_cmd",
    "elaborate_impact_presentation",
    "forget_cmd",
    "forget_impact_presentation",
    "resolve_cmd",
    "resolve_impact_presentation",
]
