"""Sever terminal setup projections."""

from memcommit.adapters.interfaces.tui.operations.sever.model import (
    SeverEndpointSelection,
    SeverSetupReceipt,
    SeverTuiSetup,
)
from memcommit.adapters.interfaces.tui.operations.sever.setup import (
    _shared_local_output_name,
    choose_sever_endpoint_setup,
    choose_sever_setup,
    sever_endpoint_setup_spec,
)

__all__ = [
    "SeverEndpointSelection",
    "SeverSetupReceipt",
    "SeverTuiSetup",
    "_shared_local_output_name",
    "choose_sever_endpoint_setup",
    "choose_sever_setup",
    "sever_endpoint_setup_spec",
]
