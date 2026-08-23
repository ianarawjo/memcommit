"""Deterministic passing responses for Elaborate's independent validation turns."""

from __future__ import annotations

import json

from memcommit.conformance import CONTEXT_CONFORMANCE_OPERATION
from memcommit.fit_judgment import (
    FIT_JUDGMENT_OPERATION,
    FIT_JUDGMENT_PAYLOAD_MARKER,
)


def passing_elaborate_validation_response(
    prompt: str,
    operation: str,
) -> str | None:
    """Return a passing validation envelope, or None for a generation turn."""

    if operation == CONTEXT_CONFORMANCE_OPERATION:
        payload = json.loads(
            prompt.split("CONFORMANCE CONTEXT PAYLOAD:\n", 1)[1]
        )
        memory_ids = [
            item["memory_id"]
            for item in payload["target_context"]["memories"]
        ]
        return json.dumps(
            {
                "judgments": [
                    {
                        "rule_id": rule["rule_id"],
                        "status": "CONFORMS",
                        "evidence_memory_ids": memory_ids,
                        "nonconforming_cases": [],
                        "reason": "Every generated Case visibly follows this Rule.",
                    }
                    for rule in payload["rules"]
                ],
                "outside_memory_ids": [],
            }
        )
    if operation == FIT_JUDGMENT_OPERATION:
        payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
        questions = payload["questions"]
        if not questions or not all(
            str(question["question_id"]).startswith("c")
            for question in questions
        ):
            return None
        judgments = []
        for question in questions:
            aliases = [
                item["proposition_id"]
                for item in (*question["background"], *question["propositions"])
            ]
            judgments.append(
                {
                    "question_id": question["question_id"],
                    "verdict": "YES",
                    "reason": "The generated Case and complete Source can coexist.",
                    "considered_proposition_ids": aliases,
                    "material_proposition_ids": [],
                    "consistent_reading": "",
                    "inconsistent_reading": "",
                }
            )
        return json.dumps(
            {
                "overview": "Every generated Case Fits the complete Source.",
                "judgments": judgments,
            }
        )
    return None


__all__ = ["passing_elaborate_validation_response"]
