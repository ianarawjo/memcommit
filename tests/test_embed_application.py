"""Application-boundary tests for Embed independent of Store and terminal."""

from __future__ import annotations

from dataclasses import replace

import pytest

from memcommit.application.operations.embed.application import (
    EmbedError,
    EmbedPlacement,
    EmbedRequest,
    EmbedResult,
    FrozenEmbedPlan,
    prepare_embed,
    run_embed,
)


class _FakeEmbedPort:
    def __init__(self) -> None:
        self.applied: list[FrozenEmbedPlan] = []

    def freeze(self, request: EmbedRequest) -> FrozenEmbedPlan:
        return FrozenEmbedPlan(
            request=request,
            child_name="source",
            child_uid="child-uid",
            child_digest="child-digest",
            into_name="target",
            into_uid="target-uid",
            into_digest="target-digest",
            placement=EmbedPlacement(1, "before-uid", "after-uid"),
            item_count=2,
            token=self,
        )

    def apply(self, plan: FrozenEmbedPlan) -> EmbedResult:
        self.applied.append(plan)
        return EmbedResult(
            child_name=plan.child_name,
            child_uid=plan.child_uid,
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            placement=plan.placement,
            checkpoint_uid="checkpoint-uid",
        )


def test_application_freezes_and_applies_one_typed_embed() -> None:
    port = _FakeEmbedPort()
    request = EmbedRequest("source", "target", before="after-uid")

    plan = prepare_embed(request, port=port)
    result = run_embed(request, port=port, frozen_plan=plan)

    assert port.applied == [plan]
    assert result.placement == EmbedPlacement(1, "before-uid", "after-uid")
    assert result.checkpoint_uid == "checkpoint-uid"


def test_application_rejects_two_anchors_before_opening_a_port() -> None:
    port = _FakeEmbedPort()

    with pytest.raises(EmbedError, match="only one"):
        prepare_embed(
            EmbedRequest("source", "target", before="a", after="b"),
            port=port,
        )

    assert port.applied == []


def test_application_rejects_a_receipt_that_does_not_match_the_plan() -> None:
    class WrongReceiptPort(_FakeEmbedPort):
        def apply(self, plan: FrozenEmbedPlan) -> EmbedResult:
            return replace(super().apply(plan), child_uid="other")

    port = WrongReceiptPort()
    request = EmbedRequest("source", "target")

    with pytest.raises(EmbedError, match="does not match"):
        run_embed(request, port=port)
