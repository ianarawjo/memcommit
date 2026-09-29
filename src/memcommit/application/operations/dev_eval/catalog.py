"""Register scenario names and load only the selected application."""

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module

from memcommit.application.operations.dev_eval.duplicates_coffee import data as coffee
from memcommit.application.operations.dev_eval.merge_visitor_notices import (
    data as notices,
)
from memcommit.persistence.store import MemoryStore
from memcommit.providers.types import SemanticProvider


@dataclass(frozen=True)
class ScenarioEntry:
    name: str
    entrypoint: str

    def run(
        self,
        *,
        store: MemoryStore,
        provider_factory: Callable[[], SemanticProvider],
    ) -> list[tuple[str, bool]]:
        module, function = self.entrypoint.split(":", 1)
        # Entrypoints come only from the authored catalog, never from CLI text.
        execute = getattr(import_module(module), function)
        return execute(store=store, provider_factory=provider_factory)


_SCENARIOS = (
    ScenarioEntry(
        coffee.NAME,
        "memcommit.application.operations.dev_eval.duplicates_coffee.application:run_scenario",
    ),
    ScenarioEntry(
        notices.NAME,
        "memcommit.application.operations.dev_eval.merge_visitor_notices.application:run_scenario",
    ),
)


def list_scenarios() -> tuple[ScenarioEntry, ...]:
    return _SCENARIOS


def get_scenario(name: str) -> ScenarioEntry:
    for scenario in list_scenarios():
        if scenario.name == name:
            return scenario
    raise ValueError(
        f"Unknown scenario '{name}'. Run 'mem dev-eval' to list scenarios."
    )
