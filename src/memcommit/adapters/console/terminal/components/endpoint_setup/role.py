"""Configure one endpoint by composing Context, Memory, and new-name settings."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class EndpointMemoryOptions:
    """Optional direct-Memory control and its initial selection, not live state."""

    enabled: bool = False
    allow_inline: bool = False
    preview_only: bool = False
    required: bool = False
    unselected_label: str = "WHOLE CONTEXT"
    selected_uid: str | None = None
    height: int = 7

    def __post_init__(self) -> None:
        self._validate_controls()
        self._validate_initial_selection()
        if (
            not isinstance(self.unselected_label, str)
            or not self.unselected_label.strip()
            or any(character in self.unselected_label for character in "\r\n")
        ):
            raise ValueError(
                "Endpoint role unselected Memory label must be single-line text."
            )
        if (
            isinstance(self.height, bool)
            or not isinstance(self.height, int)
            or self.height < 3
        ):
            raise ValueError("Endpoint role Memory height must be at least three.")

    def _validate_controls(self) -> None:
        if any(
            type(flag) is not bool
            for flag in (
                self.enabled,
                self.allow_inline,
                self.preview_only,
                self.required,
            )
        ):
            raise TypeError("Endpoint role Memory-focus state must be boolean.")
        if self.preview_only and not self.enabled:
            raise ValueError(
                "Endpoint role read-only Memory preview requires a Memory control."
            )
        if self.required and (not self.enabled or self.preview_only):
            raise ValueError(
                "Endpoint role required Memory selection needs an editable Memory control."
            )
        if self.allow_inline and (not self.enabled or self.preview_only):
            raise ValueError(
                "Inline Memory input requires one editable existing-Context role "
                "with stored-Memory focus."
            )

    def _validate_initial_selection(self) -> None:
        if self.selected_uid is None:
            return
        if (
            not isinstance(self.selected_uid, str)
            or not self.selected_uid
            or any(character in self.selected_uid for character in "\r\n")
        ):
            raise ValueError("Endpoint role initial Memory UID is invalid.")
        if not self.enabled:
            raise ValueError(
                "Endpoint role cannot retain Memory focus without a control."
            )
        if self.preview_only:
            raise ValueError(
                "A read-only Memory preview cannot retain a selected Memory."
            )


@dataclass(frozen=True)
class EndpointNewContextOptions:
    """New-name input and caller-owned callbacks; construction never invokes them."""

    enabled: bool = False
    label: str = "CREATE NEW CONTEXT"
    existing_label: str = "EXISTING"
    initial_name: str = ""
    prefer_new: bool = False
    name_validator: Callable[[str], object] | None = None
    name_suggester: Callable[[Mapping[str, str]], str] | None = None
    parent_locator: bool = False

    def __post_init__(self) -> None:
        if any(
            type(flag) is not bool
            for flag in (self.enabled, self.prefer_new, self.parent_locator)
        ):
            raise TypeError("Endpoint role new-Context state must be boolean.")
        if (
            not isinstance(self.label, str)
            or not self.label
            or not isinstance(self.existing_label, str)
            or not self.existing_label
            or any(
                character in self.label + self.existing_label for character in "\r\n"
            )
            or not isinstance(self.initial_name, str)
            or any(character in self.initial_name for character in "\r\n")
        ):
            raise ValueError("Endpoint role new-Context labels are invalid.")
        if (self.initial_name or self.prefer_new) and not self.enabled:
            raise ValueError(
                "Endpoint role cannot prefer or initialize an unavailable new name."
            )
        if self.name_validator is not None and (
            not self.enabled or not callable(self.name_validator)
        ):
            raise ValueError(
                "Endpoint new-name validation requires a creatable role callback."
            )
        if self.name_suggester is not None and (
            not self.enabled or not callable(self.name_suggester)
        ):
            raise ValueError(
                "Endpoint new-name suggestions require a creatable role callback."
            )
        if self.parent_locator and (
            not self.enabled or not self.prefer_new or not self.initial_name
        ):
            raise ValueError(
                "Endpoint parent location requires a preferred new-only role "
                "with one initial exact name."
            )


@dataclass(frozen=True)
class EndpointSetupRole:
    """Frozen Context catalog and defaults with optional Memory/new-name controls."""

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
    memory: EndpointMemoryOptions = field(default_factory=EndpointMemoryOptions)
    new_context: EndpointNewContextOptions = field(
        default_factory=EndpointNewContextOptions
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.uid, str)
            or not self.uid
            or not isinstance(self.label, str)
            or not self.label
            or any(character in self.uid + self.label for character in "\r\n")
        ):
            raise ValueError("Endpoint setup roles require stable text identity.")
        if not isinstance(self.memory, EndpointMemoryOptions):
            raise TypeError("Endpoint role requires typed Memory options.")
        if not isinstance(self.new_context, EndpointNewContextOptions):
            raise TypeError("Endpoint role requires typed new-Context options.")
        if type(self.fixed) is not bool:
            raise TypeError("Endpoint role fixed state must be a boolean.")
        if (
            isinstance(self.height, bool)
            or not isinstance(self.height, int)
            or self.height < 1
        ):
            raise ValueError("Endpoint role height must be positive.")
        self._validate_catalog()
        self._validate_reach()
        self._validate_feature_combinations()

    def _validate_catalog(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Endpoint setup roles require a distinct Context catalog.")
        if (
            not self.selectable_names and not self.new_context.enabled
        ) or not self.selectable_names <= set(self.names):
            raise ValueError("Endpoint role availability is outside its catalog.")
        if self.selected_name not in self.names or (
            self.selectable_names and self.selected_name not in self.selectable_names
        ):
            raise ValueError("Endpoint role initial selection is unavailable.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Endpoint role annotations are outside its catalog.")
        if self.fixed and self.selectable_names != frozenset({self.selected_name}):
            raise ValueError("A fixed endpoint must expose exactly one selected value.")

    def _validate_reach(self) -> None:
        if (
            type(self.allow_descendants) is not bool
            or type(self.include_descendants) is not bool
        ):
            raise TypeError("Endpoint role descendant state must be boolean.")
        if self.include_descendants and not self.allow_descendants:
            raise ValueError(
                "Endpoint role cannot include descendants without a range control."
            )
        if self.memory.selected_uid is not None and self.include_descendants:
            raise ValueError(
                "Endpoint role cannot combine Memory focus with descendants."
            )

    def _validate_feature_combinations(self) -> None:
        # Each options object validates itself; only the role can check the
        # boundaries between Memory input, Context creation, and fixed endpoints.
        if self.memory.allow_inline and (self.new_context.enabled or self.fixed):
            raise ValueError(
                "Inline Memory input requires one editable existing-Context role "
                "with stored-Memory focus."
            )
        if self.new_context.parent_locator and self.selectable_names:
            raise ValueError(
                "Endpoint parent location requires a preferred new-only role "
                "with one initial exact name."
            )
