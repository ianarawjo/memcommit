"""Profile-local provider routes are editable only outside Study runs."""

from __future__ import annotations

import json
import uuid

import pytest

from memcommit.providers.policy import (
    PROFILE_PROVIDER_OPERATION_NAMES,
    STUDY_PROVIDER_POLICY_DIGEST,
    STUDY_PROVIDER_POLICY_VERSION,
    ProviderRoute,
)
from memcommit.providers.profile_routes import (
    ProfileProviderRoutesError,
    load_active_provider_scope,
    profile_provider_routes_file,
    reset_active_profile_route,
    resolve_active_provider_policy,
    set_active_profile_route,
)
from memcommit.application.operations.profile.config import ProfileEntry, ProfileRegistry


class MachineConfig:
    def semantic_provider(self) -> str:
        return "openrouter"

    def model_for_provider(self, provider: str) -> str | None:
        return "machine/model"

    def codex_reasoning_effort(self) -> str | None:
        return "medium"

    def semantic_timeout_seconds(self) -> float:
        return 120.0


def _registry(profile: ProfileEntry) -> ProfileRegistry:
    return ProfileRegistry(
        generation=1,
        active_uid=profile.uid,
        profiles=(profile,),
    )


def _ordinary_profile() -> ProfileEntry:
    return ProfileEntry(
        uid=str(uuid.uuid4()),
        name="authoring",
        kind="MANAGED",
    )


def _study_profile(*, pin: bool = True, digest: str | None = None) -> ProfileEntry:
    source: dict[str, object] = {
        "kind": "STUDY_RUN",
        "study_uid": str(uuid.uuid4()),
        "study_name": "pilot-001",
        "created_at": "2026-08-22T12:00:00+00:00",
        "baseline_sha256": "0" * 64,
        "baseline_profile_uid": str(uuid.uuid4()),
        "baseline_profile_name": "study-baseline",
    }
    if pin:
        source.update(
            {
                "provider_policy_version": STUDY_PROVIDER_POLICY_VERSION,
                "provider_policy_digest": digest or STUDY_PROVIDER_POLICY_DIGEST,
            }
        )
    return ProfileEntry(
        uid=str(uuid.uuid4()),
        name="pilot-001",
        kind="MANAGED",
        source=source,
    )


def test_ordinary_profile_falls_back_then_overrides_default_and_operation(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    profile = _ordinary_profile()
    registry = _registry(profile)

    inherited, scope = resolve_active_provider_policy(
        "query",
        machine_config=MachineConfig(),  # type: ignore[arg-type]
        registry=registry,
    )
    assert scope.mode == "GENERAL"
    assert inherited.source == "GLOBAL_DEFAULT"
    assert inherited.provider_id == "openrouter"

    set_active_profile_route(
        ProviderRoute("ollama", "qwen:latest", None, 300.0),
        registry=registry,
    )
    set_active_profile_route(
        ProviderRoute("codex_chatgpt", "gpt-5.6-luna", "low", 45.0),
        operation="query",
        registry=registry,
    )
    default, _ = resolve_active_provider_policy(
        "search",
        machine_config=MachineConfig(),  # type: ignore[arg-type]
        registry=registry,
    )
    query, _ = resolve_active_provider_policy(
        "query",
        machine_config=MachineConfig(),  # type: ignore[arg-type]
        registry=registry,
    )

    assert (default.provider_id, default.source) == ("ollama", "PROFILE_DEFAULT")
    assert (query.model, query.reasoning_effort, query.source) == (
        "gpt-5.6-luna",
        "low",
        "PROFILE_OPERATION",
    )

    reset_active_profile_route("query", registry=registry)
    reset_active_profile_route(registry=registry)
    restored, _ = resolve_active_provider_policy(
        "query",
        machine_config=MachineConfig(),  # type: ignore[arg-type]
        registry=registry,
    )
    assert restored.source == "GLOBAL_DEFAULT"


def test_profile_operation_routes_accept_only_exact_routable_names(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    profile = _ordinary_profile()
    registry = _registry(profile)
    route = ProviderRoute("codex_chatgpt", None, "none", 45.0)

    assert PROFILE_PROVIDER_OPERATION_NAMES == {
        "compare_contexts",
        "compare_summary",
        "forget",
        "help",
        "meld_contexts",
        "query",
        "search",
    }
    for operation in sorted(PROFILE_PROVIDER_OPERATION_NAMES):
        set_active_profile_route(route, operation=operation, registry=registry)

    for invalid in ("", "memory", " search ", "SEARCH", "semantic_default"):
        with pytest.raises(
            ProfileProviderRoutesError,
            match="one exact supported name",
        ):
            set_active_profile_route(route, operation=invalid, registry=registry)
        with pytest.raises(
            ProfileProviderRoutesError,
            match="one exact supported name",
        ):
            reset_active_profile_route(invalid, registry=registry)


def test_unknown_persisted_profile_operation_route_fails_closed(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    profile = _ordinary_profile()
    path = profile_provider_routes_file(profile)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profile_uid": profile.uid,
                "default": None,
                "operations": {
                    "memory": ProviderRoute(
                        "codex_chatgpt",
                        None,
                        "none",
                        45.0,
                    ).to_dict(),
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ProfileProviderRoutesError,
        match="one exact supported name",
    ):
        load_active_provider_scope(
            machine_config=MachineConfig(),  # type: ignore[arg-type]
            registry=_registry(profile),
        )


def test_unknown_active_policy_operation_is_rejected_before_resolution(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    profile = _ordinary_profile()

    with pytest.raises(
        ProfileProviderRoutesError,
        match="one exact supported name",
    ):
        resolve_active_provider_policy(
            "memory",
            machine_config=MachineConfig(),  # type: ignore[arg-type]
            registry=_registry(profile),
        )


def test_route_file_is_bound_to_the_profile_uid(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    profile = _ordinary_profile()
    path = profile_provider_routes_file(profile)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profile_uid": str(uuid.uuid4()),
                "default": None,
                "operations": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProfileProviderRoutesError, match="different Profile"):
        load_active_provider_scope(
            machine_config=MachineConfig(),  # type: ignore[arg-type]
            registry=_registry(profile),
        )


def test_study_route_is_pinned_and_editing_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    profile = _study_profile()
    registry = _registry(profile)

    resolved, scope = resolve_active_provider_policy(
        "search",
        machine_config=MachineConfig(),  # type: ignore[arg-type]
        registry=registry,
    )

    assert scope.mode == "STUDY"
    assert scope.editable is False
    assert resolved.source == "STUDY_POLICY"
    assert (resolved.provider_id, resolved.model, resolved.reasoning_effort) == (
        "codex_chatgpt",
        "gpt-5.6-terra",
        "low",
    )
    with pytest.raises(ProfileProviderRoutesError, match="fixed"):
        set_active_profile_route(
            ProviderRoute("ollama", "qwen:latest", None, 300.0),
            registry=registry,
        )
    assert not profile_provider_routes_file(profile).exists()


@pytest.mark.parametrize(
    "profile, message",
    [
        (_study_profile(pin=False), "predates provider-policy pinning"),
        (_study_profile(digest="f" * 64), "digest does not match"),
    ],
)
def test_unreproducible_study_route_fails_closed(
    profile,
    message,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HOME", str(tmp_path))

    with pytest.raises(ProfileProviderRoutesError, match=message):
        load_active_provider_scope(
            machine_config=MachineConfig(),  # type: ignore[arg-type]
            registry=_registry(profile),
        )
