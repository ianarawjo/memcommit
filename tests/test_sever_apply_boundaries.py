"""Dependency direction and recovery metadata contracts for Sever Apply."""

from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest

from memcommit.application.operations.sever.apply.checkpoints import (
    checkpoint_args_match,
)


@pytest.mark.parametrize("module", ["inputs", "apply.projection", "apply.execution"])
def test_apply_dependencies_do_not_load_runtime_or_terminal(module):
    subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import importlib
import sys
importlib.import_module('memcommit.application.operations.sever.{module}')
assert 'memcommit.application.operations.sever.runtime' not in sys.modules
assert not any(name.startswith(('memcommit.adapters.console', 'prompt_toolkit', 'typer')) for name in sys.modules)
""",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )


def test_runtime_compatibility_names_are_the_same_implementations():
    from memcommit.application.operations.sever import runtime
    from memcommit.application.operations.sever.apply.execution import (
        MemoryStoreSeverOutputPort,
    )
    from memcommit.application.operations.sever.inputs import (
        MemoryStoreSeverInputPort,
        capture_sever_binding,
    )

    assert runtime.MemoryStoreSeverOutputPort is MemoryStoreSeverOutputPort
    assert runtime.MemoryStoreSeverInputPort is MemoryStoreSeverInputPort
    assert runtime.capture_sever_binding is capture_sever_binding


@pytest.mark.parametrize("save_mode", ["SELF_SAVE", "OTHER_SAVE"])
def test_checkpoint_compatibility_retains_exact_review_identity(save_mode):
    expected = {
        "sever": {"save_mode": save_mode, "session_digest": "reviewed-digest"},
        **(
            {"command_contexts": [{"uid": "source-uid", "name": "source"}]}
            if save_mode == "SELF_SAVE"
            else {"context_creation": {"version": 1, "context_uid": "result-uid"}}
        ),
    }
    original = deepcopy(expected)
    legacy = deepcopy(expected)
    if save_mode == "SELF_SAVE":
        del legacy["command_contexts"]
    else:
        del legacy["sever"]["save_mode"]
    assert checkpoint_args_match(expected, expected, save_mode=save_mode)
    assert checkpoint_args_match(legacy, expected, save_mode=save_mode)

    for shape in (expected, legacy):
        stale = deepcopy(shape)
        stale["sever"]["session_digest"] = "different-review"
        assert not checkpoint_args_match(stale, expected, save_mode=save_mode)
    assert not checkpoint_args_match(None, expected, save_mode=save_mode)
    assert expected == original


def test_self_save_checkpoint_cannot_change_its_owner_membership():
    expected = {
        "sever": {"save_mode": "SELF_SAVE"},
        "command_contexts": [{"uid": "source-uid", "name": "source"}],
    }
    changed = deepcopy(expected)
    changed["command_contexts"].append({"uid": "other-uid", "name": "other"})
    assert not checkpoint_args_match(changed, expected, save_mode="SELF_SAVE")
