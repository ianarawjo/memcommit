"""Application operation for reading and writing global configuration."""

from memcommit.application.operations.config.application import (
    ConfigEntry,
    ConfigurationPort,
    list_configuration,
    set_configuration,
)

__all__ = [
    "ConfigEntry",
    "ConfigurationPort",
    "list_configuration",
    "set_configuration",
]
