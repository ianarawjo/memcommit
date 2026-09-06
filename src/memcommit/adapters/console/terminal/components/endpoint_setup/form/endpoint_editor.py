"""Edit one endpoint's Context, source kind, reach, and selected Memory."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from prompt_toolkit.application import get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    VSplit,
    Window,
)
from prompt_toolkit.widgets import TextArea

from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.reach import (
    ContextReachState,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.name_draft import (
    ContextNameDraftState,
    infer_context_parent,
)
from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.memory_focus import (
    EndpointMemoryFocusController,
    MemoryProjectionLoader,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.model import (
    EndpointSetupRole,
    EndpointSetupSpec,
    EndpointSetupValue,
)
from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    focused_control_style,
)
from memcommit.adapters.console.terminal.components.selection import (
    choice_marker,
    choice_visual_state,
)
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator
from memcommit.source_projection.presentation import source_display_text


def completion_metadata(role: EndpointSetupRole) -> dict[str, str]:
    annotations = dict(role.annotations)
    result: dict[str, str] = {}
    for name in role.names:
        if name not in role.selectable_names:
            continue
        values: list[str] = []
        if name == role.current_context:
            values.append("CURRENT")
        annotation = source_display_text(annotations.get(name))
        if annotation:
            values.append(annotation)
        result[name] = " · ".join(values)
    return result


class EndpointEditor:
    """Own one persistent input row while the screen coordinates peer rows."""

    def __init__(
        self,
        spec: EndpointSetupSpec,
        role: EndpointSetupRole,
        *,
        selected_mode_uid: Callable[[], str],
        memory_loader: MemoryProjectionLoader | None,
        on_input_changed: Callable[[str], None],
    ) -> None:
        self.spec = spec
        self.role = role
        self.uid = role.uid
        self.selected_mode_uid = selected_mode_uid
        self.on_input_changed = on_input_changed
        self.updating_input = False
        self.inline_input: TextArea | None = None
        self.selector: ContextSelectorControl | None = None
        self.source_type: HorizontalChoiceState | None = None
        self.source_type_control: FormattedTextControl | None = None
        self.browse_control: FormattedTextControl | None = None
        self.reach_control: FormattedTextControl | None = None
        self.memory_control: FormattedTextControl | None = None
        if role.allow_inline_memory:
            self.source_type = HorizontalChoiceState(
                (
                    HorizontalChoiceOption(
                        "CONTEXT", "CONTEXT", "Use the selected Context frame."
                    ),
                    HorizontalChoiceOption(
                        "STORED_MEMORY",
                        "STORED MEMORY",
                        "Use one exact Memory from its owning Context.",
                    ),
                    HorizontalChoiceOption(
                        "INLINE_MEMORY",
                        "INLINE MEMORY",
                        "Use exact process-local text without a Source Context.",
                    ),
                ),
                selected_uid="CONTEXT",
            )
        initial = (
            role.initial_new_name
            if role.allow_new and role.prefer_new
            else role.selected_name
        )
        candidates = (
            ()
            if role.new_parent_locator
            else tuple(name for name in role.names if name in role.selectable_names)
        )
        catalog_candidates = (
            role.names
            if role.new_parent_locator
            else tuple(name for name in role.names if name in role.selectable_names)
        )
        completer = WordCompleter(
            candidates,
            meta_dict=completion_metadata(role),
            sentence=True,
            match_middle=True,
        )
        input_control = ExactNameInputControl.create(
            ExactNameFieldView(
                value=initial,
                label="MEMORY LOCATOR" if role.memory_required else "CONTEXT",
                detail=(
                    "Enter an owner Context, UID prefix for that owner, or CONTEXT:UID."
                    if role.memory_required
                    else "Enter one exact existing or operation-valid new Context name."
                ),
                value_label=(
                    "Memory owner or locator"
                    if role.memory_required
                    else "Context name"
                ),
            ),
            input_name=f"endpoint-form-{role.uid.casefold()}",
            prompt="› ",
            completer=completer,
            complete_while_typing=True,
            width=(
                Dimension(min=18, preferred=56, max=64)
                if role.memory_required
                else Dimension(min=18, preferred=42, max=52)
            ),
            dont_extend_width=True,
        )
        self.name_control = input_control
        self.input = input_control.input
        if role.allow_inline_memory:
            self.inline_input = TextArea(
                text="",
                multiline=False,
                prompt="› ",
                focusable=True,
                focus_on_click=True,
                wrap_lines=False,
                width=Dimension(min=18, preferred=74, max=92),
                height=Dimension.exact(1),
                dont_extend_width=True,
                name=f"endpoint-form-{role.uid.casefold()}-inline-memory",
            )
        if catalog_candidates:
            selected = (
                role.selected_name
                if role.new_parent_locator
                else initial
                if initial in role.selectable_names
                else catalog_candidates[0]
            )
            selector = ContextSelectorControl(
                ContextSelectorView(
                    names=catalog_candidates,
                    selected=(selected,),
                    label=f"{role.label} · ALL ALLOWED",
                    current_context=role.current_context,
                    annotations=tuple(
                        (name, annotation)
                        for name, annotation in role.annotations
                        if name in catalog_candidates
                    ),
                ),
                height=min(8, max(3, len(catalog_candidates))),
            )
            # This transient view promises the complete frozen role catalog,
            # so lexical branches start expanded instead of hiding candidates.
            selector.toggle_expand_all()
            self.selector = selector

        self.reach = (
            ContextReachState.create(include_descendants=role.include_descendants)
            if role.allow_descendants
            else None
        )
        self.required_memory_owner = role.selected_name
        self.memory_focus = (
            EndpointMemoryFocusController(
                role.uid,
                selected_context=self.selected_memory_context,
                loader=memory_loader,
                selected_memory_uid=role.selected_memory_uid,
                required=role.memory_required,
            )
            if role.allow_memory_focus
            else None
        )
        self.new_name_draft = (
            ContextNameDraftState(
                exact_name=self.input.text,
                parent_name=infer_context_parent(
                    self.input.text, role.names, fallback=role.selected_name
                )
                if role.new_parent_locator
                else None,
            )
            if role.new_parent_locator or role.new_name_suggester is not None
            else None
        )
        self.input.buffer.on_text_changed += self.record_role_text_changed

    def selected_memory_context(self) -> str:
        return (
            self.required_memory_owner
            if self.role.memory_required
            else self.input.text.strip()
        )

    def set_role_text(self, value: str) -> None:
        """Synchronize the field without claiming a direct person edit."""
        self.updating_input = True
        try:
            self.name_control.set_text(value)
        finally:
            self.updating_input = False

    def record_role_text_changed(self, _buffer) -> None:
        if self.memory_focus is not None:
            self.memory_focus.clear()
        if self.new_name_draft is not None and not self.updating_input:
            self.new_name_draft.record_direct_edit(self.input.text)
        self.on_input_changed(self.uid)

    def set_source_type(self, source_type: str) -> bool:
        changed = self.source_type.choose(source_type)
        self.memory_focus.required = source_type == "STORED_MEMORY"
        return changed

    def move_source_type(self, delta: int) -> bool:
        changed = self.source_type.move(delta)
        # Keyboard and decoded-command edits must update the same requirement.
        self.set_source_type(self.source_type.selected_uid)
        return changed

    def label(self) -> str:
        return self.spec.role_label(self.selected_mode_uid(), self.uid)

    def reconcile_mode(self) -> None:
        if self.memory_focus is not None and not self.role_allows_memory_focus():
            self.memory_focus.clear()

    def confirm_input(self) -> None:
        if self.effective_source_type() == "INLINE_MEMORY":
            self.checked_inline_content()
        elif self.role.memory_required:
            self.synchronize_required_memory_input()
        else:
            self.resolve_role()

    def checked_inline_content(self) -> str:
        content = self.inline_input.text
        if not content.strip():
            raise ValueError(f"{self.label()} needs inline Memory text.")
        return content

    def set_descendants(self, include_descendants: bool) -> bool:
        """Return whether broadening this role invalidated its exact Memory."""
        self.reach.move(1 if include_descendants else -1)
        if self.reach.include_descendants and self.memory_focus is not None:
            return self.memory_focus.clear()
        return False

    def catalog_initial_name(self) -> str:
        return (
            self.new_name_draft.parent_name
            if self.role.new_parent_locator
            else self.selected_memory_context()
        )

    def select_catalog_name(self, name: str) -> str:
        """Apply a browser choice through the same stale-selection clearing path."""
        if self.role.new_parent_locator:
            draft = self.new_name_draft
            self.set_role_text(draft.choose_parent(name))
            return (
                "Parent selected; edited exact name preserved." if draft.edited else ""
            )
        if self.role.memory_required:
            self.required_memory_owner = name
        self.set_role_text(name)
        return ""

    def refresh_name_suggestion(self, values: Mapping[str, str]) -> None:
        """Inherit an operation suggestion only while the name remains untouched."""
        role = self.role
        if role.new_name_suggester is None:
            return
        candidate = role.new_name_suggester(values)
        parent = (
            infer_context_parent(candidate, role.names, fallback=role.selected_name)
            if role.new_parent_locator
            else None
        )
        inherited = self.new_name_draft.inherit_suggestion(
            candidate, parent_name=parent
        )
        if self.input.text != inherited:
            self.set_role_text(inherited)

    def prepare_memory_selection(self) -> None:
        if self.reach is not None and self.reach.include_descendants:
            self.memory_focus.clear()
            raise ValueError("Focused Memory requires THIS CONTEXT ONLY.")
        if self.role.memory_required:
            context_name, _memory_uid = self.synchronize_required_memory_input()
        else:
            context_name, create = self.resolve_role()
            if create:
                raise ValueError("A new Context cannot select an existing Memory.")
        self.memory_focus.prepare_context(context_name)
        self.memory_focus.state()

    def select_memory(self) -> str | None:
        if self.role.memory_preview_only:
            raise ValueError("Read-only Memory evidence cannot change an endpoint.")
        selected = self.memory_focus.choose()
        if self.role.memory_required:
            if selected is None:
                raise RuntimeError("A required Memory chooser returned no Memory.")
            owner = self.required_memory_owner
            # Field synchronization clears old Memory state. Restore the exact
            # selection only after its canonical owner-qualified locator is shown.
            self.set_role_text(self.required_memory_locator_text(selected))
            self.memory_focus.select_exact(owner, selected)
        return selected

    def role_is_active(self) -> bool:
        return self.uid in self.spec.active_role_uids(self.selected_mode_uid())

    def role_allows_descendants(self) -> bool:
        return self.spec.role_allows_descendants(self.selected_mode_uid(), self.uid)

    def role_allows_memory_focus(self) -> bool:
        return self.spec.role_allows_memory_focus(self.selected_mode_uid(), self.uid)

    def role_allows_inline_memory(self) -> bool:
        return self.spec.role_allows_inline_memory(self.selected_mode_uid(), self.uid)

    def effective_source_type(self) -> str:
        state = self.source_type
        if state is None:
            return "CONTEXT"
        selected = state.selected_uid
        if selected == "INLINE_MEMORY" and (not self.role_allows_inline_memory()):
            return "CONTEXT"
        if selected == "STORED_MEMORY" and (not self.role_allows_memory_focus()):
            return "CONTEXT"
        return selected

    def source_type_visible(self) -> bool:
        return self.source_type is not None and (
            self.role_allows_memory_focus() or self.role_allows_inline_memory()
        )

    def role_primary_input(self) -> TextArea:
        return (
            self.inline_input
            if self.effective_source_type() == "INLINE_MEMORY"
            else self.input
        )

    def role_uses_context_name(self) -> bool:
        return self.effective_source_type() != "INLINE_MEMORY"

    def role_uses_context_range(self) -> bool:
        return self.effective_source_type() == "CONTEXT"

    def role_uses_stored_memory(self) -> bool:
        return self.effective_source_type() == "STORED_MEMORY"

    def required_memory_locator_text(self, memory_uid: str | None) -> str:
        owner = self.required_memory_owner
        return owner if memory_uid is None else f"{owner}:{memory_uid}"

    def required_memory_input_is_canonical(self) -> bool:
        memory_uid = self.memory_focus.selected_memory_uid
        return self.input.text.strip() == self.required_memory_locator_text(memory_uid)

    def synchronize_required_memory_input(self) -> tuple[str, str | None]:
        """Resolve an owner, owner-qualified UID, or UID under the shown owner.

        The retained owner is explicit process-local state. A bare UID is
        resolved only inside that owner; it never broadens into a scan of
        granted or unrelated Contexts. The canonical field then makes the
        coordinate visible as ``CONTEXT:FULL_UID``.
        """

        role = self.role
        candidate = self.input.text.strip()
        if not candidate:
            raise ValueError(
                f"{self.spec.role_label(self.selected_mode_uid(), self.uid)} needs an owner Context or Memory locator."
            )
        if candidate in role.selectable_names:
            self.required_memory_owner = candidate
            self.set_role_text(candidate)
            self.memory_focus.clear()
            selector = self.selector
            if selector is not None:
                selector.select_name(candidate)
            return candidate, None

        locator = parse_direct_memory_locator(candidate)
        owner = locator.context_locator or self.required_memory_owner
        if owner not in role.selectable_names:
            raise ValueError(
                f"{self.spec.role_label(self.selected_mode_uid(), self.uid)} owner Context '{owner}' is unavailable."
            )
        memory_uid = self.memory_focus.resolve_selector(owner, locator.memory_selector)
        self.required_memory_owner = owner
        # Updating the field clears stale Memory state through the ordinary
        # text-change path; reselect only after the canonical locator is shown.
        self.set_role_text(f"{owner}:{memory_uid}")
        self.memory_focus.select_exact(owner, memory_uid)
        selector = self.selector
        if selector is not None:
            selector.select_name(owner)
        return owner, memory_uid

    def resolve_role(self) -> tuple[str, bool]:
        role = self.role
        candidate = self.input.text.strip()
        if not candidate:
            raise ValueError(
                f"{self.spec.role_label(self.selected_mode_uid(), self.uid)} needs a Context name."
            )
        if role.memory_required:
            if not self.required_memory_input_is_canonical():
                raise ValueError(
                    f"{self.spec.role_label(self.selected_mode_uid(), self.uid)} locator changed; press Enter to resolve it."
                )
            return self.required_memory_owner, False
        if role.new_parent_locator:
            if role.new_name_validator is not None:
                role.new_name_validator(candidate)
            return candidate, True
        if candidate in role.selectable_names:
            return candidate, False
        if not role.allow_new:
            raise ValueError(
                f"{self.spec.role_label(self.selected_mode_uid(), self.uid)} requires an existing readable Context."
            )
        if role.new_name_validator is not None:
            role.new_name_validator(candidate)
        return candidate, True

    def role_row_focused(self) -> bool:
        controls: list[object] = [self.input]
        if self.inline_input is not None:
            controls.append(self.inline_input)
        if self.browse_control is not None:
            controls.append(self.browse_control)
        if self.reach_control is not None:
            controls.append(self.reach_control)
        if self.memory_control is not None:
            controls.append(self.memory_control)
        return any(get_app().layout.has_focus(control) for control in controls)

    def render_role_label(self) -> StyleAndTextTuples:
        focused = self.role_row_focused()
        label = self.spec.role_label(self.selected_mode_uid(), self.uid)
        if self.source_type_visible():
            label = {
                "CONTEXT": f"{self.uid} · SOURCE · CONTEXT",
                "STORED_MEMORY": f"{self.uid} · SOURCE · MEMORY OWNER",
                "INLINE_MEMORY": f"{self.uid} · SOURCE · INLINE MEMORY",
            }[self.effective_source_type()]
        return [
            (
                focused_control_style(focused=focused),
                f"{'›' if focused else ' '} {safe_terminal_text(label)}",
            )
        ]

    def render_role_state(self) -> StyleAndTextTuples:
        role = self.role
        if self.effective_source_type() == "INLINE_MEMORY":
            label = (
                "PROCESS LOCAL · INLINE MEMORY"
                if self.inline_input.text.strip()
                else "TYPE INLINE MEMORY"
            )
            return [("class:source-state", label)]
        candidate = self.input.text.strip()
        if role.memory_required:
            if not self.required_memory_input_is_canonical():
                return [("class:source-state", "PRESS ENTER TO RESOLVE")]
            candidate = self.required_memory_owner
        if not candidate:
            if role.allow_new:
                label = (
                    "CHOOSE EMPTY OR ENTER NEW NAME"
                    if self.browse_control is not None
                    else "ENTER NEW NAME"
                )
            else:
                label = "TYPE CONTEXT"
            style = "class:source-state"
        elif role.new_parent_locator:
            label = "NEW · CREATE ON START"
            style = "class:source-state"
        elif candidate in role.selectable_names:
            values = []
            if role.allow_new:
                values.append(role.existing_label)
            if candidate == role.current_context:
                values.append("CURRENT")
            annotation = source_display_text(dict(role.annotations).get(candidate))
            if annotation:
                values.append(annotation)
            label = " · ".join(values)
            style = "class:source-access"
        elif role.allow_new:
            label = "NEW · CREATE ON START"
            style = "class:source-state"
        else:
            completion_state = self.input.buffer.complete_state
            match_count = (
                len(completion_state.completions) if completion_state is not None else 0
            )
            label = f"{match_count} MATCHES" if match_count else "UNAVAILABLE"
            style = "class:source-state"
        return [(style, safe_terminal_text(label))]

    def render_source_type(self) -> StyleAndTextTuples:
        return render_horizontal_choice(
            self.source_type,
            title=f"{self.uid} · SOURCE TYPE",
            focused=get_app().layout.has_focus(self.source_type_control),
            inline_boxed=True,
        )

    def render_reach(self) -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(self.reach_control)
        selected = self.reach.include_descendants
        visual = choice_visual_state(
            cursor=True,
            selected=selected,
            focused=focused,
        )
        return [
            (visual.border_style, "["),
            (
                visual.content_style,
                f" {choice_marker(selected=selected)} INCLUDE DESCENDANTS ",
            ),
            (visual.border_style, "]"),
        ]

    def render_browse(self) -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(self.browse_control)
        role = self.role
        label = (
            "BROWSE CONTEXT"
            if role.memory_required
            else "BROWSE PARENT"
            if role.new_parent_locator
            else "BROWSE"
        )
        return [
            (
                focused_control_style(focused=focused, selected=focused),
                f"[ {label} ]",
            )
        ]

    def render_memory(self) -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(self.memory_control)
        role = self.role
        descendants = (
            self.reach.include_descendants if self.reach is not None else False
        )
        selected_memory = self.memory_focus.selected_memory_uid
        value = (
            "READ ONLY"
            if role.memory_preview_only
            else "WHOLE SUBTREE"
            if descendants
            else selected_memory[:8]
            if selected_memory is not None
            else "CHOOSE MEMORY"
            if self.source_type is not None and self.role_uses_stored_memory()
            else role.memory_unselected_label
        )
        label = (
            "CHOOSE MEMORY"
            if role.memory_required
            else f"MEMORY · {safe_terminal_text(value)}"
        )
        return [
            (
                focused_control_style(
                    focused=focused,
                    selected=selected_memory is not None and not descendants,
                ),
                f"[ {label} ]",
            )
        ]

    def role_peer_controls(self) -> tuple[object, ...]:
        """Return the visible left-to-right controls for one endpoint row."""

        values: list[object] = [self.role_primary_input()]
        if self.browse_control is not None and self.role_uses_context_name():
            values.append(self.browse_control)
        if (
            self.reach_control is not None
            and self.role_allows_descendants()
            and self.role_uses_context_range()
        ):
            values.append(self.reach_control)
        if (
            self.memory_control is not None
            and self.role_allows_memory_focus()
            and (self.source_type is None or self.role_uses_stored_memory())
        ):
            values.append(self.memory_control)
        return tuple(values)

    def collect_value(self) -> EndpointSetupValue:
        role = self.role
        source_type = self.effective_source_type()
        if source_type == "INLINE_MEMORY":
            return EndpointSetupValue(
                self.uid, "", inline_memory_content=self.checked_inline_content()
            )
        context_name, create = self.resolve_role()
        descendants = (
            self.reach.include_descendants
            if not create
            and self.reach is not None
            and self.role_allows_descendants()
            and source_type == "CONTEXT"
            else False
        )
        memory_uid = (
            self.memory_focus.selected_memory_uid
            if not create
            and not descendants
            and self.memory_focus is not None
            and self.role_allows_memory_focus()
            and not role.memory_preview_only
            and (self.source_type is None or source_type == "STORED_MEMORY")
            else None
        )
        if source_type == "STORED_MEMORY" and memory_uid is None:
            raise ValueError(
                f"{self.spec.role_label(self.selected_mode_uid(), self.uid)} requires one exact stored Memory."
            )
        if role.memory_required and memory_uid is None:
            raise ValueError(
                f"{self.spec.role_label(self.selected_mode_uid(), self.uid)} requires one exact Memory."
            )
        return EndpointSetupValue(
            self.uid,
            context_name,
            include_descendants=descendants,
            memory_uid=memory_uid,
            create=create,
        )

    def apply_value(
        self, value: EndpointSetupValue, resolved_memory_uid: str | None
    ) -> None:
        role = self.role
        source_type_state = self.source_type
        if value.inline_memory_content is not None:
            if source_type_state is None:
                raise ValueError(f"{role.label} cannot accept inline Memory input.")
            self.set_source_type("INLINE_MEMORY")
            self.inline_input.text = value.inline_memory_content
            self.inline_input.buffer.cursor_position = len(value.inline_memory_content)
            return
        if source_type_state is not None:
            self.set_source_type(
                "STORED_MEMORY" if value.memory_uid is not None else "CONTEXT"
            )
        if role.memory_required:
            self.required_memory_owner = value.context_name
            self.set_role_text(self.required_memory_locator_text(resolved_memory_uid))
        else:
            self.set_role_text(value.context_name)
        name_draft = self.new_name_draft
        if name_draft is not None:
            name_draft.record_direct_edit(value.context_name)
        selector = self.selector
        if selector is not None:
            if not value.create and value.context_name in selector.selectable:
                selector.select_name(value.context_name)
            elif role.new_parent_locator:
                parent = infer_context_parent(
                    value.context_name,
                    role.names,
                    fallback=role.selected_name,
                )
                selector.select_name(parent)
                if name_draft is not None:
                    name_draft.parent_name = parent
        if self.reach is not None:
            self.reach = ContextReachState.create(
                include_descendants=value.include_descendants
            )
        if self.memory_focus is not None:
            self.memory_focus.select_exact(value.context_name, resolved_memory_uid)

    def build_rows(self, label_width: int) -> list:
        role = self.role
        role_rows = []
        if self.source_type is not None:
            self.source_type_control = FormattedTextControl(
                self.render_source_type,
                focusable=True,
                show_cursor=False,
            )
            role_rows.append(
                ConditionalContainer(
                    Window(
                        self.source_type_control,
                        height=Dimension.exact(1),
                        dont_extend_height=True,
                        wrap_lines=False,
                    ),
                    filter=Condition(
                        lambda: self.role_is_active() and self.source_type_visible()
                    ),
                )
            )
        self.label_control = FormattedTextControl(
            self.render_role_label, show_cursor=False
        )
        self.state_control = FormattedTextControl(
            self.render_role_state, show_cursor=False
        )
        if self.selector is not None:
            self.browse_control = FormattedTextControl(
                self.render_browse,
                focusable=True,
                show_cursor=False,
            )
        if role.allow_descendants:
            self.reach_control = FormattedTextControl(
                self.render_reach,
                focusable=True,
                show_cursor=False,
            )
        if role.allow_memory_focus:
            self.memory_control = FormattedTextControl(
                self.render_memory,
                focusable=True,
                show_cursor=False,
            )

        columns = [
            Window(
                self.label_control,
                width=Dimension.exact(label_width),
                dont_extend_height=True,
            )
        ]
        if self.inline_input is not None:
            columns.extend(
                [
                    ConditionalContainer(
                        self.input,
                        filter=Condition(lambda: self.role_uses_context_name()),
                    ),
                    ConditionalContainer(
                        self.inline_input,
                        filter=Condition(lambda: not self.role_uses_context_name()),
                    ),
                ]
            )
        else:
            columns.append(self.input)
        if self.browse_control is not None:
            columns.append(
                ConditionalContainer(
                    Window(
                        self.browse_control,
                        width=Dimension.exact(
                            19
                            if role.memory_required
                            else 18
                            if role.new_parent_locator
                            else 11
                        ),
                        dont_extend_height=True,
                    ),
                    filter=Condition(lambda: self.role_uses_context_name()),
                )
            )
        columns.extend(
            [
                Window(
                    self.state_control,
                    width=Dimension(min=0, preferred=31, max=34),
                    dont_extend_height=True,
                )
            ]
        )
        if self.reach_control is not None:
            columns.append(
                ConditionalContainer(
                    Window(
                        self.reach_control,
                        width=Dimension.exact(27),
                        dont_extend_height=True,
                    ),
                    filter=Condition(
                        lambda: self.role_allows_descendants()
                        and self.role_uses_context_range()
                    ),
                )
            )
        if self.memory_control is not None:
            columns.append(
                ConditionalContainer(
                    Window(
                        self.memory_control,
                        width=Dimension.exact(19 if role.memory_required else 27),
                        dont_extend_height=True,
                    ),
                    filter=Condition(
                        lambda: self.role_allows_memory_focus()
                        and (self.source_type is None or self.role_uses_stored_memory())
                    ),
                )
            )
        role_rows.append(
            ConditionalContainer(
                VSplit(columns, height=Dimension.exact(1)),
                filter=Condition(self.role_is_active),
            )
        )

        return role_rows
