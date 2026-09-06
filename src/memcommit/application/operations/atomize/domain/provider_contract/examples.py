"""Authored example loading, integrity checks, and evidence-mode filtering."""

from __future__ import annotations

import hashlib

from importlib import resources

import json

from ..model import (
    ATOMIZE_RULESET_VERSION,
    ATOMIZE_SEGMENTER_VERSION,
    ATOMIZE_SIZE_REVIEW_CHARS,
    ATOMIZE_SIZE_REVIEW_SEGMENTS,
    AtomizeImpactError,
)

from .response import _reject_duplicate_json_keys


def _load_calibration(
    *,
    include_declared_frames: bool,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Load human-reviewed examples valid for the active evidence mode."""
    try:
        resource = resources.files(
            "memcommit.application.operations.atomize"
        ).joinpath("fixtures", "atomize.json")
        fixture = json.loads(
            resource.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise AtomizeImpactError(
            "Could not load the atomize calibration fixture."
        ) from error

    if (
        not isinstance(fixture, dict)
        or fixture.get("ruleset_version") != ATOMIZE_RULESET_VERSION
        or not isinstance(fixture.get("profile"), dict)
        or not isinstance(fixture.get("cases"), list)
    ):
        raise AtomizeImpactError("The atomize calibration fixture is incompatible.")

    profile = fixture["profile"]
    required_profile_keys = {
        "id",
        "version",
        "locale",
        "segmenter_version",
        "size_review_chars",
        "size_review_segments",
        "fingerprint",
    }
    if set(profile) != required_profile_keys:
        raise AtomizeImpactError(
            "The atomize calibration fixture has an invalid profile."
        )
    if (
        profile["segmenter_version"] != ATOMIZE_SEGMENTER_VERSION
        or profile["size_review_chars"] != ATOMIZE_SIZE_REVIEW_CHARS
        or profile["size_review_segments"] != ATOMIZE_SIZE_REVIEW_SEGMENTS
    ):
        # The local lint is deterministic code, so a fixture profile change
        # requires a code change rather than silently claiming a new profile.
        raise AtomizeImpactError(
            "The atomize calibration profile does not match the implemented size lint."
        )
    profile_payload = {
        key: value for key, value in profile.items() if key != "fingerprint"
    }
    canonical_profile = json.dumps(
        profile_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    expected_fingerprint = (
        "sha256:" + hashlib.sha256(canonical_profile.encode("utf-8")).hexdigest()
    )
    if profile["fingerprint"] != expected_fingerprint:
        raise AtomizeImpactError(
            "The atomize calibration profile fingerprint is invalid."
        )

    calibration: list[dict[str, object]] = []
    for value in fixture["cases"]:
        if not isinstance(value, dict) or not isinstance(
            value.get("declared_frames"),
            list,
        ):
            raise AtomizeImpactError(
                "The atomize calibration fixture has an invalid case."
            )
        raw_frames = value["declared_frames"]
        if raw_frames and not include_declared_frames:
            # An unreviewed preview must never be taught to borrow evidence
            # that its candidates do not receive.
            continue
        frame_contents: list[str] = []
        for frame in raw_frames:
            if (
                not isinstance(frame, dict)
                or set(frame) != {"id", "content", "fingerprint"}
                or not isinstance(frame["id"], str)
                or not frame["id"]
                or not isinstance(frame["content"], str)
                or not frame["content"].strip()
                or frame["fingerprint"]
                != "sha256:"
                + hashlib.sha256(frame["content"].encode("utf-8")).hexdigest()
            ):
                raise AtomizeImpactError(
                    "The atomize calibration fixture has an invalid declared frame."
                )
            frame_contents.append(frame["content"])
        expected = value.get("expected")
        known_wrong = value.get("known_wrong")
        if (
            not isinstance(value.get("id"), str)
            or not isinstance(value.get("source"), str)
            or not isinstance(expected, dict)
            or not isinstance(known_wrong, list)
        ):
            raise AtomizeImpactError(
                "The atomize calibration fixture has an invalid case."
            )
        calibration.append(
            {
                "id": value["id"],
                "source": value["source"],
                "declared_frame": (
                    "\n".join(frame_contents) if frame_contents else None
                ),
                "expected": {
                    "classification": expected.get("classification"),
                    "result": expected.get("result"),
                    "reason_codes": expected.get("reason_codes"),
                },
                "known_wrong": known_wrong,
            }
        )

    return dict(profile), calibration
