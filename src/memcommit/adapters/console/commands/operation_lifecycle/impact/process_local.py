"""Compatibility imports for operation-owned process-local Impact adapters."""

from memcommit.adapters.console.commands.semantic_updates.derive.distill.impact import (
    distill_cmd,
    distill_impact_presentation,
)
from memcommit.adapters.console.commands.semantic_updates.derive.makemore.impact import (
    makemore_cmd,
    makemore_impact_presentation,
)
from memcommit.adapters.console.commands.semantic_updates.curate_integrate.forget.impact import (
    forget_cmd,
    forget_impact_presentation,
)
from memcommit.adapters.console.commands.quality_resolution.repair.resolve.impact import (
    resolve_cmd,
    resolve_impact_presentation,
)


__all__ = [
    "distill_cmd",
    "distill_impact_presentation",
    "makemore_cmd",
    "makemore_impact_presentation",
    "forget_cmd",
    "forget_impact_presentation",
    "resolve_cmd",
    "resolve_impact_presentation",
]
