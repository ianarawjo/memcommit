"""Shared passing response for Distill providers used by focused tests."""

from __future__ import annotations

import json

from memcommit.application.operations.distill.goal_fit import (
    DISTILL_GOAL_FIT_OPERATION,
    DISTILL_GOAL_FIT_PAYLOAD_MARKER,
)


def passing_distill_goal_fit_response(
    prompt: str,
    operation: str,
) -> str | None:
    if operation != DISTILL_GOAL_FIT_OPERATION:
        return None
    payload = json.loads(prompt.split(DISTILL_GOAL_FIT_PAYLOAD_MARKER, 1)[1])
    aliases = [rule["rule_id"] for rule in payload["rules"]]
    return json.dumps(
        {
            "verdict": "FIT",
            "reason": "Every proposed Rule is relevant to and compatible with the Goal.",
            "considered_rule_ids": aliases,
            "material_rule_ids": [],
        }
    )


__all__ = ["passing_distill_goal_fit_response"]
