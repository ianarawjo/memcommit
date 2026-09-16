"""Pure service-wide contract for one item-bound response surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ResponseObligation = Literal["REQUIRED", "OPTIONAL", "NONE"]
ResponseState = Literal["OPEN", "ANSWERED", "NOT_APPLICABLE"]
ResponseMode = Literal["DECISION", "COMMENT"]


def _one_line(value: object, label: str, *, empty: bool = False) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or any(character in value for character in "\r\n")
    ):
        raise ValueError(f"Invalid {label}.")
    return value


@dataclass(frozen=True)
class ResponseChoice:
    """One selectable answer owned semantically by the calling operation."""

    uid: str
    label: str
    text: str

    def __post_init__(self) -> None:
        _one_line(self.uid, "response choice uid")
        _one_line(self.label, "response choice label")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Invalid response choice text.")


@dataclass(frozen=True)
class ResponseDraft:
    """One process-local or adapter-projected response value."""

    selected_choice_uid: str | None = None
    text: str = ""

    def __post_init__(self) -> None:
        if self.selected_choice_uid is not None:
            _one_line(self.selected_choice_uid, "selected response choice uid")
        if not isinstance(self.text, str):
            raise ValueError("Invalid response text.")

    @property
    def answered(self) -> bool:
        return self.selected_choice_uid is not None or bool(self.text.strip())


@dataclass(frozen=True)
class ResponseTarget:
    """One current Item projected into the common RESPONSES frame.

    The target contains presentation and staged response data only. It carries
    no provider, persistence, mutation, or application authority.
    """

    item_uid: str
    item_label: str
    obligation: ResponseObligation
    state: ResponseState
    mode: ResponseMode
    prompt_heading: str = ""
    prompt: str = ""
    choices_heading: str = "OPTIONS"
    choices: tuple[ResponseChoice, ...] = ()
    editable: bool = True

    def __post_init__(self) -> None:
        _one_line(self.item_uid, "response target uid")
        _one_line(self.item_label, "response target label")
        if self.obligation not in {"REQUIRED", "OPTIONAL", "NONE"}:
            raise ValueError("Invalid response obligation.")
        if self.state not in {"OPEN", "ANSWERED", "NOT_APPLICABLE"}:
            raise ValueError("Invalid response state.")
        if self.mode not in {"DECISION", "COMMENT"}:
            raise ValueError("Invalid response mode.")
        _one_line(self.prompt_heading, "response prompt heading", empty=True)
        if not isinstance(self.prompt, str):
            raise ValueError("Invalid response prompt.")
        _one_line(self.choices_heading, "response choices heading")
        if not isinstance(self.choices, tuple) or any(
            not isinstance(choice, ResponseChoice) for choice in self.choices
        ):
            raise ValueError("Invalid response choices.")
        if len({choice.uid for choice in self.choices}) != len(self.choices):
            raise ValueError("Duplicate response choice uid.")
        if not isinstance(self.editable, bool):
            raise ValueError("Invalid response editability.")

    @property
    def has_decision(self) -> bool:
        return bool(self.prompt or self.choices)

    def choice(self, uid: str) -> ResponseChoice:
        matches = tuple(choice for choice in self.choices if choice.uid == uid)
        if len(matches) != 1:
            raise ValueError(f"No response choice matches '{uid}'.")
        return matches[0]
