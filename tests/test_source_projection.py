from memcommit.commands.find_search_workbench import (
    FindSearchResult,
    _has_granted_materialization_source,
)
from memcommit.context_targeting.tui.rendering import (
    ContextTreeRowDecoration,
    render_context_tree_rows,
)
from memcommit.context_targeting.tui.tree import ContextTreeState, build_context_tree
from memcommit.source_projection.model import (
    SourceAccess,
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
    context_access_facts,
)
from memcommit.source_projection.presentation import (
    SourceTokenRole,
    source_annotation_text,
    source_object_label,
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
        permissions=("READ", "DERIVE", "SESSION_LOG"),
    )

    assert source_display_text(facts, include_permissions=True) == (
        "READ GRANT · PERMISSIONS READ + DERIVE + SAVE QUERY SESSION · "
        "VIA EMBED · memory ref · DANGLING · NOT INCLUDED"
    )

    assert source_object_label(facts) == "memory ref"
    assert source_object_label(facts, title=True) == "Memory ref"
    assert source_annotation_text(facts, include_permissions=True) == (
        "READ GRANT · PERMISSIONS READ + DERIVE + SAVE QUERY SESSION · "
        "VIA EMBED · DANGLING · NOT INCLUDED"
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


def test_find_authority_gate_uses_frozen_names_not_display_wording():
    result = FindSearchResult(
        context_name="public/source",
        kind="memory",
        uid="memory-1",
        content="evidence",
    )

    assert _has_granted_materialization_source((result,), {"public/source"})
    assert not _has_granted_materialization_source((result,), set())
