"""Compact direct-input and browse projection for readable Context scope."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    Float,
    FloatContainer,
    FormattedTextControl,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.menus import CompletionsMenu

from memcommit.context_targeting.tui.range_selection import (
    ContextRangeSelectionState,
)
from memcommit.context_targeting.tui.reach import render_context_reach
from memcommit.adapters.interfaces.console.text import safe_terminal_text
from memcommit.adapters.interfaces.tui.components.exact_name import (
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.adapters.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceMoveResult,
)
from memcommit.adapters.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.interfaces.tui.core.theme import focused_control_style
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    source_display_text,
)


ScopeChanged = Callable[[str], None]
ScopeStatus = Callable[[str], None]
ScopeLocked = Callable[[], bool]


def _noop(_message: str) -> None:
    return None


class CompactReadableScopeControl:
    """One-line exact Context fast path with a transient multi-select tree.

    The writable name is a draft only while it is being edited. Browse owns the
    richer process-local Profile/multiple selection, so commas in legitimate
    Context names never become an implicit parsing grammar.
    """

    def __init__(
        self,
        names: Sequence[str],
        *,
        current_name: str,
        initial_targets: Sequence[str],
        include_descendants: bool,
        follow_embeds: bool,
        annotations: Mapping[str, SourceDisplayValue] | None = None,
        input_name: str = "compact-readable-scope-context",
        on_change: ScopeChanged = _noop,
        on_status: ScopeStatus = _noop,
        locked: ScopeLocked = lambda: False,
    ) -> None:
        catalog = tuple(names)
        selected = tuple(dict.fromkeys(initial_targets))
        if (
            not catalog
            or len(set(catalog)) != len(catalog)
            or any(not isinstance(name, str) or not name for name in catalog)
        ):
            raise ValueError("Compact scope requires a distinct Context catalog.")
        if (
            current_name not in catalog
            or not selected
            or any(name not in catalog for name in selected)
        ):
            raise ValueError("Compact scope targets are outside the Context catalog.")
        if not callable(on_change) or not callable(on_status) or not callable(locked):
            raise TypeError("Compact scope callbacks must be callable.")

        self.catalog = catalog
        self.current_name = current_name
        self.annotations = dict(annotations or {})
        if set(self.annotations) - set(catalog):
            raise ValueError("Compact scope annotations are outside the catalog.")
        self.on_change = on_change
        self.on_status = on_status
        self.locked = locked
        self.browser_open = False
        self._direct_dirty = False
        self._programmatic_edit = False

        self.range = ContextRangeSelectionState.create(
            catalog,
            current_name=current_name,
            initial_target=selected[0],
            multiple=True,
            include_descendants=include_descendants,
        )
        self.range.selection.replace(selected)
        # Browse promises the complete frozen readable catalog. Start expanded
        # so opening it never hides an eligible child behind a second gesture.
        self.range.toggle_expand_all()
        self.embed_choice = HorizontalChoiceState(
            (
                HorizontalChoiceOption("EXCLUDE", "EXCLUDE"),
                HorizontalChoiceOption("FOLLOW", "FOLLOW"),
            ),
            selected_uid="FOLLOW" if follow_embeds else "EXCLUDE",
        )

        initial_direct = selected[-1]
        completer = WordCompleter(
            catalog,
            meta_dict=self._completion_metadata(),
            sentence=True,
            match_middle=True,
        )
        self.name = ExactNameInputControl.create(
            ExactNameFieldView(
                value=initial_direct,
                label="CONTEXT",
                detail="Enter one exact readable Context or use Browse.",
                validate=self._validate_context_name,
                value_label="Context name",
            ),
            input_name=input_name,
            prompt="› ",
            completer=completer,
            complete_while_typing=True,
            width=Dimension(min=18, preferred=44, max=64),
            dont_extend_width=True,
        )
        self.name.input.buffer.on_text_changed += self._direct_text_changed

        self.browse_control = FormattedTextControl(
            self._render_browse,
            focusable=True,
            show_cursor=False,
        )
        self.range_control = FormattedTextControl(
            self._render_range,
            focusable=True,
            show_cursor=False,
        )
        self.embed_control = FormattedTextControl(
            self._render_embeds,
            focusable=True,
            show_cursor=False,
        )
        self.tree_control = FormattedTextControl(
            self._render_tree,
            focusable=True,
            show_cursor=False,
        )
        self.state_control = FormattedTextControl(
            self._render_state,
            focusable=False,
            show_cursor=False,
        )

        context_row = VSplit(
            [
                Window(
                    FormattedTextControl(" CONTEXT · "),
                    width=Dimension.exact(11),
                    dont_extend_height=True,
                ),
                self.name.input,
                Window(
                    self.browse_control,
                    width=Dimension.exact(12),
                    dont_extend_height=True,
                ),
                Window(
                    self.state_control,
                    # This final column absorbs the host frame's remaining
                    # width. Capping it would also cap FloatContainer itself,
                    # leaving a stray early right border in wide terminals.
                    width=Dimension(min=16, preferred=34, weight=1),
                    dont_extend_height=True,
                ),
            ],
            height=Dimension.exact(1),
        )
        tree_detail = ConditionalContainer(
            HSplit(
                [
                    Window(
                        FormattedTextControl(
                            "  CONTEXTS · PROFILE OR CHECKED READABLE CONTEXTS"
                        ),
                        height=Dimension.exact(1),
                        dont_extend_height=True,
                    ),
                    Window(
                        self.tree_control,
                        wrap_lines=False,
                        right_margins=[ScrollbarMargin(display_arrows=True)],
                        height=Dimension.exact(min(9, len(catalog) + 1)),
                        dont_extend_height=True,
                    ),
                ]
            ),
            filter=Condition(lambda: self.browser_open),
        )
        body = HSplit(
            [
                context_row,
                Window(self.range_control, height=Dimension.exact(1)),
                Window(self.embed_control, height=Dimension.exact(1)),
                tree_detail,
            ]
        )
        self.container = FloatContainer(
            content=body,
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(
                        max_height=8,
                        scroll_offset=1,
                        display_arrows=True,
                    ),
                )
            ],
        )

    @property
    def input(self):
        return self.name.input

    @property
    def effective_names(self) -> tuple[str, ...]:
        return self.range.effective_names

    @property
    def follow_embeds(self) -> bool:
        return self.embed_choice.selected_uid == "FOLLOW"

    @property
    def include_descendants(self) -> bool:
        return self.range.reach.include_descendants

    @property
    def profile_selected(self) -> bool:
        return self.range.profile_selected

    def _completion_metadata(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for name in self.catalog:
            values: list[str] = []
            if name == self.current_name:
                values.append("CURRENT")
            annotation = source_display_text(self.annotations.get(name))
            if annotation:
                values.append(annotation)
            result[name] = " · ".join(values)
        return result

    def _validate_context_name(self, candidate: str) -> None:
        if candidate not in self.catalog:
            raise ValueError(
                f"Context {safe_terminal_text(candidate)!r} is not readable in this scope."
            )

    def _direct_text_changed(self, _buffer) -> None:
        if self._programmatic_edit:
            return
        self._direct_dirty = True
        self.on_change("CONTEXT DRAFT CHANGED · PRESS ENTER TO USE IT")

    def _set_direct_text(self, value: str) -> None:
        self._programmatic_edit = True
        try:
            self.name.set_text(value)
        finally:
            self._programmatic_edit = False
        self._direct_dirty = False

    def _locked(self) -> bool:
        if not self.locked():
            return False
        self.on_status("Wait for the current operation before changing scope.")
        return True

    def commit_direct(self) -> bool:
        """Replace Profile/multiple selection with one validated exact name."""

        if self._locked():
            return False
        candidate = self.name.validate_candidate()
        before = self.range.effective_names
        self.range.selection.replace((candidate,))
        self.range.exclusions.clear()
        self.range.profile_cursor = False
        self.range.tree.selected_name = candidate
        self._direct_dirty = False
        changed = self.range.effective_names != before
        if changed:
            self.on_change("CONTEXT CHANGED · PRESS ENTER TO RUN")
        else:
            self.on_status(f"CONTEXT CONFIRMED · {candidate}")
        return True

    def request_scope(self) -> tuple[tuple[str, ...], bool]:
        """Freeze the complete visible checked set for one execution request."""

        if self._direct_dirty:
            if not self.commit_direct():
                raise ValueError("Scope is locked by the current operation.")
        names = self.range.effective_names
        if not names:
            raise ValueError("Select at least one readable Context.")
        # effective_names has already projected reach and exclusions. A caller
        # must not ask storage to expand descendants a second time.
        return names, False

    def summary(self) -> str:
        effective_count = len(self.range.effective_names)
        if self.range.profile_selected:
            targets = f"PROFILE · {effective_count} CONTEXTS"
        else:
            roots = len(self.range.explicit_context_names)
            targets = (
                self.range.explicit_context_names[0]
                if roots == 1 and effective_count == 1
                else f"{roots} ROOTS · {effective_count} CONTEXTS"
            )
        reach = (
            "INCLUDE DESCENDANTS"
            if self.range.reach.include_descendants
            else "THIS CONTEXT ONLY"
        )
        embeds = "FOLLOW EMBEDS" if self.follow_embeds else "EXCLUDE EMBEDS"
        return f"{targets} · {reach} · {embeds}"

    def _render_state(self) -> StyleAndTextTuples:
        if self._direct_dirty:
            candidate = self.name.text.strip()
            label = "PRESS ENTER TO USE" if candidate else "TYPE CONTEXT"
            return [("class:source-state", safe_terminal_text(label))]
        if self.range.profile_selected:
            label = f"PROFILE · {len(self.range.effective_names)} CONTEXTS"
            return [("class:source-access", label)]
        roots = self.range.explicit_context_names
        if len(roots) != 1 or len(self.range.effective_names) != 1:
            label = f"{len(roots)} ROOTS · {len(self.range.effective_names)} CONTEXTS"
            return [("class:source-access", label)]
        values = ["CURRENT"] if roots[0] == self.current_name else []
        annotation = source_display_text(self.annotations.get(roots[0]))
        if annotation:
            values.append(annotation)
        return [("class:source-access", " · ".join(values) or "READABLE")]

    def _render_browse(self) -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(self.browse_control)
        return [
            (
                focused_control_style(focused=focused, selected=self.browser_open),
                "[ BROWSE ]",
            )
        ]

    def _render_range(self) -> StyleAndTextTuples:
        return render_context_reach(
            self.range.reach,
            title="RANGE",
            focused=get_app().layout.has_focus(self.range_control),
        )

    def _render_embeds(self) -> StyleAndTextTuples:
        return render_horizontal_choice(
            self.embed_choice,
            title="EMBEDS",
            focused=get_app().layout.has_focus(self.embed_control),
        )

    def _render_tree(self) -> StyleAndTextTuples:
        return self.range.render_rows(
            focused=get_app().layout.has_focus(self.tree_control),
            annotations=self.annotations,
        )

    def open_browser(self, event: KeyPressEvent) -> SurfaceActionResult:
        if self._locked():
            return "HANDLED"
        buffer = self.name.input.buffer
        if buffer.complete_state is not None:
            buffer.cancel_completion()
        self.browser_open = True
        event.app.layout.focus(self.tree_control)
        self.on_status("BROWSE · ENTER OR SPACE CHECKS · ESC CLOSES")
        return "HANDLED"

    def close_browser(self, event: KeyPressEvent) -> bool:
        if not self.browser_open:
            return False
        self.browser_open = False
        event.app.layout.focus(self.browse_control)
        self.on_status("SCOPE STAGED · PRESS ENTER TO RUN")
        return True

    def _move_direct(
        self,
        _event: KeyPressEvent,
        delta: int,
    ) -> SurfaceMoveResult:
        buffer = self.name.input.buffer
        if buffer.complete_state is None:
            return "BOUNDARY"
        if delta > 0:
            buffer.complete_next()
        else:
            buffer.complete_previous()
        return "CONSUMED"

    def _activate_direct(self, _event: KeyPressEvent) -> SurfaceActionResult:
        buffer = self.name.input.buffer
        if (
            buffer.complete_state is not None
            and buffer.complete_state.current_completion is not None
        ):
            buffer.apply_completion(buffer.complete_state.current_completion)
        try:
            self.commit_direct()
        except (OSError, TypeError, ValueError) as error:
            self.on_status(str(error))
        return "HANDLED"

    def _move_tree(
        self,
        _event: KeyPressEvent,
        delta: int,
    ) -> SurfaceMoveResult:
        return "MOVED" if self.range.move_cursor(delta) else "BOUNDARY"

    def _toggle_tree(self, _event: KeyPressEvent) -> SurfaceActionResult:
        if self._locked():
            return "HANDLED"
        if self.range.toggle_cursor():
            explicit = self.range.explicit_context_names
            self._set_direct_text(explicit[-1] if explicit else self.current_name)
            self.on_change("CONTEXT RANGE CHANGED · PRESS ENTER TO RUN")
        return "HANDLED"

    def _move_range(
        self,
        _event: KeyPressEvent,
        delta: int,
    ) -> SurfaceMoveResult:
        if self._locked():
            return "CONSUMED"
        if not self.range.move_reach(delta):
            return "BOUNDARY"
        self.on_change("CONTEXT RANGE CHANGED · PRESS ENTER TO RUN")
        return "MOVED"

    def _toggle_range(self, event: KeyPressEvent) -> SurfaceActionResult:
        self._move_range(event, -1 if self.include_descendants else 1)
        return "HANDLED"

    def _move_embeds(
        self,
        _event: KeyPressEvent,
        delta: int,
    ) -> SurfaceMoveResult:
        if self._locked():
            return "CONSUMED"
        if not self.embed_choice.move(delta):
            return "BOUNDARY"
        self.on_change("EMBED SCOPE CHANGED · PRESS ENTER TO RUN")
        return "MOVED"

    def _toggle_embeds(self, event: KeyPressEvent) -> SurfaceActionResult:
        self._move_embeds(event, -1 if self.follow_embeds else 1)
        return "HANDLED"

    def normal_surfaces(self, *, uid_prefix: str = "scope") -> tuple[FocusSurface, ...]:
        return (
            FocusSurface(
                f"{uid_prefix}:context",
                self.name.input,
                move_vertical=self._move_direct,
                activate=self._activate_direct,
            ),
            FocusSurface(
                f"{uid_prefix}:browse",
                self.browse_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=self.open_browser,
            ),
            FocusSurface(
                f"{uid_prefix}:range",
                self.range_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=self._toggle_range,
            ),
            FocusSurface(
                f"{uid_prefix}:embeds",
                self.embed_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=self._toggle_embeds,
            ),
        )

    def browser_surface(self, *, uid_prefix: str = "scope") -> FocusSurface:
        return FocusSurface(
            f"{uid_prefix}:tree",
            self.tree_control,
            move_vertical=self._move_tree,
            activate=self._toggle_tree,
        )

    def bind_keybindings(self, bindings: KeyBindings) -> None:
        """Bind keys whose behavior belongs entirely to the shared control."""

        @bindings.add("left", filter=has_focus(self.tree_control), eager=True)
        def _tree_left(event: KeyPressEvent) -> None:
            self.range.collapse_cursor()
            event.app.invalidate()

        @bindings.add("right", filter=has_focus(self.tree_control), eager=True)
        def _tree_right(event: KeyPressEvent) -> None:
            self.range.expand_cursor()
            event.app.invalidate()

        @bindings.add("a", filter=has_focus(self.tree_control), eager=True)
        @bindings.add("A", filter=has_focus(self.tree_control), eager=True)
        def _tree_expand_all(event: KeyPressEvent) -> None:
            self.range.toggle_expand_all()
            event.app.invalidate()

        @bindings.add(" ", filter=has_focus(self.tree_control), eager=True)
        def _tree_space(event: KeyPressEvent) -> None:
            self._toggle_tree(event)
            event.app.invalidate()

        @bindings.add("left", filter=has_focus(self.range_control), eager=True)
        def _range_left(event: KeyPressEvent) -> None:
            self._move_range(event, -1)
            event.app.invalidate()

        @bindings.add("right", filter=has_focus(self.range_control), eager=True)
        def _range_right(event: KeyPressEvent) -> None:
            self._move_range(event, 1)
            event.app.invalidate()

        @bindings.add(" ", filter=has_focus(self.range_control), eager=True)
        def _range_space(event: KeyPressEvent) -> None:
            self._toggle_range(event)
            event.app.invalidate()

        @bindings.add("left", filter=has_focus(self.embed_control), eager=True)
        def _embeds_left(event: KeyPressEvent) -> None:
            self._move_embeds(event, -1)
            event.app.invalidate()

        @bindings.add("right", filter=has_focus(self.embed_control), eager=True)
        def _embeds_right(event: KeyPressEvent) -> None:
            self._move_embeds(event, 1)
            event.app.invalidate()

        @bindings.add(" ", filter=has_focus(self.embed_control), eager=True)
        def _embeds_space(event: KeyPressEvent) -> None:
            self._toggle_embeds(event)
            event.app.invalidate()


__all__ = ["CompactReadableScopeControl"]
