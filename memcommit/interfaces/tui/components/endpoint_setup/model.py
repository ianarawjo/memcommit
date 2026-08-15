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
        if self.fixed and self.selectable_names != frozenset({self.selected_name}):
            raise ValueError("A fixed endpoint must expose exactly one selected value.")
        if (
            isinstance(self.height, bool)
            or not isinstance(self.height, int)
            or self.height < 1
        ):
            raise ValueError("Endpoint role height must be positive.")


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
