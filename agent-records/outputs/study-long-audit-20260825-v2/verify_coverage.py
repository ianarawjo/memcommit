"""Validate the counted evidence for the six-world v2 audit.

The default mode is intentionally useful while collection is in progress: it
validates every artifact that exists, prints one compact coverage line, and
does not fail merely because work is incomplete.  ``--check`` additionally
requires the complete 1,980-attempt contract.

Each phase ledger lives at ``worlds/WORLD/phase-PHASE.json`` and may store
attempts either as ``operations.OP.attempts`` or as a flat ``trials`` list.
The stronger v2 evidence fields and execution identity are checked in either
representation; see ``validate_attempt`` and ``expected_execution_identity``
for the machine-readable contract.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shlex
from typing import Any, Mapping


WORLD_NAMES = (
    "task-1",
    "task-2",
    "task-3",
    "ticker",
    "a-is-apple",
    "practice-source",
)
PHASE_NAMES = ("core", "transform", "admin")
REQUIRED_ATTEMPTS = 5
EXPECTED_OPERATION_COUNT = 66
EXPECTED_TOTAL = 1_980
EXPECTED_CELL_COUNT = 396
EXPECTED_LEDGER_COUNT = 18
STUDY_NAME = "study-long-audit-20260825-v2"
PHASE_ATTEMPT_TOTALS = {"core": 105, "transform": 120, "admin": 105}

REQUIRED_TEXT_FIELDS = (
    "command",
    "starting_state",
    "entry_route",
    "target_route",
    "scope",
    "input_provenance",
    "consumer",
    "expected",
    "actual",
)
# Starting-state prose is deliberately excluded.  Merely changing "round 1"
# to "round 2" is accumulated state, not a materially different use method.
METHOD_SIGNATURE_FIELDS = (
    "entry_route",
    "target_route",
    "scope",
    "input_provenance",
)
PLACEHOLDER_TEXT = re.compile(
    r"^(?:n/?a|none|tbd|todo|unknown|same|same as (?:above|before)|"
    r"as above|varied|method\s*\d+|attempt\s*\d+|round\s*\d+)$",
    re.IGNORECASE,
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
NUMBERED_CAPTURE = re.compile(r"(?:^|[-_. ])(\d+)(?=[-_. ])")
COVERAGE_SUMMARY_FIELDS = {
    "expected_operations",
    "expected_attempts_per_operation",
    "counted_actual_mem_commands",
    "successful_exits",
    "expected_authority_rejections",
    "safe_authority_boundary_failures",
    "provider_infrastructure_failures",
    "store_resets",
}
COUNT_COVERAGE_SUMMARY_FIELDS = {
    "operations",
    "attempts_per_operation",
    "counted_actual_mem_commands",
    "exit_zero",
    "nonzero_boundary_or_failure",
    "wall_seconds",
    "tui_attempts",
    "continuity_breaks",
    "durable_context_tree_mutations",
}
COUNT_COVERAGE_REQUIRED_FIELDS = COUNT_COVERAGE_SUMMARY_FIELDS - {
    "continuity_breaks",
    "durable_context_tree_mutations",
}


@dataclass(frozen=True)
class AttemptRef:
    path: Path
    world: str
    phase: str
    operation: str
    attempt_id: int
    sequence: int
    payload: Mapping[str, Any]
    starting_boundary: Any
    interleave_exception: Mapping[str, Any] | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, errors: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path.name}: required control file is missing")
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{path.name}: cannot read valid JSON: {error}")
    return None


def normalized_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().split())


def is_meaningful_text(value: Any) -> bool:
    normalized = normalized_text(value)
    return bool(normalized) and not PLACEHOLDER_TEXT.fullmatch(normalized)


def is_nonempty_evidence(value: Any) -> bool:
    if isinstance(value, str):
        return is_meaningful_text(value)
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    return False


def require_sha256(
    value: Any,
    *,
    label: str,
    errors: list[str],
) -> str | None:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        errors.append(f"{label} must be a lowercase 64-character SHA-256")
        return None
    return value


def evidence_sha256(value: Any) -> str | None:
    """Extract a SHA-256 from a scalar or a scoped digest evidence object."""

    candidate = value.get("sha256") if isinstance(value, Mapping) else value
    if isinstance(candidate, str) and SHA256.fullmatch(candidate) is not None:
        return candidate
    return None


def validate_control_files(
    root: Path,
    catalog: Any,
    manifest: Any,
    errors: list[str],
) -> dict[str, tuple[str, ...]]:
    if not isinstance(catalog, Mapping) or not isinstance(manifest, Mapping):
        return {}

    raw_operations = catalog.get("operations")
    if not isinstance(raw_operations, list) or not all(
        isinstance(item, str) and item for item in raw_operations
    ):
        errors.append("catalog.json: operations must be a list of names")
        raw_operations = []
    operations = tuple(raw_operations)
    if len(operations) != EXPECTED_OPERATION_COUNT:
        errors.append(
            "catalog.json: expected exactly "
            f"{EXPECTED_OPERATION_COUNT} operations, found {len(operations)}"
        )
    if len(set(operations)) != len(operations):
        errors.append("catalog.json: operation names are not unique")

    raw_phases = catalog.get("phases")
    phase_operations: dict[str, tuple[str, ...]] = {}
    if not isinstance(raw_phases, Mapping):
        errors.append("catalog.json: phases must be an object")
    else:
        phase_keys = set(raw_phases)
        if phase_keys != set(PHASE_NAMES):
            errors.append(
                "catalog.json: phase names must be exactly "
                f"{list(PHASE_NAMES)!r}, found {sorted(phase_keys)!r}"
            )
        for phase in PHASE_NAMES:
            members = raw_phases.get(phase)
            if not isinstance(members, list) or not all(
                isinstance(item, str) and item for item in members
            ):
                errors.append(f"catalog.json: phase {phase} must be a name list")
                continue
            phase_operations[phase] = tuple(members)

    flattened = [
        operation
        for phase in PHASE_NAMES
        for operation in phase_operations.get(phase, ())
    ]
    if len(flattened) != len(set(flattened)):
        errors.append("catalog.json: an operation belongs to more than one phase")
    if set(flattened) != set(operations):
        errors.append(
            "catalog.json: phase membership must partition the exact operation catalog"
        )

    lanes = manifest.get("lanes")
    if not isinstance(lanes, Mapping) or set(lanes) != set(WORLD_NAMES):
        found = sorted(lanes) if isinstance(lanes, Mapping) else []
        errors.append(
            "snapshot-manifest.json: lanes must name exactly the six worlds; "
            f"found {found!r}"
        )

    catalog_manifest = manifest.get("catalog")
    if not isinstance(catalog_manifest, Mapping):
        errors.append("snapshot-manifest.json: catalog identity is missing")
    else:
        if catalog_manifest.get("operation_count") != EXPECTED_OPERATION_COUNT:
            errors.append(
                "snapshot-manifest.json: catalog operation_count is not 66"
            )
        if catalog_manifest.get("attempt_contract") != EXPECTED_TOTAL:
            errors.append(
                "snapshot-manifest.json: catalog attempt_contract is not 1980"
            )
        expected_digest = catalog_manifest.get("sha256")
        actual_digest = sha256_file(root / "catalog.json")
        if expected_digest != actual_digest:
            errors.append(
                "catalog.json: digest does not match the frozen snapshot manifest"
            )

    code_snapshot = manifest.get("code_snapshot")
    if not isinstance(code_snapshot, Mapping):
        errors.append("snapshot-manifest.json: code_snapshot identity is missing")
    else:
        require_sha256(
            code_snapshot.get("sha256"),
            label="snapshot-manifest.json: code_snapshot.sha256",
            errors=errors,
        )
        if code_snapshot.get("read_only") is not True:
            errors.append("snapshot-manifest.json: code snapshot is not marked read-only")

    launcher = manifest.get("launcher")
    if not isinstance(launcher, Mapping):
        errors.append("snapshot-manifest.json: launcher identity is missing")
    else:
        repository_root = manifest.get("repository_root")
        for path_key, digest_key in (
            ("isolated_runner", "isolated_runner_sha256"),
            ("world_runner", "world_runner_sha256"),
        ):
            relative = launcher.get(path_key)
            expected_digest = launcher.get(digest_key)
            if not isinstance(repository_root, str) or not isinstance(relative, str):
                errors.append(
                    f"snapshot-manifest.json: launcher.{path_key} is invalid"
                )
                continue
            runner_path = Path(repository_root) / relative
            if not runner_path.is_file():
                errors.append(f"{relative}: frozen launcher is missing")
            elif sha256_file(runner_path) != expected_digest:
                errors.append(f"{relative}: digest changed after the snapshot freeze")

    return phase_operations


def expected_execution_identity(
    world: str,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    template = manifest.get("study_template", {})
    catalog = manifest.get("catalog", {})
    code = manifest.get("code_snapshot", {})
    lanes = manifest.get("lanes", {})
    profile_control = lanes.get(world)
    profile_uid = template.get("participant_profile_uid")
    store_root: str | None = None
    if isinstance(profile_control, str) and isinstance(profile_uid, str):
        store_root = str(Path(profile_control) / "stores" / profile_uid)
    return {
        "code_snapshot_sha256": code.get("sha256"),
        "profile_name": template.get("participant_profile_name"),
        "profile_uid": profile_uid,
        "profile_control": profile_control,
        "store_root": store_root,
        "provider_policy_version": template.get("provider_policy_version"),
        "provider_policy_sha256": template.get("provider_policy_sha256"),
        "catalog_sha256": catalog.get("sha256"),
    }


def validate_execution_identity(
    path: Path,
    world: str,
    payload: Mapping[str, Any],
    manifest: Mapping[str, Any],
    errors: list[str],
) -> None:
    identity = payload.get("execution_identity")
    if not isinstance(identity, Mapping):
        errors.append(f"{path.name}: execution_identity is missing")
        return
    expected = expected_execution_identity(world, manifest)
    # The collection harness initially used concise evidence names.  Keep
    # those aliases first-class rather than forcing workers to rewrite actual
    # attempts while the audit is live.
    required_aliases = {
        "code snapshot": ("code_snapshot_sha256", "code_sha256"),
        "Profile UID": ("profile_uid",),
        "Store root": ("store_root", "lane_store_root"),
        "provider policy": ("provider_policy_sha256", "provider_policy_digest"),
        "catalog": ("catalog_sha256",),
    }
    expected_by_label = {
        "code snapshot": expected["code_snapshot_sha256"],
        "Profile UID": expected["profile_uid"],
        "Store root": expected["store_root"],
        "provider policy": expected["provider_policy_sha256"],
        "catalog": expected["catalog_sha256"],
    }
    for label, aliases in required_aliases.items():
        present = [(key, identity[key]) for key in aliases if key in identity]
        if not present:
            errors.append(
                f"{path.name}: execution_identity is missing pinned {label}"
            )
            continue
        for key, actual in present:
            if actual == expected_by_label[label]:
                continue
            errors.append(
                f"{path.name}: execution_identity.{key} is {actual!r}, "
                f"expected pinned value {expected_by_label[label]!r}"
            )
    # When the expanded descriptive fields are present, they are assertions
    # too and may not silently disagree with the manifest.
    for key in ("profile_name", "profile_control", "provider_policy_version"):
        if key in identity and identity[key] != expected[key]:
            errors.append(
                f"{path.name}: execution_identity.{key} is {identity[key]!r}, "
                f"expected pinned value {expected[key]!r}"
            )


def load_issue_registry(
    path: Path,
    errors: list[str],
    *,
    expected_world: str | None = None,
) -> tuple[set[str], bool]:
    """Return validated IDs from one optional root or world issue registry."""

    if not path.exists():
        return set(), False
    payload = load_json(path, errors)
    if not isinstance(payload, Mapping):
        if payload is not None:
            errors.append(f"{path}: registry must be a JSON object")
        return set(), True
    if expected_world is not None and payload.get("world") != expected_world:
        errors.append(
            f"{path}: registry world {payload.get('world')!r} does not match "
            f"{expected_world!r}"
        )
    records = payload.get("issues")
    ids: list[str] = []
    if isinstance(records, Mapping):
        for key, record in records.items():
            if not is_meaningful_text(key):
                errors.append(f"{path}: issue map contains an invalid ID key {key!r}")
                continue
            if not isinstance(record, Mapping):
                errors.append(f"{path}: issue {key!r} is not an object")
                continue
            record_id = record.get("id")
            if record_id is not None and record_id != key:
                errors.append(
                    f"{path}: issue key {key!r} disagrees with record id {record_id!r}"
                )
                continue
            ids.append(key)
    elif isinstance(records, list):
        for index, record in enumerate(records):
            if not isinstance(record, Mapping) or not is_meaningful_text(record.get("id")):
                errors.append(f"{path}: issues[{index}] has no meaningful id")
                continue
            ids.append(record["id"])
    else:
        errors.append(f"{path}: issues must be an object or list")
    if len(ids) != len(set(ids)):
        errors.append(f"{path}: issue IDs are not unique")
    return set(ids), True


def resolve_evidence_path(
    value: Any,
    *,
    root: Path,
    ledger_dir: Path,
    world: str,
    label: str,
    errors: list[str],
    require_nonempty: bool = False,
) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty path")
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        # A bare relative path belongs to the phase ledger's world directory.
        # Two early recorders wrote an explicit campaign prefix; normalize
        # that prefix without making the repository root the resolution base.
        if candidate.parts and candidate.parts[0] == "worlds":
            candidate = root / candidate
        elif candidate.parts[:2] == ("outputs", root.name):
            candidate = root.joinpath(*candidate.parts[2:])
        elif candidate.parts[:3] == ("agent-records", "outputs", root.name):
            candidate = root.joinpath(*candidate.parts[3:])
        else:
            candidate = ledger_dir / candidate
    try:
        resolved = candidate.resolve()
        world_root = (root / "worlds" / world).resolve()
        resolved.relative_to(world_root)
    except (OSError, ValueError):
        errors.append(f"{label} must stay under worlds/{world}")
        return None
    if not resolved.is_file():
        errors.append(f"{label} does not reference an existing file: {value}")
        return None
    if require_nonempty and resolved.stat().st_size == 0:
        errors.append(f"{label} references an empty file: {value}")
    return resolved


def validate_command_launcher(
    attempt: Mapping[str, Any],
    *,
    path: Path,
    world: str,
    manifest: Mapping[str, Any],
    errors: list[str],
) -> None:
    command = attempt.get("command")
    if not isinstance(command, str):
        return
    try:
        tokens = shlex.split(command)
    except ValueError as error:
        errors.append(f"{path.name}: command is not shell-parseable: {error}")
        return
    runner_relative = manifest.get("launcher", {}).get("world_runner")
    repository_root = manifest.get("repository_root")
    if not isinstance(runner_relative, str) or not isinstance(repository_root, str):
        return
    expected_runner = (Path(repository_root) / runner_relative).resolve()
    matches: list[int] = []
    for index, token in enumerate(tokens):
        if Path(token).name != expected_runner.name:
            continue
        token_path = Path(token)
        if not token_path.is_absolute():
            token_path = Path(repository_root) / token_path
        if token_path.resolve() == expected_runner:
            matches.append(index)
    if len(matches) != 1:
        errors.append(
            f"{path.name}: command must use the one pinned run_world_mem.py launcher"
        )
        return
    runner_index = matches[0]
    if runner_index + 1 >= len(tokens) or tokens[runner_index + 1] != world:
        errors.append(f"{path.name}: command launcher is not pinned to world {world}")


def validate_tui_evidence(
    attempt: Mapping[str, Any],
    *,
    root: Path,
    ledger_dir: Path,
    world: str,
    label: str,
    errors: list[str],
) -> None:
    evidence = attempt.get("tui_evidence")
    if not isinstance(evidence, Mapping):
        errors.append(f"{label}: TUI attempt is missing tui_evidence")
        return
    pty = evidence.get("pty")
    if not isinstance(pty, Mapping):
        errors.append(f"{label}: tui_evidence.pty is missing")
    else:
        expected_pty = {
            "columns": 180,
            "rows": 52,
            "term": "xterm-256color",
            "colorterm": "truecolor",
            "no_color_removed": True,
        }
        for key, expected in expected_pty.items():
            if pty.get(key) != expected:
                errors.append(
                    f"{label}: tui_evidence.pty.{key} must be {expected!r}"
                )
    if evidence.get("ansi_color_verified") is not True:
        errors.append(f"{label}: ANSI color must be explicitly verified")

    raw_path = resolve_evidence_path(
        evidence.get("raw_pty_path"),
        root=root,
        ledger_dir=ledger_dir,
        world=world,
        label=f"{label}: tui_evidence.raw_pty_path",
        errors=errors,
        require_nonempty=True,
    )
    if raw_path is not None:
        try:
            if b"\x1b[" not in raw_path.read_bytes():
                errors.append(f"{label}: raw PTY stream contains no ANSI CSI sequence")
        except OSError as error:
            errors.append(f"{label}: cannot inspect raw PTY stream: {error}")

    resolve_evidence_path(
        evidence.get("interaction_log_path"),
        root=root,
        ledger_dir=ledger_dir,
        world=world,
        label=f"{label}: tui_evidence.interaction_log_path",
        errors=errors,
        require_nonempty=True,
    )
    screenshots = evidence.get("screenshots")
    if not isinstance(screenshots, list) or not screenshots:
        errors.append(f"{label}: tui_evidence.screenshots must be a non-empty list")
        return
    ordinals: list[int] = []
    seen_paths: set[str] = set()
    for index, record in enumerate(screenshots):
        value = record.get("path") if isinstance(record, Mapping) else record
        screenshot = resolve_evidence_path(
            value,
            root=root,
            ledger_dir=ledger_dir,
            world=world,
            label=f"{label}: tui_evidence.screenshots[{index}]",
            errors=errors,
            require_nonempty=True,
        )
        if screenshot is None:
            continue
        if screenshot.suffix.casefold() != ".png":
            errors.append(f"{label}: TUI screenshot must be a PNG: {value}")
        numbered_components = NUMBERED_CAPTURE.findall(screenshot.name)
        if not numbered_components:
            errors.append(f"{label}: screenshot is not ordered with a numeric prefix: {value}")
        else:
            # Capture sets may prefix the command sequence before their own
            # ordered state number, e.g. 041-share-2-01-entry.png.
            ordinals.append(int(numbered_components[-1]))
        resolved_text = str(screenshot)
        if resolved_text in seen_paths:
            errors.append(f"{label}: duplicate TUI screenshot path: {value}")
        seen_paths.add(resolved_text)
    if ordinals != sorted(ordinals) or len(ordinals) != len(set(ordinals)):
        errors.append(f"{label}: TUI screenshots are not in unique numeric order")


def validate_raw_artifacts(
    attempt: Mapping[str, Any],
    *,
    root: Path,
    ledger_dir: Path,
    world: str,
    label: str,
    is_tui: bool,
    errors: list[str],
) -> None:
    if is_tui:
        return
    artifacts = attempt.get("artifacts")
    if isinstance(artifacts, Mapping):
        for stream in ("stdout_path", "stderr_path"):
            resolve_evidence_path(
                artifacts.get(stream),
                root=root,
                ledger_dir=ledger_dir,
                world=world,
                label=f"{label}: artifacts.{stream}",
                errors=errors,
            )
        return
    if "raw_stdout" in attempt or "raw_stderr" in attempt:
        # Some recorders preserve the two subprocess streams separately.
        # Both files are evidence even when a successful command leaves the
        # stderr artifact empty.
        for stream in ("raw_stdout", "raw_stderr"):
            resolve_evidence_path(
                attempt.get(stream),
                root=root,
                ledger_dir=ledger_dir,
                world=world,
                label=f"{label}: {stream}",
                errors=errors,
            )
        return
    # A colorless subprocess capture may intentionally combine stdout and
    # stderr in one chronological raw artifact.
    if "raw_output" in attempt:
        resolve_evidence_path(
            attempt.get("raw_output"),
            root=root,
            ledger_dir=ledger_dir,
            world=world,
            label=f"{label}: raw_output",
            errors=errors,
        )
        return
    errors.append(f"{label}: non-TUI attempt is missing raw output artifacts")


def documented_interleave_exception(
    payload: Mapping[str, Any],
    *,
    world: str,
    phase: str,
    errors: list[str],
) -> Mapping[str, Any] | None:
    """Parse the one allowed ADMIN safety-transaction adjacency exception."""

    plural = payload.get("interleave_exceptions")
    singular = payload.get("interleave_exception")
    if plural is not None and singular is not None:
        errors.append(
            f"{world}/{phase}: declare only one interleave exception container"
        )
        return None
    if plural is None and singular is None:
        return None
    if plural is not None:
        if not isinstance(plural, list) or len(plural) != 1:
            errors.append(
                f"{world}/{phase}: interleave_exceptions must contain exactly one item"
            )
            return None
        exception = plural[0]
    else:
        exception = singular
    if not isinstance(exception, Mapping):
        errors.append(f"{world}/{phase}: interleave exception must be an object")
        return None
    declared_attempts = exception.get("attempt_ids", exception.get("attempts"))
    operation_is_switch = exception.get("operation") == "switch" or (
        exception.get("operation") is None
        and declared_attempts == ["switch#1", "switch#2"]
    )
    if phase != "admin" or not operation_is_switch:
        errors.append(
            f"{world}/{phase}: only the ADMIN switch transaction may be excepted"
        )
        return None
    if declared_attempts not in ([1, 2], ["switch#1", "switch#2"]):
        errors.append(
            f"{world}/{phase}: switch exception attempt IDs must be exactly [1, 2]"
        )
        return None
    rationale = normalized_text(exception.get("rationale"))
    declared_commands = exception.get("commands")
    if declared_commands is not None and declared_commands != [
        "mem switch --previous",
        "mem switch --next",
    ]:
        errors.append(
            f"{world}/{phase}: switch exception commands must be exact previous/next"
        )
        return None
    rationale_and_commands = " ".join(
        (rationale, normalized_text(" ".join(declared_commands or [])))
    )
    required_markers = (
        ("round 1", "round1", "round-1"),
        ("last", "end-of-round-1"),
        ("--previous",),
        ("round 2", "round2", "round-2"),
        ("first", "start-of-round-2"),
        ("--next",),
        ("no intervening",),
        ("mem",),
    )
    if not rationale or any(
        not any(marker in rationale_and_commands for marker in alternatives)
        for alternatives in required_markers
    ):
        errors.append(
            f"{world}/{phase}: switch exception rationale must state round-1-last "
            "--previous then round-2-first --next with no intervening mem"
        )
        return None
    return exception


def allows_switch_adjacency(
    left: AttemptRef,
    right: AttemptRef,
) -> bool:
    exception = left.interleave_exception
    if exception is None or exception != right.interleave_exception:
        return False
    if not (
        left.phase == "admin"
        and left.operation == right.operation == "switch"
        and left.attempt_id == 1
        and right.attempt_id == 2
        and right.sequence == left.sequence + 1
    ):
        return False
    try:
        left_tokens = shlex.split(left.payload["command"])
        right_tokens = shlex.split(right.payload["command"])
    except (KeyError, TypeError, ValueError):
        return False
    if left_tokens[-2:] != ["switch", "--previous"]:
        return False
    if right_tokens[-2:] != ["switch", "--next"]:
        return False
    declared_sequences = exception.get("sequences")
    return declared_sequences is None or declared_sequences == [
        left.sequence,
        right.sequence,
    ]


def validate_attempt(
    attempt: Any,
    *,
    root: Path,
    path: Path,
    world: str,
    phase: str,
    operation: str,
    manifest: Mapping[str, Any],
    issue_ids: set[str],
    issue_registry_exists: bool,
    starting_boundary: Any,
    interleave_exception: Mapping[str, Any] | None,
    errors: list[str],
) -> AttemptRef | None:
    label = f"{world}/{phase}: {operation} attempt"
    if not isinstance(attempt, Mapping):
        errors.append(f"{label} is not an object")
        return None

    attempt_id = attempt.get("attempt", attempt.get("round"))
    if isinstance(attempt_id, bool) or not isinstance(attempt_id, int):
        errors.append(f"{label} has a non-integer attempt ID")
        return None
    if attempt_id not in range(1, REQUIRED_ATTEMPTS + 1):
        errors.append(f"{label} ID {attempt_id} is outside 1..5")

    sequence = attempt.get("sequence", attempt.get("world_sequence"))
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        errors.append(f"{label} {attempt_id} needs a positive integer sequence")
        return None
    label = f"{label} {attempt_id}"

    for field in REQUIRED_TEXT_FIELDS:
        if not is_meaningful_text(attempt.get(field)):
            errors.append(f"{label} has empty or placeholder {field}")

    exit_code = attempt.get("exit")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        errors.append(f"{label} exit is not an integer")

    defect_ids = attempt.get("defect_ids")
    if not isinstance(defect_ids, list) or not all(
        isinstance(item, str) and item.strip() for item in defect_ids
    ):
        errors.append(f"{label} defect_ids must be a list of non-empty strings")
    else:
        if len(defect_ids) != len(set(defect_ids)):
            errors.append(f"{label} repeats a defect ID")
        for defect_id in defect_ids:
            if not issue_registry_exists:
                errors.append(
                    f"{label} references {defect_id!r}, but issues.json is missing"
                )
            elif defect_id not in issue_ids:
                errors.append(
                    f"{label} references unknown issue ID {defect_id!r}"
                )

    cost = attempt.get("cost")
    if isinstance(cost, Mapping) and cost:
        is_tui = cost.get("tui") is True
        if "tui" in cost and not isinstance(cost.get("tui"), bool):
            errors.append(f"{label} cost.tui must be boolean")
    elif is_meaningful_text(cost):
        is_tui = False
    else:
        errors.append(f"{label} cost must be non-empty text or an object")
        is_tui = False

    for field in ("pre_target_digest", "post_target_digest", "recovery_evidence"):
        if not is_nonempty_evidence(attempt.get(field)):
            errors.append(f"{label} has empty {field}")

    continuity = attempt.get("state_continuity")
    if isinstance(continuity, Mapping) and continuity:
        if "reset" in continuity and continuity.get("reset") is not False:
            errors.append(f"{label} must record state_continuity.reset=false")
        for digest_key in ("pre_state_sha256", "post_state_sha256"):
            if digest_key in continuity:
                require_sha256(
                    continuity.get(digest_key),
                    label=f"{label} state_continuity.{digest_key}",
                    errors=errors,
                )
        if "predecessor_sequence" in continuity:
            predecessor = continuity.get("predecessor_sequence")
            if predecessor is not None and (
                isinstance(predecessor, bool)
                or not isinstance(predecessor, int)
                or predecessor < 1
            ):
                errors.append(
                    f"{label} state_continuity.predecessor_sequence is invalid"
                )
        for assertion in ("same_as_previous_post", "one_cumulative_store"):
            if assertion in continuity and continuity.get(assertion) is not True:
                errors.append(
                    f"{label} state_continuity.{assertion} must be true"
                )
    elif is_meaningful_text(continuity):
        normalized_continuity = normalized_text(continuity)
        continuity_markers = (
            "no reset",
            "without reset",
            "remained",
            "retained",
            "cumulative",
            "same pinned",
            "continuous_lane",
            "continuous lane",
        )
        if not any(marker in normalized_continuity for marker in continuity_markers):
            errors.append(
                f"{label} state_continuity does not provide no-reset continuity evidence"
            )
    else:
        errors.append(f"{label} is missing state_continuity")

    validate_command_launcher(
        attempt,
        path=path,
        world=world,
        manifest=manifest,
        errors=errors,
    )
    validate_raw_artifacts(
        attempt,
        root=root,
        ledger_dir=path.parent,
        world=world,
        label=label,
        is_tui=is_tui,
        errors=errors,
    )
    if is_tui or "tui_evidence" in attempt:
        if not is_tui:
            errors.append(f"{label} has TUI evidence but cost.tui is not true")
        validate_tui_evidence(
            attempt,
            root=root,
            ledger_dir=path.parent,
            world=world,
            label=label,
            errors=errors,
        )

    return AttemptRef(
        path=path,
        world=world,
        phase=phase,
        operation=operation,
        attempt_id=attempt_id,
        sequence=sequence,
        payload=attempt,
        starting_boundary=starting_boundary,
        interleave_exception=interleave_exception,
    )


def phase_attempts(
    payload: Mapping[str, Any],
    *,
    path: Path,
    errors: list[str],
) -> dict[str, list[Any]]:
    operations = payload.get("operations")
    result: dict[str, list[Any]] = {}
    if isinstance(operations, Mapping):
        for operation, record in operations.items():
            if not isinstance(operation, str):
                errors.append(f"{path.name}: operation key is not text")
                continue
            if not isinstance(record, Mapping):
                errors.append(f"{path.name}: {operation} record is not an object")
                continue
            attempts = record.get("attempts")
            if not isinstance(attempts, list):
                errors.append(f"{path.name}: {operation} attempts is not a list")
                continue
            result[operation] = attempts
        return result

    trials = payload.get("trials")
    if not isinstance(trials, list):
        errors.append(f"{path.name}: missing operations object or trials list")
        return result
    for index, attempt in enumerate(trials):
        if not isinstance(attempt, Mapping):
            errors.append(f"{path.name}: trials[{index}] is not an object")
            continue
        operation = attempt.get("operation")
        if not isinstance(operation, str):
            errors.append(f"{path.name}: trials[{index}] has no operation")
            continue
        result.setdefault(operation, []).append(attempt)
    return result


def ledger_issue_ids(
    payload: Mapping[str, Any],
    *,
    path: Path,
    errors: list[str],
) -> tuple[set[str], bool]:
    """Read a phase-local issue index when the worker keeps findings nearby."""

    if "issues" not in payload:
        return set(), False
    records = payload.get("issues")
    if not isinstance(records, list):
        errors.append(f"{path.name}: issues must be a list")
        return set(), True
    result: list[str] = []
    for index, record in enumerate(records):
        if isinstance(record, str) and is_meaningful_text(record):
            result.append(record)
        elif isinstance(record, Mapping) and is_meaningful_text(record.get("id")):
            result.append(record["id"])
        else:
            errors.append(f"{path.name}: issues[{index}] has no meaningful id")
    if len(result) != len(set(result)):
        errors.append(f"{path.name}: local issue IDs are not unique")
    return set(result), True


def validate_coverage_summary(
    coverage: Mapping[str, Any],
    *,
    path: Path,
    expected_operations: set[str],
    refs: list[AttemptRef],
    errors: list[str],
) -> None:
    """Validate the aggregate form used by the task-2 recorder.

    Failure categories are mutually exclusive in that schema.  Their sum is
    therefore checked against actual nonzero exits instead of being accepted
    as unaudited descriptive metadata.
    """

    missing = COVERAGE_SUMMARY_FIELDS - set(coverage)
    extras = set(coverage) - COVERAGE_SUMMARY_FIELDS
    if missing:
        errors.append(f"{path.name}: coverage summary missing fields {sorted(missing)}")
    if extras:
        errors.append(f"{path.name}: coverage summary has unknown fields {sorted(extras)}")

    expected_count = coverage.get("expected_operations")
    if isinstance(expected_count, list):
        if (
            not all(isinstance(item, str) for item in expected_count)
            or len(expected_count) != len(set(expected_count))
            or set(expected_count) != expected_operations
        ):
            errors.append(
                f"{path.name}: coverage.expected_operations must list the exact phase"
            )
    elif expected_count != len(expected_operations):
        errors.append(
            f"{path.name}: coverage.expected_operations={expected_count!r}, "
            f"expected {len(expected_operations)}"
        )

    expected_attempts = coverage.get("expected_attempts_per_operation")
    if expected_attempts != REQUIRED_ATTEMPTS:
        errors.append(
            f"{path.name}: coverage.expected_attempts_per_operation="
            f"{expected_attempts!r}, expected {REQUIRED_ATTEMPTS}"
        )

    actual_exits = [
        ref.payload.get("exit")
        for ref in refs
        if isinstance(ref.payload.get("exit"), int)
        and not isinstance(ref.payload.get("exit"), bool)
    ]
    actual_total = len(refs)
    actual_successes = sum(exit_code == 0 for exit_code in actual_exits)
    actual_failures = sum(exit_code != 0 for exit_code in actual_exits)
    if coverage.get("counted_actual_mem_commands") != actual_total:
        errors.append(
            f"{path.name}: coverage.counted_actual_mem_commands="
            f"{coverage.get('counted_actual_mem_commands')!r}, ledger has {actual_total}"
        )
    if coverage.get("successful_exits") != actual_successes:
        errors.append(
            f"{path.name}: coverage.successful_exits="
            f"{coverage.get('successful_exits')!r}, ledger has {actual_successes}"
        )

    failure_fields = (
        "expected_authority_rejections",
        "safe_authority_boundary_failures",
        "provider_infrastructure_failures",
    )
    failure_counts: list[int] = []
    for field in failure_fields:
        value = coverage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append(f"{path.name}: coverage.{field} must be a nonnegative integer")
        else:
            failure_counts.append(value)
    if len(failure_counts) == len(failure_fields) and sum(failure_counts) != actual_failures:
        errors.append(
            f"{path.name}: coverage failure categories total {sum(failure_counts)}, "
            f"ledger has {actual_failures} nonzero exits"
        )
    if coverage.get("store_resets") != 0:
        errors.append(f"{path.name}: coverage.store_resets must be 0")


def validate_count_coverage_summary(
    coverage: Mapping[str, Any],
    *,
    path: Path,
    expected_operations: set[str],
    refs: list[AttemptRef],
    errors: list[str],
) -> None:
    """Validate the compact operations/counts form used by task-1."""

    missing = COUNT_COVERAGE_REQUIRED_FIELDS - set(coverage)
    extras = set(coverage) - COUNT_COVERAGE_SUMMARY_FIELDS
    if missing:
        errors.append(f"{path.name}: coverage summary missing fields {sorted(missing)}")
    if extras:
        errors.append(f"{path.name}: coverage summary has unknown fields {sorted(extras)}")

    expected_values = {
        "operations": len(expected_operations),
        "attempts_per_operation": REQUIRED_ATTEMPTS,
        "counted_actual_mem_commands": len(refs),
        "exit_zero": sum(ref.payload.get("exit") == 0 for ref in refs),
        "nonzero_boundary_or_failure": sum(
            isinstance(ref.payload.get("exit"), int)
            and not isinstance(ref.payload.get("exit"), bool)
            and ref.payload.get("exit") != 0
            for ref in refs
        ),
        "tui_attempts": sum(
            isinstance(ref.payload.get("cost"), Mapping)
            and ref.payload["cost"].get("tui") is True
            for ref in refs
        ),
    }
    for field, expected in expected_values.items():
        if coverage.get(field) != expected:
            errors.append(
                f"{path.name}: coverage.{field}={coverage.get(field)!r}, "
                f"ledger value is {expected}"
            )
    wall_seconds = coverage.get("wall_seconds")
    if (
        isinstance(wall_seconds, bool)
        or not isinstance(wall_seconds, (int, float))
        or wall_seconds < 0
    ):
        errors.append(f"{path.name}: coverage.wall_seconds must be nonnegative")

    if "continuity_breaks" in coverage:
        ordered = sorted(refs, key=lambda ref: ref.sequence)
        digest_pairs = [
            (
                evidence_sha256(left.payload.get("post_target_digest")),
                evidence_sha256(right.payload.get("pre_target_digest")),
            )
            for left, right in zip(ordered, ordered[1:])
        ]
        if any(left is None or right is None for left, right in digest_pairs):
            errors.append(
                f"{path.name}: coverage.continuity_breaks is not derivable from "
                "attempt digests; move it out of coverage"
            )
        else:
            actual_breaks = sum(left != right for left, right in digest_pairs)
            if coverage.get("continuity_breaks") != actual_breaks:
                errors.append(
                    f"{path.name}: coverage.continuity_breaks="
                    f"{coverage.get('continuity_breaks')!r}, ledger value is "
                    f"{actual_breaks}"
                )

    if "durable_context_tree_mutations" in coverage:
        mutation_flags: list[bool] = []
        for ref in refs:
            continuity = ref.payload.get("state_continuity")
            if isinstance(continuity, Mapping) and isinstance(
                continuity.get("durable_context_tree_changed"), bool
            ):
                mutation_flags.append(continuity["durable_context_tree_changed"])
                continue
            prose = normalized_text(continuity)
            if "durable context tree changed during this attempt" in prose:
                mutation_flags.append(True)
            elif any(
                marker in prose
                for marker in (
                    "durable context tree unchanged",
                    "durable context tree did not change",
                )
            ):
                mutation_flags.append(False)
            else:
                errors.append(
                    f"{path.name}: coverage.durable_context_tree_mutations is not "
                    "derivable for every attempt; move it out of coverage"
                )
                mutation_flags = []
                break
        if mutation_flags:
            actual_mutations = sum(mutation_flags)
            if coverage.get("durable_context_tree_mutations") != actual_mutations:
                errors.append(
                    f"{path.name}: coverage.durable_context_tree_mutations="
                    f"{coverage.get('durable_context_tree_mutations')!r}, ledger "
                    f"value is {actual_mutations}"
                )


def validate_phase_ledger(
    path: Path,
    *,
    root: Path,
    expected_world: str,
    expected_phase: str,
    expected_operations: tuple[str, ...],
    manifest: Mapping[str, Any],
    issue_ids: set[str],
    issue_registry_exists: bool,
    strict: bool,
    errors: list[str],
    missing_details: list[str],
) -> list[AttemptRef]:
    payload = load_json(path, errors)
    if not isinstance(payload, Mapping):
        return []
    world = payload.get("world")
    phase = payload.get("phase")
    if world != expected_world:
        errors.append(
            f"{path.name}: payload world {world!r} does not match {expected_world!r}"
        )
    if phase != expected_phase:
        errors.append(
            f"{path.name}: payload phase {phase!r} does not match {expected_phase!r}"
        )
    if "study" in payload and payload.get("study") != STUDY_NAME:
        errors.append(
            f"{expected_world}/{expected_phase}: study must be {STUDY_NAME!r}"
        )
    if "schema_version" in payload and not isinstance(payload.get("schema_version"), int):
        errors.append(f"{path.name}: schema_version must be an integer")
    declared_goal = payload.get("world_goal", payload.get("goal"))
    if declared_goal is not None and not is_meaningful_text(declared_goal):
        errors.append(f"{path.name}: declared world goal is empty or a placeholder")
    validate_execution_identity(path, expected_world, payload, manifest, errors)
    local_issue_ids, local_issue_registry_exists = ledger_issue_ids(
        payload,
        path=path,
        errors=errors,
    )
    known_issue_ids = issue_ids | local_issue_ids
    interleave_exception = documented_interleave_exception(
        payload,
        world=expected_world,
        phase=expected_phase,
        errors=errors,
    )

    by_operation = phase_attempts(payload, path=path, errors=errors)
    present = set(by_operation)
    expected = set(expected_operations)
    extras = sorted(present - expected)
    if extras:
        errors.append(f"{path.name}: operations belong to another phase: {extras}")
    if strict:
        missing_operations = sorted(expected - present)
        if missing_operations:
            missing_details.append(
                f"{expected_world} {expected_phase}: missing operations {missing_operations}"
            )

    refs: list[AttemptRef] = []
    actual_counts: dict[str, int] = {}
    for operation, attempts in by_operation.items():
        if operation not in expected:
            continue
        actual_counts[operation] = len(attempts)
        if len(attempts) > REQUIRED_ATTEMPTS:
            errors.append(
                f"{path.name}: {operation} has {len(attempts)} attempts, maximum is 5"
            )
        seen_ids: set[int] = set()
        signatures: dict[tuple[str, ...], int] = {}
        for raw_attempt in attempts:
            ref = validate_attempt(
                raw_attempt,
                root=root,
                path=path,
                world=expected_world,
                phase=expected_phase,
                operation=operation,
                manifest=manifest,
                issue_ids=known_issue_ids,
                issue_registry_exists=(
                    issue_registry_exists or local_issue_registry_exists
                ),
                starting_boundary=payload.get("starting_boundary"),
                interleave_exception=interleave_exception,
                errors=errors,
            )
            if ref is None:
                continue
            if ref.attempt_id in seen_ids:
                errors.append(
                    f"{expected_world}/{expected_phase}: {operation} repeats "
                    f"attempt ID {ref.attempt_id}"
                )
            seen_ids.add(ref.attempt_id)
            signature = tuple(
                normalized_text(ref.payload.get(field))
                for field in METHOD_SIGNATURE_FIELDS
            )
            if signature in signatures:
                errors.append(
                    f"{expected_world}/{expected_phase}: {operation} attempts "
                    f"{signatures[signature]} and {ref.attempt_id} repeat the "
                    "same method signature"
                )
            else:
                signatures[signature] = ref.attempt_id
            refs.append(ref)
        if strict and seen_ids != set(range(1, REQUIRED_ATTEMPTS + 1)):
            missing_details.append(
                f"{expected_world} {operation}: attempt IDs "
                f"{sorted(seen_ids)!r}, expected 1..5"
            )

    coverage = payload.get("coverage")
    if coverage is not None:
        if not isinstance(coverage, Mapping):
            errors.append(f"{path.name}: coverage must be an object")
        elif "expected_operations" in coverage:
            validate_coverage_summary(
                coverage,
                path=path,
                expected_operations=expected,
                refs=refs,
                errors=errors,
            )
        elif "operations" in coverage and "attempts_per_operation" in coverage:
            validate_count_coverage_summary(
                coverage,
                path=path,
                expected_operations=expected,
                refs=refs,
                errors=errors,
            )
        else:
            if set(coverage) - expected:
                errors.append(f"{path.name}: coverage contains out-of-phase operations")
            for operation, declared in coverage.items():
                if isinstance(declared, bool) or not isinstance(declared, int):
                    errors.append(f"{path.name}: coverage.{operation} is not an integer")
                elif declared != actual_counts.get(operation, 0):
                    errors.append(
                        f"{path.name}: coverage.{operation}={declared}, but ledger has "
                        f"{actual_counts.get(operation, 0)} attempts"
                    )
    return refs


def validate_world_sequence(
    world: str,
    refs: list[AttemptRef],
    *,
    manifest: Mapping[str, Any],
    strict: bool,
    errors: list[str],
    missing_details: list[str],
) -> None:
    if not refs:
        return
    by_phase: dict[str, list[AttemptRef]] = {
        phase: [ref for ref in refs if ref.phase == phase]
        for phase in PHASE_NAMES
    }
    initial_digest = manifest.get("study_template", {}).get("initial_state_sha256")

    for phase, phase_refs in by_phase.items():
        if not phase_refs:
            continue
        by_sequence: dict[int, AttemptRef] = {}
        for ref in phase_refs:
            previous_at_sequence = by_sequence.get(ref.sequence)
            if previous_at_sequence is not None:
                errors.append(
                    f"{world}/{phase}: sequence {ref.sequence} is shared by "
                    f"{previous_at_sequence.operation}/{previous_at_sequence.attempt_id} "
                    f"and {ref.operation}/{ref.attempt_id}"
                )
            else:
                by_sequence[ref.sequence] = ref
        ordered = [by_sequence[key] for key in sorted(by_sequence)]
        sequences = [ref.sequence for ref in ordered]
        expected_prefix = list(range(1, len(ordered) + 1))
        if sequences != expected_prefix:
            errors.append(
                f"{world}/{phase}: sequences are not one phase-local contiguous "
                f"prefix; found {sequences[:8]!r}"
                f"{'...' if len(sequences) > 8 else ''}"
            )
        if strict and sequences != list(
            range(1, PHASE_ATTEMPT_TOTALS[phase] + 1)
        ):
            missing_details.append(
                f"{world} {phase}: sequence is not complete "
                f"1..{PHASE_ATTEMPT_TOTALS[phase]}"
            )

        previous: AttemptRef | None = None
        for ref in ordered:
            continuity = ref.payload.get("state_continuity")
            if not isinstance(continuity, Mapping):
                previous = ref
                continue
            has_pre_digest = "pre_state_sha256" in continuity
            has_predecessor = "predecessor_sequence" in continuity
            pre_digest = continuity.get("pre_state_sha256")
            predecessor = continuity.get("predecessor_sequence")
            if previous is None:
                if has_predecessor and predecessor is not None:
                    errors.append(
                        f"{world}/{phase}: first attempt predecessor_sequence "
                        "must be null"
                    )
                if phase == "core" and has_pre_digest and pre_digest != initial_digest:
                    errors.append(
                        f"{world}/{phase}: first attempt does not begin at the "
                        "frozen initial state"
                    )
            else:
                previous_continuity = previous.payload.get("state_continuity")
                previous_has_post = (
                    isinstance(previous_continuity, Mapping)
                    and "post_state_sha256" in previous_continuity
                )
                previous_post = (
                    previous_continuity.get("post_state_sha256")
                    if previous_has_post
                    else None
                )
                if has_predecessor and predecessor != previous.sequence:
                    errors.append(
                        f"{world}/{phase}: sequence {ref.sequence} names predecessor "
                        f"{predecessor!r}, expected {previous.sequence}"
                    )
                if has_pre_digest and previous_has_post and pre_digest != previous_post:
                    errors.append(
                        f"{world}/{phase}: sequence {ref.sequence} pre-state does not "
                        f"equal sequence {previous.sequence} post-state"
                    )
            previous = ref

        by_operation: dict[str, list[AttemptRef]] = {}
        for ref in ordered:
            by_operation.setdefault(ref.operation, []).append(ref)
        for operation, cell_refs in by_operation.items():
            ordered_cell = sorted(cell_refs, key=lambda item: item.sequence)
            for left, right in zip(ordered_cell, ordered_cell[1:]):
                intervening = [
                    item
                    for item in ordered
                    if left.sequence < item.sequence < right.sequence
                    and item.operation != operation
                ]
                if not intervening and not allows_switch_adjacency(left, right):
                    errors.append(
                        f"{world} {phase}/{operation}: attempts {left.attempt_id} "
                        f"and {right.attempt_id} are not interleaved with another "
                        "operation"
                    )

    # Phase numbering restarts by design.  Preserve cumulative-world proof at
    # each boundary with a matching digest when available, or explicit prose
    # that the next phase starts from the preceding phase's accumulated Store.
    for prior_phase, next_phase in zip(PHASE_NAMES, PHASE_NAMES[1:]):
        prior_refs = by_phase[prior_phase]
        next_refs = by_phase[next_phase]
        if not prior_refs or not next_refs:
            continue
        prior_last = max(prior_refs, key=lambda item: item.sequence)
        next_first = min(next_refs, key=lambda item: item.sequence)
        prior_post = evidence_sha256(prior_last.payload.get("post_target_digest"))
        next_pre = evidence_sha256(next_first.payload.get("pre_target_digest"))
        matching_digest = (
            prior_post is not None
            and prior_post == next_pre
        )
        starting_state = normalized_text(next_first.payload.get("starting_state"))
        phase_bridge = any(
            marker in starting_state
            for marker in (
                f"post-{prior_phase}",
                f"after {prior_phase}",
                f"follows {prior_phase}",
                f"{prior_phase} sequence",
            )
        )
        # A worker may freeze the complete Context-tree boundary separately
        # from the final operation's target digest.  Validate both supported
        # structured spellings, including ticker's explicit full-tree bridge.
        boundary = next_first.starting_boundary
        structured_bridge = False
        if isinstance(boundary, Mapping):
            cumulative_key = (
                "cumulative_from_core"
                if next_phase == "transform"
                else "cumulative_from_transform"
            )
            if boundary.get(cumulative_key) is not True:
                errors.append(
                    f"{world}: {next_phase} starting_boundary must assert "
                    f"{cumulative_key}=true"
                )
            if boundary.get("no_reset") is not True:
                errors.append(
                    f"{world}: {next_phase} starting_boundary must assert no_reset=true"
                )
            boundary_variants = (
                (
                    "core_final_context_tree_digest",
                    "transform_initial_tree_digest",
                    "matches_core_final_context_tree_digest",
                ),
                (
                    "core_final_digest",
                    "transform_initial_digest",
                    "matches_core_final_digest",
                ),
                (
                    "transform_final_context_tree_digest",
                    "admin_initial_context_tree_digest",
                    "matches_transform_final_context_tree_digest",
                ),
                (
                    "transform_final_digest",
                    "admin_initial_digest",
                    "matches_transform_final_digest",
                ),
            )
            nested_admin_bridge = boundary.get(
                "transform_final_to_admin_first_pre_digest_bridge"
            )
            if isinstance(nested_admin_bridge, Mapping):
                source_bridge = nested_admin_bridge.get("source_sha256")
                tree_bridge = nested_admin_bridge.get("context_tree_sha256")
                source_valid = (
                    isinstance(source_bridge, Mapping)
                    and evidence_sha256(source_bridge.get("transform_final"))
                    == evidence_sha256(source_bridge.get("admin_phase_entry_pre"))
                    is not None
                    and source_bridge.get("match") is True
                )
                tree_valid = (
                    isinstance(tree_bridge, Mapping)
                    and evidence_sha256(
                        tree_bridge.get("transform_final_host_boundary")
                    )
                    == evidence_sha256(tree_bridge.get("admin_first_attempt_pre"))
                    is not None
                    and tree_bridge.get("match") is True
                )
                bridge_note = normalized_text(nested_admin_bridge.get("note"))
                note_valid = (
                    "no reset" in bridge_note
                    and (
                        "no intervening mem" in bridge_note
                        or "no reset or intervening mem" in bridge_note
                    )
                )
                if not (
                    source_valid
                    and tree_valid
                    and note_valid
                    and boundary.get("same_pinned_identity") is True
                    and boundary.get("matches_transform_final_digest") is True
                ):
                    errors.append(
                        f"{world}: admin nested transform boundary is invalid"
                    )
                else:
                    structured_bridge = (
                        boundary.get(cumulative_key) is True
                        and boundary.get("no_reset") is True
                    )
            selected = next(
                (
                    keys
                    for keys in boundary_variants
                    if keys[0] in boundary or keys[2] in boundary
                ),
                None,
            ) if nested_admin_bridge is None else None
            if selected is not None:
                final_key, initial_key, matches_key = selected
                final_digest = evidence_sha256(boundary.get(final_key))
                initial_digest = evidence_sha256(boundary.get(initial_key))
                if final_digest is None or initial_digest is None:
                    errors.append(
                        f"{world}: {next_phase} starting_boundary has invalid digests"
                    )
                elif final_digest != initial_digest:
                    errors.append(
                        f"{world}: {next_phase} starting_boundary digest mismatch"
                    )
                elif boundary.get(matches_key) is not True:
                    errors.append(
                        f"{world}: {next_phase} starting_boundary.{matches_key} "
                        "must be true"
                    )
                elif next_pre is not None and next_pre != initial_digest:
                    errors.append(
                        f"{world}: {next_phase} first pre digest differs from its "
                        "structured starting boundary"
                    )
                else:
                    explicit_bridge = boundary.get("explicit_cumulative_bridge")
                    if explicit_bridge is not None and not is_meaningful_text(
                        explicit_bridge
                    ):
                        errors.append(
                            f"{world}: {next_phase} explicit_cumulative_bridge is empty"
                        )
                    else:
                        structured_bridge = (
                            boundary.get(cumulative_key) is True
                            and boundary.get("no_reset") is True
                        )
            elif next_phase == "admin":
                admin_initial = evidence_sha256(boundary.get("admin_initial_digest"))
                if admin_initial is not None and admin_initial == prior_post == next_pre:
                    structured_bridge = (
                        boundary.get(cumulative_key) is True
                        and boundary.get("no_reset") is True
                    )
        # Task-2's recorder states the boundary in prose: it identifies the
        # complete prior phase, cumulative lane, and absence of a Store reset.
        explicit_prose_bridge = (
            prior_phase in starting_state
            and "cumulative" in starting_state
            and (
                str(PHASE_ATTEMPT_TOTALS[prior_phase]) in starting_state
                or phase_bridge
            )
            and "reset" in starting_state
        )
        if not (
            matching_digest
            or phase_bridge
            or structured_bridge
            or explicit_prose_bridge
        ):
            errors.append(
                f"{world}: {prior_phase}->{next_phase} lacks a matching boundary "
                "digest or explicit cumulative starting-state bridge"
            )


def discover_unexpected_ledgers(root: Path, errors: list[str]) -> None:
    worlds_root = root / "worlds"
    if not worlds_root.exists():
        return
    for child in worlds_root.iterdir():
        if child.is_dir() and child.name not in WORLD_NAMES:
            errors.append(f"worlds/{child.name}: unknown world directory")
    expected_names = {f"phase-{phase}.json" for phase in PHASE_NAMES}
    for path in worlds_root.glob("*/phase-*.json"):
        if path.parent.name not in WORLD_NAMES or path.name not in expected_names:
            errors.append(f"{path.relative_to(root)}: unexpected phase ledger")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="require all 1,980 attempts and return nonzero when incomplete",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print individual missing ledgers/cells during partial progress",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    errors: list[str] = []
    missing_details: list[str] = []

    catalog = load_json(root / "catalog.json", errors)
    manifest = load_json(root / "snapshot-manifest.json", errors)
    if not isinstance(catalog, Mapping) or not isinstance(manifest, Mapping):
        print("recorded=0/1980 complete_cells=0/396 complete_ledgers=0/18 status=invalid")
        for error in errors:
            print(f"ERROR {error}")
        return 1

    phase_operations = validate_control_files(root, catalog, manifest, errors)
    root_issue_ids, root_issue_registry_exists = load_issue_registry(
        root / "issues.json",
        errors,
    )
    world_issue_registries: dict[str, tuple[set[str], bool]] = {}
    for world in WORLD_NAMES:
        world_issue_registries[world] = load_issue_registry(
            root / "worlds" / world / "issues.json",
            errors,
            expected_world=world,
        )
    discover_unexpected_ledgers(root, errors)

    counts = {
        (world, operation): 0
        for world in WORLD_NAMES
        for operation in catalog.get("operations", [])
    }
    refs_by_world: dict[str, list[AttemptRef]] = {
        world: [] for world in WORLD_NAMES
    }
    seen_ledgers = 0
    for world in WORLD_NAMES:
        world_issue_ids, world_issue_registry_exists = world_issue_registries[world]
        for phase in PHASE_NAMES:
            path = root / "worlds" / world / f"phase-{phase}.json"
            if not path.exists():
                if args.check or args.verbose:
                    missing_details.append(f"{world} {phase}: ledger missing")
                continue
            seen_ledgers += 1
            refs = validate_phase_ledger(
                path,
                root=root,
                expected_world=world,
                expected_phase=phase,
                expected_operations=phase_operations.get(phase, ()),
                manifest=manifest,
                # Deliberately omit registries from every other world: a
                # defect reference is local unless the campaign root owns it.
                issue_ids=root_issue_ids | world_issue_ids,
                issue_registry_exists=(
                    root_issue_registry_exists or world_issue_registry_exists
                ),
                strict=args.check,
                errors=errors,
                missing_details=missing_details,
            )
            refs_by_world[world].extend(refs)
            for ref in refs:
                key = (world, ref.operation)
                if key in counts:
                    counts[key] += 1

    for world, refs in refs_by_world.items():
        validate_world_sequence(
            world,
            refs,
            manifest=manifest,
            strict=args.check,
            errors=errors,
            missing_details=missing_details,
        )

    complete_cells = sum(
        count == REQUIRED_ATTEMPTS for count in counts.values()
    )
    recorded = sum(counts.values())
    if recorded > EXPECTED_TOTAL:
        errors.append(f"recorded attempts exceed contract: {recorded}/{EXPECTED_TOTAL}")
    complete = (
        recorded == EXPECTED_TOTAL
        and complete_cells == EXPECTED_CELL_COUNT
        and seen_ledgers == EXPECTED_LEDGER_COUNT
        and not errors
    )
    status = "complete" if complete else ("invalid" if errors else "partial")
    print(
        f"recorded={recorded}/{EXPECTED_TOTAL} "
        f"complete_cells={complete_cells}/{EXPECTED_CELL_COUNT} "
        f"complete_ledgers={seen_ledgers}/{EXPECTED_LEDGER_COUNT} status={status}"
    )
    for error in errors:
        print(f"ERROR {error}")
    if args.check or args.verbose:
        for detail in missing_details:
            print(f"MISSING {detail}")
        if args.verbose:
            for (world, operation), count in sorted(counts.items()):
                if count < REQUIRED_ATTEMPTS:
                    print(f"MISSING {world} {operation} {count}/5")

    incomplete_in_check = args.check and not complete
    return 1 if errors or incomplete_in_check else 0


if __name__ == "__main__":
    raise SystemExit(main())
