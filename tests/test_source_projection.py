import click

from memcommit.adapters.console.commands.search.search_workbench import (
    SearchResult,
    _has_granted_materialization_source,
)
from memcommit.core.context_targeting.catalog import (
    grant_navigation_annotation,
    grant_navigation_capability_labels,
)
from memcommit.core.context_targeting.tui.rendering import (
    ContextTreeRowDecoration,
    render_context_tree_rows,
)
from memcommit.core.context_targeting.tui.tree import (
    ContextTreeState,
    build_context_tree,
)
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
    semantic_source_role,
)
from memcommit.source_projection.console import (
    styled_source_reach_label,
    styled_source_relationship_label,
)
from memcommit.source_projection.model import (
    SourceAccess,
    SourceDisplayFacts,
    SourceForm,
    SourceReferenceRow,
    SourceReach,
    SourceState,
    context_access_facts,
)
from memcommit.source_projection.presentation import (
    SourceReferenceLayout,
    SourceTokenRole,
    render_source_reference_row,
    source_annotation_text,
    source_object_label,
    source_reach_label,
    source_relationship_label,
    source_display_text,
    source_display_tokens,
)
from memcommit.source_projection.tui import render_source_display_tokens


def test_source_display_uses_one_axis_order_and_canonical_vocabulary():
    facts = SourceDisplayFacts(
        access=SourceAccess.READ_GRANT,
        reach=SourceReach.VIA_EMBED,
        form=SourceForm.MEMORY_REF,
        states=(SourceState.NOT_INCLUDED, SourceState.DANGLING),
        permissions=("READ", "DERIVE", "QUERY"),
    )

    assert source_display_text(facts, include_permissions=True) == (
        "READ GRANT · PERMISSIONS READ + DERIVE + QUERY · "
        "VIA EMBED · memory ref · DANGLING · NOT INCLUDED"
    )

    assert source_object_label(facts) == "memory ref"
    assert source_object_label(facts, title=True) == "Memory ref"
    assert source_annotation_text(facts, include_permissions=True) == (
        "READ GRANT · PERMISSIONS READ + DERIVE + QUERY · "
        "VIA EMBED · DANGLING · NOT INCLUDED"
    )


def test_relationship_labels_and_colors_distinguish_live_embed_from_snapshot():
    embedded = SourceDisplayFacts(form=SourceForm.MEMORY_EMBED)
    reference = SourceDisplayFacts(form=SourceForm.MEMORY_REFERENCE)

    assert source_relationship_label(embedded) == "embedded"
    assert source_relationship_label(reference) == "reference"
    assert semantic_source_role(embedded) is SemanticColorRole.EMBED
    assert semantic_source_role(reference) is SemanticColorRole.REFERENCE
    assert click.unstyle(styled_source_relationship_label(embedded)) == "embedded"
    assert click.unstyle(styled_source_relationship_label(reference)) == "reference"
    assert (
        f"\x1b[38;2;{';'.join(map(str, semantic_color_rgb(SemanticColorRole.EMBED)))}m"
        in styled_source_relationship_label(embedded)
    )
    assert (
        f"\x1b[38;2;{';'.join(map(str, semantic_color_rgb(SemanticColorRole.REFERENCE)))}m"
        in styled_source_relationship_label(reference)
    )


def test_reach_labels_keep_context_identity_separate_from_embed_color():
    assert source_reach_label(SourceReach.DESCENDANT) == "DESCENDANT"
    assert source_reach_label(SourceReach.VIA_EMBED) == "VIA EMBED"
    assert click.unstyle(styled_source_reach_label(SourceReach.VIA_EMBED)) == (
        "VIA EMBED"
    )
    assert (
        f"\x1b[38;2;{';'.join(map(str, semantic_color_rgb(SemanticColorRole.EMBED)))}m"
        in styled_source_reach_label(SourceReach.VIA_EMBED)
    )


def test_source_reference_row_folds_content_and_keeps_owner_alias_separate():
    row = SourceReferenceRow(
        number=1,
        content="First line\n  second\tline",
        uid="6fad23ab-full-memory-uid",
        context_name="practice/source",
        alias="m5",
    )

    assert render_source_reference_row(row) == (
        "[1] First line second line — 6fad23ab, practice/source, m5"
    )


def test_source_reference_row_retains_memory_ref_owner_and_source_identity():
    row = SourceReferenceRow(
        number=2,
        content="Referenced content.",
        uid="owner-ref-uid",
        context_name="target/context",
        source_uid="source-memory-uid",
        source_context_name="source/context",
    )

    assert render_source_reference_row(row) == (
        "[2] Referenced content. — owner-re, target/context → source-m, source/context"
    )


def test_source_reference_row_supports_identity_content_location_arrangement():
    row = SourceReferenceRow(
        number=1,
        content="First line\n  second line.",
        uid="6fad23ab-full-memory-uid",
        context_name="practice/source",
        alias="m5",
    )

    assert (
        render_source_reference_row(
            row,
            layout=SourceReferenceLayout.IDENTITY_FIRST,
        )
        == "1 [6fad23ab] First line second line. [practice/source m5]"
    )


def test_source_reference_row_marks_optional_content_elision():
    row = SourceReferenceRow(
        number=3,
        content="A deliberately long supporting passage.",
        uid="memory-uid",
        context_name="scope",
    )

    assert render_source_reference_row(row, content_character_limit=16) == (
        "[3] A deliberately… — memory-u, scope"
    )


def test_dense_context_labels_omit_defaults_but_object_lists_can_request_them():
    facts = SourceDisplayFacts()

    assert source_display_text(facts) == ""
    assert source_display_text(facts, include_defaults=True) == (
        "OWNED · DIRECT · context"
    )
    assert source_object_label(facts) == "context"


def test_query_grant_is_distinct_from_read_grant_and_query_view_form():
    facts = context_access_facts(
        granted=True,
        permission="QUERY",
        permissions=("QUERY",),
        form=SourceForm.QUERY_VIEW,
    )

    assert source_display_text(facts) == "QUERY GRANT · query view"


def test_tui_token_roles_share_palette_and_focus_can_override_every_token():
    tokens = source_display_tokens(
        SourceDisplayFacts(
            access=SourceAccess.READ_GRANT,
            form=SourceForm.MEMORY_REF,
            states=(SourceState.DANGLING,),
        )
    )

    assert [token.role for token in tokens] == [
        SourceTokenRole.ACCESS,
        SourceTokenRole.FORM,
        SourceTokenRole.STATE,
    ]
    assert render_source_display_tokens(tokens) == [
        ("class:source-access", "READ GRANT"),
        ("", " · "),
        ("class:reference", "memory ref"),
        ("", " · "),
        ("class:source-state", "DANGLING"),
    ]
    assert {
        style
        for style, _text in render_source_display_tokens(
            tokens,
            override_style="class:memcommit.table.selected",
        )
    } == {"class:memcommit.table.selected"}


def test_shared_context_tree_renders_typed_source_tokens_not_raw_copy():
    state = ContextTreeState.create(build_context_tree(("alpha",)), selected="alpha")

    fragments = render_context_tree_rows(
        state,
        lambda _row, _cursor: ContextTreeRowDecoration(
            annotation=SourceDisplayFacts(
                access=SourceAccess.READ_GRANT,
                reach=SourceReach.VIA_EMBED,
            )
        ),
    )

    rendered = "".join(text for _style, text in fragments)
    assert rendered.endswith("alpha  READ GRANT · VIA EMBED")
    assert ("class:source-access", "READ GRANT") in fragments
    assert ("class:source-reach", "VIA EMBED") in fragments


def test_grant_navigation_separates_ownership_from_compact_capabilities():
    tokens = grant_navigation_annotation(
        (
            "CREATE",
            "READ",
            "EMBED",
            "UPDATE",
            "DELETE",
            "QUERY",
            "DERIVE",
            "COMBINE",
            "EXPORT",
            "ACCEPT_DERIVED",
            "SAVE_BOUND_ANALYSIS",
            "SAVE_ANALYSIS",
        )
    )

    assert grant_navigation_capability_labels(
        (
            "CREATE",
            "READ",
            "UPDATE",
            "DELETE",
            "QUERY",
            "EXPORT",
        )
    ) == ("READ", "QUERY", "EDIT", "DELETE", "EXPORT")
    assert [token.role for token in tokens] == [
        SourceTokenRole.OWNERSHIP,
        SourceTokenRole.CAPABILITY,
    ]
    assert render_source_display_tokens(tokens) == [
        ("class:source-ownership", "GRANT"),
        ("", " · "),
        ("class:source-capability", "READ + QUERY + EDIT + DELETE + EXPORT"),
    ]


def test_shared_context_tree_places_grant_before_the_public_name():
    state = ContextTreeState.create(build_context_tree(("public",)), selected="public")

    fragments = render_context_tree_rows(
        state,
        lambda _row, _cursor: ContextTreeRowDecoration(
            annotation=grant_navigation_annotation(("READ", "EXPORT"))
        ),
    )

    rendered = "".join(text for _style, text in fragments)
    assert rendered.endswith("· GRANT public  READ + EXPORT")
    assert ("class:source-ownership", "GRANT") in fragments
    assert ("class:source-capability", "READ + EXPORT") in fragments


def test_find_authority_gate_uses_frozen_names_not_display_wording():
    result = SearchResult(
        context_name="public/source",
        kind="memory",
        uid="memory-1",
        content="evidence",
    )

    assert _has_granted_materialization_source((result,), {"public/source"})
    assert not _has_granted_materialization_source((result,), set())
