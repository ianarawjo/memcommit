"""Load a Context and its independent lexical descendants."""

from __future__ import annotations

from typing import Literal, Protocol

from memcommit.models.context import Context
from memcommit.core.context_targeting.resolution import expand_lexical_context_names


class ReadableContextStore(Protocol):
    def load(self, name: str) -> Context: ...
    def list_context_names(
        self,
        *,
        sort_order: Literal["hierarchical", "alphabetical"] = "hierarchical",
    ) -> list[str]: ...


def load_context_and_descendants(
    store: ReadableContextStore,
    context_name: str,
) -> tuple[Context, ...]:
    root_context = store.load(context_name)
    context_names = expand_lexical_context_names(
        (context_name,),
        store.list_context_names(sort_order="alphabetical"),
        include_descendants=True,
    )
    # Keep the selected root first: receipts and analysis use its identity.
    return (
        root_context,
        *(store.load(name) for name in context_names if name != context_name),
    )
