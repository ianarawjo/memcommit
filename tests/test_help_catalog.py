"""Contracts for interface-neutral operation Help and its projections."""

import click
from typer.main import get_command

from memcommit.cli import app
from memcommit.commands.help_inventory import (
    HELP_CATEGORY_DESCRIPTIONS,
    HELP_CATEGORY_GROUPS,
    _help_group_fragments,
    command_entries,
)
from memcommit.help_catalog import (
    OPERATION_HELP_BY_NAME,
    ExecutionKind,
    compose_operation_help,
    operation_help,
)
from memcommit.help_catalog.best_for import BEST_FOR_BY_OPERATION
from memcommit.help_catalog.details import ALL_OPERATION_DETAILS, DETAILS_BY_OPERATION
from memcommit.interfaces.tui.core.text_layout import terminal_cell_width
from memcommit.interfaces.tui.operations.help.localization import HELP_LANGUAGES


def _root_context():
    root = get_command(app)
    return root, click.Context(root)


def test_catalog_covers_every_visible_top_level_operation_exactly():
    root, context = _root_context()
    try:
        visible = {
            name
            for name in root.list_commands(context)
            if (command := root.get_command(context, name)) is not None
            and not command.hidden
        }
    finally:
        context.close()

    assert set(OPERATION_HELP_BY_NAME) == visible


def test_every_operation_has_one_reviewed_best_for_value():
    assert set(BEST_FOR_BY_OPERATION) == set(OPERATION_HELP_BY_NAME)
    assert all(
        operation.best_for == BEST_FOR_BY_OPERATION[name]
        and operation.use_when == operation.best_for
        and operation.best_for.strip()
        for name, operation in OPERATION_HELP_BY_NAME.items()
    )


def test_detailed_help_topics_reference_only_visible_operations():
    assert set(DETAILS_BY_OPERATION) <= set(OPERATION_HELP_BY_NAME)


def test_typed_detail_registry_has_stable_unique_ids_and_discovery_summaries():
    keys = [(detail.operation, detail.id) for detail in ALL_OPERATION_DETAILS]

    assert len(keys) == len(set(keys))
    assert {detail.kind.value for detail in ALL_OPERATION_DETAILS} == {
        "COMPARISON",
        "LIMITATION",
        "ACCESS_BOUNDARY",
        "SEMANTIC_BOUNDARY",
    }
    assert all(
        detail.discovery.value != "TOOL_SELECTION"
        or detail.discovery_summary is not None
        for detail in ALL_OPERATION_DETAILS
    )


def test_update_and_meld_share_one_concise_semantic_boundary_note():
    expected = (
        "Update is revision-oriented: it treats a Source as verified change "
        "evidence and semantically patches an existing Target. Meld is "
        "merge-oriented: it semantically combines two inputs while reconciling "
        "their relationships and conflicts, either into an existing Baseline or "
        "a new Result."
    )

    for operation_name in ("update", "meld"):
        [note] = [
            detail
            for detail in operation_help(operation_name).details
            if detail.id == "update-vs-meld"
        ]
        assert note.kind.value == "SEMANTIC_BOUNDARY"
        assert note.title == "UPDATE VS. MELD"
        assert note.body == expected


def test_update_meld_note_is_visible_only_in_each_expanded_help_record():
    root, context = _root_context()
    try:
        entries = {
            entry.name: entry
            for entry in command_entries(context)
            if entry.name in {"update", "meld"}
        }
    finally:
        context.close()

    for operation_name in ("update", "meld"):
        collapsed = "".join(
            text
            for _style, text in _help_group_fragments(
                [(0, entries[operation_name])],
                title="SEMANTIC TRANSFORMATIONS",
                width=180,
                focused=True,
                selected_index=0,
                expanded_index=None,
                selected_form=None,
            )
        )
        expanded = "".join(
            text
            for _style, text in _help_group_fragments(
                [(0, entries[operation_name])],
                title="SEMANTIC TRANSFORMATIONS",
                width=180,
                focused=True,
                selected_index=0,
                expanded_index=0,
                selected_form=None,
            )
        )

        assert "UPDATE VS. MELD" not in collapsed
        assert "UPDATE VS. MELD" in expanded
        assert "Update is revision-oriented" in expanded
        assert "Meld is merge-oriented" in expanded


def test_add_has_one_structured_copy_or_link_comparison():
    [comparison] = operation_help("add").details

    assert comparison.title == "COPY OR LINK"
    assert "Memory UID or Context name" in comparison.explanation
    assert [option.label for option in comparison.options] == [
        "INDEPENDENT WORK",
        "EXACT MEMORY OR CONTEXT",
        "LIVE MEMORY",
        "LIVE CONTEXT",
    ]
    assert "mem reference" in comparison.options[1].guidance
    assert "mem embed" in comparison.options[2].guidance


def test_init_has_one_structured_parent_context_comparison():
    [comparison] = operation_help("init").details

    assert comparison.title == "PARENT CONTEXTS"
    assert "mem init NAME creates only that exact Context" in comparison.explanation
    assert [option.label for option in comparison.options] == [
        "DEFAULT",
        "WITH -P",
    ]
    assert "does not embed children" in comparison.options[1].guidance


def test_registered_cli_summaries_share_the_catalog_source():
    root, context = _root_context()
    try:
        for name, expected in OPERATION_HELP_BY_NAME.items():
            command = root.get_command(context, name)
            assert command is not None
            assert command.help == expected.summary
    finally:
        context.close()


def test_composer_keeps_common_meaning_separate_from_cli_forms():
    operation = operation_help("update")
    composed = compose_operation_help(
        operation,
        cli_forms=("mem update", "mem update --from A --to B"),
    )

    assert operation.summary == (
        "Update a Target Context from a Source Context, resolving required execution "
        "decisions before atomic Apply."
    )
    assert operation.execution is ExecutionKind.SEMANTIC
    assert [(row.label, row.value) for row in composed.overview] == [
        ("FLOW", "Source Context -> decisions -> Target Apply -> receipt"),
        ("EXECUTION", "SEMANTIC"),
        ("EFFECT", "Changes only the local Target after Apply"),
        ("RANGE", "Each endpoint exact or readable descendants"),
        ("BEST FOR", "Updating an existing Context using newly verified Memories."),
    ]
    assert composed.cli_forms == (
        "mem update",
        "mem update --from A --to B",
    )


def test_compare_help_includes_the_reviewed_use_case():
    composed = compose_operation_help(operation_help("compare"))

    assert (
        "BEST FOR",
        "Comparing two Contexts as a whole to understand where they align and differ.",
    ) in [(row.label, row.value) for row in composed.overview]


def test_meld_help_distinguishes_symmetric_and_directional_modes():
    composed = compose_operation_help(operation_help("meld"))
    overview = [(row.label, row.value) for row in composed.overview]

    assert composed.operation.summary == (
        "Semantically incorporate an incoming Context into an authoritative "
        "baseline, or derive a separate Result from two equal peers."
    )
    assert (
        "FLOW",
        "INCOMING -> BASELINE; PEER A + PEER B -> RESULT",
    ) in overview
    assert (
        "EFFECT",
        "Symmetric mode requires a distinct empty Result; directional mode "
        "changes only the existing Target after required execution decisions",
    ) in overview
    assert (
        "BEST FOR",
        "Combining two bodies of work when overlap, conflicts, and newly "
        "synthesized content must be reviewed semantically.",
    ) in overview


def test_merge_help_distinguishes_structural_selection_from_meld_synthesis():
    composed = compose_operation_help(operation_help("merge"))
    overview = [(row.label, row.value) for row in composed.overview]

    assert composed.operation.summary == (
        "Add Source-only items to a selected Target, leave exact matches "
        "unchanged, and choose Source or Target for stored-item conflicts."
    )
    assert ("EXECUTION", "DETERMINISTIC") in overview
    assert (
        "BEST FOR",
        "Appending Source-only items or bringing a copied or branched Context "
        "into a selected Target Context without semantic synthesis.",
    ) in overview

    [boundary] = composed.operation.details
    assert boundary.title == "MERGE BOUNDARY"
    assert [option.label for option in boundary.options] == [
        "SOURCE ONLY",
        "EXACT MATCH",
        "CONFLICT",
        "TARGET ONLY",
        "RECURSIVE",
    ]


def test_distill_help_separates_case_propositions_from_goal_focus():
    assert operation_help("distill").summary == (
        "Derive higher-level Rules or condition propositions from Case or Example "
        "propositions in a bounded Context, optionally guided by a Goal."
    )
    [comparison] = operation_help("distill").details
    assert comparison.title == "DISTILL OR ATOMIZE"
    assert comparison.discovery.value == "TOOL_SELECTION"
    assert "optional Goal focuses" in comparison.explanation


def test_elaborate_help_separates_candidate_rules_from_concrete_cases():
    assert operation_help("elaborate").summary == (
        "Expand an abstract Goal, Rule, or condition into multiple more specific "
        "candidate propositions."
    )
    assert BEST_FOR_BY_OPERATION["elaborate"] == (
        "Generating several more concrete candidate Rules or Cases from an "
        "abstract concept or condition."
    )
    assert operation_help("elaborate").flow == (
        "Goal -> added Rules; Rules -> added Case propositions -> receipt"
    )


def test_collapsed_by_kind_row_connects_summary_and_when_without_extra_height():
    root, context = _root_context()
    try:
        entry = next(
            entry for entry in command_entries(context) if entry.name == "compare"
        )
    finally:
        context.close()

    fragments = _help_group_fragments(
        [(0, entry)],
        title="CHECK, COMPARE & REVIEW",
        width=180,
        focused=True,
        selected_index=0,
        expanded_index=None,
        selected_form=None,
    )
    rendered = "".join(text for _style, text in fragments)
    lines = rendered.splitlines()
    command_index = next(
        index for index, line in enumerate(lines) if "▸ mem compare" in line
    )
    command_line = lines[command_index]
    when_line = next(line for line in lines if "WHEN ·" in line)

    assert all(len(line) == 180 for line in lines)
    assert "mem compare ─┬ Compare Memories in two Contexts" in command_line
    assert "└ WHEN · Comparing two Contexts" in when_line
    assert lines.index(when_line) == command_index + 1
    assert any(
        style == "class:help-command.selected" and text == "┬ "
        for style, text in fragments
    )
    assert any(
        style == "class:help-command.selected" and text == "WHEN"
        for style, text in fragments
    )
    assert "DESCRIPTION:" not in rendered
    assert "USE WHEN:" not in rendered
    assert "BEST FOR" not in rendered
    assert "FORM 1" not in rendered


def test_adjacent_command_records_use_connectors_without_background_bands():
    root, context = _root_context()
    try:
        entries = [
            entry
            for entry in command_entries(context)
            if entry.name in {"compare", "review"}
        ]
    finally:
        context.close()

    fragments = _help_group_fragments(
        list(enumerate(entries)),
        title="CHECK, COMPARE & REVIEW",
        width=180,
        focused=False,
        selected_index=0,
        expanded_index=None,
        selected_form=None,
    )

    assert not any("help-zebra" in style for style, _text in fragments)
    assert any(
        style == "class:help-connector" and text == "┬ "
        for style, text in fragments
    )
    assert any(style == "" and text == "WHEN" for style, text in fragments)
    assert any(
        style == "class:help-command" and "▸ mem review" in text
        for style, text in fragments
    )
    assert any(
        style == "class:help-group bold" and text == " CHECK, COMPARE & REVIEW "
        for style, text in fragments
    )
    category_copy = [
        (style, text)
        for style, text in fragments
        if "Check compatibility" in text
    ]
    assert category_copy
    assert all(style == "class:help-category-description bold" for style, _ in category_copy)


def test_every_help_category_explains_its_intent_and_execution_basis():
    root, context = _root_context()
    try:
        entries = command_entries(context)
        edit_entry = next(entry for entry in entries if entry.name == "edit")
        atomize_entry = next(entry for entry in entries if entry.name == "atomize")
        ground_entry = next(entry for entry in entries if entry.name == "ground")
        help_entry = next(entry for entry in entries if entry.name == "help")
    finally:
        context.close()

    assert set(HELP_CATEGORY_DESCRIPTIONS) == {
        title for title, _commands in HELP_CATEGORY_GROUPS
    }

    deterministic = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, edit_entry)],
            title="DETERMINISTIC CONTENT CHANGES",
            width=120,
            focused=False,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    semantic = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, atomize_entry)],
            title="SEMANTIC TRANSFORMATIONS",
            width=120,
            focused=False,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    ground = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, ground_entry)],
            title="GROUND WORKBENCH",
            width=120,
            focused=False,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    system = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, help_entry)],
            title="SYSTEM & STUDY TOOLS",
            width=120,
            focused=False,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    a_z = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, edit_entry)],
            title="A–Z",
            width=120,
            focused=False,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )

    assert "NO LLM · Apply explicit inputs" in deterministic
    assert "deterministic program logic" in deterministic
    assert "LLM-BASED · Uses LLM semantic analysis" in semantic
    assert "abstract ideas into reviewable common ground" in ground
    assert "Configure MemCommit and prepare or run study" in system
    assert "MIXED · Configure" not in system
    assert "NO LLM" not in a_z
    assert "LLM-BASED" not in a_z


def test_collapsed_a_z_rows_use_the_same_connected_record():
    root, context = _root_context()
    try:
        entries = command_entries(context)
    finally:
        context.close()
    indexed = list(enumerate(entries))
    compare_index = next(index for index, entry in indexed if entry.name == "compare")

    rendered = "".join(
        text
        for _style, text in _help_group_fragments(
            indexed,
            title="A–Z",
            width=180,
            focused=True,
            selected_index=compare_index,
            expanded_index=None,
            selected_form=None,
        )
    )
    lines = rendered.splitlines()
    command_index = next(
        index for index, line in enumerate(lines) if "▸ mem compare" in line
    )
    command_line = lines[command_index]
    when_line = next(
        line for line in lines[command_index + 1 :] if "WHEN ·" in line
    )

    assert "─┬ Compare Memories" in command_line
    assert "└ WHEN · Comparing two Contexts" in when_line
    assert "DESCRIPTION:" not in rendered
    assert "USE WHEN:" not in rendered
    assert "BEST FOR" not in rendered


def test_every_help_language_localizes_learning_copy_without_renaming_commands():
    root, context = _root_context()
    try:
        entry = next(
            entry for entry in command_entries(context) if entry.name == "atomize"
        )
    finally:
        context.close()

    expected_copy = {
        "EN": "Immediately atomize the current Context",
        "FR": "Atomiser immédiatement le Context courant",
        "ZH": "立即将当前 Context 原子化",
        "KO": "현재 Context를 독립적으로 검토할 수 있는 Memory로 즉시 atomize",
        "MN": "Одоогийн Context-г тус тусад нь хянах боломжтой Memory болгон шууд atomize",
    }
    for language in HELP_LANGUAGES:
        rendered = "".join(
            text
            for _style, text in _help_group_fragments(
                [(0, entry)],
                title="SEMANTIC TRANSFORMATIONS",
                width=100,
                focused=True,
                selected_index=0,
                expanded_index=None,
                selected_form=None,
                language=language,
            )
        )

        assert "mem atomize" in rendered
        assert expected_copy[language] in rendered
        assert all(terminal_cell_width(line) == 100 for line in rendered.splitlines())


def test_long_and_annotated_command_labels_use_both_record_rows():
    root, context = _root_context()
    try:
        entries = command_entries(context)
    finally:
        context.close()

    selected = {
        entry.name: entry
        for entry in entries
        if entry.name in {"delete", "check-conformance", "config", "ground", "import"}
    }
    rendered = "".join(
        text
        for _style, text in _help_group_fragments(
            list(enumerate(selected.values())),
            title="A–Z",
            width=100,
            focused=True,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    lines = rendered.splitlines()

    expected_labels = {
        "delete": "(remove)",
        "check-": "conformance",
        "config": "(legacy)",
        "ground": "[PARTIAL]",
        "import": "[PARTIAL]",
    }
    for first_row, second_row in expected_labels.items():
        command_index = next(
            index for index, line in enumerate(lines) if f"▸ mem {first_row}" in line
        )
        assert "─┬" in lines[command_index]
        assert second_row in lines[command_index + 1]
        assert "mem " not in lines[command_index + 1]
        assert lines[command_index + 1].index(second_row) == lines[
            command_index
        ].index("mem") + 2
        assert lines[command_index].index("┬") == lines[command_index + 1].index(
            "│" if "│" in lines[command_index + 1] else "└"
        )
    assert all(len(line) == 100 for line in lines)


def test_collapsed_narrow_row_connects_wrapped_summary_and_when_blocks():
    root, context = _root_context()
    try:
        entry = next(
            entry for entry in command_entries(context) if entry.name == "compare"
        )
    finally:
        context.close()

    rendered = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="CHECK, COMPARE & REVIEW",
            width=90,
            focused=False,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    lines = rendered.splitlines()
    command_index = next(
        index for index, line in enumerate(lines) if "▸ mem compare" in line
    )
    best_for_index = next(
        index
        for index, line in enumerate(lines)
        if "Comparing two Contexts as a whole" in line
    )

    assert all(len(line) == 90 for line in lines)
    assert best_for_index > command_index
    connector_start = lines[command_index].index("┬")
    summary_start = lines[command_index].index("Compare Memories")
    when_label_start = lines[best_for_index].index("WHEN ·")
    use_case_start = lines[best_for_index].index("Comparing two Contexts")
    summary_continuation = next(
        line for line in lines if "what appears only on one side." in line
    )
    continuation = next(line for line in lines if "align and differ." in line)
    assert summary_start == connector_start + len("┬ ")
    assert summary_continuation[summary_start:].startswith(
        "differs, and what appears only on one side."
    )
    assert when_label_start == summary_start
    assert use_case_start == when_label_start + len("WHEN · ")
    assert continuation.index("align and differ.") == use_case_start
    assert "└ WHEN ·" in lines[best_for_index]
    assert "│" not in continuation[connector_start : connector_start + 2]
    assert "BEST FOR" not in rendered


def test_expanded_tui_entry_projects_composed_meaning_before_cli_forms():
    root, context = _root_context()
    try:
        entry = next(
            entry for entry in command_entries(context) if entry.name == "update"
        )
    finally:
        context.close()

    rendered = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="SEMANTIC TRANSFORMATIONS",
            width=120,
            focused=True,
            selected_index=0,
            expanded_index=0,
            selected_form=0,
        )
    )

    assert rendered.index("FLOW") < rendered.index("FORM 1")
    assert "Source Context -> decisions -> Target Apply -> receipt" in rendered
    assert "EXECUTION · SEMANTIC" in rendered
    assert "Changes only the local Target after Apply" in rendered
    assert "Updating an existing Context using newly verified Memories." in rendered
    assert "BEST FOR" not in rendered
    assert (
        rendered.count("Updating an existing Context using newly verified Memories.")
        == 1
    )


def test_expanded_add_explains_literal_content_and_copy_or_link_routes():
    root, context = _root_context()
    try:
        entry = next(entry for entry in command_entries(context) if entry.name == "add")
    finally:
        context.close()

    collapsed = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="CREATE, COPY & CONNECT",
            width=120,
            focused=True,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    rendered = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="CREATE, COPY & CONNECT",
            width=120,
            focused=True,
            selected_index=0,
            expanded_index=0,
            selected_form=None,
        )
    )

    assert "COPY OR LINK" not in collapsed
    assert "COPY OR LINK" in rendered
    assert "Memory UID or Context name does not" in rendered
    assert "copy that object; it creates a new Memory containing that text" in rendered
    assert "Branch the containing Context and merge it" in rendered
    assert "copy the Memory content and add it" in rendered
    assert "directly." in rendered
    assert (
        "- EXACT MEMORY OR CONTEXT · Use mem reference to retain an immutable" in rendered
    )
    assert "- LIVE MEMORY · Use mem embed SOURCE:MEMORY" in rendered
    assert "- LIVE CONTEXT · Use mem embed." in rendered
    assert "parent stores" in rendered
    assert "only the Context identity" in rendered
    assert "* EXISTING MEMORY" not in rendered


def test_expanded_init_keeps_parent_context_guidance_out_of_collapsed_row():
    root, context = _root_context()
    try:
        entry = next(
            entry for entry in command_entries(context) if entry.name == "init"
        )
    finally:
        context.close()

    collapsed = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="CREATE, COPY & CONNECT",
            width=120,
            focused=True,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    rendered = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="CREATE, COPY & CONNECT",
            width=120,
            focused=True,
            selected_index=0,
            expanded_index=0,
            selected_form=None,
        )
    )

    assert "PARENT CONTEXTS" not in collapsed
    assert "PARENT CONTEXTS" in rendered
    assert "mem init NAME creates only that exact Context" in rendered
    assert "WITH -P" in rendered
    assert "does not embed children" in rendered


def test_import_keeps_ordinary_copy_and_use_case_with_partial_scope_detail():
    operation = operation_help("import")

    assert operation.summary == (
        "Import a clean-baseline Profile, Context tree, or Memory by value "
        "while preserving resource identity."
    )
    assert operation.use_when == (
        "Bringing externally supplied material into a locally managed store."
    )
    assert operation.maturity == "PARTIAL"
    [detail] = operation.details
    assert detail.kind.value == "LIMITATION"
    assert detail.title == "CURRENT LIMITATION"
    assert "MemCommit-to-MemCommit transfer" in detail.body
    assert "arbitrary documents or Skills" in detail.body


def test_import_partial_tag_is_collapsed_while_its_limitation_is_expanded():
    root, context = _root_context()
    try:
        entry = next(
            entry for entry in command_entries(context) if entry.name == "import"
        )
    finally:
        context.close()

    collapsed = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="CREATE, COPY & CONNECT",
            width=120,
            focused=True,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    expanded = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="CREATE, COPY & CONNECT",
            width=120,
            focused=True,
            selected_index=0,
            expanded_index=0,
            selected_form=None,
        )
    )

    assert "mem import" in collapsed
    assert "[PARTIAL]" in collapsed
    assert "CURRENT LIMITATION" not in collapsed
    assert "CURRENT LIMITATION" in expanded
    assert "MemCommit-to-MemCommit transfer" in expanded


def test_search_and_explain_copy_distinguishes_exact_and_llm_based_routes():
    assert operation_help("find").execution is ExecutionKind.DETERMINISTIC
    assert operation_help("find").best_for == (
        "Locating exact words, identifiers, or text patterns within a selected "
        "Context scope."
    )
    assert operation_help("search").best_for == (
        "Finding relevant Memories through meaning and context, including "
        "related content without obvious keyword overlap."
    )
    assert operation_help("query").summary.startswith("Generate an LLM-based answer")
    assert operation_help("summarize").summary.startswith(
        "Show an LLM-derived overview"
    )

    [query_detail] = operation_help("query").details
    assert query_detail.kind.value == "ACCESS_BOUNDARY"
    assert query_detail.title == "QUERY-ONLY ACCESS"
    assert "QUERY without READ" in query_detail.body
    assert "full underlying policy concealed" in query_detail.body


def test_semantic_transform_and_review_details_preserve_reviewed_boundaries():
    [atomize_routes] = operation_help("atomize").details
    [translation_routes] = operation_help("translate").details
    [impact_invocation] = operation_help("impact").details
    [fit_verdicts] = operation_help("fit").details
    [conformance_comparison] = operation_help("check-conformance").details

    assert atomize_routes.title == "ATOMIZE ROUTES"
    assert "directional Meld" in atomize_routes.options[1].guidance
    assert translation_routes.title == "MATERIALIZATION ROUTES"
    assert [option.label for option in translation_routes.options] == [
        "VIEW",
        "--SAVE-AS",
        "--IN-PLACE",
    ]
    assert impact_invocation.title == "INVOCATION"
    assert "--from or --to" in impact_invocation.options[1].guidance
    assert fit_verdicts.title == "YES, MAY, OR NO"
    assert "multiple entrances" in fit_verdicts.options[1].guidance
    assert "only one entrance" in fit_verdicts.options[2].guidance
    assert conformance_comparison.title == "FIT OR CONFORMANCE"
    assert conformance_comparison.discovery.value == "TOOL_SELECTION"


def test_final_help_categories_match_their_reviewed_runtime_boundaries():
    ground = operation_help("ground")
    log = operation_help("log")
    diff = operation_help("diff")
    undo = operation_help("undo")
    revert = operation_help("revert")
    profile = operation_help("profile")
    provider = operation_help("provider")
    config = operation_help("config")
    eval_operation = operation_help("eval")

    assert ground.summary.startswith("Develop an abstract idea")
    assert ground.maturity == "PARTIAL"
    assert "Ground workspace Contexts" in ground.effect
    assert log.summary == (
        "Print or search recorded Context, Memory, and Profile history."
    )
    assert diff.flow == "Context checkpoint or active Update -> diff report"
    assert undo.summary == "Undo the most recent recorded command as one unit."
    assert "every Context and Memory change" in undo.effect
    assert revert.summary.startswith(
        "Restore the current or an explicit local Context"
    )
    assert "Create, select, and manage" in profile.summary
    assert "Study headings can be renamed" in profile.summary
    assert "backend semantic operations should use" in provider.best_for
    assert "legacy low-level interface" in config.best_for
    assert "existing semantic evaluation campaigns" in eval_operation.summary


def test_final_help_categories_expose_exact_on_demand_details():
    [log_routes] = operation_help("log").details
    [revert_routes] = operation_help("revert").details
    [profile_management] = operation_help("profile").details
    [provider_actions] = operation_help("provider").details
    [evaluation_scope] = operation_help("eval").details

    assert log_routes.title == "LOG ROUTES"
    assert [option.label for option in log_routes.options] == [
        "CONTEXT CHECKPOINTS",
        "MEMORY LINEAGE",
        "SEMANTIC SEARCH",
        "PROFILE ATTEMPTS",
        "STUDY ACTIONS",
    ]
    assert revert_routes.title == "REVERT ROUTES"
    assert [option.label for option in revert_routes.options] == [
        "EXACT CHECKPOINT",
        "INTERACTIVE",
        "NATURAL-LANGUAGE",
        "--KEEP",
    ]
    assert profile_management.title == "PROFILE MANAGEMENT"
    assert "remove, not delete" in profile_management.explanation
    assert [option.label for option in profile_management.options] == [
        "CREATE",
        "SELECT",
        "RENAME",
        "RENAME STUDY",
        "REMOVE",
        "REMOVE STUDY",
    ]
    assert provider_actions.title == "PROVIDER ACTIONS"
    assert "synthetic strict-schema" in provider_actions.options[2].guidance
    assert evaluation_scope.title == "EVALUATION SCOPE"
    assert "general evaluation interface remains future work" in (
        evaluation_scope.explanation
    )


def test_eval_and_config_are_compactly_marked_legacy():
    root, context = _root_context()
    try:
        entries = {entry.name: entry for entry in command_entries(context)}
    finally:
        context.close()

    assert entries["config"].annotation == "legacy"
    assert entries["eval"].annotation == "legacy"
