"""Public positional Context operand grammar."""

from __future__ import annotations

import pytest
from memcommit.commands.compare.command import (
    CompareCommandError,
    _resolve_endpoint_syntax,
)
from memcommit.commands.shared.context_operand import choose_context_operand
from memcommit.context_targeting.operands import choose_endpoint_operand
from memcommit.context_targeting.model import ExistingContextOperand, InlineTextOperand
from memcommit.context_targeting.operands import classify_context_or_inline_text_operand
from memcommit.update_endpoints import choose_update_endpoint_operands


def test_unary_context_operand_defaults_to_current_and_rejects_duplicates():
    assert choose_context_operand(None, option=None) is None
    assert choose_context_operand("scope/target", option=None) == "scope/target"
    assert choose_context_operand(None, option="scope/target") == "scope/target"
    with pytest.raises(ValueError, match="both positionally"):
        choose_context_operand("scope/a", option="scope/b")


def test_directional_endpoint_options_never_use_silent_precedence():
    assert (
        choose_endpoint_operand(
            "source",
            role="Source",
            options=(("--from", None),),
        )
        == "source"
    )
    assert (
        choose_endpoint_operand(
            None,
            role="Target",
            options=(("--into", None), ("--to", "target")),
        )
        == "target"
    )
    with pytest.raises(ValueError, match="both positionally and with --from"):
        choose_endpoint_operand(
            "source",
            role="Source",
            options=(("--from", "other"),),
        )
    with pytest.raises(ValueError, match="--into and --to"):
        choose_endpoint_operand(
            None,
            role="Target",
            options=(("--into", "one"), ("--to", "two")),
        )


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


def test_update_opt_in_single_source_uses_named_or_current_target():
    assert choose_update_endpoint_operands(
        ["source"],
        source_option=None,
        target_option="target",
        allow_single_source=True,
    ) == ("source", "target")
    assert choose_update_endpoint_operands(
        ["source"],
        source_option=None,
        target_option=None,
        allow_single_source=True,
    ) == ("source", None)
    with pytest.raises(ValueError, match="both positionally and with --from"):
        choose_update_endpoint_operands(
            ["source"],
            source_option="other",
            target_option=None,
            allow_single_source=True,
        )
    with pytest.raises(ValueError, match="SOURCE, or SOURCE TARGET"):
        choose_update_endpoint_operands(
            ["want", "to", "make", "fruits"],
            source_option=None,
            target_option=None,
            allow_single_source=True,
        )


def test_context_or_inline_text_classification_fails_safe_for_locator_typos():
    existing = {"practice/rules", "legacy invalid name"}

    def classify(value):
        return classify_context_or_inline_text_operand(
            value,
            current="practice",
            context_exists=existing.__contains__,
        )

    assert classify("practice/rules") == ExistingContextOperand("practice/rules")
    assert classify("practice/rulse") == ExistingContextOperand("practice/rulse")
    assert classify("../rulse") == ExistingContextOperand("../rulse")
    assert classify("legacy invalid name") == ExistingContextOperand(
        "legacy invalid name"
    )
    assert classify("make every final word a fruit") == InlineTextOperand(
        "make every final word a fruit"
    )
