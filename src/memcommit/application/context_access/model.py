"""Serializable bindings for resolved cross-Profile Context access."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from memcommit.application.operations.profiles.profile.config import (
    ProfileConfigError,
    canonical_grant_permissions,
)


def _require_mapping(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"Invalid {label}.")
    return value


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {label}.")
    return value


def _require_uid(value: object, label: str) -> str:
    text = _require_text(value, label)
    try:
        parsed = uuid.UUID(text)
    except ValueError as error:
        raise ValueError(f"Invalid {label}.") from error
    if str(parsed) != text:
        raise ValueError(f"Invalid {label}.")
    return text


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True)
class GrantedContextBinding:
    """Frozen control-plane identity behind one granted public Context."""

    public_name: str
    grantee_profile_uid: str
    authority_profile_uid: str
    attachment_context_uid: str
    attachment_context_name: str
    grant_uid: str
    grant_revision: int
    grant_digest: str
    resource_uid: str
    resource_name: str
    authority_context_name: str
    permissions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "GRANTED_CONTEXT",
            "public_name": self.public_name,
            "grantee_profile_uid": self.grantee_profile_uid,
            "authority_profile_uid": self.authority_profile_uid,
            "attachment": {
                "uid": self.attachment_context_uid,
                "name": self.attachment_context_name,
            },
            "grant": {
                "uid": self.grant_uid,
                "revision": self.grant_revision,
                "digest": self.grant_digest,
                "permissions": list(self.permissions),
            },
            "resource": {
                "uid": self.resource_uid,
                "name": self.resource_name,
            },
            "authority_context_name": self.authority_context_name,
        }

    @classmethod
    def from_dict(cls, value: object) -> GrantedContextBinding:
        data = _require_mapping(
            value,
            {
                "kind",
                "public_name",
                "grantee_profile_uid",
                "authority_profile_uid",
                "attachment",
                "grant",
                "resource",
                "authority_context_name",
            },
            "granted Context binding",
        )
        if data["kind"] != "GRANTED_CONTEXT":
            raise ValueError("Invalid granted Context binding kind.")
        attachment = _require_mapping(
            data["attachment"],
            {"uid", "name"},
            "granted Context attachment",
        )
        grant = _require_mapping(
            data["grant"],
            {"uid", "revision", "digest", "permissions"},
            "granted Context grant",
        )
        resource = _require_mapping(
            data["resource"],
            {"uid", "name"},
            "granted Context resource",
        )
        revision = grant["revision"]
        permissions = grant["permissions"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError("Invalid granted Context grant revision.")
        if (
            not isinstance(permissions, list)
            or not permissions
            or any(not isinstance(item, str) or not item for item in permissions)
            or len(set(permissions)) != len(permissions)
        ):
            raise ValueError("Invalid granted Context permissions.")
        try:
            canonical_permissions = canonical_grant_permissions(
                permissions,
                allow_legacy=True,
            )
        except ProfileConfigError as error:
            raise ValueError("Invalid granted Context permissions.") from error
        if not _is_sha256(grant["digest"]):
            raise ValueError("Invalid granted Context grant digest.")
        return cls(
            public_name=_require_text(data["public_name"], "granted public name"),
            grantee_profile_uid=_require_uid(
                data["grantee_profile_uid"],
                "granted grantee Profile uid",
            ),
            authority_profile_uid=_require_uid(
                data["authority_profile_uid"],
                "granted authority Profile uid",
            ),
            attachment_context_uid=_require_text(
                attachment["uid"],
                "granted attachment Context uid",
            ),
            attachment_context_name=_require_text(
                attachment["name"],
                "granted attachment Context name",
            ),
            grant_uid=_require_uid(grant["uid"], "granted grant uid"),
            grant_revision=revision,
            grant_digest=grant["digest"],
            resource_uid=_require_text(resource["uid"], "granted resource uid"),
            resource_name=_require_text(resource["name"], "granted resource name"),
            authority_context_name=_require_text(
                data["authority_context_name"],
                "granted authority Context name",
            ),
            permissions=canonical_permissions,
        )


def authority_context_name(
    binding: GrantedContextBinding,
    public_name: str,
) -> str:
    """Map one public Context inside a frozen Grant to its physical name."""

    if not isinstance(binding, GrantedContextBinding):
        raise TypeError("Expected a granted Context binding.")
    if not (
        public_name == binding.public_name
        or public_name.startswith(binding.public_name + "/")
    ):
        raise ValueError("The public Context is outside the granted namespace.")
    return binding.resource_name + public_name[len(binding.public_name) :]


def public_context_name(
    binding: GrantedContextBinding,
    authority_name: str,
) -> str:
    """Map one physical Context inside a frozen Grant to its public name."""

    if not isinstance(binding, GrantedContextBinding):
        raise TypeError("Expected a granted Context binding.")
    if not (
        authority_name == binding.resource_name
        or authority_name.startswith(binding.resource_name + "/")
    ):
        raise ValueError("The authority Context is outside the granted namespace.")
    return binding.public_name + authority_name[len(binding.resource_name) :]


def granted_context_binding_digest(value: object) -> str:
    """Digest one validated registry Grant record for a frozen binding."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "GrantedContextBinding",
    "authority_context_name",
    "granted_context_binding_digest",
    "public_context_name",
]
