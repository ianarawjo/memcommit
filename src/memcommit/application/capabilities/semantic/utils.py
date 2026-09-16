"""
    Generic helpers shared across all semantic (LLM-based) operations.
    These utilities are operation-agnostic: they handle message construction
    and JSON extraction, leaving interpretation to each operation's own module.
"""
from __future__ import annotations

import json
import re
import warnings


def build_messages(
    system: str = "",
    user_content: str = "",
    history: list[dict] | None = None,
    feedback: str | None = None,
) -> list[dict]:
    """
    Construct the message list for an LLM chat call.

    First call (history=None, feedback=None):
        Returns [{"role": "system", ...}, {"role": "user", ...}].
    Revision call (history and feedback both provided):
        Appends a user feedback turn to the existing history.
        system and user_content are ignored — they are already in the history.
    """
    if history is not None and feedback is not None:
        return history + [
            {"role": "user", "content": f"Please revise your proposal. Feedback: {feedback}"}
        ]
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user_content},
    ]


def extract_json(text: str) -> dict:
    """
    Find and parse the first JSON object in text.
    Tolerates prose before and after the JSON block (common LLM leakage).
    If no valid JSON object can be found or parsed, emits a warning and
    returns an empty object.
    """
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        warnings.warn(
            f"No JSON object found in LLM response; using empty response.\n{text[:400]}",
            RuntimeWarning,
            stacklevel=2,
        )
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        warnings.warn(
            f"Could not parse JSON from LLM response; using empty response: {e}\n{match.group()[:400]}",
            RuntimeWarning,
            stacklevel=2,
        )
        return {}
