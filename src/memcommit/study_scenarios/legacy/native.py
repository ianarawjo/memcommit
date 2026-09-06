"""Project native Context documents into the existing Study authoring model."""

from __future__ import annotations

import csv
from dataclasses import replace
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING

from memcommit.application.operations.resource_import.documents.codec import (
    read_document,
)
from memcommit.core.context import Context, Memory
from memcommit.core.context_targeting.naming import validate_portable_context_name

if TYPE_CHECKING:
    from .fixtures import FixtureDataset, StudyFixtureSpec


def load_native_fixture(
    spec: StudyFixtureSpec, *, language: str, root: Path
) -> FixtureDataset:
    # Keep the authoring projection independent of the package/install builder.
    # The public JSON codec is also used by mem import; sidecars never enter it.
    from .fixtures import (
        AudienceRole,
        FixtureDataset,
        StudyFixtureError,
        _RawRecord,
        _load_purpose_sidecar,
        _merge_and_validate,
        _resolve_language_file,
    )

    metadata = root / "native" / "metadata" / f"{spec.name}.tsv"
    with metadata.open(encoding="utf-8", newline="") as handle:
        rows = tuple(csv.DictReader(handle, delimiter="\t"))
    documents = {}
    document_lines = {}
    paths = []
    uids = []
    raw = []
    for row in rows:
        if row["task"] != str(spec.task):
            raise StudyFixtureError("Native fixture task differs from its dataset.")
        profile = validate_portable_context_name(row["profile"])
        name = validate_portable_context_name(row["context"])
        path = (
            root
            / "native"
            / f"task-{spec.task}"
            / profile
            / language
            / name
            / "context.json"
        )
        if path not in documents:
            documents[path] = read_document(path).value
            document_lines[path] = path.read_text(encoding="utf-8").splitlines()
        context = documents[path]
        if not isinstance(context, Context) or context.name != name:
            raise StudyFixtureError(
                "Native fixture Context identity differs from its metadata."
            )
        if language != "en":
            canonical_path = (
                root
                / "native"
                / f"task-{spec.task}"
                / profile
                / "en"
                / name
                / "context.json"
            )
            if canonical_path not in documents:
                documents[canonical_path] = read_document(canonical_path).value
            canonical = documents[canonical_path]
            if (
                not isinstance(canonical, Context)
                or context.uid != canonical.uid
                or context.order != canonical.order
            ):
                raise StudyFixtureError(
                    "Native translation Context identity or item order drifted."
                )
        memory = context.memories.get(row["memory_uid"])
        if not isinstance(memory, Memory):
            raise StudyFixtureError(
                "Native fixture metadata must select an owned Memory."
            )
        verified = json.loads(row["verified"])
        if verified is not None and type(verified) is not bool:
            raise StudyFixtureError("Native fixture Verified must be boolean or null.")
        uid_field = re.compile(r'"uid"\s*:\s*' + re.escape(json.dumps(memory.uid)))
        line = next(
            (
                index
                for index, text in enumerate(document_lines[path], 1)
                if uid_field.search(text)
            ),
            1,
        )
        raw.append(
            _RawRecord(
                fixture_id=row["fixture_id"] or None,
                locator=row["locator"],
                content=memory.content,
                purpose=None,
                audiences=tuple(
                    AudienceRole(value) for value in json.loads(row["audiences"])
                ),
                verified=verified,
                source_line=line,
            )
        )
        paths.append(path)
        uids.append(memory.uid)
    if len(uids) != len(set(uids)):
        raise StudyFixtureError("Native fixture metadata repeats a Memory identity.")
    actual = {
        item.uid
        for context in documents.values()
        for item in context.iter_items()
        if isinstance(item, Memory)
    }
    if actual != set(uids):
        raise StudyFixtureError(
            "Native fixture metadata does not cover its Memory documents exactly."
        )
    sidecar_path = _resolve_language_file(
        root, language, spec.purpose_sidecar_stem, ".tsv"
    )
    records = _merge_and_validate(
        tuple(raw),
        _load_purpose_sidecar(sidecar_path, spec),
        spec=spec,
        language=language,
        source_path=metadata,
        preserve_content=True,
    )
    return FixtureDataset(
        spec=spec,
        language=language,
        records=tuple(
            replace(
                record,
                source_path=path,
                memory_uid=uid,
                source_relative_path=path.relative_to(root).as_posix(),
            )
            for record, path, uid in zip(records, paths, uids, strict=True)
        ),
    )
