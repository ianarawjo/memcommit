"""Profile-local editable routes and active Study-policy selection."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Mapping

from memcommit.config import Config
from memcommit.infrastructure.providers.policy import (
    ConfiguredProviderRoute,
    PROFILE_PROVIDER_OPERATION_NAMES,
    ProviderPolicyConfig,
    ProviderPolicyError,
    ProviderRoute,
    ResolvedProviderPolicy,
    resolve_operation_provider_policy,
    study_provider_config,
    validate_provider_route,
)
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_control_dir,
    study_run_identity,
)
from memcommit.storage_permissions import ensure_private_directory


PROFILE_PROVIDER_ROUTES_SCHEMA_VERSION = 1


class ProfileProviderRoutesError(RuntimeError):
    """A Profile provider route or Study policy pin is unsafe to use."""


def _profile_provider_operation(
    value: object,
    *,
    allow_default: bool = False,
) -> str:
    """Return one exact operation key understood by Profile policy routing."""

    allowed = PROFILE_PROVIDER_OPERATION_NAMES | (
        {"semantic_default"} if allow_default else set()
    )
    if not isinstance(value, str) or value not in allowed:
        raise ProfileProviderRoutesError(
            "Profile provider operation must be one exact supported name: "
            + ", ".join(sorted(allowed))
            + "."
        )
    return value


@dataclass(frozen=True)
class GeneralProfileRoutes:
    """Editable route combinations owned by one ordinary Profile."""

    profile_uid: str
    default: ProviderRoute | None = None
    operations: Mapping[str, ProviderRoute] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for operation in self.operations:
            _profile_provider_operation(operation)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PROFILE_PROVIDER_ROUTES_SCHEMA_VERSION,
            "profile_uid": self.profile_uid,
            "default": self.default.to_dict() if self.default is not None else None,
            "operations": {
                operation: route.to_dict()
                for operation, route in sorted(self.operations.items())
            },
        }


@dataclass(frozen=True)
class ActiveProviderScope:
    """Frozen provider configuration scope for one command process."""

    profile: ProfileEntry
    mode: str
    config: ProviderPolicyConfig
    routes: GeneralProfileRoutes | None = None
    study_policy_version: str | None = None
    study_policy_digest: str | None = None

    @property
    def editable(self) -> bool:
        return self.mode == "GENERAL"


class _ProfileRouteConfig:
    """Decorate machine transport config with one Profile route matrix."""

    def __init__(self, machine: Config, routes: GeneralProfileRoutes) -> None:
        self.machine = machine
        self.routes = routes

    def __getattr__(self, name: str):
        return getattr(self.machine, name)

    def provider_route(self, operation: str) -> ConfiguredProviderRoute | None:
        operation_route = self.routes.operations.get(operation)
        if operation_route is not None:
            return ConfiguredProviderRoute(
                route=operation_route,
                source="PROFILE_OPERATION",
            )
        if self.routes.default is not None:
            return ConfiguredProviderRoute(
                route=self.routes.default,
                source="PROFILE_DEFAULT",
            )
        return None

    def semantic_provider(self) -> str:
        if self.routes.default is not None:
            return self.routes.default.provider_id
        return self.machine.semantic_provider()

    def model_for_provider(self, provider: str) -> str | None:
        if (
            self.routes.default is not None
            and self.routes.default.provider_id == provider
        ):
            return self.routes.default.model
        return self.machine.model_for_provider(provider)

    def codex_reasoning_effort(self) -> str | None:
        if (
            self.routes.default is not None
            and self.routes.default.provider_id == "codex_chatgpt"
        ):
            return self.routes.default.reasoning_effort
        return self.machine.codex_reasoning_effort()

    def semantic_timeout_seconds(self) -> float:
        if self.routes.default is not None:
            return self.routes.default.timeout_seconds
        return self.machine.semantic_timeout_seconds()


def profile_provider_routes_dir() -> Path:
    return profile_control_dir() / "provider-routes"


def profile_provider_routes_file(profile: ProfileEntry) -> Path:
    return profile_provider_routes_dir() / f"{profile.uid}.json"


def _route_from_dict(value: object) -> ProviderRoute:
    if not isinstance(value, dict) or set(value) != {
        "provider",
        "model",
        "reasoning_effort",
        "timeout_seconds",
    }:
        raise ProfileProviderRoutesError("Profile provider route is invalid.")
    provider = value.get("provider")
    model = value.get("model")
    reasoning = value.get("reasoning_effort")
    timeout = value.get("timeout_seconds")
    if not isinstance(provider, str):
        raise ProfileProviderRoutesError("Profile provider id is invalid.")
    if model is not None and not isinstance(model, str):
        raise ProfileProviderRoutesError("Profile provider model is invalid.")
    if reasoning is not None and not isinstance(reasoning, str):
        raise ProfileProviderRoutesError("Profile provider reasoning is invalid.")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        raise ProfileProviderRoutesError("Profile provider timeout is invalid.")
    try:
        return validate_provider_route(
            ProviderRoute(
                provider_id=provider,
                model=model,
                reasoning_effort=reasoning,
                timeout_seconds=float(timeout),
            )
        )
    except ProviderPolicyError as error:
        raise ProfileProviderRoutesError(str(error)) from error


def load_profile_routes(profile: ProfileEntry) -> GeneralProfileRoutes:
    path = profile_provider_routes_file(profile)
    if path.is_symlink():
        raise ProfileProviderRoutesError(
            "Profile provider configuration storage is invalid."
        )
    if not path.exists():
        return GeneralProfileRoutes(profile_uid=profile.uid)
    if not path.is_file():
        raise ProfileProviderRoutesError(
            "Profile provider configuration storage is invalid."
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProfileProviderRoutesError(
            f"Profile provider configuration could not be read: {error}"
        ) from error
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "profile_uid",
        "default",
        "operations",
    }:
        raise ProfileProviderRoutesError("Profile provider configuration is invalid.")
    if value.get("schema_version") != PROFILE_PROVIDER_ROUTES_SCHEMA_VERSION:
        raise ProfileProviderRoutesError(
            "Unsupported Profile provider configuration schema version."
        )
    if value.get("profile_uid") != profile.uid:
        raise ProfileProviderRoutesError(
            "Profile provider configuration belongs to a different Profile."
        )
    raw_default = value.get("default")
    default = None if raw_default is None else _route_from_dict(raw_default)
    raw_operations = value.get("operations")
    if not isinstance(raw_operations, dict):
        raise ProfileProviderRoutesError("Profile provider operation routes are invalid.")
    operations: dict[str, ProviderRoute] = {}
    for operation, raw_route in raw_operations.items():
        canonical_operation = _profile_provider_operation(operation)
        operations[canonical_operation] = _route_from_dict(raw_route)
    return GeneralProfileRoutes(
        profile_uid=profile.uid,
        default=default,
        operations=operations,
    )


def load_active_provider_scope(
    *,
    machine_config: Config | None = None,
    registry: ProfileRegistry | None = None,
) -> ActiveProviderScope:
    frozen_registry = registry or load_profile_registry()
    profile = frozen_registry.active
    machine = machine_config or Config()
    identity = study_run_identity(profile)
    if identity is None:
        routes = load_profile_routes(profile)
        return ActiveProviderScope(
            profile=profile,
            mode="GENERAL",
            config=_ProfileRouteConfig(machine, routes),
            routes=routes,
        )
    version = identity.provider_policy_version
    digest = identity.provider_policy_digest
    if version is None or digest is None:
        raise ProfileProviderRoutesError(
            "This Study Profile predates provider-policy pinning; recreate it "
            "with 'mem init-study' before semantic execution."
        )
    try:
        study = study_provider_config(version)
    except ProviderPolicyError as error:
        raise ProfileProviderRoutesError(str(error)) from error
    if study.digest != digest:
        raise ProfileProviderRoutesError(
            "Study provider policy digest does not match the installed policy."
        )
    return ActiveProviderScope(
        profile=profile,
        mode="STUDY",
        config=machine,
        study_policy_version=version,
        study_policy_digest=digest,
    )


def resolve_active_provider_policy(
    operation: str,
    *,
    machine_config: Config | None = None,
    registry: ProfileRegistry | None = None,
) -> tuple[ResolvedProviderPolicy, ActiveProviderScope]:
    operation = _profile_provider_operation(operation, allow_default=True)
    scope = load_active_provider_scope(
        machine_config=machine_config,
        registry=registry,
    )
    policy = resolve_operation_provider_policy(
        operation,
        config=scope.config,
        mode="STUDY_PARTICIPANT" if scope.mode == "STUDY" else "PRODUCTION",
        study_policy_version=scope.study_policy_version,
    )
    return policy, scope


@contextmanager
def _routes_lock(profile: ProfileEntry) -> Iterator[None]:
    directory = profile_provider_routes_dir()
    ensure_private_directory(directory, parents=True)
    lock_path = directory / f"{profile.uid}.lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
    except BaseException:
        os.close(descriptor)
        raise
    with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _write_profile_routes(profile: ProfileEntry, routes: GeneralProfileRoutes) -> None:
    path = profile_provider_routes_file(profile)
    ensure_private_directory(path.parent, parents=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{profile.uid}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(routes.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            directory_flags |= os.O_DIRECTORY
        directory_descriptor = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def set_active_profile_route(
    route: ProviderRoute,
    *,
    operation: str | None = None,
    registry: ProfileRegistry | None = None,
) -> tuple[ProfileEntry, GeneralProfileRoutes]:
    route = validate_provider_route(route)
    if operation is not None:
        operation = _profile_provider_operation(operation)
    frozen_registry = registry or load_profile_registry()
    profile = frozen_registry.active
    if study_run_identity(profile) is not None:
        raise ProfileProviderRoutesError(
            "Provider configuration is fixed for this Study Profile. Switch "
            "to an ordinary Profile to edit provider routes."
        )
    with _routes_lock(profile):
        current = load_profile_routes(profile)
        operations = dict(current.operations)
        default = current.default
        if operation is None:
            default = route
        else:
            operations[operation] = route
        updated = GeneralProfileRoutes(
            profile_uid=profile.uid,
            default=default,
            operations=operations,
        )
        _write_profile_routes(profile, updated)
    return profile, updated


def reset_active_profile_route(
    operation: str | None = None,
    *,
    registry: ProfileRegistry | None = None,
) -> tuple[ProfileEntry, GeneralProfileRoutes]:
    if operation is not None:
        operation = _profile_provider_operation(operation)
    frozen_registry = registry or load_profile_registry()
    profile = frozen_registry.active
    if study_run_identity(profile) is not None:
        raise ProfileProviderRoutesError(
            "Provider configuration is fixed for this Study Profile. Switch "
            "to an ordinary Profile to edit provider routes."
        )
    with _routes_lock(profile):
        current = load_profile_routes(profile)
        operations = dict(current.operations)
        default = current.default
        if operation is None:
            if default is None:
                raise ProfileProviderRoutesError(
                    "Profile provider default is not configured."
                )
            default = None
        else:
            if operation not in operations:
                raise ProfileProviderRoutesError(
                    f"Profile provider route {operation!r} is not configured."
                )
            del operations[operation]
        updated = GeneralProfileRoutes(
            profile_uid=profile.uid,
            default=default,
            operations=operations,
        )
        _write_profile_routes(profile, updated)
    return profile, updated


__all__ = [
    "ActiveProviderScope",
    "GeneralProfileRoutes",
    "PROFILE_PROVIDER_ROUTES_SCHEMA_VERSION",
    "ProfileProviderRoutesError",
    "load_active_provider_scope",
    "load_profile_routes",
    "profile_provider_routes_dir",
    "profile_provider_routes_file",
    "reset_active_profile_route",
    "resolve_active_provider_policy",
    "set_active_profile_route",
]
