"""Adapter-neutral use cases for the Config operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


class ConfigurationPort(Protocol):
    """Minimal global configuration boundary used by the operation."""

    def all(self) -> Mapping[str, object]: ...

    def set(self, key: str, value: object) -> None: ...


@dataclass(frozen=True, slots=True)
class ConfigEntry:
    """One stable key/value projection returned by Config."""

    key: str
    value: object


_PUBLIC_KEY_ALIASES = {
    "llm": "llm_model",
    "provider": "semantic_provider",
    "model": "semantic_model",
}


def list_configuration(port: ConfigurationPort) -> tuple[ConfigEntry, ...]:
    """Return the stored configuration in its persisted iteration order."""

    return tuple(ConfigEntry(key, value) for key, value in port.all().items())


def set_configuration(
    port: ConfigurationPort,
    key: str,
    value: object,
) -> ConfigEntry:
    """Normalize a public key alias and persist its exact value."""

    canonical_key = _PUBLIC_KEY_ALIASES.get(key, key)
    port.set(canonical_key, value)
    return ConfigEntry(canonical_key, value)


__all__ = [
    "ConfigEntry",
    "ConfigurationPort",
    "list_configuration",
    "set_configuration",
]
