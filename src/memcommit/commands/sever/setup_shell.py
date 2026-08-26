"""Compatibility facade for the interface-owned Sever endpoint setup."""

from memcommit.interfaces.tui.operations.sever import (
    SeverSetupReceipt,
    _shared_local_output_name,
    choose_sever_setup,
)

__all__ = [
    "SeverSetupReceipt",
    "_shared_local_output_name",
    "choose_sever_setup",
]
