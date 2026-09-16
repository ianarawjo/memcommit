"""Profile-wide and Context-range selection over one frozen readable catalog."""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field

from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.reach import (
    ContextReachState,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.tree_rendering import (
    ContextTreeRowDecoration,
    render_context_tree_rows,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.selection import (
    ContextSelectionState,
    ContextTargetModeState,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.tree import (
    ContextTree,
    ContextTreeState,
    build_context_tree,
    context_subtree_names,
)
from memcommit.adapters.console.terminal.components.selection import tree_choice_marker, tree_choice_styles
from memcommit.source_projection.presentation import SourceDisplayValue


_PROFILE_TARGET_UID = "\x00PROFILE"


def project_checked_context_names(
    tree: ContextTree,
    selected_names: Sequence[str],
    *,
    include_descendants: bool,
    selectable_names: Set[str] | None = None,
) -> tuple[str, ...]:
    """Project exact roots and lexical reach into visible checked rows.

    Saved-session operations continue to persist one root plus a descendant
    boolean.  This projection makes that compact semantic value visible as the
    complete checked range without turning implied descendants into separately
    persisted selections.  An availability filter keeps opaque or otherwise
    unavailable catalog rows from appearing selected.
    """

    catalog = tuple(tree.parent_by_name)
    roots = tuple(selected_names)
    if len(set(roots)) != len(roots) or any(name not in catalog for name in roots):
        raise ValueError("Checked Context roots are outside the frozen tree.")
    if type(include_descendants) is not bool:
        raise ValueError("Checked Context descendant scope must be a boolean.")
    selectable = frozenset(catalog if selectable_names is None else selectable_names)
    if not selectable <= set(catalog):
        raise ValueError("Selectable checked Contexts are outside the frozen tree.")
    if not roots:
        return ()
    expanded = expand_lexical_context_names(
        ContextScope.create(roots, include_descendants=include_descendants),
        catalog,
    )
    return tuple(name for name in expanded if name in selectable)


@dataclass
class ContextRangeSelectionState:
    """Compose Profile, root cardinality, reach, and effective checked rows.

    The root selection remains independent from lexical reach.  Exact
    exclusions preserve a person's independently unchecked descendant while
    execution consumers freeze ``effective_names`` instead of applying hidden
    expansion again.
    """

    catalog: tuple[str, ...]
    current_name: str
    tree: ContextTreeState
    selection: ContextSelectionState
    target_mode: ContextTargetModeState
    reach: ContextReachState
    profile_cursor: bool = False
    exclusions: set[str] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        names: Sequence[str],
        *,
        current_name: str,
        initial_target: str,
        multiple: bool,
        include_descendants: bool,
    ) -> "ContextRangeSelectionState":
        catalog = tuple(names)
        if (
            not catalog
            or len(set(catalog)) != len(catalog)
            or any(not isinstance(name, str) or not name for name in catalog)
        ):
            raise ValueError("Context range selection requires a distinct catalog.")
        if current_name not in catalog or initial_target not in catalog:
            raise ValueError("Initial Context range target is outside the catalog.")
        mode = "MULTIPLE" if multiple else "SINGLE"
        return cls(
            catalog=catalog,
            current_name=current_name,
            tree=ContextTreeState.create(
                build_context_tree(catalog),
                selected=initial_target,
            ),
            selection=ContextSelectionState.create(
                (_PROFILE_TARGET_UID, *catalog),
                selected=(initial_target,),
                mode=mode,
            ),
            target_mode=ContextTargetModeState.create(multiple=multiple),
            reach=ContextReachState.create(include_descendants=include_descendants),
        )

    @property
    def profile_selected(self) -> bool:
        return _PROFILE_TARGET_UID in self.selection.selected_set

    @property
    def explicit_context_names(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in self.selection.selected_names
            if name != _PROFILE_TARGET_UID
        )

    @property
    def base_names(self) -> tuple[str, ...]:
        if self.profile_selected:
            return self.catalog
        return project_checked_context_names(
            self.tree.tree,
            self.explicit_context_names,
            include_descendants=self.reach.include_descendants,
        )

    @property
    def effective_names(self) -> tuple[str, ...]:
        return tuple(name for name in self.base_names if name not in self.exclusions)

    def _prune_exclusions(self) -> None:
        self.exclusions.intersection_update(self.base_names)

    def move_cursor(self, delta: int) -> bool:
        if delta not in {-1, 1}:
            raise ValueError("Context range cursor direction must be -1 or 1.")
        if self.profile_cursor:
            if delta < 0:
                return False
            self.profile_cursor = False
            self.tree.selected_name = self.tree.visible_rows()[0].name
            return True
        if delta < 0 and self.tree.selected_row_index() == 0:
            self.profile_cursor = True
            return True
        before = self.tree.selected_name
        self.tree.move(delta)
        return self.tree.selected_name != before

    def enter_from_boundary(self, delta: int) -> None:
        if delta > 0:
            self.profile_cursor = True
            return
        self.profile_cursor = False
        self.tree.selected_name = self.tree.visible_rows()[-1].name

    def expand_cursor(self) -> None:
        if not self.profile_cursor:
            self.tree.expand_selected()

    def collapse_cursor(self) -> None:
        if not self.profile_cursor:
            self.tree.collapse_selected()

    def toggle_expand_all(self) -> None:
        self.tree.toggle_expand_all()

    def toggle_cursor(self) -> bool:
        """Change the staged range and report whether its effective set changed."""

        before = self.effective_names
        if self.profile_cursor:
            if self.selection.multiple and self.profile_selected:
                self.selection.replace(())
            else:
                self.selection.replace((_PROFILE_TARGET_UID,))
            self.exclusions.clear()
            return self.effective_names != before

        name = self.tree.selected_name
        if not self.selection.multiple:
            self.selection.replace((name,))
            self.exclusions.clear()
            return self.effective_names != before

        if not self.reach.include_descendants:
            if self.profile_selected:
                self.selection.replace(self.catalog)
            self.exclusions.clear()
            self.selection.choose(name)
            return self.effective_names != before

        if self.profile_selected:
            # A child edit must remove the virtual all-target marker; otherwise
            # PROFILE would still visibly claim every Context is selected.
            self.selection.replace(self.tree.tree.roots)
            self.exclusions.clear()
        effective = frozenset(self.effective_names)
        subtree = frozenset(context_subtree_names(self.tree.tree, name))
        if name in effective:
            retained = tuple(
                candidate
                for candidate in self.explicit_context_names
                if candidate not in subtree
            )
            self.selection.replace(retained)
            self.exclusions.update(subtree)
            self._prune_exclusions()
        else:
            self.exclusions.difference_update(subtree)
            if name not in self.base_names:
                retained = tuple(
                    candidate
                    for candidate in self.explicit_context_names
                    if candidate not in subtree
                )
                self.selection.replace((*retained, name))
            self._prune_exclusions()
        return self.effective_names != before

    def move_target_mode(self, delta: int) -> tuple[bool, bool]:
        """Move cardinality; return (control changed, effective set changed)."""

        before = self.effective_names
        if not self.target_mode.move(delta):
            return False, False
        self.selection.set_multiple(
            self.target_mode.multiple,
            fallback_name=(
                _PROFILE_TARGET_UID if self.profile_cursor else self.tree.selected_name
            ),
        )
        self.exclusions.clear()
        return True, self.effective_names != before

    def move_reach(self, delta: int) -> bool:
        if not self.reach.move(delta):
            return False
        self.exclusions.clear()
        return True

    def render_rows(
        self,
        *,
        focused: bool,
        annotations: Mapping[str, SourceDisplayValue] | None = None,
        profile_label: str = "PROFILE",
        profile_description: str = "ALL READABLE CONTEXTS",
    ) -> list[tuple[str, str]]:
        if not profile_label or not profile_description:
            raise ValueError("Context range Profile labels must be nonblank.")
        labels = dict(annotations or {})
        effective = frozenset(self.effective_names)
        profile_cursor_style, profile_value_style = tree_choice_styles(
            cursor=self.profile_cursor,
            selected=self.profile_selected,
            focused=focused,
        )
        fragments: list[tuple[str, str]] = []
        if self.profile_cursor:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.extend(
            [
                (
                    profile_cursor_style,
                    f"{'›' if self.profile_cursor else ' '} "
                    f"{tree_choice_marker(selected=self.profile_selected)}   ",
                ),
                (profile_value_style, profile_label),
                ("", f"  {profile_description}\n"),
            ]
        )

        def decorate(row, cursor: bool) -> ContextTreeRowDecoration:
            selected = row.name in effective
            visible_cursor = cursor and not self.profile_cursor
            cursor_style, value_style = tree_choice_styles(
                cursor=visible_cursor,
                selected=selected,
                focused=focused,
            )
            return ContextTreeRowDecoration(
                marker=tree_choice_marker(selected=selected),
                active="*" if row.name == self.current_name else " ",
                annotation=labels.get(row.name, ""),
                cursor_style=cursor_style,
                value_style=value_style,
                show_cursor=not self.profile_cursor,
            )

        fragments.extend(render_context_tree_rows(self.tree, decorate))
        return fragments
