"""Public positional Context operand grammar."""

from __future__ import annotations

import pytest
from memcommit.adapters.console.commands.compare.command import (
    CompareCommandError,
    _resolve_endpoint_syntax,
)
from memcommit.adapters.console.coordination.context_operand import choose_context_operand
from memcommit.adapters.console.coordination.endpoint_operand import (
    choose_endpoint_operand,
)
from memcommit.application.capabilities.context_operand_classification import (
    classify_context_or_inline_text_operand,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    resolve_existing_memorization_target,
    resolve_existing_semantic_result_endpoints,
)
from memcommit.core.context_targeting.model import ExistingContextOperand, InlineTextOperand
from memcommit.adapters.console.commands.update.endpoint_operands import (
    choose_update_endpoint_operands,
    resolve_update_endpoint_accesses,
)
from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore


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


def test_update_endpoints_share_name_relative_and_context_uid_resolution(
    isolated_store,
):
    store = MemoryStore()
    source = Context(
        uid="2a4dc8ab-1111-4111-8111-111111111111",
        name="practice/coffee/source",
    )
    target = Context(
        uid="bbbbbbbb-1111-4111-8111-111111111111",
        name="practice/coffee/target",
    )
    store.save(source)
    store.save(target)
    store.set_current(target.name)

    endpoints = resolve_update_endpoint_accesses(
        store,
        source_locator="2a4dc8ab",
        target_locator=".",
        current=target.name,
    )

    assert endpoints.source.name == source.name
    assert endpoints.target.name == target.name


def test_semantic_result_endpoints_resolve_read_source_and_local_target_uids(
    isolated_store,
):
    store = MemoryStore()
    source = Context(
        uid="2a4dc8ab-1111-4111-8111-111111111111",
        name="derive/source",
    )
    target = Context(
        uid="bbbbbbbb-1111-4111-8111-111111111111",
        name="derive/target",
    )
    store.save(source)
    store.save(target)
    store.set_current(source.name)

    endpoints = resolve_existing_semantic_result_endpoints(
        store,
        source_locator=source.uid[:8],
        target_locator=target.uid[:8],
        current=source.name,
    )

    assert endpoints.source_name == source.name
    assert endpoints.target_name == target.name
    assert resolve_existing_memorization_target(
        store,
        target_locator=target.uid[:8],
        current=source.name,
    ) == target.name


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
