"""Contracts for the aggregate saved-Impact launcher adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import memcommit.commands.impact_catalog as impact_catalog
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionOpenReceipt,
    SessionPickerEntry,
)
from memcommit.store import MemoryStore


def _entry(
    kind: str,
    key: str,
    *,
    title: str | None = None,
    reopen_argv: tuple[str, ...] | None = None,
) -> SessionPickerEntry:
    return SessionPickerEntry(
        kind=kind,
        key=key,
        title=title or f"{kind} title",
        status="CURRENT",
        subtitle=f"{kind} summary",
        group=f"{kind}/context",
        sort_timestamp=1.0,
        detail=f"{kind} detail",
        reopen_argv=reopen_argv or ("mem", kind, key),
    )


def test_catalog_unites_only_durable_impact_artifacts(
    isolated_store,
    monkeypatch,
):
    atomize = _entry("atomize", "atomize-1")
    meld = SimpleNamespace(
        session_uid="meld-1",
        title="left → right",
        status="REVIEW",
        subtitle="directional",
        group="right",
        modified_timestamp=2.0,
        detail="meld detail",
        reopen_argv=("mem", "meld", "left", "right"),
    )
    sever = SimpleNamespace(picker_entry=_entry("sever", "sever-1"))
    update = _entry(
        "update",
        "update-1",
        title="UPDATE · source → target",
        reopen_argv=(
            "mem",
            "impact",
            "update",
            "--session",
            "update-1",
        ),
    )
    monkeypatch.setattr(
        impact_catalog,
        "atomize_session_entries",
        lambda _store: (atomize,),
    )
    monkeypatch.setattr(
        impact_catalog,
        "list_meld_session_catalog",
        lambda _store: (meld,),
    )
    monkeypatch.setattr(
        impact_catalog,
        "list_sever_session_catalog",
        lambda _sessions: (sever,),
    )
    monkeypatch.setattr(
        impact_catalog,
        "_update_entry",
        lambda _store: impact_catalog._impact_entry(update),
    )

    entries = impact_catalog.impact_session_entries(MemoryStore())

    assert [entry.kind for entry in entries] == [
        "atomize",
        "meld",
        "sever",
        "update",
    ]
    assert [entry.key for entry in entries] == [
        "atomize-1",
        "meld-1",
        "sever-1",
        "update-1",
    ]
    assert entries[0].title.startswith("ATOMIZE ·")
    assert entries[1].reopen_argv == (
        "mem",
        "impact",
        "meld",
        "--session",
        "meld-1",
    )
    assert entries[2].detail_only is True
    assert "does not call a semantic provider" in entries[3].detail


def test_filtered_launcher_returns_frozen_exact_receipt(
    isolated_store,
    monkeypatch,
):
    entries = (
        _entry(
            "atomize",
            "atomize-1",
            reopen_argv=(
                "mem",
                "impact",
                "atomize",
                "--session",
                "atomize-1",
            ),
        ),
        _entry(
            "update",
            "update-1",
            reopen_argv=(
                "mem",
                "impact",
                "update",
                "--session",
                "update-1",
            ),
        ),
    )
    monkeypatch.setattr(
        impact_catalog,
        "impact_session_entries",
        lambda _store: entries,
    )
    monkeypatch.setattr(
        impact_catalog,
        "session_picker_location",
        lambda _store: None,
    )
    observed = []

    def choose(options, **kwargs):
        observed.append((tuple(options), kwargs))
        selected = options[0]
        return SessionOpenReceipt(
            kind=selected.kind,
            key=selected.key,
            argv=selected.reopen_argv,
        )

    monkeypatch.setattr(impact_catalog, "choose_session", choose)

    receipt = impact_catalog.choose_impact_session(
        MemoryStore(),
        kinds=("atomize",),
        title="ATOMIZE ONLY",
    )

    assert receipt is not None
    assert receipt.kind == "atomize"
    assert receipt.key == "atomize-1"
    assert [entry.kind for entry in observed[0][0]] == ["atomize"]
    assert observed[0][1]["catalog_label"] == "saved Impact analyses"
    assert observed[0][1]["enter_action"] == "inspect"


@pytest.mark.parametrize(
    "kinds",
    ((), ("forget",), ("atomize", "atomize")),
)
def test_launcher_rejects_non_durable_or_duplicate_filters(
    isolated_store,
    kinds,
):
    with pytest.raises(ValueError, match="invalid operation kinds"):
        impact_catalog.choose_impact_session(MemoryStore(), kinds=kinds)
