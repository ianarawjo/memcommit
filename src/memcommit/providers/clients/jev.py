"""OpenRouter Jev decisions over host-authored choices, without executing them."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from memcommit.providers.http import JsonRequester, request_json
from memcommit.providers.errors import QueryProviderError


JEV_MODEL = "typesafe/jev-1.13"
JEV_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"


@dataclass(frozen=True)
class JevDecision:
    """A choice and its evidence; execution and confidence policy belong to the caller."""

    choice: str
    confidence: float
    probabilities: tuple[tuple[str, float], ...]
    model: str
    request_id: str | None
    provider: str | None
    cost: float | None


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QueryProviderError(f"Jev {label} must be non-empty text.")
    return value


def _number(value: object, label: str, *, maximum=math.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QueryProviderError(f"Jev returned invalid {label}.")
    try:
        number = float(value)
    except OverflowError:
        raise QueryProviderError(f"Jev returned invalid {label}.") from None
    if not math.isfinite(number) or not 0 <= number <= maximum:
        raise QueryProviderError(f"Jev returned invalid {label}.")
    return number


def _decode(response: dict[str, object], choices: Mapping[str, str]) -> JevDecision:
    answers = response.get("answers")
    if (
        "error" in response
        or not isinstance(answers, dict)
        or set(answers) != {"action"}
    ):
        raise QueryProviderError("Jev returned no valid action answer.")
    answer = answers["action"]
    if (
        not isinstance(answer, dict)
        or set(answer) != {"type", "choice", "confidence", "probabilities"}
        or answer["type"] != "choice"
    ):
        raise QueryProviderError("Jev returned an invalid choice answer.")
    choice = answer["choice"]
    if not isinstance(choice, str) or choice not in choices:
        raise QueryProviderError("Jev selected an action outside the supplied choices.")
    raw = answer["probabilities"]
    if not isinstance(raw, dict) or set(raw) != set(choices):
        raise QueryProviderError("Jev probabilities do not match the supplied choices.")
    probabilities = tuple(
        (key, _number(raw[key], "probability", maximum=1)) for key in choices
    )
    if not math.isclose(sum(p for _, p in probabilities), 1, abs_tol=1e-6):
        raise QueryProviderError("Jev probabilities do not sum to one.")
    if raw[choice] < max(p for _, p in probabilities):
        raise QueryProviderError(
            "Jev choice does not match its probability distribution."
        )
    model = _text(response.get("model"), "response model")
    # OpenRouter may report the dated serving build of the pinned model.
    if (
        model != JEV_MODEL
        and re.fullmatch(re.escape(JEV_MODEL) + r"-\d{8}", model) is None
    ):
        raise QueryProviderError("Jev returned a different model than requested.")
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise QueryProviderError("Jev returned no usage metadata.")
    return JevDecision(
        choice=choice,
        confidence=_number(answer["confidence"], "confidence", maximum=1),
        probabilities=probabilities,
        model=model,
        request_id=_text(response["id"], "request ID") if "id" in response else None,
        provider=_text(response["provider"], "provider")
        if "provider" in response
        else None,
        cost=_number(usage["cost"], "cost") if "cost" in usage else None,
    )


@dataclass(frozen=True)
class JevClient:
    """One bounded Choice call; no chat completion, input generation, or key presses."""

    api_key: str = field(repr=False)
    timeout: float = 15.0
    _requester: JsonRequester = field(default=request_json, repr=False, compare=False)

    def __post_init__(self) -> None:
        _text(self.api_key, "OPENROUTER_API_KEY")
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not math.isfinite(self.timeout)
            or self.timeout <= 0
        ):
            raise QueryProviderError("Jev timeout must be a finite positive number.")

    def choose(
        self, *, state: str, instructions: str, choices: Mapping[str, str]
    ) -> JevDecision:
        """Return one of the caller's identifiers; never generate executable input."""
        _text(state, "state")
        _text(instructions, "instructions")
        if not isinstance(choices, Mapping) or not choices:
            raise QueryProviderError("Jev requires a non-empty choice mapping.")
        frozen_choices = dict(choices)
        for key, description in frozen_choices.items():
            _text(key, "choice identifier")
            _text(description, "choice description")
        response = self._requester(
            JEV_ENDPOINT,
            "POST",
            {
                "model": JEV_MODEL,
                "state": state,
                "questions": {
                    "action": {
                        "type": "choice",
                        "instructions": instructions,
                        "criteria": dict(frozen_choices),
                    }
                },
                "provider": {"allow_fallbacks": False, "data_collection": "deny"},
            },
            {"Authorization": f"Bearer {self.api_key}"},
            self.timeout,
            "Jev decision",
        )
        return _decode(response, frozen_choices)
