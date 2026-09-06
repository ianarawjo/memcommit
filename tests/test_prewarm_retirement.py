"""Retired Study acceleration must not enter current execution or clean imports."""

import importlib.util
import inspect

from memcommit.adapters.python_api import MemCommitClient
from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisOpenRequest,
)
from memcommit.application.operations.resource_import.profile import (
    _copy_store_baseline,
    baseline_store_digest,
)
from memcommit.persistence.store import MemoryStore
import memcommit.application.capabilities.ops as ops


def test_retired_package_and_atomize_switch_are_absent():
    assert importlib.util.find_spec("memcommit.study_scenarios.legacy.prewarm") is None
    assert (
        "use_prepared"
        not in inspect.signature(MemCommitClient.open_atomize_analysis).parameters
    )
    assert (
        "allow_prepared" not in inspect.signature(AtomizeAnalysisOpenRequest).parameters
    )


def test_clean_profile_import_ignores_old_bundles_but_preserves_scenario_data(
    isolated_store,
    tmp_path,
    retired_study_artifacts,
):
    store = MemoryStore(root=isolated_store)
    identities = {}
    for name in ("practice", "task-1", "task-2", "task-3"):
        context = ops.init(name)
        ops.add(context, f"Unchanged {name} scenario content.")
        store.save(context)
        identities[name] = context.to_dict()
    store.set_current("practice")
    before = baseline_store_digest(isolated_store)
    # Prewarm data cannot invalidate a clean baseline digest or be copied.
    extra = isolated_store / "study-semantic-prewarm" / "extra.json"
    extra.write_text('{"obsolete": true}')
    assert baseline_store_digest(isolated_store) == before
    destination = tmp_path / "clean-copy"
    _copy_store_baseline(isolated_store, destination)
    copied = MemoryStore(root=destination)
    assert copied.current_context_name() == "practice"
    for name, expected in identities.items():
        assert copied.load_direct(name).to_dict() == expected
    for path in retired_study_artifacts:
        assert not (destination / path.relative_to(isolated_store)).exists()
    assert not (destination / "study-semantic-prewarm").exists()


def test_agent_rejects_retired_option_before_provider(isolated_store):
    from memcommit.adapters.agent.atomize import AtomizeAgentAdapter

    def forbidden_provider():
        raise AssertionError("Invalid retired option must not reach inference")

    client = MemCommitClient(
        root=isolated_store, semantic_provider_factory=forbidden_provider
    )
    result = AtomizeAgentAdapter(client).invoke(
        {"version": 1, "kind": "open", "use_prepared": True}
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_request"
