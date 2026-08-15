"""Typed role and mode contracts for a terminal endpoint setup step."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


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
        if (
            len(set(self.active_role_uids)) != len(self.active_role_uids)
            or any(
                not isinstance(role_uid, str)
                or not role_uid
                or any(character in role_uid for character in "\r\n")
                for role_uid in self.active_role_uids
            )
        ):
            raise ValueError("Endpoint setup mode roles require stable identity.")
        labels = dict(self.role_labels)
        if (
            len(labels) != len(self.role_labels)
            or any(
                not isinstance(role_uid, str)
                or not role_uid
                or not isinstance(label, str)
                or not label
                or any(character in role_uid + label for character in "\r\n")
                for role_uid, label in self.role_labels
            )
        ):
            raise ValueError("Endpoint setup mode role labels are invalid.")
        for role_uids, label in (
            (self.descendant_role_uids, "descendant"),
            (self.memory_focus_role_uids, "Memory-focus"),
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
                raise ValueError(
                    f"Endpoint setup mode {label} roles are invalid."
                )


@dataclass(frozen=True)
class EndpointSetupMemory:
    """One frozen direct Memory projection offered by an endpoint role."""

    context_name: str
    uid: str
    preview: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.context_name, str)
            or not self.context_name
            or any(character in self.context_name for character in "\r\n")
            or not isinstance(self.uid, str)
            or not self.uid
            or any(character in self.uid for character in "\r\n")
            or not isinstance(self.preview, str)
        ):
            raise ValueError(
                "Endpoint setup Memories require stable Context, uid, and preview text."
            )


@dataclass(frozen=True)
class EndpointSetupRole:
    """One Context endpoint with operation-owned availability and labels."""

    uid: str
    label: str
    names: tuple[str, ...]
    selectable_names: frozenset[str]
    selected_name: str
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    fixed: bool = False
    height: int = 6
    allow_descendants: bool = False
    include_descendants: bool = False
    allow_memory_focus: bool = False
    selected_memory_uid: str | None = None
    memory_height: int = 7
    allow_new: bool = False
    new_label: str = "CREATE NEW CONTEXT"
    initial_new_name: str = ""
    prefer_new: bool = False
    new_name_validator: Callable[[str], object] | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.uid, str)
            or not self.uid
            or not isinstance(self.label, str)
            or not self.label
            or any(character in self.uid + self.label for character in "\r\n")
        ):
            raise ValueError("Endpoint setup roles require stable text identity.")
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Endpoint setup roles require a distinct Context catalog.")
        if (
            (not self.selectable_names and not self.allow_new)
            or not self.selectable_names <= set(self.names)
        ):
            raise ValueError("Endpoint role availability is outside its catalog.")
        if self.selected_name not in self.names or (
            self.selectable_names and self.selected_name not in self.selectable_names
        ):
            raise ValueError("Endpoint role initial selection is unavailable.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Endpoint role annotations are outside its catalog.")
        if type(self.fixed) is not bool:
            raise TypeError("Endpoint role fixed state must be a boolean.")
        if (
            type(self.allow_descendants) is not bool
            or type(self.include_descendants) is not bool
        ):
            raise TypeError("Endpoint role descendant state must be boolean.")
        if self.include_descendants and not self.allow_descendants:
            raise ValueError(
                "Endpoint role cannot include descendants without a range control."
            )
        if type(self.allow_memory_focus) is not bool:
            raise TypeError("Endpoint role Memory-focus state must be boolean.")
        if type(self.allow_new) is not bool or type(self.prefer_new) is not bool:
            raise TypeError("Endpoint role new-Context state must be boolean.")
        if (
            not isinstance(self.new_label, str)
            or not self.new_label
            or any(character in self.new_label for character in "\r\n")
            or not isinstance(self.initial_new_name, str)
            or any(character in self.initial_new_name for character in "\r\n")
        ):
            raise ValueError("Endpoint role new-Context labels are invalid.")
        if (self.initial_new_name or self.prefer_new) and not self.allow_new:
            raise ValueError(
                "Endpoint role cannot prefer or initialize an unavailable new name."
            )
        if self.new_name_validator is not None and (
            not self.allow_new or not callable(self.new_name_validator)
        ):
            raise ValueError(
                "Endpoint new-name validation requires a creatable role callback."
            )
        if self.selected_memory_uid is not None:
            if (
                not isinstance(self.selected_memory_uid, str)
                or not self.selected_memory_uid
                or any(
                    character in self.selected_memory_uid
                    for character in "\r\n"
                )
            ):
                raise ValueError("Endpoint role initial Memory UID is invalid.")
            if not self.allow_memory_focus:
                raise ValueError(
                    "Endpoint role cannot retain Memory focus without a control."
                )
            if self.include_descendants:
                raise ValueError(
                    "Endpoint role cannot combine Memory focus with descendants."
                )
        if self.fixed and self.selectable_names != frozenset({self.selected_name}):
            raise ValueError("A fixed endpoint must expose exactly one selected value.")
        if (
            isinstance(self.height, bool)
            or not isinstance(self.height, int)
            or self.height < 1
        ):
            raise ValueError("Endpoint role height must be positive.")
        if (
            isinstance(self.memory_height, bool)
            or not isinstance(self.memory_height, int)
            or self.memory_height < 3
        ):
            raise ValueError("Endpoint role Memory height must be at least three.")


@dataclass(frozen=True)
class EndpointSetupSpec:
    """Complete process-local setup contract for one operation launch."""

    title: str
    subtitle: str
    modes: tuple[EndpointSetupMode, ...]
    initial_mode_uid: str
    roles: tuple[EndpointSetupRole, ...]
    action_label: str = "CONTINUE TO PLAN REVIEW"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.title, str)
            or not self.title
            or not isinstance(self.subtitle, str)
            or not self.subtitle
            or not isinstance(self.action_label, str)
            or not self.action_label
            or any(
                character in self.title + self.subtitle + self.action_label
                for character in "\r\n"
            )
        ):
            raise ValueError("Endpoint setup screen labels must be single-line text.")
        if not self.modes or len({mode.uid for mode in self.modes}) != len(self.modes):
            raise ValueError("Endpoint setup requires distinct operation modes.")
        if self.initial_mode_uid not in {mode.uid for mode in self.modes}:
            raise ValueError("Endpoint setup initial mode is unavailable.")
        if not self.roles or len({role.uid for role in self.roles}) != len(self.roles):
            raise ValueError("Endpoint setup requires distinct endpoint roles.")
        if all(role.fixed for role in self.roles):
            raise ValueError("Endpoint setup requires one editable endpoint role.")
        role_by_uid = {role.uid: role for role in self.roles}
        for mode in self.modes:
            active = (
                frozenset(mode.active_role_uids)
                if mode.active_role_uids
                else frozenset(role_by_uid)
            )
            labels = dict(mode.role_labels)
            if (
                not active
                or not active <= set(role_by_uid)
                or not set(labels) <= active
            ):
                raise ValueError("Endpoint setup mode references an unknown role.")
            descendants = (
                mode.descendant_role_uids
                if mode.descendant_role_uids is not None
                else frozenset(
                    uid for uid in active if role_by_uid[uid].allow_descendants
                )
            )
            memory_focus = (
                mode.memory_focus_role_uids
                if mode.memory_focus_role_uids is not None
                else frozenset(
                    uid for uid in active if role_by_uid[uid].allow_memory_focus
                )
            )
            if (
                not descendants <= active
                or any(not role_by_uid[uid].allow_descendants for uid in descendants)
            ):
                raise ValueError(
                    "Endpoint setup mode enables unavailable descendant reach."
                )
            if (
                not memory_focus <= active
                or any(
                    not role_by_uid[uid].allow_memory_focus for uid in memory_focus
                )
            ):
                raise ValueError(
                    "Endpoint setup mode enables unavailable Memory focus."
                )

    def mode(self, uid: str) -> EndpointSetupMode:
        try:
            return next(mode for mode in self.modes if mode.uid == uid)
        except StopIteration as error:
            raise KeyError(uid) from error

    def active_role_uids(self, mode_uid: str) -> tuple[str, ...]:
        mode = self.mode(mode_uid)
        return mode.active_role_uids or tuple(role.uid for role in self.roles)

    def role_label(self, mode_uid: str, role_uid: str) -> str:
        labels = dict(self.mode(mode_uid).role_labels)
        return labels.get(
            role_uid,
            next(role.label for role in self.roles if role.uid == role_uid),
        )

    def role_allows_descendants(self, mode_uid: str, role_uid: str) -> bool:
        mode = self.mode(mode_uid)
        if mode.descendant_role_uids is not None:
            return role_uid in mode.descendant_role_uids
        return role_uid in self.active_role_uids(mode_uid) and next(
            role.allow_descendants for role in self.roles if role.uid == role_uid
        )

    def role_allows_memory_focus(self, mode_uid: str, role_uid: str) -> bool:
        mode = self.mode(mode_uid)
        if mode.memory_focus_role_uids is not None:
            return role_uid in mode.memory_focus_role_uids
        return role_uid in self.active_role_uids(mode_uid) and next(
            role.allow_memory_focus for role in self.roles if role.uid == role_uid
        )


@dataclass(frozen=True)
class EndpointSetupValue:
    """One exact endpoint selected in a completed setup draft."""

    role_uid: str
    context_name: str
    include_descendants: bool = False
    memory_uid: str | None = None
    create: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.role_uid, str)
            or not self.role_uid
            or not isinstance(self.context_name, str)
            or not self.context_name
            or type(self.include_descendants) is not bool
            or type(self.create) is not bool
            or (
                self.memory_uid is not None
                and (
                    not isinstance(self.memory_uid, str)
                    or not self.memory_uid
                    or any(character in self.memory_uid for character in "\r\n")
                )
            )
        ):
            raise ValueError("Endpoint setup values require one exact typed range.")
        if self.memory_uid is not None and self.include_descendants:
            raise ValueError(
                "Endpoint setup values cannot focus one Memory across descendants."
            )
        if self.create and (self.include_descendants or self.memory_uid is not None):
            raise ValueError(
                "A new endpoint cannot retain descendant or Memory focus state."
            )


@dataclass(frozen=True)
class EndpointSetupDraft:
    """Process-local operation shape returned without durable mutation."""

    mode_uid: str
    values: tuple[EndpointSetupValue, ...]

    def value(self, role_uid: str) -> EndpointSetupValue:
        try:
            return next(value for value in self.values if value.role_uid == role_uid)
        except StopIteration as error:
            raise KeyError(role_uid) from error
