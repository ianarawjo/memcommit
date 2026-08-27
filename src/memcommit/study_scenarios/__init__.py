"""Versioned built-in Study scenarios.

Legacy fixture bundles remain owned by :mod:`memcommit.application.evaluation.study_bundle` and
the editable ``study-baseline`` Profile.  Built-in scenarios live here so a
new default can evolve without rewriting that regression fixture.
"""

from memcommit.study_scenarios.coffee_v1 import (
    COFFEE_V1_SCENARIO_ID,
    build_coffee_v1_scenario,
)

__all__ = (
    "COFFEE_V1_SCENARIO_ID",
    "build_coffee_v1_scenario",
)
