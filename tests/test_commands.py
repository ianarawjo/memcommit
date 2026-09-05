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

import memcommit.adapters.console.commands.help.command as help_inventory
import memcommit.adapters.console.commands.help.selector as help_selector
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.branch.receipt import BranchCreationReceipt
from memcommit.adapters.console.commands.help.command import (
    CommandEntry,
    run_help_selector,
)
from memcommit.persistence.store import MemoryStore

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

    def test_lists_commands_with_compact_annotations_and_descriptions(self):
        result = invoke("help")

        assert result.exit_code == 0
        assert "mem command inventory" in result.output
        assert "implemented" not in result.output
        assert "Browse saved" not in result.output
        assert "start a new" not in result.output
        lines = result.output.splitlines()
        assert any(
            line.startswith("impact ") and "without applying them" in line
            for line in lines
        )
        assert any(
            line.startswith("compare ")
            and "what they share" in line
            and "what appears only on one side" in line
            for line in lines
        )
        assert any(
            line.startswith("update ")
            and "Target Context" in line
            and "Source" in line
            and "execution decisions" in line
            for line in lines
        )
        list_row = next(line for line in lines if line.startswith("list (ls) "))
        assert not any(line.startswith("ls ") for line in lines)
        assert "List a Context's direct items" in list_row
        assert "Use -r to recursively include items" in list_row
        assert "ls is the compact alias" in list_row
        assert any(
            line.startswith("checkout ")
            and "Git-style syntax" in line
            and "with -b, create and switch" in line
            for line in lines
        )
        assert "Alias for switch" not in result.output
        assert "alias for branch" not in result.output
        assert not any(line.startswith("integrate ") for line in lines)
        assert any(line.startswith("config (legacy) ") for line in lines)
        assert any(line.startswith("switch ") for line in lines)
        assert any(line.startswith("share ") for line in lines)
        assert any(line.startswith("help ") for line in lines)
        assert "bare → TUI" not in result.output
        assert any(
            line.startswith("atomize ") and "independently reviewable Memories" in line
            for line in lines
        )
        assert any(
            line.startswith("contexts ")
            and "readable cross-Profile Context views" in line
            for line in lines
        )
        assert any(
            line.startswith("reference ") and "immutable read-only snapshot" in line
            for line in lines
        )
        assert any(
            line.startswith("forget ") and "keep/edit/delete decision" in line
            for line in lines
        )

    def test_discovery_folds_hidden_exact_spellings(self):
        root = get_command(app)
        context = click.Context(root)
        list_command = root.get_command(context, "list")
        ls_command = root.get_command(context, "ls")
        delete_command = root.get_command(context, "delete")
        remove_command = root.get_command(context, "remove")

        assert list_command is not None and not list_command.hidden
        assert ls_command is not None and ls_command.hidden
        assert delete_command is not None and not delete_command.hidden
        assert remove_command is not None and remove_command.hidden
        assert help_inventory.COMMAND_DISPLAY_ALIASES == {
            "delete": ("remove",),
            "list": ("ls",),
        }
        assert list_command.callback.__wrapped__ is ls_command.callback.__wrapped__
        assert (
            delete_command.callback.__wrapped__ is remove_command.callback.__wrapped__
        )

        root_result = invoke("--help")
        inventory_result = invoke("help")

        assert root_result.exit_code == 0
        assert "│ list " in root_result.output
        assert "│ delete " in root_result.output
        assert "ls is the" in root_result.output
        assert "compact alias" in root_result.output
        assert "│ ls " not in root_result.output
        assert "│ remove " not in root_result.output
        assert inventory_result.exit_code == 0
        assert "\ndelete (remove) " in inventory_result.output
        assert "\nremove " not in inventory_result.output

    def test_help_lists_exact_duplicates_separately_from_redundancies(self):
        root = get_command(app)
        context = click.Context(root)
        try:
            find_duplicates = root.get_command(context, "find-duplicates")
            find_redundancies = root.get_command(context, "find-redundancies")
            find_redundancy = root.get_command(context, "find-redundancy")
            entry = next(
                entry
                for entry in help_inventory.command_entries(context)
                if entry.name == "find-redundancies"
            )
        finally:
            context.close()

        assert find_duplicates is not None and not find_duplicates.hidden
        assert find_redundancies is not None and not find_redundancies.hidden
        assert find_redundancy is None
        assert (
            find_duplicates.callback.__wrapped__
            is not find_redundancies.callback.__wrapped__
        )
        assert "find-redundancies" not in help_inventory.COMMAND_DISPLAY_ALIASES
        assert entry.aliases == ()
        assert entry.operation_help.name == "find-redundancies"
        assert entry.forms[0].startswith("mem find-redundancies")
        assert all("--select" not in form for form in entry.forms)

        root_result = invoke("--help")
        inventory_result = invoke("help")
        redundancy_help = invoke("find-redundancies", "--help")

        assert root_result.exit_code == 0
        assert "│ find-duplicates " in root_result.output
        assert "│ find-redundancies " in root_result.output
        assert inventory_result.exit_code == 0
        assert redundancy_help.exit_code == 0
        assert "--select" not in redundancy_help.output
        assert "\nfind-redundancies " in inventory_result.output
        assert "\nfind-duplicates " in inventory_result.output

    def test_integrate_is_not_a_public_command(self):
        result = invoke("integrate", "new information")

        assert result.exit_code == 2
        assert "No such command 'integrate'" in result.stderr

    def test_group_boxes_use_the_complete_help_viewport(self):
        assert help_inventory._help_group_width(240) == 239
        assert help_inventory._help_group_width(80) == 79
        assert help_inventory._help_group_width(20) == 36

    def test_a_z_box_fills_spare_viewport_rows_inside_its_border(self):
        fragments = help_inventory._help_group_fragments(
            [(0, self.selector_entries()[0])],
            title="A–Z",
            width=52,
            focused=False,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
            viewport_height=8,
        )
        lines = "".join(text for _style, text in fragments).splitlines()

        assert help_inventory._help_list_viewport_height(52) == 43
        assert len(lines) == 8
        assert all(len(line) == 52 for line in lines)
        assert lines[-2] == "│" + " " * 50 + "│"
        assert lines[-1] == "└" + "─" * 50 + "┘"

    def test_focused_command_cursor_anchor_follows_the_complete_record(self):
        root = get_command(app)
        context = click.Context(root)
        try:
            entry = next(
                entry
                for entry in help_inventory.command_entries(context)
                if entry.name == "eval"
            )
        finally:
            context.close()

        fragments = help_inventory._help_group_fragments(
            [(0, entry)],
            title="SYSTEM & STUDY TOOLS",
            width=180,
            focused=True,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
        cursor_index = next(
            index
            for index, (style, _text) in enumerate(fragments)
            if style == "[SetCursorPosition]"
        )
        before_cursor = "".join(text for _style, text in fragments[:cursor_index])
        after_cursor = "".join(text for _style, text in fragments[cursor_index + 1 :])

        assert "▸ mem eval" in before_cursor
        assert "WHEN ·" in before_cursor
        assert before_cursor.endswith("\n")
        assert after_cursor.startswith("┗")

    def test_information_box_is_full_width_and_only_in_by_kind(self):
        fragments = help_inventory._help_information_box_fragments(
            width=100,
            by_kind=True,
        )
        rendered = "".join(text for _style, text in fragments)
        lines = rendered.splitlines()
        prose = " ".join(line.strip("│ ") for line in lines)

        assert lines[0].startswith("┌ CORE CONCEPTS ")
        assert any(line.startswith("├ COMMON LOCATORS ") for line in lines)
        assert any(line.startswith("├ COMMON KEYS ") for line in lines)
        assert all(len(line) == 100 for line in lines)
        assert "MEMORY" in rendered
        assert "basic record unit" in rendered
        assert "task-1/participant" in rendered
        assert "separator expresses hierarchy" in prose
        assert "descendant Contexts as one subtree" in prose
        assert "OPERATION" in rendered
        assert "reusable action" in prose
        assert any(
            style == "class:memory-object bold" and "MEMORY" in text
            for style, text in fragments
        )
        assert not any(
            style == "class:memory-object bold" and "basic record unit" in text
            for style, text in fragments
        )
        assert "without direct ownership" in prose
        assert "read or query a Context" in prose
        assert "run permitted operations" in prose
        assert "Apply results and checkpoint history" in prose
        assert "does not itself mean" not in prose
        assert "created for each applied operation" in prose
        assert "recorded per affected Context" in prose
        assert "NAME" in rendered
        assert "canonical and global, never relative" in prose
        assert "./CHILD" in rendered
        assert "../PATH" in rendered
        assert "CONTEXT:UID" in rendered
        assert ": separates the direct owner" in prose
        assert "../3:ca562047" in rendered
        assert "PgUp / PgDn" in rendered
        assert "Home / End" in rendered
        assert "Esc / Q / Ctrl-C" in rendered
        assert "Backspace" not in rendered
        assert (
            help_inventory._help_information_box_fragments(
                width=100,
                by_kind=False,
            )
            == []
        )

    def test_operation_section_heading_is_full_width_and_neutral(self):
        fragments = help_inventory._help_section_heading_fragments(
            title="OPERATIONS",
            width=100,
        )

        assert fragments == [("class:category", "OPERATIONS" + " " * 90 + "\n")]

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
                style == "class:selected" and label in text for style, text in fragments
            )
            assert (
                sum(style == "[SetCursorPosition]" for style, _text in fragments) == 1
            )
            assert any(
                style == "class:help-guide.border.focused" and "┏" in text
                for style, text in fragments
            )

    def test_locator_and_key_guidance_is_localized_without_changing_syntax(self):
        fragments = help_inventory._help_information_box_fragments(
            width=180,
            by_kind=True,
            language="KO",
        )
        rendered = "".join(text for _style, text in fragments)

        assert "COMMON LOCATORS" in rendered
        assert "CONTEXT:UID" in rendered
        assert "../3:ca562047" in rendered
        assert "직접 소유 Context와 Memory UID 또는 prefix를 구분" in rendered
        assert "PgUp / PgDn" in rendered
        assert "앞이나 뒤로 10행 이동" in rendered
        assert "Esc / Q / Ctrl-C" in rendered

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
        assert help_inventory.HELP_CATEGORY_BY_COMMAND["atomize"] == "SEMANTIC UPDATES"
        assert help_inventory.HELP_CATEGORY_BY_COMMAND["forget"] == "SEMANTIC UPDATES"
        assert (
            help_inventory.HELP_CATEGORY_BY_COMMAND["reference"]
            == "CREATE, COPY & CONNECT"
        )
        assert help_inventory.HELP_CATEGORY_BY_COMMAND["merge"] == "DIRECT CHANGES"
        assert (
            help_inventory.HELP_CATEGORY_BY_COMMAND["dedup"] == "QUALITY & RESOLUTION"
        )
        assert help_inventory.HELP_CATEGORY_BY_COMMAND["replace"] == "DIRECT CHANGES"
        names = (
            "clear",
            "branch",
            "status",
            "delete",
            "add",
            "reference",
            "show",
            "switch",
            "contexts",
            "edit",
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
            "status",
            "contexts",
            "show",
            "switch",
            "add",
            "branch",
            "reference",
            "edit",
            "delete",
            "clear",
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
        assert "mem explain ── Explain a" in explain_line
        assert "sufficiently" in rendered
        assert "long" in rendered
        assert "operation" in rendered
        assert "▸ mem find" in rendered
        assert "Find one relevant" in rendered
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

    def test_atomize_help_does_not_route_issue_resolution_into_meld(self):
        atomize = invoke("atomize", "--help")
        meld = invoke("meld", "--help")

        assert atomize.exit_code == 0
        atomize_help = " ".join(atomize.output.split())
        assert "--evaluate" not in atomize_help
        assert "issue-scoped directional" not in atomize_help
        assert "independently reviewable Memories" in atomize_help

        assert meld.exit_code == 0
        meld_help = " ".join(meld.output.split())
        assert "incorporate an incoming Context" in meld_help
        assert "separate Result" in meld_help
        assert "mem meld INCOMING BASELINE" in meld_help
        assert "mem meld PEER_A PEER_B RESULT_C" in meld_help
        assert "--atomic" not in meld_help
        assert "--into" in meld_help

        forms = help_inventory.COMMAND_FORMS["meld"]
        assert "mem meld (choose mode and endpoints for a new Meld)" in forms
        assert ("mem meld [incoming_context] [baseline_context] (directional)") in forms
        assert "mem meld [peer_a] [peer_b] [result_context] (symmetric Result)" in forms
        assert (
            "mem meld team/draft-a team/draft-b team/merged-draft "
            "(example: symmetric Result)"
        ) in forms
        assert (
            "mem meld team/proposed-changes team/current-policy "
            "(example: directional Baseline)"
        ) in forms
        assert (
            "mem meld --into [baseline_context] (current Context is incoming)" in forms
        )
        assert (
            "mem meld --from [incoming_context] (current Context is baseline)" in forms
        )
        result_form = next(form for form in forms if "--to [result_context]" in form)
        assert help_inventory._selectable_form_line(result_form) == (
            "mem meld [peer_a] [peer_b] --to [result_context]"
        )

    def test_forms_name_editable_values_by_semantic_role(self):
        assert help_inventory.COMMAND_FORMS["add"][0].startswith(
            'mem add "[memory_content]"'
        )
        assert help_inventory.COMMAND_FORMS["add"][1].startswith(
            'mem add "[memory_a]" "[memory_b]"'
        )
        assert help_inventory.COMMAND_FORMS["edit"][0].startswith(
            'mem edit [UID_or_CONTEXT:UID] "[new_content]"'
        )
        assert help_inventory.COMMAND_FORMS["rename"] == (
            "mem rename [old_context] [new_context] (review and rename a Context namespace)",
            "mem rename [old_context] [new_context] --force "
            "(skip confirmation; retain all safety checks)",
        )
        assert "rename" not in help_inventory.COMMAND_RELATED_FORMS
        assert any(
            form.startswith("mem profile rename")
            for form in help_inventory.COMMAND_FORMS["profile"]
        )

    def test_direct_memory_forms_teach_canonical_and_compatibility_locators(self):
        edit_forms = help_inventory.COMMAND_FORMS["edit"]
        embed_forms = help_inventory.COMMAND_FORMS["embed"]
        reference_forms = help_inventory.COMMAND_FORMS["reference"]

        assert any("UID_or_CONTEXT:UID" in form for form in edit_forms)
        assert any("[source_context]:[UID]" in form for form in embed_forms)
        assert any("Target defaults to current Context" in form for form in embed_forms)
        assert any("--from" in form and "compatibility" in form for form in embed_forms)
        assert any(
            "--from [child_context] --to [target_context]" in form
            for form in embed_forms
        )
        assert any("[source_context]:[UID]" in form for form in reference_forms)
        assert any(
            "Target defaults to current Context" in form for form in reference_forms
        )
        assert any(
            "--from" in form and "compatibility" in form for form in reference_forms
        )
        assert any(
            "--from [source_context] --to [target_context]" in form
            for form in reference_forms
        )

    def test_directional_alias_forms_cover_merge_and_sever_roles(self):
        merge_forms = help_inventory.COMMAND_FORMS["merge"]
        sever_forms = help_inventory.COMMAND_FORMS["sever"]

        assert any(
            "--from [source_context] --to [target_context]" in form
            for form in merge_forms
        )
        assert any(
            "--from [source] --against [criteria]" in form and "--to" not in form
            for form in sever_forms
        )

    def test_forms_include_meaningful_bare_entry_routes(self):
        assert help_inventory.COMMAND_FORMS["update"][0] == (
            "mem update (choose Source and Target for a new Update)"
        )
        assert help_inventory.COMMAND_FORMS["checkpoint"][0] == (
            "mem checkpoint (save without a message)"
        )
        assert any(
            form.startswith('mem checkpoint -m "[message]"')
            for form in help_inventory.COMMAND_FORMS["checkpoint"]
        )
        assert any(
            form.startswith('mem checkpoint --message "[message]"')
            for form in help_inventory.COMMAND_FORMS["checkpoint"]
        )
        assert any(
            form.startswith('mem checkpoint [context] "[message]"')
            for form in help_inventory.COMMAND_FORMS["checkpoint"]
        )
        assert any(
            "--context [context] --recursive" in form
            for form in help_inventory.COMMAND_FORMS["checkpoint"]
        )
        assert help_inventory.COMMAND_FORMS["translate"][0] == (
            "mem translate (show/save a default-English view of the current Context)"
        )
        assert help_inventory.COMMAND_FORMS["init-study"][:2] == (
            "mem init-study (initialize coffee with an edited or generated Profile name)",
            "mem init-study [profile_name] (initialize coffee with an explicit Profile name)",
        )
        assert help_inventory.COMMAND_FORMS["checkout"][0] == (
            "mem checkout (enter the Git-style interactive Context picker)"
        )
        assert help_inventory.COMMAND_FORMS["checkout"][3] == (
            "mem checkout -b [new_context] (create and switch to a Context branch)"
        )
        assert help_inventory.COMMAND_FORMS["init"][0].startswith("mem init (")
        assert help_inventory.COMMAND_FORMS["branch"][0].startswith("mem branch (")

    def test_interactive_help_names_the_entry_surface(self):
        session_launchers = (
            "compare",
            "ground",
            "meld",
            "sever",
            "update",
        )
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
            expected_surface = "workspace" if command_name == "ground" else "session"
            assert sessions_option.help == (
                f"Enter the interactive {command_name.title()} "
                f"{expected_surface} launcher"
            )

        atomize = root.get_command(context, "atomize")
        assert atomize is not None
        assert not any(
            isinstance(parameter, click.Option) and "--sessions" in parameter.opts
            for parameter in atomize.params
        )

        all_forms = tuple(
            form for forms in help_inventory.COMMAND_FORMS.values() for form in forms
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
                assert shlex.split(command_line)[:2] == [
                    "mem",
                    command_name,
                ], f"{command_name} owns a form for another command: {command_line}"
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
        semantic_usage_errors = {"add", "makemore", "impact"}

        for command_name in root.list_commands(context):
            command = root.get_command(context, command_name)
            if command is None or command.hidden:
                continue
            if command_name in semantic_usage_errors:
                meaningful_bare = False
            elif isinstance(command, click.Group):
                meaningful_bare = command.invoke_without_command
            else:
                required_arguments = [
                    parameter
                    for parameter in command.params
                    if isinstance(parameter, click.Argument) and parameter.required
                ]
                meaningful_bare = not required_arguments
            if not meaningful_bare:
                continue

            selectable = {
                help_inventory._selectable_form_line(form)
                for form in help_inventory.COMMAND_FORMS[command_name]
            }
            assert f"mem {command_name}" in selectable

    def test_search_forms_do_not_advertise_implicit_history_routing(self):
        forms = help_inventory.COMMAND_FORMS["search"]

        assert not any("--history" in form for form in forms)
        assert not any("temporal_query" in form for form in forms)

    def test_search_forms_expose_independent_multi_root_scope_axes(self):
        forms = help_inventory.COMMAND_FORMS["search"]

        assert any(
            "--context [context1] --context [context2] --descendants" in form
            for form in forms
        )
        assert any("--context-only --follow-embeds" in form for form in forms)
        assert any("--descendants --exclude-embeds" in form for form in forms)
        assert any("-d" in form and "direct preset" in form for form in forms)

    def test_free_text_placeholders_include_shell_quotes(self):
        assert (
            help_inventory._selectable_form_line(help_inventory.COMMAND_FORMS["add"][0])
            == 'mem add "[memory_content]"'
        )
        assert (
            help_inventory._selectable_form_line(
                help_inventory.COMMAND_FORMS["search"][1]
            )
            == 'mem search "[query]"'
        )
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

    def test_selector_page_keys_match_the_visible_help_guidance(self):
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("\x1b[6~\r\r")
            selected = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem gamma"

        with create_pipe_input() as pipe_input:
            pipe_input.send_text(
                "\x1b[F\x1b[5~"
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

    def test_selector_home_and_end_match_the_visible_help_guidance(self):
        with create_pipe_input() as pipe_input:
            pipe_input.send_text(
                "\x1b[F\x1b[H"
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

    def test_help_selector_uses_shared_focused_frame_for_inventory_view(
        self,
        monkeypatch,
    ):
        bound: list[str] = []
        original = help_selector.bind_focused_frame_style

        def record(frame, *, is_focused):
            bound.append(frame.title)
            return original(frame, is_focused=is_focused)

        monkeypatch.setattr(help_selector, "bind_focused_frame_style", record)
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("q")
            result = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert result is None
        assert bound == ["HELP LANGUAGE", "INVENTORY VIEW"]

    def test_selector_tab_advances_through_by_kind_groups(self):
        entries = [
            CommandEntry(
                name=name,
                annotation=None,
                description=f"{name} description",
                command=object(),
                forms=(f"mem {name}",),
            )
            for name in ("add", "find", "edit")
        ]
        with create_pipe_input() as pipe_input:
            # BY KIND starts at Add (Create, Copy & Connect). Successive Tabs
            # must reach Find and then Edit in their following categories, rather than
            # alternating between the original row and VIEW.
            pipe_input.send_text("\t\t\r\r")
            selected = run_help_selector(
                entries,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem edit"

    def test_selector_reaches_view_then_keeps_a_z_as_one_list_surface(self):
        entries = [
            CommandEntry(
                name=name,
                annotation=None,
                description=f"{name} description",
                command=object(),
                forms=(f"mem {name}",),
            )
            for name in ("add", "find")
        ]
        with create_pipe_input() as pipe_input:
            # Create -> Search -> LANGUAGE -> VIEW, then switch projection. A–Z keeps
            # its single list surface and the selected command by name.
            pipe_input.send_text("\t\t\t\x1b[C\t\r\r")
            selected = run_help_selector(
                entries,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem find"

    def test_selector_tab_wraps_through_view_and_restores_kind_cursor(self):
        entries = [
            CommandEntry(
                name=name,
                annotation=None,
                description=f"{name} description",
                command=object(),
                forms=(f"mem {name}",),
            )
            for name in ("init", "add", "find")
        ]
        with create_pipe_input() as pipe_input:
            # Retain add inside Create, cross Search, LANGUAGE, and VIEW, then re-enter
            # Create. Tab traversal preserves that kind's cursor.
            pipe_input.send_text("\x1b[B\t\t\t\t\r\r")
            selected = run_help_selector(
                entries,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem add"

    def test_selector_shift_tab_reaches_previous_kind_through_view(self):
        entries = [
            CommandEntry(
                name=name,
                annotation=None,
                description=f"{name} description",
                command=object(),
                forms=(f"mem {name}",),
            )
            for name in ("add", "find", "edit")
        ]
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("\x1b[Z\x1b[Z\x1b[Z\r\r")
            selected = run_help_selector(
                entries,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected is not None
        assert selected.command_line == "mem edit"

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

    def test_explore_mode_reports_process_local_help_language_changes(self):
        actions: list[tuple[str, str | None]] = []
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("\x1b[Z\x1b[Z\x1b[Ch")
            selected = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
                mode="EXPLORE",
                on_explore_action=lambda action, value: actions.append((action, value)),
            )

        assert selected is None
        assert actions == [("LANGUAGE", "FR"), ("HIDE", None)]

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
            help_selector,
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
        assert "execution remains a separate operation invocation" in result.output


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

        monkeypatch.setattr(
            "memcommit.adapters.console.commands.init.command.choose_context_name",
            choose,
        )

        result = invoke("init")

        assert result.exit_code == 0
        assert observed["view"].value == "new-context-2"
        assert observed["view"].label == "CONTEXT"
        assert observed["view"].state == ""
        assert observed["view"].context_names == ()
        assert observed["view"].heading == "MEM INIT"
        assert MemoryStore().current_context_name() == "new-context-2"

    def test_bare_init_cancel_preserves_current(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "main")
        monkeypatch.setattr(
            "memcommit.adapters.console.commands.init.command.choose_context_name",
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
            "memcommit.adapters.console.commands.init.command.choose_context_name",
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

    def test_empty_context_shows_separate_zero_counts(self, isolated_store):
        invoke("init", "empty")
        result = invoke("list")
        assert result.exit_code == 0
        assert "  0 memories\n" in result.output
        assert "  0 subcontexts\n" in result.output
        assert "  (empty)\n" in result.output

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

    def test_ls_lists_embedded_context_without_leaking_child_contents(
        self, isolated_store
    ):
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
        source_memory_uid = next(iter(MemoryStore().load_current().memories))
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
            if line.startswith("  VIA EMBED · [context ") and line.endswith("] aaa/ab")
        )
        first_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line and line.endswith("] aaa")
        )
        reference_index = next(
            index
            for index, line in enumerate(lines)
            if "[reference " in line
            and "READ ONLY" in line
            and "Referenced atomic name." in line
        )
        last_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line and line.endswith("] Last atomic name.")
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
            if line.startswith("  VIA EMBED · [context ") and line.endswith("] child")
        )
        grandchild_index = next(
            index
            for index, line in enumerate(lines)
            if line.startswith("    VIA EMBED · [context ")
            and line.endswith("] grandchild")
        )
        grandchild_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line and line.endswith("] Grandchild memory.")
        )
        child_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line and line.endswith("] Child memory.")
        )
        parent_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory " in line and line.endswith("] Parent memory.")
        )
        assert (
            child_index
            < grandchild_index
            < grandchild_memory_index
            < child_memory_index
            < parent_memory_index
        )

    def test_list_separates_context_blocks_from_direct_memories(
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
            if line.startswith("  VIA EMBED · [context ") and line.endswith("] alpha")
        )
        beta_index = next(
            index
            for index, line in enumerate(recursive_lines)
            if line.startswith("  VIA EMBED · [context ") and line.endswith("] beta")
        )
        parent_memory_index = next(
            index
            for index, line in enumerate(recursive_lines)
            if "[memory " in line and line.endswith("] Parent memory.")
        )
        assert recursive_lines[alpha_index - 1] == ""
        assert recursive_lines[alpha_index - 2] != ""
        assert recursive_lines[beta_index - 1] == ""
        assert recursive_lines[beta_index + 1] != ""
        assert recursive_lines[parent_memory_index - 1] == ""
        direct_lines = direct.output.splitlines()
        direct_beta_index = next(
            index
            for index, line in enumerate(direct_lines)
            if line.startswith("  VIA EMBED · [context ") and line.endswith("] beta")
        )
        direct_parent_memory_index = next(
            index
            for index, line in enumerate(direct_lines)
            if "[memory " in line and line.endswith("] Parent memory.")
        )
        assert direct_lines[direct_beta_index - 1].startswith("  VIA EMBED · [context ")
        assert direct_lines[direct_beta_index - 1].endswith("] alpha")
        assert direct_lines[direct_parent_memory_index - 1] == ""

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
        assert "Context 'ghost' does not exist" in result.stderr
        assert "Granted view" not in result.stderr

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
        assert "No Context or direct item matches 'missing'" in result.stderr

    def test_fails_for_ambiguous_uid_prefix(self, isolated_store):
        from memcommit.core.context import Memory as Mem

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

    def test_bare_uid_resolves_a_unique_item_outside_the_current_context(
        self,
        isolated_store,
    ):
        invoke("init", "rules")
        invoke("add", "remove this mistaken Rule")
        store = MemoryStore()
        uid = next(iter(store.load_current().memories))
        invoke("init", "values")

        removed = invoke("remove", uid[:8])

        assert removed.exit_code == 0
        assert "Removed" in removed.output
        assert uid not in store.load_direct("rules").memories
        assert store.current_context_name() == "values"

    def test_ambiguous_cross_context_uid_requires_context_qualification(
        self,
        isolated_store,
    ):
        from memcommit.core.context import Memory as Mem

        store = MemoryStore()
        first = ops.init("first")
        first.add(Mem(uid="aaaa1111-1111-1111-1111-111111111111", content="first"))
        second = ops.init("second")
        second.add(Mem(uid="aaaa2222-2222-2222-2222-222222222222", content="second"))
        store.create_context(first)
        store.create_context(second)
        store.set_current("second")

        ambiguous = invoke("remove", "aaaa")

        assert ambiguous.exit_code == 1
        assert "multiple local matches (2)" in ambiguous.stderr
        assert "first:aaaa1111-1111-1111-1111-111111111111" in ambiguous.stderr
        assert "second:aaaa2222-2222-2222-2222-222222222222" in ambiguous.stderr
        assert len(store.load_direct("first").memories) == 1
        assert len(store.load_direct("second").memories) == 1

        removed = invoke("remove", "aaaa", "--context", "first")

        assert removed.exit_code == 0
        assert not store.load_direct("first").memories
        assert len(store.load_direct("second").memories) == 1

    def test_fails_on_ambiguous_prefix(self, isolated_store):
        from memcommit.core.context import Memory as Mem

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

    def test_previous_and_next_follow_actual_context_navigation(
        self,
        isolated_store,
    ):
        invoke("init", "alpha")
        invoke("init", "beta")
        invoke("init", "gamma")

        previous = invoke("switch", "--previous")
        assert previous.exit_code == 0, previous.output
        assert "Switched to context 'beta'" in previous.output
        assert MemoryStore().current_context_name() == "beta"

        previous_again = invoke("switch", "-p")
        assert previous_again.exit_code == 0, previous_again.output
        assert "Switched to context 'alpha'" in previous_again.output
        assert MemoryStore().current_context_name() == "alpha"

        next_result = invoke("switch", "--next")
        assert next_result.exit_code == 0, next_result.output
        assert "Switched to context 'beta'" in next_result.output
        assert MemoryStore().current_context_name() == "beta"

    def test_direct_switch_after_previous_clears_forward_history(
        self,
        isolated_store,
    ):
        invoke("init", "alpha")
        invoke("init", "beta")
        invoke("init", "gamma")
        invoke("switch", "-p")

        direct = invoke("switch", "alpha")
        assert direct.exit_code == 0, direct.output

        no_next = invoke("switch", "-n")
        assert no_next.exit_code == 1
        assert "No next Context is available" in no_next.stderr
        assert MemoryStore().current_context_name() == "alpha"

    def test_previous_without_history_preserves_current(self, isolated_store):
        invoke("init", "only")

        result = invoke("switch", "-p")

        assert result.exit_code == 1
        assert "No previous Context is available" in result.stderr
        assert MemoryStore().current_context_name() == "only"

    def test_missing_saved_previous_context_fails_without_moving_current(
        self,
        isolated_store,
    ):
        invoke("init", "alpha")
        invoke("init", "beta")
        MemoryStore().delete("alpha")

        result = invoke("switch", "--previous")

        assert result.exit_code == 1
        assert "Saved previous Context 'alpha' no longer exists" in result.stderr
        assert MemoryStore().current_context_name() == "beta"

    def test_rename_rewrites_saved_navigation_names(self, isolated_store):
        invoke("init", "old")
        invoke("init", "current")

        renamed = invoke("rename", "old", "new", "--force")
        previous = invoke("switch", "--previous")

        assert renamed.exit_code == 0, renamed.output
        assert previous.exit_code == 0, previous.output
        assert "Switched to context 'new'" in previous.output
        assert MemoryStore().current_context_name() == "new"

    def test_previous_rejects_concurrently_changed_navigation_history(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "alpha")
        invoke("init", "beta")
        invoke("init", "gamma")
        original_switch = MemoryStore.set_current_context_if

        def change_history_then_compare_and_set(
            store,
            expected_current,
            name,
            *,
            expected_context_uid,
            expected_context_digest,
            navigation_direction=None,
        ):
            store.set_current("alpha")
            store.set_current("gamma")
            return original_switch(
                store,
                expected_current,
                name,
                expected_context_uid=expected_context_uid,
                expected_context_digest=expected_context_digest,
                navigation_direction=navigation_direction,
            )

        monkeypatch.setattr(
            MemoryStore,
            "set_current_context_if",
            change_history_then_compare_and_set,
        )

        result = invoke("switch", "--previous")

        assert result.exit_code == 1
        assert "Context navigation changed" in result.stderr
        assert MemoryStore().current_context_name() == "gamma"

    def test_navigation_flags_are_mutually_exclusive_with_each_other_and_name(
        self,
        isolated_store,
    ):
        invoke("init", "alpha")
        invoke("init", "beta")

        both = invoke("switch", "--previous", "--next")
        named = invoke("switch", "alpha", "--previous")

        assert both.exit_code == 2
        assert "cannot be used together" in both.stderr
        assert named.exit_code == 2
        assert "cannot be combined" in named.stderr
        assert MemoryStore().current_context_name() == "beta"


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
            "memcommit.adapters.console.commands.branch.command.choose_branch_creation",
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
            "memcommit.adapters.console.commands.branch.command.choose_branch_creation",
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
            "memcommit.adapters.console.commands.branch.command.choose_branch_creation",
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
            "memcommit.adapters.console.commands.branch.command.choose_branch_creation",
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

    def test_explicit_branch_can_choose_a_noncurrent_source(self, isolated_store):
        invoke("init", "source")
        invoke("add", "source-only")
        invoke("init", "current")
        invoke("add", "current-only")

        result = invoke("branch", "experiment", "--from", "source")

        assert result.exit_code == 0
        assert "Branched 'source' → 'experiment'" in result.output
        branched = MemoryStore().load("experiment")
        assert [item.content for item in branched.memories.values()] == ["source-only"]

    def test_explicit_branch_resolves_relative_source_once(self, isolated_store):
        invoke("init", "project/source")
        invoke("add", "relative source")
        invoke("init", "project/current")

        result = invoke("branch", "experiment", "--from", "../source")

        assert result.exit_code == 0
        assert "Branched 'project/source' → 'experiment'" in result.output
        branched = MemoryStore().load("experiment")
        assert [item.content for item in branched.memories.values()] == [
            "relative source"
        ]

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
        assert "NEW 2 (2 memories)" in result.output

    def test_merge_nothing_new_when_already_merged(self, isolated_store):
        invoke("init", "src")
        invoke("add", "fact")
        invoke("init", "tgt")
        invoke("merge", "src")
        result = invoke("merge", "src")
        assert result.exit_code == 0
        assert "NEW 0" in result.output
        assert "ALREADY PRESENT 1" in result.output

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
        # The ownership column stays aligned with GRANT rows, after the marker.
        assert "*        alpha" in result.output
        assert "*        beta" not in result.output


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_removes_all_memories_without_confirmation(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "gone soon")
        result = invoke("clear")
        assert result.exit_code == 0
        assert "Continue?" not in result.output
        assert "This will remove" not in result.output

        store = MemoryStore()
        ctx = store.load_current()
        assert ctx.memories == {}

    def test_clear_is_one_undoable_and_redoable_command(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "first")
        invoke("add", "second")

        cleared = invoke("clear")
        assert cleared.exit_code == 0, cleared.output
        assert not MemoryStore().load_current().memories

        undone = invoke("undo")
        assert undone.exit_code == 0, undone.output
        assert "Undid command: mem clear ctx" in undone.output
        assert [
            memory.content for memory in MemoryStore().load_current().memories.values()
        ] == ["first", "second"]

        redone = invoke("redo")
        assert redone.exit_code == 0, redone.output
        assert "Redid command: mem clear ctx" in redone.output
        assert not MemoryStore().load_current().memories

    def test_recursive_clear_is_one_undoable_command_and_ignores_embeds(
        self,
        isolated_store,
    ):
        assert invoke("init", "tree").exit_code == 0
        assert invoke("add", "root item").exit_code == 0
        assert invoke("init", "tree/child").exit_code == 0
        assert invoke("add", "child item").exit_code == 0
        assert invoke("init", "tree/empty").exit_code == 0
        assert invoke("init", "outside").exit_code == 0
        assert invoke("add", "outside survives").exit_code == 0
        assert invoke("embed", "outside", "--into", "tree").exit_code == 0

        cleared = invoke("clear", "tree", "-r")

        assert cleared.exit_code == 0, cleared.output
        assert "Continue?" not in cleared.output
        assert "Cleared 3 item(s) from 2 of 3 Context(s)" in cleared.output
        assert "Undo can restore this command as one unit" in cleared.output
        store = MemoryStore()
        assert not store.load_direct("tree").memories
        assert not store.load_direct("tree/child").memories
        assert not store.load_direct("tree/empty").memories
        assert [item.content for item in store.load_direct("outside").iter_items()] == [
            "outside survives"
        ]

        undone = invoke("undo")

        assert undone.exit_code == 0, undone.output
        assert "Undid command: mem clear tree --recursive" in undone.output
        assert "Affected Contexts: 2" in undone.output
        assert len(store.load_direct("tree").memories) == 2
        assert [
            item.content for item in store.load_direct("tree/child").iter_items()
        ] == ["child item"]
        assert not store.load_direct("tree/empty").memories
        assert [item.content for item in store.load_direct("outside").iter_items()] == [
            "outside survives"
        ]

        redone = invoke("redo")

        assert redone.exit_code == 0, redone.output
        assert "Redid command: mem clear tree --recursive" in redone.output
        assert not store.load_direct("tree").memories
        assert not store.load_direct("tree/child").memories

    def test_recursive_clear_fails_without_partial_writes(
        self,
        isolated_store,
    ):
        assert invoke("init", "tree").exit_code == 0
        assert invoke("add", "root stays").exit_code == 0
        assert invoke("init", "tree/child").exit_code == 0
        assert invoke("add", "child stays").exit_code == 0
        assert invoke("lock", "context", "tree/child").exit_code == 0

        result = invoke("clear", "tree", "--recursive")

        assert result.exit_code == 1
        assert "tree/child" in (result.output + result.stderr)
        assert "locked against changes" in (result.output + result.stderr)
        store = MemoryStore()
        assert [item.content for item in store.load_direct("tree").iter_items()] == [
            "root stays"
        ]
        assert [
            item.content for item in store.load_direct("tree/child").iter_items()
        ] == ["child stays"]
        for name in ("tree", "tree/child"):
            assert not any(
                checkpoint.get("command") == "clear"
                for checkpoint in store.list_checkpoints(name)
            )

    def test_recursive_clear_retains_a_canonical_empty_root_in_undo_receipt(
        self,
        isolated_store,
    ):
        assert invoke("init", "tree").exit_code == 0
        assert invoke("init", "tree/child").exit_code == 0
        assert invoke("add", "child item").exit_code == 0

        cleared = invoke("clear", "..", "-r")

        assert cleared.exit_code == 0, cleared.output
        assert "1 of 2 Context(s) under 'tree'" in cleared.output
        store = MemoryStore()
        assert not store.load_direct("tree").memories
        assert not store.load_direct("tree/child").memories

        undone = invoke("undo")

        assert undone.exit_code == 0, undone.output
        assert "Undid command: mem clear tree --recursive" in undone.output
        assert [
            item.content for item in store.load_direct("tree/child").iter_items()
        ] == ["child item"]

    def test_recursive_clear_rolls_back_an_interrupted_batch(
        self,
        isolated_store,
        monkeypatch,
    ):
        assert invoke("init", "tree").exit_code == 0
        assert invoke("add", "root stays").exit_code == 0
        assert invoke("init", "tree/child").exit_code == 0
        assert invoke("add", "child stays").exit_code == 0
        original_save = MemoryStore._save_locked
        clear_writes = 0

        def fail_second_clear(store, context, checkpoint, **kwargs):
            nonlocal clear_writes
            if checkpoint is not None and checkpoint.command == "clear":
                clear_writes += 1
                if clear_writes == 2:
                    raise OSError("simulated recursive clear write failure")
            return original_save(store, context, checkpoint, **kwargs)

        monkeypatch.setattr(MemoryStore, "_save_locked", fail_second_clear)

        result = invoke("clear", "tree", "--recursive")

        assert result.exit_code == 1
        assert "simulated recursive clear write failure" in (
            result.output + result.stderr
        )
        store = MemoryStore()
        assert [item.content for item in store.load_direct("tree").iter_items()] == [
            "root stays"
        ]
        assert [
            item.content for item in store.load_direct("tree/child").iter_items()
        ] == ["child stays"]
        for name in ("tree", "tree/child"):
            assert not any(
                checkpoint.get("command") == "clear"
                for checkpoint in store.list_checkpoints(name)
            )

    def test_clear_help_hides_legacy_force_option(self):
        result = invoke("clear", "--help")
        assert result.exit_code == 0
        assert "--force" not in result.output
        assert "--recursive" in result.output

    def test_clear_fails_with_no_current_context(self, isolated_store):
        result = invoke("clear")
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
        assert len(store.list_context_lifecycle_events(context_name="to-delete")) == 1

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
        assert "Inventory · Checkpoints 1" in result.output
        assert "Memories " not in result.output

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
        from memcommit.persistence.store import MemoryStore
        import memcommit.application.capabilities.ops as ops

        store = MemoryStore()
        ctx = ops.init("bare")
        store.save(ctx)  # save without AutoCheckpoint
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

    def test_accepts_short_message_option(self, isolated_store):
        invoke("init", "ctx")

        result = invoke("checkpoint", "-m", "short option")

        assert result.exit_code == 0
        assert "short option" in result.output
        checkpoints = MemoryStore().list_checkpoints("ctx")
        assert checkpoints[0]["message"] == "short option"

    def test_accepts_long_message_option(self, isolated_store):
        invoke("init", "ctx")

        result = invoke("checkpoint", "--message", "long option")

        assert result.exit_code == 0
        assert "long option" in result.output
        checkpoints = MemoryStore().list_checkpoints("ctx")
        assert checkpoints[0]["message"] == "long option"

    def test_two_positionals_select_context_then_message(self, isolated_store):
        invoke("init", "current")
        invoke("init", "task-1")
        invoke("switch", "current")

        result = invoke("checkpoint", "task-1", "yes another checkpoint")

        assert result.exit_code == 0
        assert "Context 'task-1'" in result.output
        assert MemoryStore().list_checkpoints("task-1")[0]["message"] == (
            "yes another checkpoint"
        )
        assert all(
            entry.get("message") != "yes another checkpoint"
            for entry in MemoryStore().list_checkpoints("current")
        )

    def test_message_option_disambiguates_positional_context(self, isolated_store):
        invoke("init", "current")
        invoke("init", "task-1")
        invoke("switch", "current")

        result = invoke("checkpoint", "task-1", "-m", "option message")

        assert result.exit_code == 0
        assert MemoryStore().list_checkpoints("task-1")[0]["message"] == (
            "option message"
        )

    def test_context_option_disambiguates_positional_message(self, isolated_store):
        invoke("init", "current")
        invoke("init", "task-1")
        invoke("switch", "current")

        result = invoke("checkpoint", "message text", "-c", "task-1")

        assert result.exit_code == 0
        assert MemoryStore().list_checkpoints("task-1")[0]["message"] == (
            "message text"
        )

    def test_long_context_and_message_options_select_exact_target(
        self,
        isolated_store,
    ):
        invoke("init", "current")
        invoke("init", "task-1")
        invoke("switch", "current")

        result = invoke(
            "checkpoint",
            "--context",
            "task-1",
            "--message",
            "named options",
        )

        assert result.exit_code == 0
        assert MemoryStore().list_checkpoints("task-1")[0]["message"] == (
            "named options"
        )

    def test_context_option_supports_target_without_message(self, isolated_store):
        invoke("init", "current")
        invoke("init", "task-1")
        invoke("switch", "current")

        result = invoke("checkpoint", "--context", "task-1")

        assert result.exit_code == 0
        assert "Context 'task-1'" in result.output
        assert "(no message)" in result.output

    def test_relative_positional_context_uses_command_start_current(
        self,
        isolated_store,
    ):
        invoke("init", "tree/from")
        invoke("init", "tree/to")
        invoke("switch", "tree/from")

        result = invoke("checkpoint", "../to", "relative target")

        assert result.exit_code == 0
        assert "Context 'tree/to'" in result.output
        assert MemoryStore().list_checkpoints("tree/to")[0]["message"] == (
            "relative target"
        )

    def test_rejects_message_in_positional_and_option_forms_without_checkpointing(
        self,
        isolated_store,
    ):
        invoke("init", "ctx")
        before = MemoryStore().list_checkpoints("ctx")

        result = invoke(
            "checkpoint",
            "ctx",
            "positional",
            "-m",
            "option",
        )

        assert result.exit_code == 2
        assert "cannot be supplied both" in result.stderr
        assert MemoryStore().list_checkpoints("ctx") == before

    def test_rejects_context_in_positional_and_option_forms_without_checkpointing(
        self,
        isolated_store,
    ):
        invoke("init", "ctx")
        before = MemoryStore().list_checkpoints("ctx")

        result = invoke(
            "checkpoint",
            "ctx",
            "positional",
            "--context",
            "ctx",
        )

        assert result.exit_code == 2
        assert "cannot be supplied both" in result.stderr
        assert MemoryStore().list_checkpoints("ctx") == before

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

    def test_direct_scope_does_not_checkpoint_descendants(self, isolated_store):
        invoke("init", "tree")
        invoke("init", "tree/child")
        before_child = MemoryStore().list_checkpoints("tree/child")

        result = invoke(
            "checkpoint",
            "--context",
            "tree",
            "--direct",
            "--message",
            "direct baseline",
        )

        assert result.exit_code == 0
        assert MemoryStore().list_checkpoints("tree")[0]["message"] == (
            "direct baseline"
        )
        assert MemoryStore().list_checkpoints("tree/child") == before_child

    def test_recursive_scope_checkpoints_frozen_lexical_subtree(self, isolated_store):
        invoke("init", "tree")
        invoke("init", "tree/child")
        invoke("init", "other")
        store = MemoryStore()
        before = {
            name: store.list_checkpoints(name)
            for name in ("tree", "tree/child", "other")
        }

        result = invoke(
            "checkpoint",
            "tree",
            "recursive baseline",
            "--recursive",
        )

        assert result.exit_code == 0
        assert "Checkpoint set" in result.output
        assert "2 Context(s) under 'tree'" in result.output
        root = store.list_checkpoints("tree")[0]
        child = store.list_checkpoints("tree/child")[0]
        assert len(store.list_checkpoints("tree")) == len(before["tree"]) + 1
        assert len(store.list_checkpoints("tree/child")) == (
            len(before["tree/child"]) + 1
        )
        assert store.list_checkpoints("other") == before["other"]
        assert root["message"] == child["message"] == "recursive baseline"
        assert root["description"] == child["description"] == "recursive baseline"
        assert root["auto"] is child["auto"] is False
        assert root["command"] == child["command"] == "checkpoint"
        assert root["args"] == child["args"]
        assert root["args"]["checkpoint_set"] == {
            "version": 2,
            "uid": root["uid"],
            "root": {
                "uid": store.load_direct("tree").uid,
                "name": "tree",
            },
            "include_descendants": True,
            "members": [
                {
                    "context_uid": store.load_direct("tree").uid,
                    "context_name": "tree",
                    "checkpoint_uid": root["uid"],
                },
                {
                    "context_uid": store.load_direct("tree/child").uid,
                    "context_name": "tree/child",
                    "checkpoint_uid": child["uid"],
                },
            ],
        }
        assert root["args"]["command_contexts"] == [
            {"uid": store.load_direct("tree").uid, "name": "tree"},
            {
                "uid": store.load_direct("tree/child").uid,
                "name": "tree/child",
            },
        ]

    def test_rejects_direct_and_recursive_without_checkpointing(
        self,
        isolated_store,
    ):
        invoke("init", "ctx")
        before = MemoryStore().list_checkpoints("ctx")

        result = invoke("checkpoint", "message", "-d", "-r")

        assert result.exit_code == 2
        assert "either --direct/-d or --recursive/-r" in result.stderr
        assert MemoryStore().list_checkpoints("ctx") == before

    def test_help_lists_short_and_long_targeting_options(self, isolated_store):
        result = invoke("checkpoint", "--help")

        assert result.exit_code == 0
        assert "--context" in result.output
        assert "-c" in result.output
        assert "--message" in result.output
        assert "-m" in result.output
        assert "--direct" in result.output
        assert "-d" in result.output
        assert "--recursive" in result.output
        assert "-r" in result.output

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
            "memcommit.adapters.console.commands.branch.command.choose_branch_creation",
            lambda *args, **kwargs: BranchCreationReceipt(
                source_name="main",
                target_name="feature",
            ),
        )

        result = invoke("checkout", "-b")

        assert result.exit_code == 0
        assert MemoryStore().context_exists("feature")
        assert MemoryStore().current_context_name() == "feature"
