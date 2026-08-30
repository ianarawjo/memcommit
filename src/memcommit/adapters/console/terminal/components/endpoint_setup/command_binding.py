"""Bidirectional command binding for one Endpoint Setup screen."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from memcommit.adapters.console.terminal.components.command_editor import (
    CommandForm,
    CommandReview,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.adapters.console.terminal.components.endpoint_setup.model import (
    EndpointSetupDraft,
    EndpointSetupRole,
    EndpointSetupSpec,
    EndpointSetupValue,
)


DraftValidator = Callable[[EndpointSetupDraft], str | None]


@dataclass(frozen=True)
class EndpointCommandBinding:
    """Operation grammar connected to the common editable command control."""

    form: CommandForm
    review: Callable[[EndpointSetupDraft], CommandReview]
    parse: Callable[[Sequence[str]], EndpointSetupDraft]

    def __post_init__(self) -> None:
        if not isinstance(self.form, CommandForm):
            raise TypeError("Endpoint command binding requires a CommandForm.")
        if not callable(self.review) or not callable(self.parse):
            raise TypeError("Endpoint command binding requires review and parse callbacks.")

    def decode(
        self,
        argv: Sequence[str],
        *,
        spec: EndpointSetupSpec,
        validate_draft: DraftValidator | None,
    ) -> EndpointSetupDraft:
        """Parse and canonicalize the complete command before controls move."""

        return normalize_endpoint_command_draft(
            spec,
            self.parse(tuple(argv)),
            validate_draft=validate_draft,
        )


def _resolve_role_name(role: EndpointSetupRole, displayed: str) -> tuple[str, bool]:
    matches = tuple(
        name
        for name in role.names
        if displayed == name or displayed == display_escape_text(name)
    )
    if len(matches) > 1:
        raise ValueError(f"{role.label} is ambiguous after terminal escaping.")
    if matches:
        name = matches[0]
        if name not in role.selectable_names:
            raise ValueError(f"{role.label} Context '{displayed}' is unavailable.")
        return name, False
    if not role.allow_new:
        raise ValueError(f"{role.label} requires an available existing Context.")
    validate_portable_context_name(displayed)
    if role.new_name_validator is not None:
        role.new_name_validator(displayed)
    return displayed, True


def normalize_endpoint_command_draft(
    spec: EndpointSetupSpec,
    draft: EndpointSetupDraft,
    *,
    validate_draft: DraftValidator | None = None,
) -> EndpointSetupDraft:
    """Return one catalog-resolved, operation-valid all-or-none draft."""

    if not isinstance(spec, EndpointSetupSpec) or not isinstance(
        draft, EndpointSetupDraft
    ):
        raise TypeError("Endpoint command decoding requires a typed spec and draft.")
    mode_uids = {mode.uid for mode in spec.modes}
    if draft.mode_uid not in mode_uids:
        raise ValueError("The command selected an unavailable operation mode.")
    expected_roles = spec.active_role_uids(draft.mode_uid)
    received_roles = tuple(value.role_uid for value in draft.values)
    if received_roles != expected_roles or len(set(received_roles)) != len(
        received_roles
    ):
        raise ValueError("The command must define every active endpoint exactly once.")

    role_by_uid = {role.uid: role for role in spec.roles}
    normalized: list[EndpointSetupValue] = []
    for value in draft.values:
        if not isinstance(value, EndpointSetupValue):
            raise TypeError("Endpoint command returned an invalid endpoint value.")
        role = role_by_uid[value.role_uid]
        context_name, create = _resolve_role_name(role, value.context_name)
        if value.include_descendants and not spec.role_allows_descendants(
            draft.mode_uid, value.role_uid
        ):
            raise ValueError(f"{role.label} does not allow descendant reach in this mode.")
        if value.memory_uid is not None and not spec.role_allows_memory_focus(
            draft.mode_uid, value.role_uid
        ):
            raise ValueError(f"{role.label} does not allow direct Memory focus in this mode.")
        normalized.append(
            EndpointSetupValue(
                value.role_uid,
                context_name,
                include_descendants=value.include_descendants,
                memory_uid=value.memory_uid,
                create=create,
            )
        )
    result = EndpointSetupDraft(draft.mode_uid, tuple(normalized))
    message = validate_draft(result) if validate_draft is not None else None
    if message:
        raise ValueError(message)
    return result


__all__ = [
    "DraftValidator",
    "EndpointCommandBinding",
    "normalize_endpoint_command_draft",
]
