"""Compare terminal adapter built on shared Endpoint Setup."""

from memcommit.adapters.interfaces.tui.operations.compare.model import (
    CompareEndpointSelection,
    CompareTuiSetup,
)
from memcommit.adapters.interfaces.tui.operations.compare.setup import (
    choose_compare_endpoint_setup,
    compare_endpoint_setup_spec,
)

__all__ = [
    "CompareEndpointSelection",
    "CompareTuiSetup",
    "choose_compare_endpoint_setup",
    "compare_endpoint_setup_spec",
]
