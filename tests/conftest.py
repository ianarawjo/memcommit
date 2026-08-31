"""
Shared fixtures for memcommit tests.

The most important fixture is `isolated_store`, which redirects memcommit's
module-level storage paths to a temporary directory so tests never touch the
real ~/.mem store.
"""

import json

import pytest
import memcommit.application.capabilities.semantic.prompt_policy as semantic_prompt_policy_module
import memcommit.persistence.store as store_module
from memcommit.application.operations.profile.config import virtual_authoring_registry


class _RationaleFixtureProvider:
    """Keep ordinary CLI tests deterministic and subscription-free."""

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "rationale provenance"
        assert output_schema is not None
        payload = json.loads(prompt.split("RATIONALE PAYLOAD:\n", 1)[1])
        request = payload["request"]
        limit = request["length"]["limit"]
        unit = request["length"]["unit"]
        candidates = (
            "This Memory came from its retained source and follows the recorded lifecycle.",
            "This Memory follows its retained history.",
            "Recorded provenance.",
            "Recorded.",
            "A",
        )

        def measure(value):
            if unit == "characters":
                return len(value)
            if unit == "bytes":
                return len(value.encode("utf-8"))
            return len(value.split())

        provenance = next(value for value in candidates if measure(value) <= limit)
        return json.dumps({"provenance": provenance})


@pytest.fixture(autouse=True)
def replace_rationale_subscription_provider(monkeypatch):
    """No ordinary test may accidentally start a live Rationale provider turn."""

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.history_recovery.inspection.rationale.command.connect_semantic_provider",
        _RationaleFixtureProvider,
    )


@pytest.fixture(autouse=True)
def disable_real_command_attempt_log(monkeypatch):
    """Keep ordinary CliRunner tests from publishing host audit records."""
    monkeypatch.setenv("MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG", "1")


@pytest.fixture(autouse=True)
def isolate_default_semantic_prompt_policy(monkeypatch):
    """Keep ordinary tests independent of the developer's active Profile."""

    monkeypatch.setattr(
        semantic_prompt_policy_module,
        "load_profile_registry",
        virtual_authoring_registry,
    )


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    """Redirect MemoryStore to a fresh temporary directory for each test."""
    store_dir = tmp_path / ".mem"
    contexts_dir = store_dir / "contexts"
    query_sources_dir = store_dir / "query-sources"
    state_file = store_dir / "state.json"
    impact_plan_file = store_dir / "impact-plan.json"
    staged_update_file = store_dir / "staged-update.json"
    review_session_file = store_dir / "review-session.json"
    atomize_analyses_dir = store_dir / "atomize-analyses"
    atomize_workbenches_dir = store_dir / "atomize-workbenches"
    meld_sessions_dir = store_dir / "meld-sessions"

    monkeypatch.setattr(store_module, "STORE_DIR", store_dir)
    monkeypatch.setattr(store_module, "CONTEXTS_DIR", contexts_dir)
    monkeypatch.setattr(store_module, "QUERY_SOURCES_DIR", query_sources_dir)
    monkeypatch.setattr(store_module, "STATE_FILE", state_file)
    monkeypatch.setattr(store_module, "IMPACT_PLAN_FILE", impact_plan_file)
    monkeypatch.setattr(
        store_module,
        "STAGED_UPDATE_FILE",
        staged_update_file,
    )
    monkeypatch.setattr(
        store_module,
        "REVIEW_SESSION_FILE",
        review_session_file,
    )
    monkeypatch.setattr(
        store_module,
        "ATOMIZE_ANALYSES_DIR",
        atomize_analyses_dir,
    )
    monkeypatch.setattr(
        store_module,
        "ATOMIZE_WORKBENCHES_DIR",
        atomize_workbenches_dir,
    )
    monkeypatch.setattr(
        store_module,
        "MELD_SESSIONS_DIR",
        meld_sessions_dir,
    )

    return store_dir
