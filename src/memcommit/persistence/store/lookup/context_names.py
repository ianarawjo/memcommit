"""Select and order Context names without opening stored records."""

from collections.abc import Sequence
from typing import Literal


def list_context_and_ancestor_names(context_name: str) -> tuple[str, ...]:
    """List every lexical ancestor and the Context itself, highest ancestor first."""
    parts = context_name.split("/")
    return tuple("/".join(parts[:depth]) for depth in range(1, len(parts) + 1))


def list_child_context_names(
    context_name: str,
    catalog_names: Sequence[str],
) -> tuple[str, ...]:
    """List immediate children, excluding the root, in catalog order."""
    return tuple(
        name for name in catalog_names if name.rpartition("/")[0] == context_name
    )


def list_context_and_child_names(
    context_name: str,
    catalog_names: Sequence[str],
) -> tuple[str, ...]:
    """List the root followed by its immediate children."""
    return (context_name, *list_child_context_names(context_name, catalog_names))


def list_context_and_descendant_names(
    target_names: Sequence[str],
    catalog_names: Sequence[str],
) -> tuple[str, ...]:
    """List selected roots and all descendants, deduplicated in catalog order."""
    targets = tuple(target_names)
    if (
        not targets
        or len(set(targets)) != len(targets)
        or any(not isinstance(name, str) or not name for name in targets)
    ):
        raise ValueError("Context scope requires distinct named targets.")
    catalog = tuple(catalog_names)
    if len(set(catalog)) != len(catalog) or any(
        not isinstance(name, str) or not name for name in catalog
    ):
        raise ValueError("Context scope catalog must contain distinct names.")
    names: list[str] = []
    for target_name in targets:
        names.append(target_name)
        prefix = target_name + "/"
        names.extend(name for name in catalog if name.startswith(prefix))
    return tuple(dict.fromkeys(names))


def sort_context_names(
    catalog_names: Sequence[str],
    *,
    sort_order: Literal["hierarchical", "alphabetical"] = "hierarchical",
) -> tuple[str, ...]:
    """Sort names alphabetically, optionally keeping each subtree together."""

    if sort_order not in {"hierarchical", "alphabetical"}:
        raise ValueError(f"Unknown Context name sort order: {sort_order!r}.")
    catalog = tuple(catalog_names)
    if len(set(catalog)) != len(catalog) or any(
        not isinstance(name, str) or not name for name in catalog
    ):
        raise ValueError("Context name sorting requires distinct names.")
    catalog = tuple(sorted(catalog, key=lambda name: (name.casefold(), name)))
    if sort_order == "alphabetical":
        return catalog
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
