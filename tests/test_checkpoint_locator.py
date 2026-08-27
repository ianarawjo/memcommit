"""Typed Context/checkpoint locator boundaries."""

from __future__ import annotations

import pytest

from memcommit.core.context_targeting.checkpoint import (
    resolve_local_checkpoint_target,
    resolve_local_context_checkpoint_target,
)
from memcommit.core.context_targeting.model import CheckpointTarget, ContextTarget


class Store:
    def __init__(self, records):
        self.records = records

    def list_context_names(self):
        return list(self.records)

    def list_checkpoints(self, name):
        return self.records[name]


def test_bare_checkpoint_prefix_resolves_one_exact_owner():
    store = Store(
        {
            "source": [{"uid": "017714b1-0000-4000-8000-000000000000"}],
            "result": [{"uid": "abcdef12-0000-4000-8000-000000000000"}],
        }
    )

    assert resolve_local_context_checkpoint_target(
        store,
        "017714b1",
        current="source",
    ) == CheckpointTarget(
        "source",
        "017714b1-0000-4000-8000-000000000000",
    )


def test_relative_operand_remains_context_only():
    store = Store(
        {
            "task/current": [],
            "task/archive": [{"uid": "abcdef12-0000-4000-8000-000000000000"}],
        }
    )

    assert resolve_local_context_checkpoint_target(
        store,
        "../archive",
        current="task/current",
    ) == ContextTarget("task/archive")


def test_global_checkpoint_prefix_rejects_multiple_owners():
    store = Store(
        {
            "source": [{"uid": "017714b1-0000-4000-8000-000000000000"}],
            "result": [{"uid": "017714b1-1111-4000-8000-000000000000"}],
        }
    )

    with pytest.raises(ValueError, match="matches 2 candidates"):
        resolve_local_checkpoint_target(store, "017714b1")
