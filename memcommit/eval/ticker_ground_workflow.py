"""Strict staged corpus for the iterative synthetic-ticker Ground workflow.

The corpus is evaluation evidence, not production prompt material.  A runner may
reveal each round's propositions to Distill, Elaborate, or Fit, but it must not
send the host-side category and resolution labels as semantic hints.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Literal, cast


TICKER_WORKFLOW_SCHEMA_VERSION = 1
TICKER_WORKFLOW_RULESET_VERSION = "synthetic-ticker-ground-v1"
TICKER_WORKFLOW_CORPUS_ROLE = "ITERATIVE_GROUND_BENCHMARK"
TICKER_WORKFLOW_STAGE_SIZES = (5, 10, 20, 35, 50)
TICKER_WORKFLOW_GOAL = "티커가 어떻게 만들어지는지 규칙을 알고 싶어"
DEFAULT_TICKER_WORKFLOW_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "ticker_ground_workflow.json"
)

TickerExampleRole = Literal["FIT", "BOUNDARY", "CONTRAST"]
TickerResolution = Literal["DETERMINED", "UNRESOLVED"]


class TickerWorkflowError(ValueError):
    """The staged ticker benchmark is malformed or semantically inconsistent."""


@dataclass(frozen=True)
class TickerWorkflowExample:
    """One proposition revealed in a fixed round of the Ground dialogue."""

    case_id: str
    reveal_round: int
    company: str
    proposition: str
    expected_output: str
    role: TickerExampleRole
    resolution: TickerResolution
    categories: tuple[str, ...]


@dataclass(frozen=True)
class TickerWorkflowCorpus:
    """One immutable 5 -> 10 -> 20 -> 35 -> 50 evaluation progression."""

    path: Path
    digest: str
    vague_goal: str
    stage_sizes: tuple[int, ...]
    coverage_categories: tuple[str, ...]
    examples: tuple[TickerWorkflowExample, ...]

    def examples_through_round(
        self,
        reveal_round: int,
    ) -> tuple[TickerWorkflowExample, ...]:
        if reveal_round not in range(1, len(self.stage_sizes) + 1):
            raise TickerWorkflowError("Ticker workflow round is out of range.")
        result = tuple(
            example
            for example in self.examples
            if example.reveal_round <= reveal_round
        )
        expected_size = self.stage_sizes[reveal_round - 1]
        if len(result) != expected_size:
            raise TickerWorkflowError(
                "Ticker workflow round does not match its frozen stage size."
            )
        return result


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TickerWorkflowError(f"Duplicate ticker workflow key: {key}.")
        result[key] = value
    return result


def _text(value: object, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise TickerWorkflowError(f"Ticker workflow {label} is invalid.")
    if value != value.strip():
        raise TickerWorkflowError(
            f"Ticker workflow {label} must not have surrounding whitespace."
        )
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TickerWorkflowError(f"Ticker workflow {label} must be nonempty.")
    result = tuple(_text(item, f"{label} item") for item in value)
    if len(result) != len(set(result)):
        raise TickerWorkflowError(f"Ticker workflow {label} must be unique.")
    return result


def _mapping_proposition(company: str, expected_output: str) -> str:
    return (
        f'Applying the synthetic ticker Rules to "{company}" produces '
        f'"{expected_output}".'
    )


def _example(value: object, *, index: int) -> TickerWorkflowExample:
    fields = {
        "id",
        "reveal_round",
        "company",
        "proposition",
        "expected_output",
        "role",
        "resolution",
        "categories",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise TickerWorkflowError(
            f"Ticker workflow Example {index} has an invalid field set."
        )
    case_id = _text(value["id"], f"Example {index} id")
    reveal_round = value["reveal_round"]
    if (
        isinstance(reveal_round, bool)
        or not isinstance(reveal_round, int)
        or reveal_round not in range(1, 6)
    ):
        raise TickerWorkflowError(
            f"Ticker workflow Example {case_id} has an invalid reveal round."
        )
    company = _text(value["company"], f"Example {case_id} company")
    proposition = _text(
        value["proposition"],
        f"Example {case_id} proposition",
    )
    expected_output = _text(
        value["expected_output"],
        f"Example {case_id} expected output",
        empty=True,
    )
    role = value["role"]
    if role not in {"FIT", "BOUNDARY", "CONTRAST"}:
        raise TickerWorkflowError(
            f"Ticker workflow Example {case_id} has an invalid role."
        )
    resolution = value["resolution"]
    if resolution not in {"DETERMINED", "UNRESOLVED"}:
        raise TickerWorkflowError(
            f"Ticker workflow Example {case_id} has an invalid resolution."
        )
    if resolution == "DETERMINED":
        if not expected_output or proposition != _mapping_proposition(
            company,
            expected_output,
        ):
            raise TickerWorkflowError(
                f"Determined ticker Example {case_id} must use its exact mapping."
            )
    elif expected_output or "remains unresolved" not in proposition:
        raise TickerWorkflowError(
            f"Unresolved ticker Example {case_id} must stay visibly unresolved."
        )
    return TickerWorkflowExample(
        case_id=case_id,
        reveal_round=reveal_round,
        company=company,
        proposition=proposition,
        expected_output=expected_output,
        role=cast(TickerExampleRole, role),
        resolution=cast(TickerResolution, resolution),
        categories=_string_tuple(
            value["categories"],
            f"Example {case_id} categories",
        ),
    )


def load_ticker_workflow(
    path: Path | None = None,
) -> TickerWorkflowCorpus:
    """Load the strict benchmark without making host labels prompt-visible."""

    fixture_path = path or DEFAULT_TICKER_WORKFLOW_FIXTURE
    try:
        raw_bytes = fixture_path.read_bytes()
        value = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise TickerWorkflowError(
            "The ticker workflow fixture is not valid strict UTF-8 JSON."
        ) from error
    fields = {
        "operation",
        "schema_version",
        "ruleset_version",
        "corpus_role",
        "provider_visibility",
        "vague_goal",
        "stage_sizes",
        "coverage_categories",
        "examples",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise TickerWorkflowError(
            "The ticker workflow fixture has an invalid top-level contract."
        )
    if (
        value["operation"] != "ground"
        or value["schema_version"] != TICKER_WORKFLOW_SCHEMA_VERSION
        or isinstance(value["schema_version"], bool)
        or value["ruleset_version"] != TICKER_WORKFLOW_RULESET_VERSION
        or value["corpus_role"] != TICKER_WORKFLOW_CORPUS_ROLE
        or value["provider_visibility"] != "GOAL_AND_REVEALED_PROPOSITIONS_ONLY"
        or value["vague_goal"] != TICKER_WORKFLOW_GOAL
        or value["stage_sizes"] != list(TICKER_WORKFLOW_STAGE_SIZES)
    ):
        raise TickerWorkflowError(
            "The ticker workflow fixture identity or exposure contract is invalid."
        )
    categories = _string_tuple(
        value["coverage_categories"],
        "coverage categories",
    )
    raw_examples = value["examples"]
    if not isinstance(raw_examples, list) or len(raw_examples) != 50:
        raise TickerWorkflowError("The ticker workflow must contain exactly 50 Examples.")
    examples = tuple(
        _example(example, index=index)
        for index, example in enumerate(raw_examples, 1)
    )
    ids = tuple(example.case_id for example in examples)
    companies = tuple(example.company for example in examples)
    if len(ids) != len(set(ids)) or len(companies) != len(set(companies)):
        raise TickerWorkflowError(
            "Ticker workflow Example ids and company names must be unique."
        )
    observed_categories = {
        category for example in examples for category in example.categories
    }
    if observed_categories != set(categories):
        raise TickerWorkflowError(
            "Ticker workflow category coverage does not match its contract."
        )
    corpus = TickerWorkflowCorpus(
        path=fixture_path,
        digest=hashlib.sha256(raw_bytes).hexdigest(),
        vague_goal=TICKER_WORKFLOW_GOAL,
        stage_sizes=TICKER_WORKFLOW_STAGE_SIZES,
        coverage_categories=categories,
        examples=examples,
    )
    for reveal_round in range(1, 6):
        corpus.examples_through_round(reveal_round)
    if sum(item.resolution == "UNRESOLVED" for item in examples) != 4:
        raise TickerWorkflowError(
            "Ticker workflow must retain exactly four explicit unresolved boundaries."
        )
    return corpus


__all__ = [
    "DEFAULT_TICKER_WORKFLOW_FIXTURE",
    "TICKER_WORKFLOW_CORPUS_ROLE",
    "TICKER_WORKFLOW_GOAL",
    "TICKER_WORKFLOW_RULESET_VERSION",
    "TICKER_WORKFLOW_SCHEMA_VERSION",
    "TICKER_WORKFLOW_STAGE_SIZES",
    "TickerWorkflowCorpus",
    "TickerWorkflowError",
    "TickerWorkflowExample",
    "load_ticker_workflow",
]
