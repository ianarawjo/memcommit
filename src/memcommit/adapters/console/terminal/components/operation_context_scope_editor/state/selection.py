"""Checked Context selection and cardinality state for terminal controls."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from memcommit.core.context_targeting.model import ContextSelectionMode


@dataclass
class ContextSelectionState:
    """Track checked names separately from the moving Context-tree cursor.

    Multiple selection may be empty while a person is editing a control. The
    operation validates its required cardinality only when constructing an
    executable request or receipt; this state owns interaction mechanics, not
    operation readiness.
    """

    catalog: tuple[str, ...]
    mode: ContextSelectionMode
    _selected_order: list[str] = field(repr=False)

    @classmethod
    def create(
        cls,
        catalog: Sequence[str],
        *,
        selected: Sequence[str],
        mode: ContextSelectionMode = "SINGLE",
    ) -> "ContextSelectionState":
        names = tuple(catalog)
        chosen = list(dict.fromkeys(selected))
        if (
            not names
            or len(set(names)) != len(names)
            or any(not isinstance(name, str) or not name for name in names)
        ):
            raise ValueError("Context selection requires a distinct catalog.")
        if mode not in {"SINGLE", "MULTIPLE"}:
            raise ValueError("Context selection mode must be SINGLE or MULTIPLE.")
        if any(name not in names for name in chosen):
            raise ValueError("Initial Context selections are outside the catalog.")
        if mode == "SINGLE" and len(chosen) != 1:
            raise ValueError("Single Context selection requires exactly one value.")
        return cls(names, mode, chosen)

    @property
    def selected_names(self) -> tuple[str, ...]:
        """Return stable catalog order for provider and receipt boundaries."""

        selected = frozenset(self._selected_order)
        return tuple(name for name in self.catalog if name in selected)

    @property
    def selected_set(self) -> frozenset[str]:
        return frozenset(self._selected_order)

    @property
    def selected_name(self) -> str:
        """Return the sole selected name for a single-cardinality control."""

        if self.multiple:
            raise ValueError("Multiple Context selection has no single selected name.")
        return self._selected_order[0]

    @property
    def multiple(self) -> bool:
        return self.mode == "MULTIPLE"

    def choose(self, name: str) -> bool:
        """Choose or toggle one name and report whether the checked set changed."""

        if name not in self.catalog:
            raise ValueError(
                "The selected Context is no longer available. "
                "Reopen the operation and select it again."
            )
        if not self.multiple:
            changed = self._selected_order != [name]
            self._selected_order = [name]
            return changed
        if name in self._selected_order:
            self._selected_order.remove(name)
            return True
        self._selected_order.append(name)
        return True

    def replace(self, names: Sequence[str]) -> bool:
        """Replace the staged set while preserving the control's cardinality."""

        chosen = list(dict.fromkeys(names))
        if any(name not in self.catalog for name in chosen):
            raise ValueError(
                "One or more selected Contexts are no longer available. "
                "Reopen the operation and select them again."
            )
        if not self.multiple and len(chosen) != 1:
            raise ValueError("Single Context selection requires exactly one value.")
        changed = chosen != self._selected_order
        self._selected_order = chosen
        return changed

    def toggle_group(self, names: Sequence[str], *, anchor_name: str) -> bool:
        """Toggle a caller-defined group through one explicit anchor row.

        The selection model deliberately does not infer hierarchy. A composing
        tree can supply its frozen subtree, while a flat picker can keep using
        ``choose``.
        """

        group = tuple(dict.fromkeys(names))
        if (
            not group
            or anchor_name not in group
            or any(name not in self.catalog for name in group)
        ):
            raise ValueError(
                "The selected Context group is no longer available. "
                "Reopen the operation and select it again."
            )
        if not self.multiple:
            return self.choose(anchor_name)

        group_set = frozenset(group)
        if anchor_name in self._selected_order:
            self._selected_order = [
                name for name in self._selected_order if name not in group_set
            ]
            return True

        # Replace any partial group with the complete group.
        self._selected_order = [
            name for name in self._selected_order if name not in group_set
        ]
        self._selected_order.extend(name for name in group if name != anchor_name)
        self._selected_order.append(anchor_name)
        return True
