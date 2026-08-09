"""Pure namespace resolution shared by Context scope loaders."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.context_targeting.model import ContextScope


def expand_lexical_context_names(
    scope: ContextScope,
    catalog_names: Sequence[str],
) -> tuple[str, ...]:
    """Expand targets to canonical lexical descendants in catalog order.

    This function resolves only public Context names.  It neither follows
    embedded graph edges nor interprets Grant attachments as hierarchy edges.
    Callers retain their own authority checks and loading semantics.
    """

    catalog = tuple(catalog_names)
    if len(set(catalog)) != len(catalog) or any(
        not isinstance(name, str) or not name for name in catalog
    ):
        raise ValueError("Context scope catalog must contain distinct names.")
    expanded: list[str] = []
    for target_name in scope.target_names:
        expanded.append(target_name)
        if scope.include_descendants:
            prefix = target_name + "/"
            expanded.extend(name for name in catalog if name.startswith(prefix))
    return tuple(dict.fromkeys(expanded))
