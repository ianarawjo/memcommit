#!/usr/bin/env python3
"""Generate and verify the canonical operation-evidence index.

The classification registry owns operation route state, while the evidence
registry owns operation-to-document membership. This script validates both
against Help, verifies local links, and renders one disposable readable index.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import unquote


REPOSITORY = Path(__file__).resolve().parents[1]
AGENT_RECORDS = REPOSITORY / "agent-records" / "docs"
REGISTRY = AGENT_RECORDS / "operation-route-classification.json"
EVIDENCE_REGISTRY = AGENT_RECORDS / "operation-evidence-index.json"
GENERATED_INDEX = AGENT_RECORDS / "generated" / "operation-evidence-index.md"
CURATED_STATES = ("CLOSED", "MIXED", "LEGACY", "N/A", "UNREVIEWED")
_MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


class EvidenceError(ValueError):
    """The checked-in evidence registry or one of its governed links is invalid."""


def _help_operation_names(repository: Path) -> tuple[str, ...]:
    """Read canonical operation names without importing application code."""

    path = (
        repository
        / "src"
        / "memcommit"
        / "application"
        / "operations"
        / "operation_catalog"
        / "catalog.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_operation"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    if not names:
        raise EvidenceError(f"{path}: no Help operations found")
    return tuple(sorted(names))


def load_registry(repository: Path = REPOSITORY) -> dict[str, object]:
    path = (
        repository
        / "agent-records"
        / "docs"
        / "operation-route-classification.json"
    )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"{path}: cannot load registry: {error}") from error
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise EvidenceError(f"{path}: expected schema version 1")
    definitions = document.get("definitions")
    if not isinstance(definitions, dict) or tuple(definitions) != CURATED_STATES:
        raise EvidenceError(
            f"{path}: definitions must declare {CURATED_STATES!r} in order"
        )
    classifications = document.get("classifications")
    if not isinstance(classifications, dict) or tuple(classifications) != CURATED_STATES:
        raise EvidenceError(
            f"{path}: classifications must declare {CURATED_STATES!r} in order"
        )
    return document


def operation_records(
    document: dict[str, object],
    repository: Path = REPOSITORY,
) -> dict[str, tuple[str, tuple[str, ...], str]]:
    """Validate and flatten the registry to operation -> state/evidence/reason."""

    classifications = document["classifications"]
    assert isinstance(classifications, dict)
    records: dict[str, tuple[str, tuple[str, ...], str]] = {}
    for state in CURATED_STATES:
        entries = classifications[state]
        if state == "UNREVIEWED":
            if not isinstance(entries, list) or not all(
                isinstance(name, str) for name in entries
            ):
                raise EvidenceError(f"{REGISTRY}: UNREVIEWED must be a string list")
            state_records = ((name, (), "") for name in entries)
        else:
            if not isinstance(entries, dict):
                raise EvidenceError(f"{REGISTRY}: {state} must be an evidence object")
            flattened: list[tuple[str, tuple[str, ...], str]] = []
            for name, value in entries.items():
                if not isinstance(name, str) or not isinstance(value, dict):
                    raise EvidenceError(f"{REGISTRY}: invalid {state} record")
                evidence = value.get("evidence")
                reason = value.get("reason")
                if not isinstance(evidence, list) or not evidence or not all(
                    isinstance(item, str) for item in evidence
                ):
                    raise EvidenceError(
                        f"{REGISTRY}: {state}/{name} requires evidence paths"
                    )
                if len(evidence) != len(set(evidence)):
                    raise EvidenceError(
                        f"{REGISTRY}: {state}/{name} repeats an evidence path"
                    )
                if not isinstance(reason, str) or not reason.strip():
                    raise EvidenceError(f"{REGISTRY}: {state}/{name} requires a reason")
                flattened.append((name, tuple(evidence), reason.strip()))
            state_records = iter(flattened)

        for name, evidence, reason in state_records:
            if name in records:
                raise EvidenceError(f"{REGISTRY}: operation {name!r} is classified twice")
            for evidence_path in evidence:
                pure_path = PurePosixPath(evidence_path)
                if (
                    pure_path.is_absolute()
                    or not pure_path.parts
                    or pure_path.parts[:2] != ("agent-records", "docs")
                    or ".." in pure_path.parts
                ):
                    raise EvidenceError(
                        f"{REGISTRY}: {state}/{name} has unsafe evidence path "
                        f"{evidence_path!r}"
                    )
                candidate = repository.joinpath(*pure_path.parts)
                if not candidate.is_file():
                    raise EvidenceError(
                        f"{REGISTRY}: {state}/{name} evidence is missing: "
                        f"{evidence_path}"
                    )
            records[name] = (state, evidence, reason)

    expected = set(_help_operation_names(repository))
    actual = set(records)
    if actual != expected:
        raise EvidenceError(
            f"{REGISTRY}: coverage differs from Help; "
            f"missing={sorted(expected - actual)!r}, extra={sorted(actual - expected)!r}"
        )
    return records


def load_evidence_records(
    repository: Path = REPOSITORY,
) -> dict[str, tuple[str, ...]]:
    path = repository / "agent-records" / "docs" / "operation-evidence-index.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"{path}: cannot load evidence index: {error}") from error
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise EvidenceError(f"{path}: expected evidence schema version 1")
    if document.get("classification_source") != (
        "agent-records/docs/operation-route-classification.json"
    ):
        raise EvidenceError(f"{path}: unexpected classification source")
    operations = document.get("operations")
    if not isinstance(operations, dict):
        raise EvidenceError(f"{path}: operations must be an object")

    expected = set(_help_operation_names(repository))
    actual = set(operations)
    if actual != expected:
        raise EvidenceError(
            f"{path}: coverage differs from Help; "
            f"missing={sorted(expected - actual)!r}, extra={sorted(actual - expected)!r}"
        )

    records: dict[str, tuple[str, ...]] = {}
    for operation, evidence in operations.items():
        if not isinstance(operation, str) or not isinstance(evidence, list) or not all(
            isinstance(item, str) for item in evidence
        ):
            raise EvidenceError(f"{path}: {operation!r} must contain an evidence list")
        if len(evidence) != len(set(evidence)):
            raise EvidenceError(f"{path}: {operation!r} repeats an evidence path")
        for evidence_path in evidence:
            pure_path = PurePosixPath(evidence_path)
            if (
                pure_path.is_absolute()
                or not pure_path.parts
                or pure_path.parts[:2] != ("agent-records", "docs")
                or ".." in pure_path.parts
            ):
                raise EvidenceError(
                    f"{path}: {operation!r} has unsafe evidence path "
                    f"{evidence_path!r}"
                )
            if not repository.joinpath(*pure_path.parts).is_file():
                raise EvidenceError(
                    f"{path}: {operation!r} evidence is missing: {evidence_path}"
                )
        records[operation] = tuple(evidence)
    return records


def combine_records(
    classifications: dict[str, tuple[str, tuple[str, ...], str]],
    evidence_records: dict[str, tuple[str, ...]],
) -> dict[str, tuple[str, tuple[str, ...], str]]:
    """Join the two authored roles and reject compatibility-field drift."""

    combined: dict[str, tuple[str, tuple[str, ...], str]] = {}
    for operation, (state, classification_evidence, reason) in classifications.items():
        registered_evidence = evidence_records[operation]
        # Schema version 1 of the classification file still carries evidence
        # for reviewed states. Keep that compatibility field exact until the
        # callable catalog migrates; the separate index is the membership owner.
        if state != "UNREVIEWED" and classification_evidence != registered_evidence:
            raise EvidenceError(
                f"{REGISTRY}: {operation!r} evidence differs from "
                f"{EVIDENCE_REGISTRY.name}"
            )
        combined[operation] = (state, registered_evidence, reason)
    return combined


def _registered_evidence(
    records: dict[str, tuple[str, tuple[str, ...], str]],
) -> set[str]:
    return {
        evidence
        for _state, paths, _reason in records.values()
        for evidence in paths
    }


def validate_boundary_matrix_registration(
    records: dict[str, tuple[str, tuple[str, ...], str]],
    repository: Path = REPOSITORY,
) -> None:
    """Require every final operation boundary matrix to enter the registry."""

    registered = _registered_evidence(records)
    matrix_paths = {
        path.relative_to(repository).as_posix()
        for path in (repository / "agent-records" / "docs").glob(
            "*boundary-matrix.md"
        )
        if path.name != "operation-consistency-matrix.md"
    }
    missing = sorted(matrix_paths - registered)
    if missing:
        raise EvidenceError(
            "unregistered operation boundary matrices: " + ", ".join(missing)
        )
    allowed_suffixes = (
        "-application-boundary-matrix.md",
        "-callable-boundary-matrix.md",
    )
    invalid_names = sorted(
        path for path in matrix_paths if not path.endswith(allowed_suffixes)
    )
    if invalid_names:
        raise EvidenceError(
            "operation boundary matrices use an unsupported name: "
            + ", ".join(invalid_names)
        )


def _local_link_target(raw_target: str) -> str | None:
    raw_target = raw_target.strip()
    if raw_target.startswith("<") and ">" in raw_target:
        target = raw_target[1 : raw_target.index(">")]
    else:
        target = raw_target.split(maxsplit=1)[0]
    target = unquote(target)
    if not target or target.startswith("#"):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
        return None
    return target.split("#", 1)[0]


def validate_markdown_links(paths: set[Path], repository: Path = REPOSITORY) -> None:
    failures: list[str] = []
    for path in sorted(paths):
        if path.suffix.lower() != ".md":
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            for raw_target in _MARKDOWN_LINK.findall(line):
                target = _local_link_target(raw_target)
                if target is None:
                    continue
                candidate = (path.parent / target).resolve()
                try:
                    candidate.relative_to(repository.resolve())
                except ValueError:
                    failures.append(
                        f"{path.relative_to(repository)}:{line_number}: "
                        f"link escapes repository: {raw_target}"
                    )
                    continue
                if candidate == (
                    repository
                    / "agent-records"
                    / "docs"
                    / "generated"
                    / "operation-evidence-index.md"
                ):
                    # The write mode must be able to bootstrap this generated
                    # target. Check mode validates its presence and contents.
                    continue
                if not candidate.exists():
                    failures.append(
                        f"{path.relative_to(repository)}:{line_number}: "
                        f"missing link target: {raw_target}"
                    )
    if failures:
        raise EvidenceError("\n".join(failures))


def validate_governing_agent_records(repository: Path = REPOSITORY) -> None:
    canonical = "operation-route-classification.json"
    evidence = "operation-evidence-index.json"
    generated = "generated/operation-evidence-index.md"
    for path in (
        repository / "agent-records" / "docs" / "README.md",
        repository / "agent-records" / "docs" / "operation-consistency-matrix.md",
        repository
        / "agent-records"
        / "docs"
        / "distribution-boundary-and-architecture-understanding-plan.md",
        repository / "agent-records" / "docs" / "callable-catalog-design-rationale.md",
    ):
        text = path.read_text(encoding="utf-8")
        missing = [name for name in (canonical, evidence, generated) if name not in text]
        if missing:
            raise EvidenceError(
                f"{path}: must point to canonical operation evidence files: {missing!r}"
            )

    # Hard-coded state totals are especially prone to drift. Generated views
    # may report them; authored common ledgers must consult the registry.
    stale_count = re.compile(
        r"\b\d+\s+`?(?:CLOSED|MIXED|LEGACY|N/A|UNREVIEWED)`?",
        re.IGNORECASE,
    )
    for path in (
        repository / "agent-records" / "docs" / "operation-consistency-matrix.md",
        repository
        / "agent-records"
        / "docs"
        / "distribution-boundary-and-architecture-understanding-plan.md",
    ):
        if match := stale_count.search(path.read_text(encoding="utf-8")):
            raise EvidenceError(
                f"{path}: duplicates an operation-state total near {match.group(0)!r}"
            )


def render_index(
    records: dict[str, tuple[str, tuple[str, ...], str]],
) -> str:
    rows = [
        "# Generated operation evidence index",
        "",
        "This file is generated by `scripts/verify_operation_evidence.py`.",
        "Do not edit it directly. Route state comes only from",
        "`agent-records/docs/operation-route-classification.json`; document membership comes",
        "only from `agent-records/docs/operation-evidence-index.json`.",
        "",
        "| Operation | Route state | Registered evidence | Reviewed conclusion |",
        "| --- | --- | --- | --- |",
    ]
    for operation in sorted(records):
        state, evidence, reason = records[operation]
        links = "<br>".join(
            f"[`{PurePosixPath(path).name}`](../{PurePosixPath(path).relative_to('agent-records/docs').as_posix()})"
            for path in evidence
        ) or "—"
        safe_reason = reason.replace("|", "\\|") if reason else "—"
        rows.append(f"| `{operation}` | `{state}` | {links} | {safe_reason} |")
    return "\n".join(rows) + "\n"


def verify(repository: Path = REPOSITORY) -> str:
    document = load_registry(repository)
    classifications = operation_records(document, repository)
    evidence_records = load_evidence_records(repository)
    records = combine_records(classifications, evidence_records)
    validate_boundary_matrix_registration(records, repository)
    validate_governing_agent_records(repository)
    evidence_paths = {
        repository / path
        for path in _registered_evidence(records)
        if path.endswith(".md")
    }
    governed_paths = {
        repository / "agent-records" / "docs" / "README.md",
        repository / "agent-records" / "docs" / "operation-consistency-matrix.md",
        repository
        / "agent-records"
        / "docs"
        / "distribution-boundary-and-architecture-understanding-plan.md",
        repository
        / "agent-records"
        / "docs"
        / "operation-evidence-ledger-design-rationale.md",
        repository / "agent-records" / "docs" / "callable-catalog-design-rationale.md",
    }
    validate_markdown_links(evidence_paths | governed_paths, repository)
    return render_index(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the generated evidence index is missing or stale",
    )
    args = parser.parse_args()
    try:
        rendered = verify(REPOSITORY)
    except EvidenceError as error:
        print(error, file=sys.stderr)
        return 1

    if args.check:
        if not GENERATED_INDEX.is_file():
            print(f"missing generated evidence index: {GENERATED_INDEX}", file=sys.stderr)
            return 1
        if GENERATED_INDEX.read_text(encoding="utf-8") != rendered:
            print(f"stale generated evidence index: {GENERATED_INDEX}", file=sys.stderr)
            return 1
        print("operation evidence is consistent")
        return 0

    GENERATED_INDEX.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_INDEX.write_text(rendered, encoding="utf-8")
    print(f"wrote {GENERATED_INDEX.relative_to(REPOSITORY)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
