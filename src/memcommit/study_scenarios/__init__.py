"""Built-in Study scenarios with self-contained materialization inputs."""

from memcommit.study_scenarios.coffee import (
    COFFEE_SCENARIO_ID,
    build_coffee_scenario,
)
from memcommit.study_scenarios.legacy import LEGACY_SCENARIO_ID

__all__ = (
    "COFFEE_SCENARIO_ID",
    "LEGACY_SCENARIO_ID",
    "build_coffee_scenario",
)
