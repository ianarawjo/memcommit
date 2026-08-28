from dataclasses import FrozenInstanceError

import pytest

from memcommit.application.capabilities.reviewing.result_workbench import (
    RESULT_REPORT_FRAME_SOFT_MAX_WORDS,
    RESULT_REPORT_SECTION_SOFT_MAX_WORDS,
    RESULT_REPORT_SECTION_TARGET_MIN_WORDS,
    ResultCase,
    ResultCaseDetail,
    ResultDetailBlock,
    ResultMetric,
    ResultRef,
    ResultSection,
    ResultWorkbenchAdapter,
    ResultWorkbenchError,
    ResultWorkbenchView,
)


ARTIFACT_DIGEST = "a" * 64
STALE_DIGEST = "b" * 64
SOURCE_REF = ResultRef(kind="source-memory", key="source-1")
JUDGMENT_REF = ResultRef(kind="analysis-item", key="item-1")
OUTCOME_REF = ResultRef(kind="result-memory", key="result-1")
UNRESOLVED_REF = ResultRef(kind="quality-issue", key="issue-1")


def _section(
    text: str,
    *,
    ref: ResultRef = SOURCE_REF,
) -> ResultSection:
    return ResultSection(state="PRESENT", text=text, refs=(ref,))


def _case(
    *,
    uid: str = "case-1",
    role: str = "REPRESENTATIVE",
) -> ResultCase:
    return ResultCase(
        uid=uid,
        role=role,
        title="A source-linked inspection case",
        summary="The operation retained the source statement.",
        why_selected="It demonstrates the ordinary retained outcome.",
    )


def _view(*, case: ResultCase | None = None) -> ResultWorkbenchView:
    selected_case = case or _case()
    return ResultWorkbenchView(
        operation="atomize",
        artifact_uid="analysis-1",
        artifact_digest=ARTIFACT_DIGEST,
        title="Atomize impact",
        status="READY",
        metrics=(ResultMetric(key="source_count", label="source", value=1),),
        understood=_section("The input concerns building access."),
        happened=_section(
            "One source statement was retained.",
            ref=OUTCOME_REF,
        ),
        unresolved=ResultSection(
            state="NONE_REPORTED",
            text="The operation explicitly reported no unresolved findings.",
        ),
        cases=(selected_case,),
    )


def _detail(
    *,
    case_uid: str = "case-1",
    artifact_digest: str = ARTIFACT_DIGEST,
    judgment_refs: tuple[ResultRef, ...] = (JUDGMENT_REF,),
    outcome_refs: tuple[ResultRef, ...] = (OUTCOME_REF,),
    unresolved_refs: tuple[ResultRef, ...] = (),
) -> ResultCaseDetail:
    return ResultCaseDetail(
        case_uid=case_uid,
        artifact_digest=artifact_digest,
        blocks=(
            ResultDetailBlock(
                heading="SOURCE",
                text="The main entrance closes at 5 p.m.",
                refs=(SOURCE_REF,),
            ),
        ),
        evidence_refs=(SOURCE_REF,),
        judgment_refs=judgment_refs,
        outcome_refs=outcome_refs,
        unresolved_refs=unresolved_refs,
    )


@pytest.mark.parametrize("value", [-1, True, 1.5, "1"])
def test_metric_rejects_values_that_are_not_nonnegative_integers(
    value: object,
) -> None:
    with pytest.raises(ResultWorkbenchError, match="metric value"):
        ResultMetric(  # type: ignore[arg-type]
            key="source_count",
            label="source",
            value=value,
        )


def test_metric_accepts_zero_and_view_rejects_duplicate_metric_keys() -> None:
    zero = ResultMetric(key="source_count", label="source", value=0)
    assert zero.value == 0

    with pytest.raises(ResultWorkbenchError, match="Duplicate result metric key"):
        ResultWorkbenchView(
            operation="atomize",
            artifact_uid="analysis-1",
            artifact_digest=ARTIFACT_DIGEST,
            title="Atomize impact",
            status="READY",
            metrics=(
                zero,
                ResultMetric(key="source_count", label="again", value=1),
            ),
            understood=_section("The source was understood."),
            happened=_section("Nothing was transformed."),
            unresolved=ResultSection(
                state="NOT_RECORDED",
                text="This legacy artifact did not record unresolved findings.",
            ),
        )


def test_present_section_requires_traceable_references() -> None:
    with pytest.raises(ResultWorkbenchError, match="requires traceable"):
        ResultSection(
            state="PRESENT",
            text="The operation understood the input.",
        )


def test_report_word_budget_is_guidance_not_a_parser_truncation_rule() -> None:
    assert (
        RESULT_REPORT_SECTION_TARGET_MIN_WORDS,
        RESULT_REPORT_SECTION_SOFT_MAX_WORDS,
        RESULT_REPORT_FRAME_SOFT_MAX_WORDS,
    ) == (40, 50, 150)
    text = " ".join(["grounded"] * 51)

    section = ResultSection(
        state="PRESENT",
        text=text,
        refs=(SOURCE_REF,),
    )

    assert section.text == text


@pytest.mark.parametrize(
    "text",
    [
        "- The entrance closes.\n- The staff entrance remains open.",
        "1. The entrance closes.\n2. The staff entrance remains open.",
        "• The entrance closes.",
    ],
)
def test_overview_sections_reject_navigation_lists_instead_of_report_prose(
    text: str,
) -> None:
    with pytest.raises(ResultWorkbenchError, match="report prose"):
        ResultSection(
            state="PRESENT",
            text=text,
            refs=(SOURCE_REF,),
        )


@pytest.mark.parametrize("state", ["NONE_REPORTED", "NOT_RECORDED"])
def test_nonpresent_section_states_are_explicit_and_cannot_claim_refs(
    state: str,
) -> None:
    section = ResultSection(state=state, text="")
    assert section.state == state
    assert section.refs == ()

    with pytest.raises(ResultWorkbenchError, match="cannot cite"):
        ResultSection(
            state=state,
            text="No finding is available.",
            refs=(SOURCE_REF,),
        )


def test_projection_and_nested_sequences_are_immutable_tuples() -> None:
    view = _view()

    with pytest.raises(FrozenInstanceError):
        view.status = "CHANGED"  # type: ignore[misc]
    with pytest.raises(ResultWorkbenchError, match="Invalid result metrics"):
        ResultWorkbenchView(
            operation="atomize",
            artifact_uid="analysis-1",
            artifact_digest=ARTIFACT_DIGEST,
            title="Atomize impact",
            status="READY",
            metrics=[],  # type: ignore[arg-type]
            understood=view.understood,
            happened=view.happened,
            unresolved=view.unresolved,
        )


def test_detail_must_match_an_exact_case_and_current_artifact_digest() -> None:
    view = _view()

    with pytest.raises(ResultWorkbenchError, match="No result inspection case"):
        view.validate_detail(_detail(case_uid="missing"))
    with pytest.raises(ResultWorkbenchError, match="stale operation artifact"):
        view.validate_detail(_detail(artifact_digest=STALE_DIGEST))


def test_all_case_details_require_source_evidence_and_operation_judgment() -> None:
    with pytest.raises(ResultWorkbenchError, match="requires source evidence"):
        ResultCaseDetail(
            case_uid="case-1",
            artifact_digest=ARTIFACT_DIGEST,
            blocks=(
                ResultDetailBlock(
                    heading="SOURCE",
                    text="A source statement.",
                ),
            ),
            evidence_refs=(),
            judgment_refs=(JUDGMENT_REF,),
            outcome_refs=(OUTCOME_REF,),
        )

    with pytest.raises(ResultWorkbenchError, match="operation judgment"):
        _view().validate_detail(_detail(judgment_refs=()))


def test_representative_case_requires_a_supported_outcome() -> None:
    representative = _view(case=_case(role="REPRESENTATIVE"))

    with pytest.raises(ResultWorkbenchError, match="supported outcome"):
        representative.validate_detail(_detail(outcome_refs=()))

    assert representative.validate_detail(_detail()) == _detail()


def test_boundary_case_requires_an_outcome_or_unresolved_finding() -> None:
    boundary = _view(case=_case(role="BOUNDARY"))

    with pytest.raises(
        ResultWorkbenchError,
        match="outcome or unresolved finding",
    ):
        boundary.validate_detail(_detail(outcome_refs=()))

    unresolved = _detail(
        outcome_refs=(),
        unresolved_refs=(UNRESOLVED_REF,),
    )
    assert boundary.validate_detail(unresolved) == unresolved
    assert boundary.validate_detail(_detail()) == _detail()


def test_adapter_protocol_shape_can_supply_validated_view_and_detail() -> None:
    class Adapter:
        def __init__(self) -> None:
            self._view = _view()

        def view(self) -> ResultWorkbenchView:
            return self._view

        def case_detail(self, case_uid: str) -> ResultCaseDetail:
            return _detail(case_uid=case_uid)

    adapter: ResultWorkbenchAdapter = Adapter()
    view = adapter.view()

    assert view.validate_detail(adapter.case_detail("case-1")).case_uid == "case-1"
