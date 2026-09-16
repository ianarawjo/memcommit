"""Screen composition and one resolved set of endpoint capabilities per mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from memcommit.adapters.console.terminal.components.endpoint_setup.role import (
    EndpointSetupRole,
)


@dataclass(frozen=True)
class EndpointSetupMode:
    """One operation-owned shape offered by the common setup screen."""

    uid: str
    label: str
    description: str = ""
    active_role_uids: tuple[str, ...] = ()
    role_labels: tuple[tuple[str, str], ...] = ()
    descendant_role_uids: frozenset[str] | None = None
    memory_focus_role_uids: frozenset[str] | None = None
    inline_memory_role_uids: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.uid, str)
            or not self.uid
            or not isinstance(self.label, str)
            or not self.label
            or any(character in self.uid + self.label for character in "\r\n")
            or not isinstance(self.description, str)
        ):
            raise ValueError("Endpoint setup modes require stable text identity.")
        if len(set(self.active_role_uids)) != len(self.active_role_uids) or any(
            not isinstance(role_uid, str)
            or not role_uid
            or any(character in role_uid for character in "\r\n")
            for role_uid in self.active_role_uids
        ):
            raise ValueError("Endpoint setup mode roles require stable identity.")
        labels = dict(self.role_labels)
        if len(labels) != len(self.role_labels) or any(
            not isinstance(role_uid, str)
            or not role_uid
            or not isinstance(label, str)
            or not label
            or any(character in role_uid + label for character in "\r\n")
            for role_uid, label in self.role_labels
        ):
            raise ValueError("Endpoint setup mode role labels are invalid.")
        for role_uids, label in (
            (self.descendant_role_uids, "descendant"),
            (self.memory_focus_role_uids, "Memory-focus"),
            (self.inline_memory_role_uids, "inline-Memory"),
        ):
            if role_uids is not None and (
                not isinstance(role_uids, frozenset)
                or any(
                    not isinstance(role_uid, str)
                    or not role_uid
                    or any(character in role_uid for character in "\r\n")
                    for role_uid in role_uids
                )
            ):
                raise ValueError(f"Endpoint setup mode {label} roles are invalid.")


@dataclass(frozen=True)
class _ResolvedMode:
    """Validated role order, labels, and capability sets for one frozen mode."""

    uid: str
    active_role_uids: tuple[str, ...]
    role_labels: tuple[tuple[str, str], ...]
    descendant_role_uids: frozenset[str]
    memory_focus_role_uids: frozenset[str]
    inline_memory_role_uids: frozenset[str]


def _resolve_capability(
    override: frozenset[str] | None,
    *,
    available: frozenset[str],
    active: frozenset[str],
    label: str,
) -> frozenset[str]:
    # None inherits the role defaults; an explicit empty set disables the
    # capability. Keep that distinction identical in validation and rendering.
    enabled = available & active if override is None else override
    if not enabled <= active or not enabled <= available:
        raise ValueError(f"Endpoint setup mode enables unavailable {label}.")
    return enabled


def _resolve_mode(
    mode: EndpointSetupMode, roles: tuple[EndpointSetupRole, ...]
) -> _ResolvedMode:
    role_by_uid = {role.uid: role for role in roles}
    active_uids = mode.active_role_uids or tuple(role_by_uid)
    active = frozenset(active_uids)
    labels = dict(mode.role_labels)
    if not active <= role_by_uid.keys() or not labels.keys() <= active:
        raise ValueError("Endpoint setup mode references an unknown role.")
    descendants = _resolve_capability(
        mode.descendant_role_uids,
        available=frozenset(role.uid for role in roles if role.allow_descendants),
        active=active,
        label="descendant reach",
    )
    memory_focus = _resolve_capability(
        mode.memory_focus_role_uids,
        available=frozenset(role.uid for role in roles if role.memory.enabled),
        active=active,
        label="Memory focus",
    )
    inline_memory = _resolve_capability(
        mode.inline_memory_role_uids,
        available=frozenset(role.uid for role in roles if role.memory.allow_inline),
        active=active,
        label="inline Memory input",
    )
    if not inline_memory <= memory_focus:
        raise ValueError("Endpoint setup mode enables unavailable inline Memory input.")
    if any(
        role_by_uid[uid].memory.required and uid not in memory_focus for uid in active
    ):
        raise ValueError("Endpoint setup mode hides a required Memory selection.")
    return _ResolvedMode(
        uid=mode.uid,
        active_role_uids=active_uids,
        role_labels=tuple(
            (role.uid, labels.get(role.uid, role.label)) for role in roles
        ),
        descendant_role_uids=descendants,
        memory_focus_role_uids=memory_focus,
        inline_memory_role_uids=inline_memory,
    )


@dataclass(frozen=True)
class EndpointSetupSpec:
    """Screen labels and role composition for one process-local operation launch."""

    title: str
    subtitle: str
    modes: tuple[EndpointSetupMode, ...]
    initial_mode_uid: str
    roles: tuple[EndpointSetupRole, ...]
    action_label: str = "CONTINUE TO PLAN REVIEW"
    screen_layout: Literal["WORKBENCH", "FORM"] = "WORKBENCH"
    _resolved_modes: tuple[_ResolvedMode, ...] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        self._validate_presentation()
        if not self.modes or len({mode.uid for mode in self.modes}) != len(self.modes):
            raise ValueError("Endpoint setup requires distinct operation modes.")
        if self.initial_mode_uid not in {mode.uid for mode in self.modes}:
            raise ValueError("Endpoint setup initial mode is unavailable.")
        if not self.roles or len({role.uid for role in self.roles}) != len(self.roles):
            raise ValueError("Endpoint setup requires distinct endpoint roles.")
        if all(role.fixed for role in self.roles):
            raise ValueError("Endpoint setup requires one editable endpoint role.")
        object.__setattr__(
            self,
            "_resolved_modes",
            tuple(_resolve_mode(mode, self.roles) for mode in self.modes),
        )
        if (
            any(role.memory.allow_inline for role in self.roles)
            and self.screen_layout != "FORM"
        ):
            raise ValueError(
                "Inline Memory source selection currently requires FORM layout."
            )

    def _validate_presentation(self) -> None:
        labels = (self.title, self.subtitle, self.action_label)
        if any(
            not isinstance(label, str)
            or not label
            or any(character in label for character in "\r\n")
            for label in labels
        ) or self.screen_layout not in {"WORKBENCH", "FORM"}:
            raise ValueError("Endpoint setup screen labels must be single-line text.")

    def mode(self, uid: str) -> EndpointSetupMode:
        try:
            return next(mode for mode in self.modes if mode.uid == uid)
        except StopIteration as error:
            raise KeyError(uid) from error

    def _resolved_mode(self, uid: str) -> _ResolvedMode:
        try:
            return next(mode for mode in self._resolved_modes if mode.uid == uid)
        except StopIteration as error:
            raise KeyError(uid) from error

    def active_role_uids(self, mode_uid: str) -> tuple[str, ...]:
        return self._resolved_mode(mode_uid).active_role_uids

    def role_label(self, mode_uid: str, role_uid: str) -> str:
        return next(
            label
            for uid, label in self._resolved_mode(mode_uid).role_labels
            if uid == role_uid
        )

    def role_allows_descendants(self, mode_uid: str, role_uid: str) -> bool:
        return role_uid in self._resolved_mode(mode_uid).descendant_role_uids

    def role_allows_memory_focus(self, mode_uid: str, role_uid: str) -> bool:
        return role_uid in self._resolved_mode(mode_uid).memory_focus_role_uids

    def role_allows_inline_memory(self, mode_uid: str, role_uid: str) -> bool:
        return role_uid in self._resolved_mode(mode_uid).inline_memory_role_uids
