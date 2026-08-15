"""Typed role and mode contracts for a terminal endpoint setup step."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class EndpointSetupMode:
    """One operation-owned shape offered by the common setup screen."""

    uid: str
    label: str
    description: str = ""

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
        if not self.selectable_names or not self.selectable_names <= set(self.names):
            raise ValueError("Endpoint role availability is outside its catalog.")
        if self.selected_name not in self.selectable_names:
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


@dataclass(frozen=True)
class EndpointSetupValue:
    """One exact endpoint selected in a completed setup draft."""

    role_uid: str
    context_name: str
    include_descendants: bool = False
    memory_uid: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.role_uid, str)
            or not self.role_uid
            or not isinstance(self.context_name, str)
            or not self.context_name
            or type(self.include_descendants) is not bool
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
