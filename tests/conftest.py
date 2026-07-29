"""
Shared fixtures for memcommit tests.

The most important fixture is `isolated_store`, which redirects memcommit's
module-level storage paths to a temporary directory so tests never touch the
real ~/.mem store.
"""
import pytest
import memcommit.store as store_module


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
    ground_sessions_dir = store_dir / "ground-sessions"

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
        "GROUND_SESSIONS_DIR",
        ground_sessions_dir,
    )

    return store_dir
