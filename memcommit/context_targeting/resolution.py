"""Pure namespace resolution shared by Context scope loaders."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.context_targeting.model import ContextScope


def order_context_names_by_hierarchy(
    catalog_names: Sequence[str],
) -> tuple[str, ...]:
    """Project a frozen public catalog in depth-first namespace order.

    Siblings retain catalog order. This lets a caller append virtual Grant
    rows after ordinary local rows while still placing both beneath their
    nearest real public-name parent, matching the shared Context tree without
    importing terminal state into a static command.
    """

    catalog = tuple(catalog_names)
    if len(set(catalog)) != len(catalog) or any(
        not isinstance(name, str) or not name for name in catalog
    ):
        raise ValueError("Context hierarchy catalog must contain distinct names.")
    catalog_set = frozenset(catalog)
    children: dict[str | None, list[str]] = {None: []}
    for name in catalog:
        segments = name.split("/")
        parent = next(
            (
                "/".join(segments[:length])
                for length in range(len(segments) - 1, 0, -1)
                if "/".join(segments[:length]) in catalog_set
            ),
            None,
        )
        children.setdefault(parent, []).append(name)
        children.setdefault(name, [])

    ordered: list[str] = []
    pending = list(reversed(children[None]))
    while pending:
        name = pending.pop()
        ordered.append(name)
        pending.extend(reversed(children[name]))
    return tuple(ordered)


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
