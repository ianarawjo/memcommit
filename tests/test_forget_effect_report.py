"""Forget's exact proposal stays inspectable in a two-frame Apply surface."""

from dataclasses import replace
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.commands.forget.workbench.presentation import (
    forget_application_view,
    forget_memory_changes,
)
from memcommit.adapters.console.commands.impact.projection import ImpactController
from memcommit.adapters.console.terminal.components.resolution.effect_preview import (
    EffectReportPresentation,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.effect_report import (
    effect_report_fragments,
    effect_report_sections,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime import (
    runner,
)
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_action_role,
)
from memcommit.application.capabilities.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
)
from memcommit.application.capabilities.semantic.selective_curation import (
    CurationAnalysis,
    CurationDecision,
)
from memcommit.application.operations.forget.review import ForgetReview
from memcommit.core.context import Context, Memory


@pytest.fixture
def proposal():
    context = Context(uid=str(uuid.uuid4()), name="notes")
    # A KEEP before and after changes proves grouping preserves effect identities.
    contents = (
        "Unchanged first.",
        "Old desk. Step-free route.",
        "Old code.",
        "Unchanged last.",
    )
    memories = [Memory(uid=str(uuid.uuid4()), content=text) for text in contents]
    for memory in memories:
        context.add(memory)
    actions = (
        ("KEEP", contents[0]),
        ("TRANSFORM", "Step-free route."),
        ("DROP", ""),
        ("KEEP", contents[3]),
    )
    analysis = CurationAnalysis(
        "An assessment that the approval does not repeat.",
        tuple(
            CurationDecision(
                memory.uid, action, action, text, f"Reason {index}.", ("k1",)
            )
            for index, (memory, (action, text)) in enumerate(
                zip(memories, actions, strict=True)
            )
        ),
    )
    review = ForgetReview.create(context, "Forget the old desk and code.", analysis)
    view = forget_application_view(review)
    impact = ImpactController.from_memory_changes(
        operation=view.operation,
        artifact_uid=view.artifact_uid,
        revision=view.revision,
        title="IMPACT",
        summary="Exact proposal",
        changes=forget_memory_changes(review),
    )
    presentation = EffectReportPresentation(
        review.instruction,
        "Apply 2 changes to notes",
        "KEEP",
        frozenset(memory.uid for memory in (memories[0], memories[3])),
    )
    return review, view, impact, presentation


def render(proposal, *, expanded=None, focused=0, width=176, unchanged_expanded=False):
    _, view, impact, presentation = proposal
    return effect_report_fragments(
        view,
        impact.view(),
        presentation,
        focused_section=focused,
        expanded_uid=expanded,
        content_width=width,
        unchanged_expanded=unchanged_expanded,
    )


def text(fragments):
    return "".join(value for _, value in fragments)


def test_initial_forget_report_contains_only_source_instruction_changes_and_keep_count(
    proposal,
):
    review, view, impact, _ = proposal
    rendered = text(render(proposal))
    assert rendered.count("SOURCE · notes") == 1
    assert rendered.count(review.instruction) == 1
    assert (
        "Old desk." in rendered
        and "Step-free route." in rendered
        and "Old code." in rendered
    )
    assert "KEEP · 2 Memories unchanged" in rendered
    assert "Unchanged first." not in rendered and "Unchanged last." not in rendered
    assert "Reason" not in rendered
    for redundant in (
        "PREPARED",
        "ASSESSMENT",
        "WHAT APPLIES",
        "CONTEXT LOCATIONS",
        "IMPACT",
        "APPLY",
        "FORGET DECISION",
    ):
        assert redundant not in rendered
    assert view.items == () and view.results == ()
    assert len(impact.view().entries) == 4 and len(review.changes()) == 2


def test_expansion_shows_reason_or_complete_keep_group_without_changing_batch(proposal):
    review, _, impact, presentation = proposal
    before = review.changes()
    sections = effect_report_sections(impact.view(), presentation)
    assert [section.kind for section in sections] == [
        "INSTRUCTION",
        "IMPACT_ENTRY",
        "IMPACT_ENTRY",
        "IMPACT_GROUP",
    ]
    assert sections[1].uid == f"REPORT:IMPACT:{review.candidates[1].source.uid}"
    reason = text(render(proposal, focused=1, expanded=sections[1].uid))
    assert "WHY · Reason 1." in reason and "Unchanged first." not in reason
    retained = text(render(proposal, focused=3, unchanged_expanded=True))
    assert "Unchanged first." in retained and "Unchanged last." in retained
    assert "WHY" not in retained
    expanded_sections = effect_report_sections(
        impact.view(), presentation, unchanged_expanded=True
    )
    assert len(expanded_sections) == 6
    retained_reason = text(
        render(
            proposal,
            focused=4,
            unchanged_expanded=True,
            expanded=expanded_sections[4].uid,
        )
    )
    assert "WHY · Reason 0." in retained_reason
    assert review.changes() == before


def test_same_text_transform_stays_visible_instead_of_becoming_keep(proposal):
    review, view, _, presentation = proposal
    candidate = review.candidates[1]
    review = review.select(candidate.uid, "CUSTOM", candidate.source.content)
    view = forget_application_view(review)
    impact = ImpactController.from_memory_changes(
        operation=view.operation,
        artifact_uid=view.artifact_uid,
        revision=view.revision,
        title="IMPACT",
        summary="Exact proposal",
        changes=forget_memory_changes(review),
    )
    rendered = text(render((review, view, impact, presentation)))
    assert "TRANSFORM" in rendered and candidate.source.uid[:8] in rendered
    assert "KEEP · 2 Memories unchanged" in rendered
    assert len(review.changes()) == 2


@pytest.mark.parametrize("retained", ["missing", "changed"])
def test_renderer_rejects_incorrectly_declared_keep_entries(proposal, retained):
    _, view, impact, presentation = proposal
    uid = "missing-memory" if retained == "missing" else impact.view().entries[1].uid
    with pytest.raises(ValueError, match="retained entry"):
        effect_report_fragments(
            view,
            impact.view(),
            replace(presentation, unchanged_entry_uids=frozenset({uid})),
            focused_section=0,
            expanded_uid=None,
            content_width=176,
        )


def test_effect_report_keeps_control_text_escaped_and_effect_styles_typed(proposal):
    _, view, impact, presentation = proposal
    fragments = effect_report_fragments(
        view,
        impact.view(),
        replace(presentation, instruction="지시\x1b[31m\u202e\nSecond line"),
        focused_section=0,
        expanded_uid=None,
        content_width=40,
    )
    rendered = text(fragments)
    assert "\x1b" not in rendered and "\u202e" not in rendered
    assert "Second line" in rendered
    assert semantic_action_role("TRANSFORM") == SemanticColorRole.EDIT
    assert semantic_action_role("DROP") == SemanticColorRole.REMOVE
    assert any(
        style == "class:semantic.edit" and "TRANSFORM" in value
        for style, value in fragments
    )
    assert any(
        style == "class:semantic.remove" and "DROP" in value
        for style, value in fragments
    )
    # Semantic styles do not carry the neutral Memory UID or body with them.
    assert all(
        "Old code." not in value
        for style, value in fragments
        if style == "class:semantic.remove"
    )


def test_effect_focus_overrides_action_color_then_restores_it_on_tab(proposal):
    from memcommit.adapters.console.terminal.components.semantic_viewer import (
        deactivate_semantic_viewer_fragments,
    )

    focused = render(proposal, focused=1)
    style = next(style for style, value in focused if "TRANSFORM" in value)
    assert style == "class:semantic.edit class:viewer-section"
    resting = deactivate_semantic_viewer_fragments(focused)
    assert (
        next(style for style, value in resting if "TRANSFORM" in value)
        == "class:semantic.edit"
    )


@pytest.mark.parametrize(
    "keys, action, pane, section",
    [
        ("\t\r\x1b", "ACCEPT", "todo", 0),
        ("\x1b[Z\r\x1b", "ACCEPT", "todo", 0),
        ("\x1b[B\r\t\x1b[Z\x1b", "CLOSE", "viewer", 1),
        ("\x1b[B\x1b[B\x1b[B\r\x1b", "CLOSE", "viewer", 3),
        ("\x1b[B\x1b[B\x1b[B\r\x1b[B\r\t\x1b[Z\x1b", "CLOSE", "viewer", 4),
    ],
)
def test_forget_shell_has_no_hidden_items_stop_and_preserves_viewer_cursor(
    proposal, monkeypatch, keys, action, pane, section
):
    _, view, impact, presentation = proposal
    navigation = SessionWorkbenchNavigation()
    captured = []
    original = runner.ResolutionShellControls

    def observe(*args, **kwargs):
        controls = original(*args, **kwargs)
        captured.append(controls)
        return controls

    monkeypatch.setattr(runner, "ResolutionShellControls", observe)
    with create_pipe_input() as pipe:
        pipe.send_text(keys)
        result = runner.run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            report_apply=True,
            impact_controller=impact,
            effect_report=presentation,
            workbench_navigation=navigation,
            app_input=pipe,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert result.kind == action and navigation.pane == pane
    sections = effect_report_sections(
        impact.view(),
        presentation,
        unchanged_expanded=captured[0].controller.unchanged_effects_expanded,
    )
    assert navigation.section_uid == sections[section].uid
    assert presentation.apply_label in text(captured[0].todo_fragments())
    if section >= 3:
        assert "Unchanged first." in captured[0].current_viewer_plain_text(
            whole_document=True
        )
    if section == 4:
        assert "WHY · Reason 0." in captured[0].current_viewer_plain_text(
            whole_document=True
        )


@pytest.mark.parametrize("mode", ["required_items", "auto_accept"])
def test_compact_report_cannot_hide_review_obligations_or_automatically_apply(
    proposal, mode
):
    from memcommit.adapters.console.commands.forget.workbench.presentation import (
        ForgetResolutionWorkbenchAdapter,
    )

    review, view, impact, presentation = proposal
    kwargs = {}
    if mode == "required_items":
        view = ForgetResolutionWorkbenchAdapter(review).view()
        message = "cannot hide actionable review items"
    else:
        kwargs["decision_free_behavior"] = "AUTO_ACCEPT"
        message = "explicit Apply"
    with pytest.raises(ValueError, match=message):
        runner.run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            report_apply=True,
            impact_controller=impact,
            effect_report=presentation,
            require_tty=False,
            **kwargs,
        )


def test_effect_report_rejects_mismatched_revision(proposal):
    _, view, impact, presentation = proposal
    from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.controls import (
        report_sections,
    )

    with pytest.raises(ValueError, match="active artifact revision"):
        report_sections(
            replace(view, revision="999"),
            split_report_text=None,
            global_strategies=(),
            review_and_apply=False,
            report_apply=True,
            read_only=False,
            impact_controller=impact,
            drafts={},
            effect_report=presentation,
        )
