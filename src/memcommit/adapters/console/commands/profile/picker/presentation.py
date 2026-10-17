"""Read-only Profile picker rendering and prompt-toolkit layout composition."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import (
    ConditionalContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.styles import Style, merge_styles

from memcommit.adapters.console.commands.profile.picker.model import (
    ProfilePickerEntry,
    ProfilePickerRow,
)
from memcommit.adapters.console.commands.profile.picker.review import (
    creation_review,
    removal_review,
    rename_review,
)
from memcommit.adapters.console.commands.profile.picker.state import ProfilePickerState
from memcommit.adapters.console.terminal.components.background_turn import (
    BackgroundExecutorTurn,
)
from memcommit.adapters.console.terminal.components.command_editor import (
    render_exact_command_review,
)
from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameFieldControl,
    ExactNameFieldView,
)
from memcommit.adapters.console.terminal.components.progress import busy_suffix
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.theme import REPORT_HEX
from memcommit.adapters.console.terminal.components.selection.rendering import render_horizontal_choice_row


def _entry_name_label(entry: ProfilePickerEntry) -> str:
    if entry.study_name is None:
        return display_escape_text(entry.name)
    if entry.study_role == "PARTICIPANT":
        role = "Participant"
    elif entry.study_role == "GRANTED_MEMORY":
        role = "Granted memory"
    else:
        raise ValueError(f"Unknown Study role: {entry.study_role!r}")
    return f"{role} · {display_escape_text(entry.name)}"


def render_profile_options(
    rows: Sequence[ProfilePickerRow],
    *,
    selected: int,
    current: str,
) -> list[tuple[str, str]]:
    """Render Study headers and Profile children as peer keyboard rows."""

    options = tuple(row.entry for row in rows if row.entry is not None)
    if selected < 0 or selected >= len(rows):
        raise ValueError("Selected profile row index is out of range.")
    name_width = min(
        max(max(len(_entry_name_label(entry)) for entry in options), 8),
        24,
    )
    fragments: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        is_selected = index == selected
        if is_selected:
            fragments.append(("[SetCursorPosition]", ""))
        pointer = "›" if is_selected else " "
        row_style = "class:selected" if is_selected else ""
        if row.kind == "STUDY":
            count_label = f"{row.profile_count} active"
            fragments.append(
                (
                    row_style or "class:study",
                    f"{pointer} STUDY {display_escape_text(row.name)} · "
                    f"{count_label} · created="
                    f"{display_escape_text(row.created_at or '')}",
                )
            )
        else:
            entry = row.entry
            assert entry is not None
            is_current = entry.name == current
            marker = "*" if is_current else " "
            action = "CURRENT" if is_current else ("USE" if is_selected else "")
            action_style = row_style or ("class:current" if is_current else "")
            project_location = (
                display_escape_text(entry.root_dir)
                if entry.root_dir
                else "(none)"
            )
            query_note = (
                " · query="
                + ",".join(
                    display_escape_text(name) for name in entry.query_source_names
                )
                if entry.query_source_names
                else (
                    f" · {entry.query_source_count} query-only"
                    if entry.query_source_count
                    else ""
                )
            )
            fragments.extend(
                [
                    (
                        row_style,
                        f"{pointer} {marker} {_entry_name_label(entry):<{name_width}}  ",
                    ),
                    (action_style, f"{action:<7}"),
                    (
                        row_style,
                        f"  Contexts {entry.context_count} owned + "
                        f"{entry.granted_context_count} granted · "
                        f"Memories {entry.memory_count} owned + "
                        f"{entry.granted_memory_count} granted"
                        f"{query_note} · location={project_location}",
                    ),
                ]
            )
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments


class ProfilePickerView:
    """Project picker and executor state without changing either one."""

    def __init__(
        self,
        state: ProfilePickerState,
        background_turn: BackgroundExecutorTurn[str],
    ) -> None:
        self.state = state
        self.background_turn = background_turn
        self.review_mode = Condition(
            lambda: state.action is not None and not background_turn.busy
        )
        self.create_mode = Condition(
            lambda: state.edit is not None
            and state.edit.kind == "CREATE_PROFILE"
            and not background_turn.busy
        )
        self.rename_mode = Condition(
            lambda: state.edit is not None
            and state.edit.kind != "CREATE_PROFILE"
            and not background_turn.busy
        )
        self.picker_mode = Condition(
            lambda: state.stage is None and not background_turn.busy
        )
        self.control = FormattedTextControl(
            text=self.render_content,
            focusable=True,
            show_cursor=False,
        )
        self.name_fields = {
            "CREATE_PROFILE": self._name_field("Profile", create=True),
            "RENAME_PROFILE": self._name_field("Profile"),
            "RENAME_STUDY": self._name_field("Study"),
        }
        self.folder_field = ExactNameFieldControl.create(
            ExactNameFieldView(value="", label="PROJECT FOLDER", state="", detail="Tab moves between fields · Enter reviews the exact command", value_label="Project folder", strip_candidate=False),
            input_name="profile-picker-project-folder", frame_style="class:profile-create-field")
        self.restoring_fields = False
        self.import_control = FormattedTextControl(
            text=lambda: self.render_setup_option(
                label="IMPORT PROJECT FILES",
                selection=self.state.import_selection,
                control=self.import_control,
            ),
            focusable=True, show_cursor=False,
        )
        self.sync_control = FormattedTextControl(
            text=lambda: self.render_setup_option(
                label="AUTO SYNC",
                selection=self.state.sync_selection,
                control=self.sync_control,
            ),
            focusable=True, show_cursor=False,
        )
        self.layout = self._layout()
        self.style = merge_styles(
            [
                MEMCOMMIT_TUI_STYLE,
                Style.from_dict(
                    {
                        "selected": "reverse bold",
                        "current": "ansigreen bold",
                        "study": "ansicyan bold",
                        "success": "ansigreen bold",
                        "error": "ansired bold",
                        "profile-create-field": f"fg:{REPORT_HEX}",
                        "profile-rename-field": f"fg:{REPORT_HEX}",
                    }
                ),
            ]
        )

    @staticmethod
    def _name_field(target: str, *, create: bool = False) -> ExactNameFieldControl:
        suffix = (
            "create" if create else ("study-rename" if target == "Study" else "rename")
        )
        return ExactNameFieldControl.create(
            ExactNameFieldView(
                value="",
                label=f"NEW {target.upper()} NAME",
                state="NOT CREATED" if create else "NEW NAME",
                detail=(
                    "Tab moves between fields · Enter reviews project setup."
                    if create
                    else f"Enter to review this exact {target} rename."
                ),
                value_label=f"{target} name",
                # Padding must never normalize an exact reviewed registry key.
                strip_candidate=False,
            ),
            input_name=f"profile-picker-{suffix}",
            frame_style="class:profile-create-field"
            if create
            else "class:profile-rename-field",
        )

    def active_name_field(self) -> ExactNameFieldControl:
        edit = self.state.edit
        assert edit is not None
        return self.name_fields[edit.kind]

    def render_setup_option(self, label, selection, control):
        return [("", f" {label:<23}")] + render_horizontal_choice_row(
            selection, focused=self.layout.has_focus(control),
        )

    def active_setup_selection(self):
        if self.layout.has_focus(self.import_control):
            return self.state.import_selection
        if self.layout.has_focus(self.sync_control):
            return self.state.sync_selection
        return None

    def focus_stage(self) -> None:
        edit = self.state.edit
        if edit is None:
            self.layout.focus(self.control)
        else:
            field = self.active_name_field()
            self.restoring_fields = True
            try:
                field.set_text(edit.value)
                if edit.kind == "CREATE_PROFILE":
                    self.folder_field.set_text(edit.root_dir or str(Path.cwd()))
            finally:
                self.restoring_fields = False
            self.layout.focus(field.input)

    def render_content(self):
        action = self.state.action
        if action is not None:
            if action.kind == "CREATE_PROFILE":
                review = creation_review(action)
            elif action.kind in {"RENAME_PROFILE", "RENAME_STUDY"}:
                review = rename_review(action)
            else:
                review = removal_review(action=action, row=self.state.current_row)
            return [("", render_exact_command_review(review))]
        if self.state.select_created and self.state.edit is not None:
            return [
                ("", "NEW PROFILE (WORKSPACE)\n\n"),
                ("", "Use the chosen folder and its subfolders as one workspace.\n"),
                ("", "Review the folder and the two options below, then create your first Profile.\n"),
                ("", "The new Profile will be selected for subsequent mem commands.\n"),
            ]
        return render_profile_options(
            self.state.rows,
            selected=self.state.index,
            current=self.state.current,
        )

    def header_text(self) -> str:
        action = self.state.action
        if self.background_turn.busy:
            assert action is not None
            target_kind = "Study" if action.kind == "REMOVE_STUDY" else "Profile"
            return f" Permanently deleting {target_kind} {busy_suffix(self.background_turn.frame)}"
        edit = self.state.edit
        if edit is not None:
            if edit.kind == "CREATE_PROFILE":
                return " Create a Profile"
            target_kind = "Study" if edit.kind == "RENAME_STUDY" else "Profile"
            return f" Rename {target_kind} " + display_escape_text(
                self.state.rows[edit.row_index].name
            )
        if action is None:
            return " Select a Profile or Study"
        if action.kind == "CREATE_PROFILE":
            return " Review exact Profile creation"
        if action.kind == "RENAME_STUDY":
            return " Review exact Study rename"
        if action.kind == "RENAME_PROFILE":
            return " Review exact Profile rename"
        return " Review irreversible deletion"

    def footer_text(self):
        if self.background_turn.busy:
            close_note = (
                " · close requested"
                if self.background_turn.close_requested
                else " · Esc/Ctrl-C closes after deletion"
            )
            return (
                " DELETING STORE AND CHECKPOINTS "
                + busy_suffix(self.background_turn.frame)
                + close_note
            )
        action = self.state.action
        if action is not None:
            if action.kind == "CREATE_PROFILE":
                return " Enter/A create Profile  Esc back"
            if action.kind in {"RENAME_PROFILE", "RENAME_STUDY"}:
                target_kind = "Study" if action.kind == "RENAME_STUDY" else "Profile"
                return f" Enter/A rename {target_kind}  Esc back"
            return (
                " Enter/A apply exact command  Esc back · IRREVERSIBLE · "
                "store and checkpoints will be deleted"
            )
        message = self.state.status
        if self.state.edit is not None:
            prefix = " Tab next  Shift-Tab previous  ←/→ choose  Space toggle  Enter review exact command  Esc back"
            if not message:
                return prefix
            message_style = (
                "class:error"
                if self.state.status_is_error
                else "class:memcommit.notification"
            )
            return [("", prefix + " · "), (message_style, message)]
        row = self.state.current_row
        action_hint = (
            "R rename  D remove Study"
            if row.kind == "STUDY"
            else "Enter use  R rename  D remove Profile"
        )
        prefix = f" ↑/↓ move  {action_hint}  "
        suffix = f"  Esc/q cancel  ·  {self.state.index + 1}/{len(self.state.rows)}"
        fragments = [
            ("", prefix),
            ("class:semantic.create", "N new Profile"),
            ("", suffix + ("\n " if message else "")),
        ]
        if message:
            message_style = (
                "class:error" if self.state.status_is_error else "class:success"
            )
            fragments.append((message_style, message))
        return fragments

    def _layout(self) -> Layout:
        header = Window(
            content=FormattedTextControl(text=self.header_text),
            height=Dimension.exact(1),
            dont_extend_height=True,
        )
        options_window = Window(
            content=self.control,
            # Absolute project paths must remain visible even for long Study rows.
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )
        footer = Window(
            content=FormattedTextControl(text=self.footer_text),
            # A completed deletion receipt must remain readable alongside the
            # navigation keys, including long Study-generated Profile names.
            height=lambda: 2 if (
                self.state.status and self.state.action is None
                and self.state.edit is None and not self.background_turn.busy
            ) else 1,
            dont_extend_height=True,
        )
        name_containers = [
            ConditionalContainer(
                content=HSplit([Window(height=1, char="─"), field.frame]),
                filter=Condition(
                    lambda kind=kind: self.state.edit is not None
                    and self.state.edit.kind == kind
                ),
            )
            for kind, field in self.name_fields.items()
        ]
        return Layout(
            container=HSplit(
                [
                    header,
                    Window(height=1, char="─"),
                    options_window,
                    *name_containers,
                    ConditionalContainer(self.folder_field.frame, filter=self.create_mode),
                    ConditionalContainer(
                        HSplit([
                            Window(height=1),
                            Window(content=self.import_control, height=1),
                            Window(content=FormattedTextControl(
                                text=" Import supported documents in this folder and its subfolders as Memories.",
                            ), height=1),
                            Window(content=self.sync_control, height=1),
                            Window(content=FormattedTextControl(
                                text=" Reflect mem changes in managed documents in this folder and its subfolders, including future Contexts.",
                            ), height=1),
                        ]), filter=self.create_mode,
                    ),
                    Window(height=1, char="─"),
                    footer,
                ]
            ),
            focused_element=self.control,
        )
