"""Cache identity checks for exact Memory-focused Compare inputs."""

from __future__ import annotations

from types import SimpleNamespace

import memcommit.ops as ops
from memcommit.comparison import (
    ComparisonInput,
    comparison_analysis_matches_input,
)


def _analysis_shape(comparison_input: ComparisonInput):
    return SimpleNamespace(
        include_descendants=comparison_input.include_descendants,
        frames=comparison_input.frames,
    )


def test_focused_compare_identity_reuses_only_the_same_actionable_memories() -> None:
    reference = ops.init("reference")
    first = ops.add(reference, "First reference claim.")
    second = ops.add(reference, "Second reference claim.")
    peer = ops.init("peer")
    peer_memory = ops.add(peer, "Peer claim.")

    focused = ComparisonInput.from_contexts(
        reference,
        peer,
        reference_memory_selector=first.uid,
        compared_memory_selector=peer_memory.uid,
    )
    same_focus = ComparisonInput.from_contexts(
        reference,
        peer,
        reference_memory_selector=first.uid,
        compared_memory_selector=peer_memory.uid,
    )
    different_focus = ComparisonInput.from_contexts(
        reference,
        peer,
        reference_memory_selector=second.uid,
        compared_memory_selector=peer_memory.uid,
    )
    whole = ComparisonInput.from_contexts(reference, peer)

    assert comparison_analysis_matches_input(_analysis_shape(focused), same_focus)
    assert not comparison_analysis_matches_input(
        _analysis_shape(focused),
        different_focus,
    )
    assert not comparison_analysis_matches_input(_analysis_shape(focused), whole)
    assert not comparison_analysis_matches_input(_analysis_shape(whole), focused)


def test_focused_compare_identity_retains_complete_context_freshness() -> None:
    reference = ops.init("reference")
    focus = ops.add(reference, "Focused reference claim.")
    neighbor = ops.add(reference, "Neighboring interpretation context.")
    peer = ops.init("peer")
    peer_memory = ops.add(peer, "Peer claim.")
    before = ComparisonInput.from_contexts(
        reference,
        peer,
        reference_memory_selector=focus.uid,
        compared_memory_selector=peer_memory.uid,
    )

    ops.edit(reference, neighbor.uid, "Changed neighboring context.")
    after = ComparisonInput.from_contexts(
        reference,
        peer,
        reference_memory_selector=focus.uid,
        compared_memory_selector=peer_memory.uid,
    )

    assert not comparison_analysis_matches_input(_analysis_shape(before), after)


def test_singleton_explicit_focus_remains_distinct_from_whole_context() -> None:
    reference = ops.init("reference")
    focus = ops.add(reference, "Only reference claim.")
    peer = ops.init("peer")
    peer_memory = ops.add(peer, "Only peer claim.")

    focused = ComparisonInput.from_contexts(
        reference,
        peer,
        reference_memory_selector=focus.uid,
        compared_memory_selector=peer_memory.uid,
    )
    whole = ComparisonInput.from_contexts(reference, peer)

    assert focused.frames[0].selected_memory_uid == focus.uid
    assert focused.frames[1].selected_memory_uid == peer_memory.uid
    assert focused.frames[0].context_evidence == ()
    assert not comparison_analysis_matches_input(_analysis_shape(focused), whole)
    assert not comparison_analysis_matches_input(_analysis_shape(whole), focused)
