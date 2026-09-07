"""Version-1 receipt compatibility and strict operation-owned manifest decoding."""

import copy
import json

import pytest

from tests.atomize_restoration_support import create_save_as, snapshot_records
from memcommit.application.operations.atomize.records import (
    atomize_review_record_digest,
)
from memcommit.persistence.store.command_restoration.handlers.atomize.records import (
    AtomizeArchiveManifest,
    load_creation_receipt,
)


@pytest.mark.parametrize("with_workbench", [True, False])
def test_manifest_round_trips_existing_json_shape(isolated_store, with_workbench):
    case = create_save_as(with_workbench=with_workbench)
    receipt = load_creation_receipt(
        case.store.list_checkpoints(case.output.name), case.unit.changes[0]
    )
    assert receipt.source_context_uid == case.source.uid
    assert receipt.analysis_uid == case.analysis.uid
    case.store.restore_recent_context_command("undo")
    raw = json.loads((case.archive / "manifest.json").read_text())
    # Spell out the historical JSON contract independently of the new codec.
    assert raw == {
        "version": 1,
        "command": "atomize",
        "unit_uid": case.unit.uid,
        "context_uid": case.output.uid,
        "context_name": case.output.name,
        "checkpoint_uid": case.checkpoint.uid,
        "analysis_uid": case.analysis.uid,
        "source_context_uid": case.source.uid,
        "source_context_name": case.source.name,
        "source_workbench": None
        if case.reviewing is None
        else {
            "uid": case.reviewing.uid,
            "output_context_name": case.reviewing.output_context_name,
            "record_digest": atomize_review_record_digest(case.reviewing),
        },
        "reviewing_workbench_digest": None
        if case.reviewing is None
        else atomize_review_record_digest(case.reviewing),
        "terminal_workbench_digest": None
        if case.terminal is None
        else atomize_review_record_digest(case.terminal),
        "current_before": case.source.name,
    }
    parsed = AtomizeArchiveManifest.from_dict(raw)
    assert parsed.to_dict() == raw
    assert parsed.source_workbench == receipt.source_workbench
    assert raw["version"] == 1


@pytest.mark.parametrize(
    "corruption",
    [
        "extra_key",
        "version",
        "source_uid",
        "current_before",
        "analysis_uid",
        "workbench_uid",
        "workbench_digest",
        "creation_identity",
    ],
)
def test_invalid_creation_receipts_are_rejected(isolated_store, corruption):
    case = create_save_as()
    entries = copy.deepcopy(case.store.list_checkpoints(case.output.name))
    args = entries[0]["args"]
    receipt = args["atomize_save_as"]
    if corruption == "extra_key":
        receipt["unexpected"] = True
    elif corruption == "version":
        receipt["version"] = 2
    elif corruption == "source_uid":
        receipt["source_context"]["uid"] = None
    elif corruption == "current_before":
        receipt["current_before"] = 123
    elif corruption == "analysis_uid":
        args["analysis_uid"] = "a different analysis"
    elif corruption == "workbench_uid":
        receipt["source_workbench"]["uid"] = []
    elif corruption == "workbench_digest":
        receipt["source_workbench"]["record_digest"] = "z" * 64
    else:
        args["context_creation"]["context_uid"] = case.source.uid
    with pytest.raises(ValueError):
        load_creation_receipt(entries, case.unit.changes[0])


@pytest.mark.parametrize(
    "corruption",
    [
        "extra_key",
        "version",
        "unit_uid",
        "source_name",
        "digest",
        "workbench_shape",
    ],
)
def test_archive_reader_uses_atomize_manifest_validation(isolated_store, corruption):
    case = create_save_as()
    case.store.restore_recent_context_command("undo")
    path = case.archive / "manifest.json"
    manifest = json.loads(path.read_text())
    if corruption == "extra_key":
        manifest["unexpected"] = True
    elif corruption == "version":
        manifest["version"] = 2
    elif corruption == "unit_uid":
        manifest["unit_uid"] = "unrelated command"
    elif corruption == "source_name":
        manifest["source_context_name"] = "../invalid"
    elif corruption == "digest":
        manifest["terminal_workbench_digest"] = "z" * 64
    else:
        manifest["source_workbench"] = {"uid": "incomplete"}
    path.write_text(json.dumps(manifest))
    before = snapshot_records(case.store)
    with pytest.raises(ValueError):
        case.store.list_command_context_archives()
    assert snapshot_records(case.store) == before
