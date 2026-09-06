"""Contracts for Reference's form exact-Memory endpoint setup."""

from __future__ import annotations

import pytest

from memcommit.adapters.console.commands.reference.command_codec import (
    REFERENCE_COMMAND_FORM,
    build_review,
    parse_endpoint_argv,
)
from memcommit.adapters.console.commands.reference.endpoint_setup import (
    ReferenceTuiSetup,
    reference_endpoint_setup_spec,
)
from memcommit.adapters.console.terminal.components.command_editor import (
    format_exact_command,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointSetupDraft,
    EndpointSetupValue,
)


MEMORY_UID = "abcd1234-0000-4000-8000-000000000000"


def _draft() -> EndpointSetupDraft:
    return EndpointSetupDraft(
        "REFERENCE",
        (
            EndpointSetupValue("TARGET", "workspace"),
            EndpointSetupValue(
                "SOURCE",
                "shared/source",
                memory_uid=MEMORY_UID,
            ),
        ),
    )


def test_reference_setup_is_one_form_target_then_exact_memory_form() -> None:
    setup = ReferenceTuiSetup(
        names=("workspace",),
        selected_source="shared/source",
        selected_target="workspace",
        current_context="workspace",
        memory_source_names=("shared/source", "workspace"),
        memory_source_selectable_names=frozenset({"shared/source", "workspace"}),
        selected_memory_source="shared/source",
    )

    spec = reference_endpoint_setup_spec(setup)

    assert spec.screen_layout == "FORM"
    assert tuple(mode.uid for mode in spec.modes) == ("REFERENCE",)
    assert spec.active_role_uids("REFERENCE") == ("TARGET", "SOURCE")
    assert spec.role_label("REFERENCE", "TARGET") == "TARGET CONTEXT"
    assert spec.role_label("REFERENCE", "SOURCE") == "SOURCE MEMORY"
    assert spec.role_allows_descendants("REFERENCE", "SOURCE") is False
    assert spec.role_allows_memory_focus("REFERENCE", "SOURCE") is True
    assert spec.roles[0].names == ("workspace",)
    assert spec.roles[1].memory_required is True
    assert spec.roles[1].memory_unselected_label == "CHOOSE MEMORY"
    assert spec.command_ready_hint == "ENTER TO PROCEED"


def test_reference_command_codec_round_trips_the_complete_exact_memory_form() -> None:
    review = build_review(_draft())

    assert format_exact_command(review) == (
        "mem reference abcd1234-0000-4000-8000-000000000000 "
        "--from shared/source --into workspace"
    )
    assert parse_endpoint_argv(review.argv) == _draft()
    assert REFERENCE_COMMAND_FORM.command == ("mem", "reference")


def test_reference_command_codec_rejects_context_snapshot_scope() -> None:
    with pytest.raises(ValueError, match="does not accept --recursive"):
        parse_endpoint_argv(
            (
                "mem",
                "reference",
                "shared/source",
                "--into",
                "workspace",
                "--recursive",
            )
        )


def test_reference_review_requires_one_exact_memory() -> None:
    with pytest.raises(ValueError, match="SOURCE MEMORY"):
        build_review(
            EndpointSetupDraft(
                "REFERENCE",
                (
                    EndpointSetupValue("TARGET", "workspace"),
                    EndpointSetupValue("SOURCE", "shared/source"),
                ),
            )
        )
