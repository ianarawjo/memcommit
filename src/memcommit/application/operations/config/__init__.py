"""Application operation for reading and writing global configuration."""

from memcommit.application.operations.config.application import (
    list_configuration,
    set_configuration,
)

__all__ = [
    "list_configuration",
    "set_configuration",
]
