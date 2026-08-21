"""Shared semantic palette contracts for console and TUI adapters."""

from memcommit.interfaces.console.theme import (
    SemanticColorRole,
    semantic_action_role,
    semantic_color_hex,
    semantic_color_rgb,
    semantic_judgment_role,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    semantic_role_style,
)


def test_history_action_aliases_resolve_without_classifying_mixed_operations():
    expected = {
        "init": SemanticColorRole.CREATE,
        "CREATED": SemanticColorRole.CREATE,
        "add": SemanticColorRole.ADD,
        "SURVIVOR": SemanticColorRole.ADD,
        "SURVIVORS": SemanticColorRole.ADD,
        "mem embed": SemanticColorRole.EMBED,
        "EDITED": SemanticColorRole.EDIT,
        "delete": SemanticColorRole.REMOVE,
        "ABSORB": SemanticColorRole.REMOVE,
        "ABSORBED": SemanticColorRole.REMOVE,
        "mem undo ← mem remove": SemanticColorRole.UNDO,
        "redo": SemanticColorRole.REDO,
        "checkpoint": SemanticColorRole.HISTORY,
    }

    assert {label: semantic_action_role(label) for label in expected} == expected
    assert semantic_action_role("update") is None
    assert semantic_action_role("atomize") is None


def test_judgments_have_distinct_roles_without_reusing_action_meaning():
    assert semantic_judgment_role("YES") is SemanticColorRole.JUDGMENT_YES
    assert semantic_judgment_role("may") is SemanticColorRole.JUDGMENT_MAY
    assert semantic_judgment_role(" NO ") is SemanticColorRole.JUDGMENT_NO
    assert semantic_judgment_role("STALE") is None


def test_console_and_tui_resolve_the_same_semantic_foregrounds():
    for role in SemanticColorRole:
        assert semantic_color_rgb(role) == tuple(
            bytes.fromhex(semantic_color_hex(role)[1:])
        )
        style = semantic_role_style(role)
        attrs = SEMANTIC_VIEWER_STYLE.get_attrs_for_style_str(style)
        assert attrs.color == semantic_color_hex(role)[1:]


def test_source_access_and_capabilities_share_teal_but_grant_stays_neutral():
    capability = semantic_color_hex(SemanticColorRole.CAPABILITY)[1:]
    grant = semantic_color_hex(SemanticColorRole.GRANT)[1:]

    assert (
        MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str("class:source-access").color
        == capability
    )
    assert (
        MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str("class:source-capability").color
        == capability
    )
    assert (
        MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str("class:source-ownership").color
        == grant
    )
    assert grant != capability


def test_context_navigation_grant_category_uses_the_shared_green_role():
    expected = semantic_color_hex(SemanticColorRole.NAVIGATION_GRANT)[1:]

    assert (
        MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str("class:context-grant-token").color
        == expected
    )
