"""
CLI command tests — run each command through Typer's CliRunner so we exercise
the full user-facing path (argument parsing, error messages, exit codes).

All tests use the `isolated_store` fixture from conftest.py to avoid touching
the real ~/.mem directory.
"""
import shlex

import click
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.main import get_command
from typer.testing import CliRunner

import memcommit.commands.help_inventory as help_inventory
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.branch_dialog import BranchCreationReceipt
from memcommit.commands.help_inventory import CommandEntry, run_help_selector
from memcommit.store import MemoryStore

runner = CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def invoke(*args):
    """Invoke the CLI with the given arguments and return the result."""
    return runner.invoke(app, list(args))


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------

class TestHelp:
    @staticmethod
    def selector_entries():
        return [
            CommandEntry(
                name=name,
                annotation=None,
                description=f"{name} description",
                command=object(),
                forms=(f"mem {name}", f"mem {name} VALUE"),
            )
            for name in ("alpha", "beta", "gamma")
        ]

    def test_lists_commands_with_exception_annotations_and_descriptions(self):
        result = invoke("help")

        assert result.exit_code == 0
        assert "mem command inventory" in result.output
        assert "implemented" not in result.output
        assert "Browse saved" not in result.output
        assert "start a new" not in result.output
        lines = result.output.splitlines()
        assert any(
            line.startswith("impact ")
            and "no Context changes" in line
            for line in lines
        )
        assert any(
            line.startswith("update ")
            and "local target" in line
            and "no shared publication" in line
            for line in lines
        )
        list_row = next(line for line in lines if line.startswith("list "))
        ls_row = next(line for line in lines if line.startswith("ls "))
        assert list_row.split(" - ", 1)[1] == ls_row.split(" - ", 1)[1]
        assert "interactive Context browser" in list_row
        assert "print child Contexts and direct items" in list_row
        assert any(
            line.startswith("checkout ")
            and "Alias for switch" in line
            and "including its picker" in line
            and "alias for branch" in line
            for line in lines
        )
        assert not any(line.startswith("integrate ") for line in lines)
        assert any(line.startswith("config (legacy) ") for line in lines)
        assert any(line.startswith("switch ") for line in lines)
        assert any(line.startswith("share ") for line in lines)
        assert any(line.startswith("help ") for line in lines)
        assert "bare → TUI" not in result.output
        assert any(
            line.startswith("atomize ")
            and "issue-scoped directional meld" in line
            for line in lines
        )
        assert any(
            line.startswith("contexts ")
            and "readable cross-Profile Context views" in line
            for line in lines
        )
        assert any(
            line.startswith("reference ")
            and "identity metadata rather than copying" in line
            for line in lines
        )
        assert any(
            line.startswith("forget ")
            and "keep/edit/delete decision" in line
            for line in lines
        )

    def test_integrate_is_not_a_public_command(self):
        result = invoke("integrate", "new information")

        assert result.exit_code == 2
        assert "No such command 'integrate'" in result.stderr

    def test_group_boxes_use_the_complete_help_viewport(self):
        assert help_inventory._help_group_width(240) == 239
        assert help_inventory._help_group_width(80) == 79
        assert help_inventory._help_group_width(20) == 36

    def test_information_box_is_full_width_and_only_in_by_kind(self):
        fragments = help_inventory._help_information_box_fragments(
            width=100,
            by_kind=True,
        )
        rendered = "".join(text for _style, text in fragments)
        lines = rendered.splitlines()
        prose = " ".join(line.strip("│ ") for line in lines)

        assert lines[0].startswith("┌ CORE CONCEPTS ")
        assert any(line.startswith("├ COMMON KEYS ") for line in lines)
        assert all(len(line) == 100 for line in lines)
        assert "MEMORY" in rendered
        assert "An atomic unit of information" in rendered
        assert "without direct ownership" in prose
        assert "read or query a Context" in prose
        assert "run permitted operations" in prose
        assert "created for each applied operation" in prose
        assert "recorded per affected Context" in prose
        assert "Esc / Backspace" in rendered
        assert "Q" not in rendered
        assert help_inventory._help_information_box_fragments(
            width=100,
            by_kind=False,
        ) == []

    def test_each_core_concept_can_own_focus_without_an_action(self):
        for concept_index, (label, _description) in enumerate(
            help_inventory.HELP_CORE_CONCEPTS
        ):
            fragments = help_inventory._help_information_box_fragments(
                width=100,
                by_kind=True,
                focused_concept_index=concept_index,
                focused=True,
            )

            assert any(
                style == "class:selected" and label in text
                for style, text in fragments
            )
            assert sum(
                style == "[SetCursorPosition]" for style, _text in fragments
            ) == 1
            assert any(
                style == "class:help-guide.border.focused" and "┏" in text
                for style, text in fragments
            )

    def test_concepts_join_the_vertical_path_before_the_first_command(self):
        with create_pipe_input() as pipe_input:
            pipe_input.send_text(
                "\x1b[A\r\x1b[C\x1b[Dh"
                + "\x1b[A" * (len(help_inventory.HELP_CORE_CONCEPTS) - 1)
                + "\x1b[B" * len(help_inventory.HELP_CORE_CONCEPTS)
                + "\r\r"
            )
            selected = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem alpha"

    def test_by_kind_preserves_workflow_order_while_a_z_sorts_names(self):
        assert (
            help_inventory.HELP_CATEGORY_BY_COMMAND["atomize"]
            == "ANALYZE & TRANSFORM"
        )
        assert help_inventory.HELP_CATEGORY_BY_COMMAND["reference"] == "MEMORIES"
        names = (
            "clear", "branch", "status", "delete", "add", "reference",
            "show", "switch", "contexts", "edit", "remove",
        )
        entries = [
            CommandEntry(
                name=name,
                annotation=None,
                description=name,
                command=object(),
                forms=(f"mem {name}",),
            )
            for name in reversed(names)
        ]

        by_kind = help_inventory._ordered_help_entries(entries, by_kind=True)
        a_z = help_inventory._ordered_help_entries(entries, by_kind=False)

        assert [entry.name for entry in by_kind] == [
            "status", "contexts", "show", "switch", "branch",
            "add", "reference", "edit", "remove", "delete", "clear",
        ]
        assert [entry.name for entry in a_z] == sorted(names, key=str.casefold)

    def test_help_kind_box_contains_multiple_commands_and_expanded_forms(self):
        entries = [
            (
                0,
                CommandEntry(
                    name="explain",
                    annotation=None,
                    description=(
                        "Explain a sufficiently long operation description without "
                        "letting its meaning disappear beyond the terminal edge."
                    ),
                    command=object(),
                    forms=(
                        "mem explain [memory] --context [context] "
                        "(inspect one explicit target)",
                    ),
                ),
            ),
            (
                1,
                CommandEntry(
                    name="find",
                    annotation=None,
                    description="Find one relevant record.",
                    command=object(),
                    forms=("mem find [query]",),
                ),
            ),
        ]

        fragments = help_inventory._help_group_fragments(
            entries,
            title="SEARCH & EXPLAIN",
            width=52,
            focused=True,
            selected_index=0,
            expanded_index=0,
            selected_form=0,
        )
        rendered = "".join(text for _style, text in fragments)
        lines = rendered.splitlines()

        assert lines[0].startswith("┏ SEARCH & EXPLAIN ")
        assert lines[-1] == "┗" + "━" * 50 + "┛"
        assert all(len(line) == 52 for line in lines)
        assert rendered.count("┏") == 1
        assert rendered.count("┛") == 1
        explain_line = next(line for line in lines if "▾ mem explain" in line)
        assert "Explain a sufficiently" in explain_line
        assert "▸ mem find     Find one relevant record." in rendered
        assert "terminal edge." in rendered
        assert "FORM 1 · mem explain" in rendered
        find_line = next(
            index for index, line in enumerate(lines) if "▸ mem find" in line
        )
        assert lines[find_line - 1].strip("┃ ")
        assert any(style == "[SetCursorPosition]" for style, _text in fragments)
        assert any(style == "class:selected" for style, _text in fragments)

    def test_lists_commands_alphabetically(self):
        result = invoke("help")

        assert result.exit_code == 0
        command_names = [
            line.split(maxsplit=1)[0]
            for line in result.output.splitlines()
            if " - " in line
        ]
        assert command_names == sorted(command_names, key=str.casefold)

    def test_meld_help_distinguishes_atomic_and_context_entry_points(self):
        atomize = invoke("atomize", "--help")
        meld = invoke("meld", "--help")

        assert atomize.exit_code == 0
        atomize_help = " ".join(atomize.output.split())
        assert "--evaluate ISSUE" in atomize_help
        assert "issue-scoped directional" in atomize_help
        assert "informally, atomic" in atomize_help

        assert meld.exit_code == 0
        meld_help = " ".join(meld.output.split())
        assert "two equal-authority Contexts" in meld_help
        assert "current empty Context" in meld_help
        assert "--atomic" not in meld_help
        assert "--into" in meld_help
        assert "authoritative BASELINE" in meld_help

        forms = help_inventory.COMMAND_FORMS["meld"]
        assert "mem meld (enter the interactive Meld session launcher)" in forms
        assert (
            "mem meld [context1] [context2] "
            "(symmetric into current empty Context)"
        ) in forms
        assert (
            "mem meld [incoming_context] --into [baseline_context] (directional)"
            in forms
        )
        assert (
            "mem meld --into [baseline_context] (current Context is incoming)"
            in forms
        )
        assert (
            "mem meld --from [incoming_context] (current Context is baseline)"
            in forms
        )
        result_form = next(
            form for form in forms if "--to [result_context]" in form
        )
        assert help_inventory._selectable_form_line(result_form) == (
            "mem meld [context1] [context2] --to [result_context]"
        )

    def test_forms_name_editable_values_by_semantic_role(self):
        assert help_inventory.COMMAND_FORMS["add"][0].startswith(
            'mem add "[memory]"'
        )
        assert help_inventory.COMMAND_FORMS["edit"][0].startswith(
            'mem edit [memory] "[new_content]"'
        )
        assert help_inventory.COMMAND_FORMS["rename"][0] == (
            "mem rename [existing_context] [new_context]"
        )
        assert help_inventory.COMMAND_FORMS["remove"][0].startswith(
            "mem remove [item]"
        )

    def test_forms_include_meaningful_bare_entry_routes(self):
        assert help_inventory.COMMAND_FORMS["update"][0] == (
            "mem update (enter the interactive Update session launcher)"
        )
        assert help_inventory.COMMAND_FORMS["checkpoint"][0] == (
            "mem checkpoint (save without a message)"
        )
        assert help_inventory.COMMAND_FORMS["translate"][0] == (
            "mem translate "
            "(show/save a default-English view of the current Context)"
        )
        assert help_inventory.COMMAND_FORMS["init-study"][:2] == (
            "mem init-study (edit or generate a Study Profile name)",
            "mem init-study [profile_name] (use an explicit Study Profile name)",
        )
        assert help_inventory.COMMAND_FORMS["checkout"][0] == (
            "mem checkout (enter the interactive Context picker; switch alias)"
        )
        assert help_inventory.COMMAND_FORMS["checkout"][3] == (
            "mem checkout -b [new_context] (branch-and-checkout)"
        )
        assert help_inventory.COMMAND_FORMS["init"][0].startswith("mem init (")
        assert help_inventory.COMMAND_FORMS["branch"][0].startswith("mem branch (")

    def test_interactive_help_names_the_entry_surface(self):
        session_launchers = ("atomize", "compare", "ground", "meld", "sever")
        root = get_command(app)
        context = click.Context(root)
        for command_name in session_launchers:
            command = root.get_command(context, command_name)

            assert command is not None
            sessions_option = next(
                parameter
                for parameter in command.params
                if isinstance(parameter, click.Option)
                and "--sessions" in parameter.opts
            )
            assert sessions_option.help == (
                f"Enter the interactive {command_name.title()} session launcher"
            )

        all_forms = tuple(
            form
            for forms in help_inventory.COMMAND_FORMS.values()
            for form in forms
        )
        assert not any("browse saved work or start" in form for form in all_forms)
        assert not any("browse saved Grounds or start" in form for form in all_forms)

    def test_every_visible_command_has_explicitly_audited_forms(self):
        root = get_command(app)
        context = click.Context(root)
        visible = {
            name
            for name in root.list_commands(context)
            if (command := root.get_command(context, name)) is not None
            and not command.hidden
        }

        assert set(help_inventory.COMMAND_FORMS) == visible

    def test_every_advertised_form_is_accepted_by_the_registered_parser(self):
        root = get_command(app)

        def parse_without_invoking(
            command,
            command_name: str,
            argv: list[str],
            *,
            parent: click.Context | None = None,
        ) -> None:
            context = command.make_context(command_name, argv, parent=parent)
            try:
                if not isinstance(command, click.Group):
                    return
                remaining = [*context.protected_args, *context.args]
                if not remaining:
                    return
                child_name, child, child_argv = command.resolve_command(
                    context,
                    remaining,
                )
                assert child_name is not None
                assert child is not None
                parse_without_invoking(
                    child,
                    child_name,
                    child_argv,
                    parent=context,
                )
            finally:
                context.close()

        samples = {
            "[campaign]": "ambiguity",
            "[kind]": "compare",
            "[method]": "paragraphs",
            "[permission]": "READ",
            "[provider]": "codex_chatgpt",
        }
        for command_name, forms in help_inventory.COMMAND_FORMS.items():
            for form in forms:
                command_line = help_inventory._selectable_form_line(form)
                assert shlex.split(command_line)[:2] == ["mem", command_name], (
                    f"{command_name} owns a form for another command: "
                    f"{command_line}"
                )
                for placeholder, sample in samples.items():
                    command_line = command_line.replace(placeholder, sample)
                argv = shlex.split(command_line)[1:]

                try:
                    parse_without_invoking(root, "mem", argv)
                except click.ClickException as error:
                    raise AssertionError(
                        f"{command_name} advertises an unparseable form: "
                        f"{command_line}\n{error.format_message()}"
                    ) from error

    def test_meaningful_bare_callbacks_have_a_bare_form(self):
        root = get_command(app)
        context = click.Context(root)
        semantic_usage_errors = {"add", "edit", "impact"}

        for command_name in root.list_commands(context):
            command = root.get_command(context, command_name)
            if command is None or command.hidden:
                continue
            if isinstance(command, click.Group):
                meaningful_bare = command.invoke_without_command
            else:
                required_arguments = [
                    parameter
                    for parameter in command.params
                    if isinstance(parameter, click.Argument) and parameter.required
                ]
                meaningful_bare = (
                    not required_arguments
                    and command_name not in semantic_usage_errors
                )
            if not meaningful_bare:
                continue

            selectable = {
                help_inventory._selectable_form_line(form)
                for form in help_inventory.COMMAND_FORMS[command_name]
            }
            assert f"mem {command_name}" in selectable

    def test_find_history_form_uses_the_temporal_query_contract(self):
        forms = help_inventory.COMMAND_FORMS["find"]

        assert not any("--history" in form for form in forms)
        assert any('mem find "[temporal_query]"' in form for form in forms)

    def test_find_forms_expose_independent_multi_root_scope_axes(self):
        forms = help_inventory.COMMAND_FORMS["find"]

        assert any(
            "--context [context1] --context [context2] --descendants" in form
            for form in forms
        )
        assert any("--context-only --follow-embeds" in form for form in forms)
        assert any("--descendants --exclude-embeds" in form for form in forms)
        assert any(
            "--direct" in form and "compatibility shorthand" in form
            for form in forms
        )

    def test_free_text_placeholders_include_shell_quotes(self):
        assert help_inventory._selectable_form_line(
            help_inventory.COMMAND_FORMS["add"][0]
        ) == 'mem add "[memory]"'
        assert help_inventory._selectable_form_line(
            help_inventory.COMMAND_FORMS["find"][1]
        ) == 'mem find "[query]"'
        request_form = next(
            form
            for form in help_inventory.COMMAND_FORMS["ground"]
            if "--request" in form
        )
        assert help_inventory._selectable_form_line(request_form) == (
            'mem ground --request "[request]"'
        )

    def test_selector_first_enter_opens_forms_and_second_returns_first_form(self):
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("\x1b[B\r\r")
            selected = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem beta"

    def test_selector_up_reaches_view_choice_then_down_returns_to_list(self):
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("\x1b[A\x1b[C\x1b[B\r\r")
            selected = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )
        assert selected is not None
        assert selected.command_line == "mem alpha"

        with create_pipe_input() as pipe_input:
            pipe_input.send_text("q")
            cancelled = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )
        assert cancelled is None

    def test_help_selector_uses_shared_focused_frame_for_inventory_view(
        self,
        monkeypatch,
    ):
        bound: list[str] = []
        original = help_inventory.bind_focused_frame_style

        def record(frame, *, is_focused):
            bound.append(frame.title)
            return original(frame, is_focused=is_focused)

        monkeypatch.setattr(help_inventory, "bind_focused_frame_style", record)
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("q")
            result = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert result is None
        assert bound == ["INVENTORY VIEW"]

    def test_selector_tab_switches_category_and_a_z_views(self):
        entries = [
            CommandEntry(
                name=name,
                annotation=None,
                description=f"{name} description",
                command=object(),
                forms=(f"mem {name}",),
            )
            for name in ("add", "branch", "find")
        ]
        with create_pipe_input() as pipe_input:
            # BY KIND starts at branch (Contexts); Down reaches add (Memories).
            # Tab focuses VIEW, Right switches to A-Z while retaining add, and
            # Tab returns to the list for the normal two-stage selection.
            pipe_input.send_text("\x1b[B\t\x1b[C\t\r\r")
            selected = run_help_selector(
                entries,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem add"

    def test_selector_right_expands_left_collapses_and_enter_enters_forms(self):
        with create_pipe_input() as pipe_input:
            # One Right expands directly onto FORM 1. Two Lefts return to the
            # command and collapse it; Right then expands onto FORM 1 again.
            pipe_input.send_text("\x1b[C\x1b[D\x1b[D\x1b[C\r")
            selected = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem alpha"

        with create_pipe_input() as pipe_input:
            pipe_input.send_text("\x1b[C\x1b[B\r")
            second_form = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )
        assert second_form is not None
        assert second_form.command_line == "mem alpha VALUE"

    def test_selector_second_enter_returns_placeholder_form_for_shell_editing(self):
        entry = CommandEntry(
            name="switch",
            annotation=None,
            description="Switch Contexts.",
            command=object(),
            forms=help_inventory.COMMAND_FORMS["switch"],
        )
        with create_pipe_input() as pipe_input:
            # First Enter opens FORM 1, Down reaches FORM 2, and the second
            # Enter returns the template rather than invoking ``mem switch``.
            pipe_input.send_text("\r\x1b[B\r")
            selected = run_help_selector(
                [entry],
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem switch [context]"

    def test_explore_mode_keeps_forms_inside_help_until_h_hides_it(self):
        actions: list[tuple[str, str | None]] = []
        with create_pipe_input() as pipe_input:
            # The second Enter would return a shell template in SELECT mode.
            # EXPLORE keeps the session open, permits further navigation, and
            # returns when H toggles the visible Help inventory off.
            pipe_input.send_text("\r\r\x1b[B\rh")
            selected = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
                mode="EXPLORE",
                on_explore_action=lambda action, command: actions.append(
                    (action, command)
                ),
            )

        assert selected is None
        assert actions[:2] == [("EXPAND", "alpha"), ("FORM", "alpha")]
        assert ("FORM", "alpha") in actions
        assert actions[-1] == ("HIDE", None)
        assert not any(action == "DETAIL" for action, _command in actions)

    def test_selector_reuses_shared_held_arrow_acceleration(self, monkeypatch):
        class FiveStepAccelerator:
            def move(self, direction, *, app, move_one):
                assert direction == 1
                for _ in range(5):
                    move_one(direction)
                    app.invalidate()

            def reset(self):
                pass

        monkeypatch.setattr(
            help_inventory,
            "NavigationAccelerator",
            FiveStepAccelerator,
        )
        entries = [
            CommandEntry(
                name=f"command-{index}",
                annotation=None,
                description="Description.",
                command=object(),
                forms=(f"mem command-{index}",),
            )
            for index in range(8)
        ]
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("\x1b[B\r\r")
            selected = run_help_selector(
                entries,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem command-5"

    def test_enter_opens_command_help_without_running_command(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            help_inventory,
            "_interactive_terminal",
            lambda: True,
        )
        monkeypatch.setattr(
            help_inventory,
            "run_help_selector",
            lambda entries: help_inventory.HelpSelection(
                command_name="impact",
                command_line="mem impact",
                show_help=True,
            ),
        )

        result = invoke("help")

        assert result.exit_code == 0
        assert "Command: mem impact" in result.output
        assert "Usage: mem impact" in result.output
        assert "no Context changes" in result.output



# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

class TestInit:
    def test_bare_init_edits_a_fresh_suggestion_and_switches(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "new-context")
        observed = {}

        def choose(view):
            observed["view"] = view
            return view.value

        monkeypatch.setattr("memcommit.commands.init.choose_context_name", choose)

        result = invoke("init")

        assert result.exit_code == 0
        assert observed["view"].value == "new-context-2"
        assert observed["view"].label == "NEW CONTEXT NAME"
        assert observed["view"].state == "NOT CREATED"
        assert MemoryStore().current_context_name() == "new-context-2"

    def test_bare_init_cancel_preserves_current(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "main")
        monkeypatch.setattr(
            "memcommit.commands.init.choose_context_name",
            lambda view: None,
        )

        result = invoke("init")

        assert result.exit_code == 0
        assert "cancelled" in result.output
        assert MemoryStore().list_context_names() == ["main"]
        assert MemoryStore().current_context_name() == "main"

    def test_bare_init_parents_uses_the_same_name_editor(
        self,
        isolated_store,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "memcommit.commands.init.choose_context_name",
            lambda view: "project/work",
        )

        result = invoke("init", "--parents")

        assert result.exit_code == 0
        assert MemoryStore().list_context_names() == ["project", "project/work"]
        assert MemoryStore().current_context_name() == "project/work"

    def test_bare_init_requires_a_terminal_without_an_explicit_name(
        self,
        isolated_store,
    ):
        result = invoke("init")

        assert result.exit_code == 1
        assert "requires a terminal" in result.stderr
        assert MemoryStore().list_context_names() == []

    def test_creates_context_and_switches(self, isolated_store):
        result = invoke("init", "myctx")
        assert result.exit_code == 0
        assert "Initialized context 'myctx'" in result.output

        store = MemoryStore()
        assert store.context_exists("myctx")
        assert store.current_context_name() == "myctx"

    def test_fails_if_context_already_exists(self, isolated_store):
        invoke("init", "dup")
        result = invoke("init", "dup")
        assert result.exit_code == 1
        assert "already exists" in result.stderr

    def test_creates_initial_checkpoint(self, isolated_store):
        invoke("init", "ckpt-test")
        store = MemoryStore()
        cps = store.list_checkpoints("ckpt-test")
        assert len(cps) == 1
        assert cps[0]["command"] == "init"


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

class TestAdd:
    def test_adds_memory_to_current_context(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("add", "Remember this fact")
        assert result.exit_code == 0
        assert "Remember this fact" in result.output

        store = MemoryStore()
        ctx = store.load_current()
        contents = [m.content for m in ctx.memories.values()]
        assert "Remember this fact" in contents

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("add", "orphan memory")
        assert result.exit_code == 1

    def test_creates_checkpoint_after_add(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "some info")
        store = MemoryStore()
        cps = store.list_checkpoints("ctx")
        commands = [c["command"] for c in cps]
        assert "add" in commands


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestList:
    def test_lists_memory_ids_with_atomic_contents(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "fact one")
        invoke("add", "fact two")

        store = MemoryStore()
        uids = list(store.load_current().memories)
        result = invoke("list")

        assert result.exit_code == 0
        assert all(uid[:8] in result.output for uid in uids)
        assert "fact one" in result.output
        assert "fact two" in result.output

    def test_empty_context_shows_no_items(self, isolated_store):
        invoke("init", "empty")
        result = invoke("list")
        assert result.exit_code == 0
        assert "no items" in result.output

    def test_list_explicit_context_name(self, isolated_store):
        invoke("init", "alpha")
        invoke("add", "alpha fact")
        alpha_uid = next(iter(MemoryStore().load_current().memories))
        invoke("init", "beta")  # switches current to beta
        result = invoke("list", "alpha")
        assert result.exit_code == 0
        assert alpha_uid[:8] in result.output
        assert "alpha fact" in result.output

    def test_ls_and_list_have_identical_output(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "listed through either command")
        result = invoke("list")
        alias_result = invoke("ls")
        assert alias_result.exit_code == 0
        assert alias_result.output == result.output

    def test_ls_lists_embedded_context_without_leaking_child_contents(self, isolated_store):
        invoke("init", "building-access")
        invoke("add", "The east entrance is closed until Friday.")
        invoke("init", "task-123")
        invoke("embed", "building-access", "--into", "task-123")

        result = invoke("ls")

        assert result.exit_code == 0
        assert "building-access" in result.output
        assert "The east entrance is closed until Friday." not in result.output

    def test_lists_aaa_slash_ab_context_before_aaa_memory_and_preserves_groups(
        self,
        isolated_store,
    ):
        invoke("init", "source")
        invoke("add", "Referenced atomic name.")
        source_memory_uid = next(
            iter(MemoryStore().load_current().memories)
        )
        invoke("init", "aaa/ab")
        invoke("init", "parent")
        invoke("add", "aaa")
        invoke("embed", "aaa/ab", "--into", "parent")
        invoke("reference", source_memory_uid[:8], "--from", "source")
        invoke("add", "Last atomic name.")

        store = MemoryStore()
        stored_items = list(store.load("parent").iter_items())
        assert stored_items[0].content == "aaa"
        assert stored_items[1].name == "aaa/ab"
        assert stored_items[2].target_context_name == "source"
        assert stored_items[3].content == "Last atomic name."

        result = invoke("ls", "parent")

        assert result.exit_code == 0
        lines = result.output.splitlines()
        context_index = next(
            index
            for index, line in enumerate(lines)
            if "[context " in line and line.endswith("aaa/ab  VIA EMBED")
        )
        first_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line and line.endswith("] aaa")
        )
        reference_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory ref " in line
            and "READ ONLY" in line
            and "Referenced atomic name." in line
        )
        last_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line
            and line.endswith("] Last atomic name.")
        )
        assert context_index < first_memory_index < reference_index < last_memory_index

    def test_recursive_list_descends_contexts_before_listing_memories(
        self,
        isolated_store,
    ):
        invoke("init", "grandchild")
        invoke("add", "Grandchild memory.")
        invoke("init", "child")
        invoke("add", "Child memory.")
        invoke("embed", "grandchild", "--into", "child")
        invoke("init", "parent")
        invoke("add", "Parent memory.")
        invoke("embed", "child", "--into", "parent")

        result = invoke("ls", "-R", "parent")

        assert result.exit_code == 0
        lines = result.output.splitlines()
        child_index = next(
            index
            for index, line in enumerate(lines)
            if "[context " in line and line.endswith("child  VIA EMBED")
        )
        grandchild_index = next(
            index
            for index, line in enumerate(lines)
            if "[context " in line
            and line.endswith("grandchild  VIA EMBED")
        )
        grandchild_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line
            and line.endswith("] Grandchild memory.")
        )
        child_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line
            and line.endswith("] Child memory.")
        )
        parent_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line
            and line.endswith("] Parent memory.")
        )
        assert (
            child_index
            < grandchild_index
            < grandchild_memory_index
            < child_memory_index
            < parent_memory_index
        )

    def test_recursive_list_separates_sibling_context_blocks_only(
        self,
        isolated_store,
    ):
        invoke("init", "alpha")
        invoke("add", "Alpha memory.")
        invoke("init", "beta")
        invoke("add", "Beta memory.")
        invoke("init", "parent")
        invoke("add", "Parent memory.")
        invoke("embed", "alpha", "--into", "parent")
        invoke("embed", "beta", "--into", "parent")

        recursive = invoke("ls", "-R", "parent")
        direct = invoke("ls", "parent")

        assert recursive.exit_code == 0
        assert direct.exit_code == 0
        recursive_lines = recursive.output.splitlines()
        alpha_index = next(
            index
            for index, line in enumerate(recursive_lines)
            if "[context " in line and line.endswith("alpha  VIA EMBED")
        )
        beta_index = next(
            index
            for index, line in enumerate(recursive_lines)
            if "[context " in line and line.endswith("beta  VIA EMBED")
        )
        assert recursive_lines[alpha_index - 1] == ""
        assert recursive_lines[alpha_index - 2] != ""
        assert recursive_lines[beta_index - 1] == ""
        assert recursive_lines[beta_index + 1] != ""
        assert "" not in recursive_lines[beta_index + 1 :]
        direct_lines = direct.output.splitlines()
        direct_beta_index = next(
            index
            for index, line in enumerate(direct_lines)
            if "[context " in line and line.endswith("beta  VIA EMBED")
        )
        assert direct_lines[direct_beta_index - 1].endswith("alpha  VIA EMBED")

    def test_recursive_long_option_matches_short_option(self, isolated_store):
        invoke("init", "child")
        invoke("add", "Nested memory.")
        invoke("init", "parent")
        invoke("embed", "child", "--into", "parent")

        short_result = invoke("ls", "-R", "parent")
        long_result = invoke("ls", "--recursive", "parent")
        beginner_result = invoke("ls", "--expand", "parent")
        canonical_result = invoke("list", "-R", "parent")
        canonical_beginner_result = invoke("list", "--expand", "parent")
        help_result = invoke("ls", "--help")

        assert short_result.exit_code == 0
        assert long_result.exit_code == 0
        assert beginner_result.exit_code == 0
        assert canonical_result.exit_code == 0
        assert canonical_beginner_result.exit_code == 0
        assert help_result.exit_code == 0
        assert "--expand" in help_result.output
        assert (
            short_result.output
            == long_result.output
            == beginner_result.output
            == canonical_result.output
            == canonical_beginner_result.output
        )

    def test_recursive_list_terminates_for_persisted_indirect_cycle(
        self,
        isolated_store,
    ):
        invoke("init", "cycle/a")
        invoke("init", "cycle/b")
        invoke("embed", "cycle/b", "--into", "cycle/a")
        invoke("embed", "cycle/a", "--into", "cycle/b")

        result = invoke("ls", "-R", "cycle/a")

        assert result.exit_code == 0
        assert len(result.output) < 1_000
        assert result.output.count("cycle/a") == 1
        assert result.output.count("cycle/b") == 1

    def test_recursive_list_visits_shared_context_along_each_embed_path(
        self,
        isolated_store,
    ):
        invoke("init", "graph/shared")
        invoke("add", "Shared atomic memory.")
        invoke("init", "graph/left")
        invoke("embed", "graph/shared", "--into", "graph/left")
        invoke("init", "graph/right")
        invoke("embed", "graph/shared", "--into", "graph/right")
        invoke("init", "graph/root")
        invoke("embed", "graph/left", "--into", "graph/root")
        invoke("embed", "graph/right", "--into", "graph/root")

        result = invoke("ls", "-R", "graph/root")

        assert result.exit_code == 0
        assert result.output.count("graph/shared") == 2
        assert result.output.count("Shared atomic memory.") == 2

    def test_fails_for_nonexistent_context(self, isolated_store):
        result = invoke("list", "ghost")
        assert result.exit_code == 1
        assert "not found" in result.stderr

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("list")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

class TestShow:
    def test_without_selector_shows_all_memory_contents(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "fact one")
        invoke("add", "fact two")

        result = invoke("show")

        assert result.exit_code == 0
        assert "fact one" in result.output
        assert "fact two" in result.output

    def test_shows_one_memory_by_uid_prefix(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "First line.\nSecond line.")
        invoke("add", "another memory")
        uid = next(iter(MemoryStore().load_current().memories))

        result = invoke("show", uid[:8])

        assert result.exit_code == 0
        assert uid in result.output
        assert "First line.\nSecond line." in result.output
        assert "another memory" not in result.output

    def test_shows_contents_of_explicit_context(self, isolated_store):
        invoke("init", "alpha")
        invoke("add", "alpha fact")
        invoke("init", "beta")
        invoke("add", "beta fact")

        result = invoke("show", "--context", "alpha")

        assert result.exit_code == 0
        assert "alpha fact" in result.output
        assert "beta fact" not in result.output

    def test_shows_embedded_context_by_exact_name(self, isolated_store):
        invoke("init", "child")
        invoke("add", "child-only fact")
        invoke("init", "parent")
        invoke("add", "parent-only fact")
        invoke("embed", "child", "--into", "parent")

        result = invoke("show", "child")

        assert result.exit_code == 0
        assert "Context: child" in result.output
        assert "child-only fact" in result.output
        assert "parent-only fact" not in result.output

    def test_fails_for_unknown_selector(self, isolated_store):
        invoke("init", "ctx")

        result = invoke("show", "missing")

        assert result.exit_code == 1
        assert "No direct item matching" in result.stderr

    def test_fails_for_ambiguous_uid_prefix(self, isolated_store):
        from memcommit.context import Memory as Mem

        invoke("init", "ctx")
        store = MemoryStore()
        ctx = store.load_current()
        ctx.add(Mem(uid="aaaa1111-1111-1111-1111-111111111111", content="first"))
        ctx.add(Mem(uid="aaaa2222-2222-2222-2222-222222222222", content="second"))
        store.save(ctx)

        result = invoke("show", "aaaa")

        assert result.exit_code == 1
        assert "Ambiguous selector" in result.stderr


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

class TestRemove:
    def test_removes_memory_by_uid_prefix(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "to be removed")

        store = MemoryStore()
        ctx = store.load_current()
        uid = next(iter(ctx.memories))

        result = invoke("remove", uid[:8])
        assert result.exit_code == 0
        assert "Removed" in result.output

        ctx2 = store.load_current()
        assert uid not in ctx2.memories

    def test_fails_on_nonexistent_uid(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("remove", "deadbeef")
        assert result.exit_code == 1
        assert "Error" in result.stderr

    def test_fails_on_ambiguous_prefix(self, isolated_store):
        from memcommit.context import Memory as Mem
        invoke("init", "ctx")
        # Insert two memories that share a prefix directly.
        store = MemoryStore()
        ctx = store.load_current()
        ctx.add(Mem(uid="aaaa1111-1111-1111-1111-111111111111", content="first"))
        ctx.add(Mem(uid="aaaa2222-2222-2222-2222-222222222222", content="second"))
        store.save(ctx)

        result = invoke("remove", "aaaa")
        assert result.exit_code == 1
        assert "Error" in result.stderr

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("remove", "anything")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# switch
# ---------------------------------------------------------------------------

class TestSwitch:
    def test_switches_to_existing_context(self, isolated_store):
        invoke("init", "alpha")
        invoke("init", "beta")
        result = invoke("switch", "alpha")
        assert result.exit_code == 0
        assert "Switched to context 'alpha'" in result.output

        store = MemoryStore()
        assert store.current_context_name() == "alpha"

    def test_fails_for_nonexistent_context(self, isolated_store):
        result = invoke("switch", "ghost")
        assert result.exit_code == 1
        assert "does not exist" in result.stderr

    def test_no_op_when_already_on_context(self, isolated_store):
        invoke("init", "same")
        result = invoke("switch", "same")
        assert result.exit_code == 0
        assert "Already on" in result.output


# ---------------------------------------------------------------------------
# branch
# ---------------------------------------------------------------------------

class TestBranch:
    def test_bare_branch_can_choose_a_noncurrent_local_source(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "source")
        invoke("add", "source-only")
        invoke("init", "current")
        invoke("add", "current-only")
        monkeypatch.setattr(
            "memcommit.commands.branch.choose_branch_creation",
            lambda *args, **kwargs: BranchCreationReceipt(
                source_name="source",
                target_name="experiment",
            ),
        )

        result = invoke("branch")

        assert result.exit_code == 0
        assert "Branched 'source' → 'experiment'" in result.output
        branched = MemoryStore().load("experiment")
        contents = [item.content for item in branched.memories.values()]
        assert contents == ["source-only"]
        assert MemoryStore().current_context_name() == "experiment"

    def test_bare_branch_cancel_preserves_current(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "main")
        monkeypatch.setattr(
            "memcommit.commands.branch.choose_branch_creation",
            lambda *args, **kwargs: None,
        )

        result = invoke("branch")

        assert result.exit_code == 0
        assert "cancelled" in result.output
        assert MemoryStore().list_context_names() == ["main"]
        assert MemoryStore().current_context_name() == "main"

    def test_bare_branch_can_select_a_source_when_current_is_unset(
        self,
        isolated_store,
        monkeypatch,
    ):
        store = MemoryStore()
        store.create_context(ops.init("source"))
        monkeypatch.setattr(
            "memcommit.commands.branch.choose_branch_creation",
            lambda *args, **kwargs: BranchCreationReceipt(
                source_name="source",
                target_name="feature",
            ),
        )

        result = invoke("branch")

        assert result.exit_code == 0
        assert store.context_exists("feature")
        assert store.current_context_name() == "feature"

    def test_bare_branch_refuses_an_existing_empty_target(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "source")
        invoke("add", "source-only")
        invoke("init", "empty")
        empty_uid = MemoryStore().load_direct("empty").uid
        invoke("switch", "source")
        monkeypatch.setattr(
            "memcommit.commands.branch.choose_branch_creation",
            lambda *args, **kwargs: BranchCreationReceipt(
                source_name="source",
                target_name="empty",
            ),
        )

        result = invoke("branch")

        assert result.exit_code == 1
        assert "already exists" in result.stderr
        target = MemoryStore().load_direct("empty")
        assert target.uid == empty_uid
        assert list(target.memories.values()) == []
        assert MemoryStore().current_context_name() == "source"

    def test_bare_branch_requires_a_terminal_without_an_explicit_name(
        self,
        isolated_store,
    ):
        invoke("init", "source")

        result = invoke("branch")

        assert result.exit_code == 1
        assert "requires a terminal" in result.stderr
        assert MemoryStore().list_context_names() == ["source"]

    def test_creates_branch_and_switches(self, isolated_store):
        invoke("init", "main")
        invoke("add", "shared memory")
        result = invoke("branch", "feature")
        assert result.exit_code == 0
        assert "Branched 'main' → 'feature'" in result.output

        store = MemoryStore()
        assert store.current_context_name() == "feature"
        assert store.context_exists("feature")

    def test_branch_inherits_memories(self, isolated_store):
        invoke("init", "main")
        invoke("add", "important fact")
        invoke("branch", "feature")

        store = MemoryStore()
        ctx = store.load("feature")
        contents = [m.content for m in ctx.memories.values()]
        assert "important fact" in contents

    def test_fails_if_branch_name_exists(self, isolated_store):
        invoke("init", "main")
        invoke("init", "existing")
        invoke("switch", "main")
        result = invoke("branch", "existing")
        assert result.exit_code == 1
        assert "already exists" in result.stderr

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("branch", "orphan")
        assert result.exit_code == 1

    def test_explicit_branch_explains_nonlocal_current_source(self, isolated_store):
        store = MemoryStore()
        store.create_context(ops.init("local"))
        store.set_current("local")
        store.set_current_virtual_context_if("local", "granted-campus-wiki")

        result = invoke("branch", "local/wiki-draft")

        assert result.exit_code == 1
        assert "Branch requires a local Source" in result.stderr
        assert "'granted-campus-wiki' is not in the local catalog" in result.stderr
        assert not store.context_exists("local/wiki-draft")


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

class TestMerge:
    def test_merges_memories_from_other_context(self, isolated_store):
        invoke("init", "source")
        invoke("add", "sourced fact")
        invoke("init", "target")
        result = invoke("merge", "source")
        assert result.exit_code == 0
        assert "sourced fact" in invoke("show").output

    def test_merge_reports_added_count(self, isolated_store):
        invoke("init", "src")
        invoke("add", "fact A")
        invoke("add", "fact B")
        invoke("init", "tgt")
        result = invoke("merge", "src")
        assert result.exit_code == 0
        assert "added 2 memories" in result.output

    def test_merge_nothing_new_when_already_merged(self, isolated_store):
        invoke("init", "src")
        invoke("add", "fact")
        invoke("init", "tgt")
        invoke("merge", "src")
        result = invoke("merge", "src")
        assert result.exit_code == 0
        assert "nothing new" in result.output

    def test_fails_merging_nonexistent_context(self, isolated_store):
        invoke("init", "tgt")
        result = invoke("merge", "ghost")
        assert result.exit_code == 1
        assert "does not exist" in result.stderr

    def test_fails_merging_into_itself(self, isolated_store):
        invoke("init", "self")
        result = invoke("merge", "self")
        assert result.exit_code == 1

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("merge", "anything")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# contexts
# ---------------------------------------------------------------------------

class TestContexts:
    def test_lists_all_contexts(self, isolated_store):
        invoke("init", "alpha")
        invoke("init", "beta")
        result = invoke("contexts")
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" in result.output

    def test_marks_current_context(self, isolated_store):
        invoke("init", "alpha")
        invoke("init", "beta")
        invoke("switch", "alpha")
        result = invoke("contexts")
        assert result.exit_code == 0
        # Current context has the * prefix; others don't.
        assert "* alpha" in result.output
        assert "* beta" not in result.output


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_removes_all_memories(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "gone soon")
        result = invoke("clear", "--force")
        assert result.exit_code == 0

        store = MemoryStore()
        ctx = store.load_current()
        assert ctx.memories == {}

    def test_clear_fails_with_no_current_context(self, isolated_store):
        result = invoke("clear", "--force")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_removes_context(self, isolated_store):
        invoke("init", "to-delete")
        invoke("init", "keep")
        result = invoke("delete", "to-delete", "--force")
        assert result.exit_code == 0
        assert "ledger [" in result.output

        store = MemoryStore()
        assert not store.context_exists("to-delete")
        event = store.list_context_lifecycle_events(context_name="to-delete")[0]
        assert f"ledger [{event.event_uid[:8]}]" in result.output

    def test_post_commit_cleanup_failure_reports_deletion_as_committed(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "to-delete")

        def fail_state_write(self, state):
            raise OSError("injected state cleanup failure")

        monkeypatch.setattr(MemoryStore, "_write_state", fail_state_write)

        result = invoke("delete", "to-delete", "--force")

        assert result.exit_code == 1
        assert "Deleted context 'to-delete'" in result.stderr
        assert "post-delete cleanup was incomplete" in result.stderr
        store = MemoryStore()
        assert not store.context_exists("to-delete")
        assert len(
            store.list_context_lifecycle_events(context_name="to-delete")
        ) == 1

    def test_delete_fails_for_nonexistent_context(self, isolated_store):
        result = invoke("delete", "ghost", "--force")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_shows_context_name_and_memory_count(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "fact one")
        invoke("add", "fact two")
        result = invoke("status")
        assert result.exit_code == 0
        assert "On context: ctx" in result.output
        assert "Memories 2" in result.output

    def test_shows_checkpoint_count(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "a memory")
        result = invoke("status")
        # init + add = 2 auto-checkpoints
        assert "Checkpoints 2" in result.output

    def test_shows_no_memories_message_when_empty(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("status")
        assert "no memories yet" in result.output

    def test_no_current_context_exits_cleanly(self, isolated_store):
        result = invoke("status")
        assert result.exit_code == 0  # status uses secho+return, not Exit(1)


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------

class TestLog:
    def test_shows_checkpoint_entries(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "a memory")
        result = invoke("log")
        assert result.exit_code == 0
        assert "Log for 'ctx'" in result.output
        assert "init" in result.output
        assert "add" in result.output

    def test_no_checkpoints_message_on_fresh_context(self, isolated_store):
        # Bypass the CLI to create a context with no checkpoints.
        from memcommit.store import MemoryStore
        import memcommit.ops as ops
        store = MemoryStore()
        ctx = ops.init("bare")
        store.save(ctx)          # save without AutoCheckpoint
        store.set_current("bare")

        result = invoke("log")
        assert result.exit_code == 0
        assert "No checkpoints" in result.output

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("log")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# checkpoint
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def test_saves_manual_checkpoint_with_message(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("checkpoint", "stable baseline")
        assert result.exit_code == 0
        assert "stable baseline" in result.output

        store = MemoryStore()
        cps = store.list_checkpoints("ctx")
        messages = [c.get("message", "") for c in cps]
        assert "stable baseline" in messages

    def test_saves_manual_checkpoint_without_message(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("checkpoint")
        assert result.exit_code == 0
        assert "(no message)" in result.output

    def test_manual_checkpoint_is_not_auto(self, isolated_store):
        invoke("init", "ctx")
        invoke("checkpoint", "manual one")
        store = MemoryStore()
        cps = store.list_checkpoints("ctx")
        manual = [c for c in cps if c.get("message") == "manual one"]
        assert len(manual) == 1
        assert manual[0].get("auto") is False

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("checkpoint", "orphan")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# revert
# ---------------------------------------------------------------------------

class TestRevert:
    def test_reverts_to_earlier_checkpoint(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "keep this")

        # Capture the uid of the current head checkpoint.
        store = MemoryStore()
        head_uid = store.list_checkpoints("ctx")[0]["uid"]

        invoke("add", "remove this")
        assert len(store.load_current().memories) == 2

        result = invoke("revert", head_uid[:8])
        assert result.exit_code == 0
        assert "Reverted" in result.output

        ctx = store.load_current()
        assert len(ctx.memories) == 1
        assert next(iter(ctx.memories.values())).content == "keep this"

    def test_output_includes_undo_hint(self, isolated_store):
        invoke("init", "ctx")
        store = MemoryStore()
        init_uid = store.list_checkpoints("ctx")[0]["uid"]

        result = invoke("revert", init_uid[:8])
        assert "mem revert" in result.output

    def test_fails_on_unknown_uid(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("revert", "deadbeef")
        assert result.exit_code == 1
        assert "Error" in result.stderr

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("revert", "anything")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# embed (error paths — happy path covered in integration tests)
# ---------------------------------------------------------------------------

class TestEmbed:
    def test_fails_when_child_does_not_exist(self, isolated_store):
        invoke("init", "parent")
        result = invoke("embed", "ghost", "--into", "parent")
        assert result.exit_code == 1
        assert "does not exist" in result.stderr

    def test_fails_when_parent_does_not_exist(self, isolated_store):
        invoke("init", "child")
        result = invoke("embed", "child", "--into", "ghost")
        assert result.exit_code == 1
        assert "does not exist" in result.stderr

    def test_fails_when_already_embedded(self, isolated_store):
        invoke("init", "child")
        invoke("init", "parent")
        invoke("embed", "child", "--into", "parent")
        result = invoke("embed", "child", "--into", "parent")
        assert result.exit_code == 1
        assert "already embedded" in result.stderr


# ---------------------------------------------------------------------------
# checkout (alias)
# ---------------------------------------------------------------------------

class TestCheckout:
    def test_checkout_switches_context(self, isolated_store):
        invoke("init", "alpha")
        invoke("init", "beta")
        result = invoke("checkout", "alpha")
        assert result.exit_code == 0
        assert MemoryStore().current_context_name() == "alpha"

    def test_checkout_b_creates_branch(self, isolated_store):
        invoke("init", "main")
        result = invoke("checkout", "-b", "feature")
        assert result.exit_code == 0
        assert MemoryStore().context_exists("feature")
        assert MemoryStore().current_context_name() == "feature"

    def test_checkout_b_without_a_name_uses_the_branch_picker(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "main")
        monkeypatch.setattr(
            "memcommit.commands.branch.choose_branch_creation",
            lambda *args, **kwargs: BranchCreationReceipt(
                source_name="main",
                target_name="feature",
            ),
        )

        result = invoke("checkout", "-b")

        assert result.exit_code == 0
        assert MemoryStore().context_exists("feature")
        assert MemoryStore().current_context_name() == "feature"
