"""Public positional Context operand grammar."""

from __future__ import annotations

import pytest
from memcommit.commands.compare import (
    CompareCommandError,
    _resolve_endpoint_syntax,
)
from memcommit.commands.context_operand import choose_context_operand
from memcommit.update_endpoints import choose_update_endpoint_operands

def test_unary_context_operand_defaults_to_current_and_rejects_duplicates():
    assert choose_context_operand(None, option=None) is None
    assert choose_context_operand("scope/target", option=None) == "scope/target"
    assert choose_context_operand(None, option="scope/target") == "scope/target"
    with pytest.raises(ValueError, match="both positionally"):
        choose_context_operand("scope/a", option="scope/b")


def test_compare_positional_arity_preserves_current_reference():
    assert _resolve_endpoint_syntax(["peer"], from_=None, to=None) == (None, "peer")
    assert _resolve_endpoint_syntax(["reference", "peer"], from_=None, to=None) == (
        "reference",
        "peer",
    )
    with pytest.raises(CompareCommandError, match="cannot be combined"):
        _resolve_endpoint_syntax(["peer"], from_=None, to="other")


def test_update_positionals_require_a_complete_pair():
    assert choose_update_endpoint_operands(
        ["source", "target"],
        source_option=None,
        target_option=None,
    ) == ("source", "target")
    assert choose_update_endpoint_operands(
        None,
        source_option="source",
        target_option=None,
    ) == ("source", None)
    with pytest.raises(ValueError, match="exactly SOURCE TARGET"):
        choose_update_endpoint_operands(
            ["source"],
            source_option=None,
            target_option=None,
        )
