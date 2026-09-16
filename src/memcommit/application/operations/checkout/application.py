"""Choose the existing Branch or Switch application route for Checkout."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CheckoutAction(str, Enum):
    """Application operation selected by the Checkout grammar."""

    SWITCH = "SWITCH"
    BRANCH = "BRANCH"


@dataclass(frozen=True, slots=True)
class CheckoutRequest:
    """Adapter-neutral Checkout operands."""

    name: str | None
    create_branch: bool = False


@dataclass(frozen=True, slots=True)
class CheckoutPlan:
    """Exact existing operation route selected for one Checkout request."""

    action: CheckoutAction
    name: str | None


def plan_checkout(request: CheckoutRequest) -> CheckoutPlan:
    """Select Branch or Switch; the selected operation owns its execution."""

    if request.create_branch:
        return CheckoutPlan(
            action=CheckoutAction.BRANCH,
            name=request.name,
        )
    return CheckoutPlan(action=CheckoutAction.SWITCH, name=request.name)


__all__ = ["CheckoutAction", "CheckoutPlan", "CheckoutRequest", "plan_checkout"]
