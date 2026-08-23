"""Stable Python entry point over reviewed MemCommit application boundaries."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.providers import (
    connect_ordinary_provider,
    connect_route_provider,
)
from memcommit.api.add import AddMemoriesResult
from memcommit.api.atomize_grounding import (
    AtomizeGroundingApplyResult,
    AtomizeGroundingSessionResult,
)
from memcommit.api.atomize import (
    AtomizeAnalysisResult,
    AtomizeReviewUpdateResult,
    AtomizeReviewedApplyResult,
    AtomizeSaveAsApplyResult,
    AtomizeStructuralApplyResult,
)
from memcommit.api.compare import ComparisonResult
from memcommit.api.delete import (
    ContextDeletePlanResult,
    ContextDeleteReceipt,
    DirectItemDeleteReceipt,
)
from memcommit.api.dedup import (
    DedunApplyResult,
    DedunPlanResult,
    ExactDedupResult,
    ExactDuplicateFindResult,
)
from memcommit.api.embed import EmbeddedContextResult, EmbeddedMemoryResult
from memcommit.api.forget import (
    ForgetApplyResult,
    ForgetReviewResult,
)
from memcommit.api.find import FindResult
from memcommit.api.help import (
    HelpCatalogResult,
    HelpDetailCatalogResult,
    HelpDetailResult,
    OperationHelpResult,
)
from memcommit.api.errors import (
    QueryConfigurationError,
)
from memcommit.api.meld import (
    MeldApplyResult as PublicMeldApplyResult,
    MeldSessionResult,
)
from memcommit.api.memory_transfer import CopyMemoriesReceipt, MoveMemoriesReceipt
from memcommit.api.query import (
    GrantedQueryResult,
    OrdinaryQueryResult,
    QueryProviderConfig,
    ReferenceQueryResult,
)
from memcommit.api.reference import ContextReferenceResult, MemoryReferenceResult
from memcommit.api.replace import ReplaceApplyReceipt, ReplacePlanResult
from memcommit.api.quality_find import QualityFindResult
from memcommit.api.resolve import ResolveAnalysisResult, ResolveApplyResult
from memcommit.api.search import SearchResult
from memcommit.api.show import ShowResult
from memcommit.api.semantic import (
    DistillApplyResult,
    DistillProposal,
    ElaborateProposal,
    FitJudgmentResult,
    FitPropositionInput,
)
from memcommit.context import QueryContextRef
from memcommit.quality_finding_handoff import QualityFindingHandoff
from memcommit.profile_config import (
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.store import MemoryStore


ProviderFactory = Callable[[], object]
RouteProviderFactory = Callable[[str], object]
StageObserver = Callable[[str], None]


class MemCommitClient:
    """Own one frozen Store boundary and provider configuration snapshot.

    Provider objects remain per-call resources. The client itself owns no open
    endpoint or terminal resource and therefore requires no explicit close.
    """

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        profile: str | None = None,
        create: bool = False,
        query_config: QueryProviderConfig | None = None,
        ordinary_provider_factory: ProviderFactory | None = None,
        query_route_provider_factory: RouteProviderFactory | None = None,
        semantic_provider_factory: ProviderFactory | None = None,
    ) -> None:
        if root is not None and profile is not None:
            raise QueryConfigurationError(
                "Choose either an explicit Store root or a Profile, not both."
            )
        if not isinstance(create, bool):
            raise QueryConfigurationError("Client create must be a boolean.")
        try:
            config = query_config or QueryProviderConfig()
        except (TypeError, ValueError) as error:
            raise_public(QueryConfigurationError, error)
        if not isinstance(config, QueryProviderConfig):
            raise QueryConfigurationError("query_config must be a QueryProviderConfig.")

        registry: ProfileRegistry | None = None
        selected_profile: ProfileEntry | None = None
        try:
            if root is None:
                registry = load_profile_registry()
                if profile is None:
                    selected_profile = registry.active
                else:
                    selected_profile = registry.by_name(profile)
                    if selected_profile is None or registry.is_removed(
                        selected_profile
                    ):
                        raise QueryConfigurationError(
                            f"Profile {profile!r} is not available."
                        )
                store_root = profile_store_dir(selected_profile)
            else:
                store_root = Path(root).expanduser().absolute()
        except QueryConfigurationError:
            raise
        except (OSError, ProfileConfigError, TypeError, ValueError) as error:
            raise_public(QueryConfigurationError, error)

        self._store = MemoryStore(root=store_root, create=create)
        self._store_root = self._store.store_dir.resolve()
        self._registry = registry
        self._profile = selected_profile
        self._query_config = config
        self._ordinary_provider_factory = ordinary_provider_factory or partial(
            connect_ordinary_provider,
            config,
        )
        self._query_route_provider_factory = query_route_provider_factory or partial(
            connect_route_provider,
            config,
        )
        self._semantic_provider_factory = (
            semantic_provider_factory or self._ordinary_provider_factory
        )
        self._runtime = ClientRuntime(
            store=self._store,
            store_root=self._store_root,
            registry=self._registry,
            profile=self._profile,
            query_config=self._query_config,
            ordinary_provider_factory=self._ordinary_provider_factory,
            query_route_provider_factory=self._query_route_provider_factory,
            semantic_provider_factory=self._semantic_provider_factory,
        )

    @property
    def store_root(self) -> Path:
        return self._store_root

    @property
    def profile_name(self) -> str | None:
        return self._profile.name if self._profile is not None else None

    @property
    def query_config(self) -> QueryProviderConfig:
        return self._query_config

    def list_operations(self) -> HelpCatalogResult:
        """List stable public operation meanings without Store or provider access."""

        from memcommit.api._operations.help import list_operations

        return list_operations()

    def describe_operation(self, operation_name: str) -> OperationHelpResult:
        """Describe one exact public operation without executing it."""

        from memcommit.api._operations.help import describe_operation

        return describe_operation(operation_name)

    def list_operation_details(
        self,
        operation_name: str,
    ) -> HelpDetailCatalogResult:
        """List individually retrievable Help details for one operation."""

        from memcommit.api._operations.help import list_operation_details

        return list_operation_details(operation_name)

    def describe_operation_detail(
        self,
        operation_name: str,
        detail_id: str,
    ) -> HelpDetailResult:
        """Describe one exact typed Help detail without executing it."""

        from memcommit.api._operations.help import describe_operation_detail

        return describe_operation_detail(operation_name, detail_id)

    def show(
        self,
        selector: str | None = None,
        *,
        context_name: str | None = None,
    ) -> ShowResult:
        """Inspect one readable Context or direct item without side effects."""

        from memcommit.api._operations.show import show

        return show(self._runtime, selector, context_name=context_name)

    def search(
        self,
        query: str,
        context_names: Sequence[str] = (),
        *,
        include_descendants: bool = False,
        follow_embeds: bool = False,
        limit: int = 5,
    ) -> SearchResult:
        """Search a readable Context scope by semantic relevance."""

        from memcommit.api._operations.search import search

        return search(
            self._runtime,
            query,
            context_names,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            limit=limit,
        )

    def find(
        self,
        pattern: str,
        context_names: Sequence[str] = (),
        *,
        include_descendants: bool = False,
        follow_embeds: bool = False,
        regex: bool = False,
        ignore_case: bool = False,
    ) -> FindResult:
        """Find literal or regex text spans without semantic inference."""

        from memcommit.api._operations.find import find

        return find(
            self._runtime,
            pattern,
            context_names,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            regex=regex,
            ignore_case=ignore_case,
        )

    def plan_replace(
        self,
        pattern: str,
        replacement: str,
        context_names: Sequence[str] = (),
        *,
        include_descendants: bool = False,
        follow_embeds: bool = False,
        regex: bool = False,
        ignore_case: bool = False,
    ) -> ReplacePlanResult:
        """Freeze and preview every deterministic replacement without mutation."""

        from memcommit.api._operations.replace import plan_replace

        return plan_replace(
            self._runtime,
            pattern,
            replacement,
            context_names,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            regex=regex,
            ignore_case=ignore_case,
        )

    def apply_replace(self, reviewed: ReplacePlanResult) -> ReplaceApplyReceipt:
        """Apply one exact plan created by this client or publish no effect."""

        from memcommit.api._operations.replace import apply_replace

        return apply_replace(self._runtime, reviewed)

    def remove_item(
        self,
        selector: str,
        *,
        context_name: str | None = None,
    ) -> DirectItemDeleteReceipt:
        """Remove one direct item through a normal Undoable checkpoint."""

        from memcommit.api._operations.delete import remove_item

        return remove_item(self._runtime, selector, context_name=context_name)

    def plan_context_delete(self, context_name: str) -> ContextDeletePlanResult:
        """Freeze one permanent Context deletion without changing the Store."""

        from memcommit.api._operations.delete import plan_context_delete

        return plan_context_delete(self._runtime, context_name)

    def apply_context_delete(
        self,
        reviewed: ContextDeletePlanResult,
    ) -> ContextDeleteReceipt:
        """Permanently delete the exact Context identity in a reviewed plan."""

        from memcommit.api._operations.delete import apply_context_delete

        return apply_context_delete(self._runtime, reviewed)

    def fit(
        self,
        propositions: Sequence[str | FitPropositionInput],
        *,
        background: Sequence[str | FitPropositionInput] = (),
    ) -> FitJudgmentResult:
        """Judge one complete proposition set without Store effects."""

        from memcommit.api._operations.fit import fit

        return fit(self._runtime, propositions, background=background)

    def compare_contexts(
        self,
        reference_context: str,
        compared_context: str,
        *,
        reference_descendants: bool = False,
        compared_descendants: bool = False,
        reference_memory: str | None = None,
        compared_memory: str | None = None,
    ) -> ComparisonResult:
        """Reuse or create one complete ordered read-only Compare analysis."""

        from memcommit.api._operations.compare import compare_contexts

        return compare_contexts(
            self._runtime,
            reference_context,
            compared_context,
            reference_descendants=reference_descendants,
            compared_descendants=compared_descendants,
            reference_memory=reference_memory,
            compared_memory=compared_memory,
        )

    def analyze_forget(
        self,
        instruction: str,
        *,
        context_name: str | None = None,
    ) -> ForgetReviewResult:
        """Analyze one complete direct Source into a process-local review."""

        from memcommit.api._operations.forget import analyze_forget_context

        return analyze_forget_context(
            self._runtime,
            instruction,
            context_name=context_name,
        )

    def select_forget(
        self,
        review: ForgetReviewResult,
        candidate_uid: str,
        selection: str,
        *,
        custom_content: str = "",
    ) -> ForgetReviewResult:
        """Change one exact process-local Forget decision without effects."""

        from memcommit.api._operations.forget import select_forget_review

        return select_forget_review(
            self._runtime,
            review,
            candidate_uid,
            selection,
            custom_content=custom_content,
        )

    def revise_forget(
        self,
        review: ForgetReviewResult,
        guidance: str,
    ) -> ForgetReviewResult:
        """Run one provider revision over a process-local Forget review."""

        from memcommit.api._operations.forget import revise_forget_review

        return revise_forget_review(self._runtime, review, guidance)

    def apply_forget(
        self,
        review: ForgetReviewResult,
    ) -> ForgetApplyResult:
        """Apply one exact reviewed Forget effect or explicit no-op."""

        from memcommit.api._operations.forget import apply_forget_review

        return apply_forget_review(self._runtime, review)

    def open_comparison(self, analysis_uid: str) -> ComparisonResult:
        """Open one exact current durable analysis without provider or mutation."""

        from memcommit.api._operations.compare import open_comparison

        return open_comparison(self._runtime, analysis_uid)

    def refresh_comparison(
        self,
        analysis_uid: str,
        *,
        expected_version: str,
    ) -> ComparisonResult:
        """Refresh exactly one reviewed latest-pair slot and replace it by CAS."""

        from memcommit.api._operations.compare import refresh_comparison

        return refresh_comparison(
            self._runtime,
            analysis_uid,
            expected_version=expected_version,
        )

    def resolve_context(
        self,
        context_name: str | None = None,
        *,
        memory_selectors: Sequence[str] = (),
        allow_create: bool = True,
        allow_delete: bool = False,
        guidance: str = "",
        target_fit: str = "MAY",
        expected_revision: str | None = None,
    ) -> ResolveAnalysisResult:
        """Return one automatic grounded or assumed full-frame interpretation plan."""

        from memcommit.api._operations.resolve import resolve_context

        return resolve_context(
            self._runtime,
            context_name,
            memory_selectors=memory_selectors,
            allow_create=allow_create,
            allow_delete=allow_delete,
            guidance=guidance,
            target_fit=target_fit,
            expected_revision=expected_revision,
        )

    def find_redundancies(
        self,
        context_names: Sequence[str] = (),
    ) -> QualityFindResult:
        """Find complete exact-DUP plus semantic-DUN evidence."""

        from memcommit.api._operations.quality_find import find_quality

        return find_quality(self._runtime, "duplicates", context_names)

    def find_duplicates(
        self,
        context_name: str | None = None,
    ) -> ExactDuplicateFindResult:
        """Find exact direct-Memory duplicate groups without mutation."""

        from memcommit.api._operations.exact_duplicates import find_duplicates_exact

        return find_duplicates_exact(self._runtime, context_name)

    def find_ambiguities(
        self,
        context_names: Sequence[str] = (),
    ) -> QualityFindResult:
        """Find ambiguity in one frozen readable Context frame."""

        from memcommit.api._operations.quality_find import find_quality

        return find_quality(self._runtime, "ambiguities", context_names)

    def find_conflicts(
        self,
        context_names: Sequence[str] = (),
    ) -> QualityFindResult:
        """Find conflicting pairs in one frozen readable Context frame."""

        from memcommit.api._operations.quality_find import find_quality

        return find_quality(self._runtime, "conflicts", context_names)

    def resolve_conflict_finding(
        self,
        handoff: QualityFindingHandoff,
        *,
        allow_create: bool = True,
        allow_delete: bool = False,
        guidance: str = "",
        target_fit: str = "MAY",
        expected_revision: str | None = None,
    ) -> ResolveAnalysisResult:
        """Resolve one exact finder receipt after fresh source and authority checks."""

        from memcommit.api._operations.resolve import resolve_conflict_finding

        return resolve_conflict_finding(
            self._runtime,
            handoff,
            allow_create=allow_create,
            allow_delete=allow_delete,
            guidance=guidance,
            target_fit=target_fit,
            expected_revision=expected_revision,
        )

    def apply_resolve(
        self,
        analysis: ResolveAnalysisResult,
        *,
        candidate_uid: str,
    ) -> ResolveApplyResult:
        """Apply one exact candidate from a reviewed Resolve analysis."""

        from memcommit.api._operations.resolve import apply_resolve

        return apply_resolve(
            self._runtime,
            analysis,
            candidate_uid=candidate_uid,
        )

    def dedup(self, context_name: str | None = None) -> ExactDedupResult:
        """Remove same-role exact duplicate direct items in one checkpoint."""

        from memcommit.api._operations.exact_dedup import dedup_exact

        return dedup_exact(self._runtime, context_name)

    def plan_dedun(
        self,
        evidence: Sequence[QualityFindingHandoff],
        *,
        expected_revision: str | None = None,
    ) -> DedunPlanResult:
        """Plan survivor choices from typed exact-plus-semantic DUN evidence."""

        from memcommit.api._operations.dedup import plan_dedun

        return plan_dedun(
            self._runtime,
            evidence,
            expected_revision=expected_revision,
        )

    def apply_dedun(
        self,
        plan: DedunPlanResult,
        *,
        survivors: Mapping[str, str],
    ) -> DedunApplyResult:
        """Apply one exact complete existing-survivor mapping."""

        from memcommit.api._operations.dedup import apply_dedun

        return apply_dedun(self._runtime, plan, survivors=survivors)

    def plan_consolidation(
        self,
        handoffs: Sequence[QualityFindingHandoff],
        *,
        expected_revision: str | None = None,
    ) -> DedunPlanResult:
        """Compatibility alias for :meth:`plan_dedun`."""

        return self.plan_dedun(
            handoffs,
            expected_revision=expected_revision,
        )

    def apply_consolidation(
        self,
        plan: DedunPlanResult,
        *,
        survivors: Mapping[str, str],
    ) -> DedunApplyResult:
        """Compatibility alias for :meth:`apply_dedun`."""

        return self.apply_dedun(plan, survivors=survivors)

    def plan_dedup(
        self,
        handoffs: Sequence[QualityFindingHandoff],
        *,
        expected_revision: str | None = None,
    ) -> DedunPlanResult:
        """Compatibility alias for :meth:`plan_dedun`."""

        return self.plan_dedun(
            handoffs,
            expected_revision=expected_revision,
        )

    def apply_dedup(
        self,
        plan: DedunPlanResult,
        *,
        survivors: Mapping[str, str],
    ) -> DedunApplyResult:
        """Compatibility alias for :meth:`apply_dedun`."""

        return self.apply_dedun(plan, survivors=survivors)

    def distill_context(
        self,
        context_name: str | None = None,
        *,
        goal: str | None = None,
        include_descendants: bool = False,
        follow_embeds: bool = False,
    ) -> DistillProposal:
        """Propose evidence-bound Rules from one exact Context frame."""

        from memcommit.api._operations.distill import distill_context

        return distill_context(
            self._runtime,
            context_name,
            goal=goal,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
        )

    def distill_ground(self, ground_name: str) -> DistillProposal:
        """Distill one exact bound Ground frame without mutating the Ground."""

        from memcommit.api._operations.ground_distill import distill_ground

        return distill_ground(self._runtime, ground_name)

    def apply_distill(
        self,
        proposal: DistillProposal,
        *,
        output_name: str,
    ) -> DistillApplyResult:
        """Materialize one reviewed standalone proposal into a new Context."""

        from memcommit.api._operations.distill import apply_distill

        return apply_distill(self._runtime, proposal, output_name=output_name)

    def elaborate(
        self,
        *,
        goal: str | None = None,
        rules: Sequence[str] | None = None,
        number: int | None = None,
    ) -> ElaborateProposal:
        """Propose unverified Rules from a Goal or Cases from Rules."""

        from memcommit.api._operations.elaborate import elaborate

        return elaborate(
            self._runtime,
            goal=goal,
            rules=rules,
            number=number,
        )

    def elaborate_ground(
        self,
        ground_name: str,
        *,
        direction: str,
        number: int | None = None,
    ) -> ElaborateProposal:
        """Project one exact Ground Goal or Rule set through Elaborate."""

        from memcommit.api._operations.ground_elaborate import elaborate_ground

        return elaborate_ground(
            self._runtime,
            ground_name,
            direction=direction,
            number=number,
        )

    def start_meld(
        self,
        left_context: str,
        right_context: str,
        *,
        mode: str = "directional",
        target_context: str | None = None,
        create_target: bool = False,
        left_descendants: bool = False,
        right_descendants: bool = False,
    ) -> MeldSessionResult:
        """Create one durable reviewed Meld without opening a terminal UI."""

        from memcommit.api._operations.meld import start_meld

        return start_meld(
            self._runtime,
            left_context,
            right_context,
            mode=mode,
            target_context=target_context,
            create_target=create_target,
            left_descendants=left_descendants,
            right_descendants=right_descendants,
        )

    def restart_meld(
        self,
        left_context: str,
        right_context: str,
        target_context: str,
        *,
        expected_version: str,
        mode: str = "directional",
        left_descendants: bool = False,
        right_descendants: bool = False,
    ) -> MeldSessionResult:
        """Replace one exact saved Meld review without deleting its target."""

        from memcommit.api._operations.meld import restart_meld

        return restart_meld(
            self._runtime,
            left_context,
            right_context,
            target_context,
            expected_version=expected_version,
            mode=mode,
            left_descendants=left_descendants,
            right_descendants=right_descendants,
        )

    def open_meld(self, target_context: str) -> MeldSessionResult:
        """Open one exact saved review without provider or mutation."""

        from memcommit.api._operations.meld import open_meld

        return open_meld(self._runtime, target_context)

    def comment_meld(
        self,
        target_context: str,
        comment: str = "",
        *,
        expected_version: str,
        issue_uid: str | None = None,
        option_uid: str | None = None,
        revision: str = "EXTEND",
        revises_turn_uids: Sequence[str] = (),
    ) -> MeldSessionResult:
        """Submit one complete semantic follow-up against a saved version."""

        from memcommit.api._operations.meld import comment_meld

        return comment_meld(
            self._runtime,
            target_context,
            comment,
            expected_version=expected_version,
            issue_uid=issue_uid,
            option_uid=option_uid,
            revision=revision,
            revises_turn_uids=revises_turn_uids,
        )

    def preserve_meld(
        self,
        target_context: str,
        *,
        expected_version: str,
    ) -> MeldSessionResult:
        """Preserve every remaining distinction under the saved-session CAS."""

        from memcommit.api._operations.meld import preserve_meld

        return preserve_meld(
            self._runtime,
            target_context,
            expected_version=expected_version,
        )

    def defer_meld(
        self,
        target_context: str,
        *,
        expected_version: str,
    ) -> MeldSessionResult:
        """Close one saved review without changing its target."""

        from memcommit.api._operations.meld import defer_meld

        return defer_meld(
            self._runtime,
            target_context,
            expected_version=expected_version,
        )

    def apply_meld(
        self,
        target_context: str,
        *,
        expected_version: str,
    ) -> PublicMeldApplyResult:
        """Apply exactly one ready saved proposal without another provider turn."""

        from memcommit.api._operations.meld import apply_meld

        return apply_meld(
            self._runtime,
            target_context,
            expected_version=expected_version,
        )

    def open_atomize_grounding(
        self,
        context_name: str | None = None,
    ) -> AtomizeGroundingSessionResult:
        """Open one saved Grounding dialogue without provider access."""

        from memcommit.api._operations.atomize_grounding import (
            open_atomize_grounding,
        )

        return open_atomize_grounding(self._runtime, context_name)

    def open_atomize_analysis(
        self,
        context_name: str | None = None,
        *,
        refresh: bool = False,
        use_prepared: bool = True,
        memory_selector: str | None = None,
    ) -> AtomizeAnalysisResult:
        """Open one exact durable structural Atomize proposal."""

        from memcommit.api._operations.atomize import open_atomize_analysis

        return open_atomize_analysis(
            self._runtime,
            context_name,
            refresh=refresh,
            use_prepared=use_prepared,
            memory_selector=memory_selector,
        )

    def update_atomize_response(
        self,
        context_name: str | None = None,
        *,
        expected_version: str,
        issue_uid: str,
        option_uid: str | None,
        comment: str,
    ) -> AtomizeReviewUpdateResult:
        """Replace or clear one response in an exact saved review."""

        from memcommit.api._operations.atomize import update_atomize_response

        return update_atomize_response(
            self._runtime,
            context_name,
            expected_version=expected_version,
            issue_uid=issue_uid,
            option_uid=option_uid,
            comment=comment,
        )

    def plan_atomize_output(
        self,
        context_name: str | None = None,
        *,
        expected_version: str,
        output_context_name: str,
    ) -> AtomizeReviewUpdateResult:
        """Set one exact in-place or require-new structural Output plan."""

        from memcommit.api._operations.atomize import plan_atomize_output

        return plan_atomize_output(
            self._runtime,
            context_name,
            expected_version=expected_version,
            output_context_name=output_context_name,
        )

    def reanalyze_atomize_responses(
        self,
        context_name: str | None = None,
        *,
        expected_version: str,
    ) -> AtomizeAnalysisResult:
        """Incorporate exact saved unary responses through the provider."""

        from memcommit.api._operations.atomize import reanalyze_atomize_responses

        return reanalyze_atomize_responses(
            self._runtime,
            context_name,
            expected_version=expected_version,
        )

    def save_saved_atomize_as(
        self,
        context_name: str | None = None,
        *,
        expected_version: str,
    ) -> AtomizeSaveAsApplyResult:
        """Publish or recover one exact reviewed require-new Output."""

        from memcommit.api._operations.atomize import save_saved_atomize_as

        return save_saved_atomize_as(
            self._runtime,
            context_name,
            expected_version=expected_version,
        )

    def incorporate_and_apply_atomize(
        self,
        context_name: str | None = None,
        *,
        expected_version: str,
    ) -> AtomizeReviewedApplyResult:
        """Incorporate exact responses and immediately apply their Output plan."""

        from memcommit.api._operations.atomize import (
            incorporate_and_apply_atomize,
        )

        return incorporate_and_apply_atomize(
            self._runtime,
            context_name,
            expected_version=expected_version,
        )

    def apply_atomize_as_is(
        self,
        analysis: AtomizeAnalysisResult,
    ) -> AtomizeStructuralApplyResult:
        """Apply or recover an accepted structural proposal in place."""

        from memcommit.api._operations.atomize import apply_atomize_as_is

        return apply_atomize_as_is(self._runtime, analysis)

    def apply_saved_atomize_as_is(
        self,
        context_name: str | None = None,
        *,
        expected_version: str,
    ) -> AtomizeStructuralApplyResult:
        """Apply an exact saved structural revision without a provider turn."""

        from memcommit.api._operations.atomize import apply_saved_atomize_as_is

        return apply_saved_atomize_as_is(
            self._runtime,
            context_name,
            expected_version=expected_version,
        )

    def start_atomize_grounding(
        self,
        selector: str,
        comment: str,
        *,
        context_name: str | None = None,
    ) -> AtomizeGroundingSessionResult:
        """Start and assess one issue-scoped Grounding dialogue."""

        from memcommit.api._operations.atomize_grounding import (
            start_atomize_grounding,
        )

        return start_atomize_grounding(
            self._runtime,
            selector,
            comment,
            context_name=context_name,
        )

    def reply_atomize_grounding(
        self,
        reply: str,
        *,
        context_name: str | None = None,
        revision: str = "EXTEND",
    ) -> AtomizeGroundingSessionResult:
        """Append and assess one explicit revision to the saved dialogue."""

        from memcommit.api._operations.atomize_grounding import (
            reply_atomize_grounding,
        )

        return reply_atomize_grounding(
            self._runtime,
            reply,
            context_name=context_name,
            revision=revision,
        )

    def keep_atomize_grounding(
        self,
        context_name: str | None = None,
    ) -> AtomizeGroundingSessionResult:
        """Close one Grounding dialogue as review-only without mutation."""

        from memcommit.api._operations.atomize_grounding import (
            keep_atomize_grounding,
        )

        return keep_atomize_grounding(self._runtime, context_name)

    def apply_atomize_grounding(
        self,
        context_name: str | None = None,
    ) -> AtomizeGroundingApplyResult:
        """Apply or recover one exact ready Grounding proposal."""

        from memcommit.api._operations.atomize_grounding import (
            apply_atomize_grounding,
        )

        return apply_atomize_grounding(self._runtime, context_name)

    def add_memories(
        self,
        contents: Sequence[str],
        *,
        context_name: str | None = None,
    ) -> AddMemoriesResult:
        """Append one exact ordered batch and publish one Add checkpoint."""

        from memcommit.api._operations.add import add_memories

        return add_memories(
            self._runtime,
            contents,
            context_name=context_name,
        )

    def copy_memories(
        self,
        memory_locators: Sequence[str],
        *,
        into_context: str | None = None,
        source_context: str | None = None,
        before: str | None = None,
        after: str | None = None,
        preserve_uids: bool = False,
    ) -> CopyMemoriesReceipt:
        """Copy one ordered direct-Memory batch into an existing local Context."""

        from memcommit.api._operations.copy import copy_memories

        return copy_memories(
            self._runtime,
            memory_locators,
            into_context=into_context,
            source_context=source_context,
            before=before,
            after=after,
            preserve_uids=preserve_uids,
        )

    def move_memories(
        self,
        memory_locators: Sequence[str],
        *,
        into_context: str | None = None,
        source_context: str | None = None,
        before: str | None = None,
        after: str | None = None,
        retarget_links: bool = False,
        break_links: bool = False,
    ) -> MoveMemoriesReceipt:
        """Move one ordered direct-Memory batch as one Undoable command unit."""

        from memcommit.api._operations.move import move_memories

        return move_memories(
            self._runtime,
            memory_locators,
            into_context=into_context,
            source_context=source_context,
            before=before,
            after=after,
            retarget_links=retarget_links,
            break_links=break_links,
        )

    def reference_memory(
        self,
        memory_selector: str,
        *,
        source_context: str,
        into_context: str | None = None,
    ) -> MemoryReferenceResult:
        """Retain one immutable snapshot of a directly owned Source Memory."""

        from memcommit.api._operations.reference import reference_memory

        return reference_memory(
            self._runtime,
            memory_selector,
            source_context=source_context,
            into_context=into_context,
        )

    def reference_context(
        self,
        source_context: str,
        *,
        into_context: str | None = None,
        recursive: bool = False,
    ) -> ContextReferenceResult:
        """Retain one immutable direct or recursive Source Context snapshot."""

        from memcommit.api._operations.reference import reference_context

        return reference_context(
            self._runtime,
            source_context,
            into_context=into_context,
            recursive=recursive,
        )

    def embed_memory(
        self,
        memory_selector: str,
        *,
        source_context: str,
        into_context: str,
        before: str | None = None,
        after: str | None = None,
    ) -> EmbeddedMemoryResult:
        """Create one live link to a directly owned Source Memory."""

        from memcommit.api._operations.embed import embed_memory

        return embed_memory(
            self._runtime,
            memory_selector,
            source_context=source_context,
            into_context=into_context,
            before=before,
            after=after,
        )

    def embed_context(
        self,
        child_context: str,
        *,
        into_context: str,
        before: str | None = None,
        after: str | None = None,
    ) -> EmbeddedContextResult:
        """Create one live link to an existing Context."""

        from memcommit.api._operations.embed import embed_context

        return embed_context(
            self._runtime,
            child_context,
            into_context=into_context,
            before=before,
            after=after,
        )

    def query_ordinary(
        self,
        question: str,
        *,
        context_names: Sequence[str] | None = None,
        include_descendants: bool = False,
        follow_embeds: bool = True,
        on_stage: StageObserver | None = None,
    ) -> OrdinaryQueryResult:
        """Answer from one exact readable Context set without publishing state."""

        from memcommit.api._operations.query import query_ordinary

        return query_ordinary(
            self._runtime,
            question,
            context_names=context_names,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            on_stage=on_stage,
        )

    def query_granted(
        self,
        public_name: str,
        question: str | None = None,
        *,
        language: str = "en",
        memory_handle: str | None = None,
        federate_descendants: bool = True,
        on_stage: StageObserver | None = None,
    ) -> GrantedQueryResult:
        """Browse or answer one active-Profile QUERY grant without persistence."""

        from memcommit.api._operations.query import query_granted

        return query_granted(
            self._runtime,
            public_name,
            question,
            language=language,
            memory_handle=memory_handle,
            federate_descendants=federate_descendants,
            on_stage=on_stage,
        )

    def query_reference(
        self,
        reference: QueryContextRef,
        question: str,
        *,
        language: str = "en",
        on_stage: StageObserver | None = None,
    ) -> ReferenceQueryResult:
        """Answer through one exact legacy QueryContextRef without persistence."""

        from memcommit.api._operations.query import query_reference

        return query_reference(
            self._runtime,
            reference,
            question,
            language=language,
            on_stage=on_stage,
        )


__all__ = ["MemCommitClient"]
