# advisor2 Memory Candidates

> Designer-only note: The two co-advisors have equal authority. Each record
> follows the order `Fixture ID — Memory Location — Purpose — Content`.
> `Memory Location` is a relative locator in `directory/slug` form, and the
> actual Memory content is only the sentence to the right of the final em dash.
> Purpose codes are `KB`, `PP`, `SM`, `UM`, `WM`, and `OM`. `KB`
> denotes verifiable research or proposal knowledge; `PP` denotes imperative
> procedures the agent must follow; `SM` denotes this advisor's own role,
> capabilities, and review limits; `UM` denotes the current proposal author's
> expectations, preferences, familiarity, and confusion; `OM` denotes the
> expectations, preferences, and judgments of other actors such as reviewers,
> participants, and operators; and `WM` denotes constraints in institutions,
> schedules, resources, and evaluation environments that are independent of
> any person's mental state.
>
> This store contains internal advising guidance that interprets
> field-neutral submission instructions for a two-page master's research
> proposal through the writing practices of an HCI lab. Two pages is the
> document length, not a two-week research period. The external guidelines
> determine what to submit; these Memories determine how to express the user
> problem, design contribution, prototype, user study, and evaluation in HCI.
>
> The two advisors are presented in corresponding pairs from the same semantic
> categories, although atomization may give individual Memories different
> locations and counts. The relationship-band sidecar uses the order
> `pair_id`, `left_fixture_ids`, `right_fixture_ids`,
> `relationship_band`. When atomization splits one advisor's guidance across
> multiple Memories, semicolon-separated Fixture IDs are linked together in
> the same pair. This file contains exactly 150 independently reviewable
> candidates.

- T2-R-001 — `structure/problem` — PP — Allow the problem framing to extend through a third sentence when a concrete person, setting, or use situation is needed to make the issue understandable.
- T2-R-070 — `structure/three-sentence-context` — PP — Use the third sentence for the specific setting and consequence rather than compressing them into an abstract two-sentence summary.
- T2-R-002 — `structure/research-question-position` — PP — Explicitly specify the users, operational stakeholders, and actual usage environment in the primary HCI research question.
- T2-R-011 — `structure/interaction-step-visual` — PP — Provide one compact visual summary when proposing an unfamiliar interaction procedure.
- T2-R-071 — `structure/interaction-transition-visual` — PP — Mark the conditions that move an unfamiliar interaction procedure from one step to the next in its visual summary.
- T2-R-015 — `structure/masters-timeline-phases` — PP — Present the master’s research schedule as phase-specific milestones for field understanding, system implementation, user study, and analysis.
- T2-R-072 — `structure/masters-timeline-deliverables` — PP — Link deliverables that determine entry into the next phase to each milestone of the master’s research.
- T2-R-017 — `structure/gap-contribution-link` — PP — Directly connect the gap in the actual usage context with the proposed design and operational contributions in a single flow.
- T2-R-018 — `structure/continuous-two-page-flow` — PP — Avoid extra subheadings in a two-page proposal; use paragraph transitions to preserve one continuous argument from problem to proposed response and next steps.
- T2-R-083 — `structure/paragraph-transition-chain` — PP — Begin each paragraph by connecting it to the previous claim so the short proposal reads as an argument rather than a stack of labeled fragments.
- T2-R-024 — `structure/preliminary-result-placement` — PP — Place preliminary results from field observations or technical validations near sentences supporting feasibility claims.
- T2-R-054 — `structure/reviewer-three-sentence-context` — OM — Readers may misinterpret a compressed opening when the person, setting, or consequence is only implied.
- T2-R-080 — `structure/compressed-opening-generic-cost` — OM — A two-sentence opening can become so general that readers understand the topic but cannot picture the situation the proposal intends to change.
- T2-R-003 — `emphasis/contribution-count` — PP — Do not exceed two primary HCI contributions that readers must remember.
- T2-R-051 — `emphasis/contribution-naming` — PP — Present each design or operational contribution as a single named sentence.
- T2-R-013 — `emphasis/recruitment-primary-constraint` — PP — In studies recruiting organizational members, emphasize workflow constraints.
- T2-R-073 — `emphasis/recruitment-secondary-constraint` — PP — In studies recruiting organizational members, emphasize manager approval constraints.
- T2-R-026 — `style/em-dash-conditional-use` — PP — Use an em dash only for a deliberate interruption or sharp contrast; otherwise split the sentence or choose ordinary punctuation.
- T2-R-055 — `emphasis/reviewer-contribution-capacity` — OM — HCI reviewers find it difficult to identify primary contributions when named design and operational contributions exceed two.
- T2-R-004 — `claim-evidence/evidence-adjacency` — PP — Place observational evidence or sources adjacent to claims regarding user needs or field effects.
- T2-R-005 — `claim-evidence/observation-prediction-status` — PP — Distinguish at the sentence level between facts already confirmed in the field and predictions to be examined in the user study.
- T2-R-009 — `expression/sequence-table-choice` — PP — Use a sequence table rather than a flow diagram when the procedure is likely to change repeatedly during drafting.
- T2-R-010 — `claim-evidence/causal-language` — PP — Do not use verbs implying proof of causality if the design does not support causal inference.
- T2-R-012 — `claim-evidence/source-priority` — PP — Prioritize citations of recent systems and field research in rapidly changing HCI topics.
- T2-R-027 — `claim-evidence/design-rationale` — PP — Explain the user or operational stakeholder needs that each design choice aims to address.
- T2-R-041 — `claim-evidence/direct-evidence` — PP — Support each important conclusion with the closest evidence that directly examined it.
- T2-R-056 — `claim-evidence/reviewer-evidence-order` — OM — Reviewers first check direct evidence placed closest to important conclusions.
- T2-R-019 — `style/action-first-procedure` — PP — In procedural passages, begin each sentence with the action, condition, or output instead of repeating “we” so the steps remain easy to follow and reuse.
- T2-R-020 — `style/confirmed-procedure-status` — PP — Write system behaviors confirmed in the actual usage environment as observed states.
- T2-R-052 — `style/unconfirmed-procedure-status` — PP — Write system behaviors not yet confirmed in the field as conditional plans.
- T2-R-057 — `style/reviewer-action-first-sequence` — OM — Readers can reconstruct a sequence more accurately when each sentence begins with the action or condition rather than the author.
- T2-R-006 — `terminology/term-consistency` — PP — Do not change names referring to the same user roles, system functions, or operational stages midway.
- T2-R-021 — `terminology/abbreviation-eligibility` — PP — Use abbreviations only for long recurring terms in a two-page proposal.
- T2-R-082 — `terminology/abbreviation-definition` — PP — Present the full term and abbreviation together when using an abbreviation for the first time.
- T2-R-042 — `terminology/participant-role-language` — PP — Refer to participants based on the roles they perform in the study rather than their status.
- T2-R-058 — `terminology/reviewer-undefined-abbreviation` — OM — Reviewers from different subfields find it difficult to infer an abbreviation from context alone when it is not defined at first use.
- T2-R-033 — `expression/prototype-fidelity-separation` — KB — The visual fidelity of a prototype and its level of connection to actual data and services may differ.
- T2-R-081 — `expression/interaction-state-change` — KB — Service flow diagrams indicate human-system transitions that are not revealed by individual screens alone.
- T2-R-059 — `expression/reviewer-caption-scan` — OM — HCI reviewers often scan system structure and service flow diagrams before the main text.
- T2-R-007 — `methods/question-evidence-analysis` — PP — Specify field and user data sources and analysis procedures corresponding to all HCI research questions.
- T2-R-014 — `style/sentence-rhythm-rule` — PP — Do not mechanically split connected thoughts into separate short sentences when doing so destroys the intended reading rhythm.
- T2-R-074 — `style/connected-thoughts` — PP — Preserve a longer sentence when its clauses form one continuous movement that is easier to follow together than apart.
- T2-R-016 — `methods/preregistration-change-condition` — PP — In preregistered studies, clarify the criteria for judging plan changes.
- T2-R-075 — `methods/preregistration-change-record` — PP — In preregistered studies, clarify the location for recording plan changes.
- T2-R-022 — `methods/bounded-target-range` — PP — Use a justified minimum-to-maximum target range when confirmations can change, and tie the minimum and maximum to different workload and budget cases.
- T2-R-028 — `methods/data-collection-tool` — PP — Specify the observation records, system logs, or interview tools used to collect each type of field and user data.
- T2-R-076 — `methods/data-collection-timing` — PP — Specify whether each type of field and user data will be collected before, during, or after deployment.
- T2-R-034 — `methods/range-boundary-review` — OM — Readers cannot assess a target range unless both bounds have a stated consequence for schedule, workload, or cost.
- T2-R-036 — `methods/deployment-failure-observation` — WM — In field deployments, network and service instability exist as independent causes of task failure alongside design choices.
- T2-R-084 — `methods/deployment-safety-signal` — WM — If a safety signal occurs in the field system, existing institutional safety procedures take precedence over the research schedule and data collection plan.
- T2-R-060 — `methods/reviewer-answerability-trace` — OM — Reviewers judge answerability by tracing the path from each research question to its data sources and analysis procedures.
- T2-R-069 — `methods/author-feature-contribution-assumption` — UM — The user authoring this proposal tends to present implemented feature lists directly as design contributions.
- T2-R-043 — `evaluation/primary-measure` — PP — Specify a single representative measure that will drive operational decisions to maintain, modify, or discontinue the deployed design.
- T2-R-061 — `evaluation/panel-primary-measure` — OM — The HCI review panel verifies whether operational decisions can be made based on the declared primary measure.
- T2-R-008 — `ethics/burden-mitigation` — PP — Link anticipated participant burden with its mitigation strategies for each field user study task.
- T2-R-029 — `ethics/accessibility-accommodation` — PP — Specify the accommodations necessary for participants to access the field system and research tasks.
- T2-R-077 — `ethics/accommodation-delivery` — PP — Specify how accessibility accommodations will be provided in the field user study.
- T2-R-030 — `ethics/identifier-separation` — PP — Describe how personal identifiers will be separated from research data immediately upon collection.
- T2-R-037 — `ethics/equipment-loan` — PP — List equipment to be loaned when participants lack necessary gear.
- T2-R-078 — `ethics/equipment-return` — PP — Describe the procedure for returning equipment loaned to participants.
- T2-R-062 — `ethics/ethics-reviewer-mitigation` — OM — The HCI ethics reviewer verifies that anticipated burden and mitigation strategies correspond for each field user study task.
- T2-R-025 — `scope/generalization-boundary` — PP — Specify in one sentence the user population and actual usage environment to which the design knowledge applies.
- T2-R-063 — `scope/reviewer-generalization-boundary` — OM — Reviewers judge the generalization boundary of results through the specified target population and environment.
- T2-R-038 — `safety/escalation-order` — PP — List whom to notify and in what order if serious discomfort is reported during the study.
- T2-R-064 — `safety/staff-escalation-reliance` — OM — Field staff rely on the pre-defined contact sequence when serious discomfort is reported.
- T2-R-039 — `feasibility/unverified-schedule-assumption` — PP — Mark unverified schedule assumptions as such.
- T2-R-085 — `feasibility/unverified-recruitment-assumption` — PP — Mark unverified recruitment assumptions as such.
- T2-R-086 — `feasibility/unverified-technical-assumption` — PP — Mark unverified technical assumptions as such.
- T2-R-044 — `feasibility/resource-traceability` — PP — Trace back the resources required for each core prototype feature and field research procedure.
- T2-R-065 — `feasibility/operations-staff-check` — OM — Operations reviewers judge feasibility by examining the personnel required for each procedure.
- T2-R-087 — `feasibility/operations-equipment-check` — OM — Operations reviewers judge feasibility by examining the equipment required for each procedure.
- T2-R-088 — `feasibility/operations-time-check` — OM — Operations reviewers judge feasibility by examining the time required for each procedure.
- T2-R-035 — `reproducibility/software-version-assessability` — OM — HCI reviewers find it difficult to assess result reproducibility if the system version used in the field deployment is not disclosed.
- T2-R-023 — `budget/separate-table-detail` — PP — Keep the main text to the total and major categories, and place quantities, unit rates, and assumptions in one compact budget table or appendix.
- T2-R-031 — `budget/table-stable-rows` — PP — Give each cost category, quantity, unit rate, and subtotal a stable row in the separate budget table.
- T2-R-079 — `budget/table-assumption-column` — PP — Put the estimate basis in a dedicated table column so one assumption can be checked or revised without rewriting the narrative.
- T2-R-066 — `budget/reviewer-table-arithmetic` — OM — Readers can verify arithmetic and compare categories faster in a consistent table than in amounts distributed across prose.
- T2-R-046 — `compensation/base-hourly-rate` — PP — Calculate user research compensation budgets based on the estimated participation burden, combining session time with required technical and travel preparation.
- T2-R-047 — `compensation/modality-burden` — PP — Compensate participants who withdraw from the study midway for their actual participation time.
- T2-R-053 — `compensation/participation-time` — PP — Compensate for the time actually spent in sessions, regardless of the research modality.
- T2-R-048 — `compensation/payment-method` — PP — Allow the issuance of gift cards of equivalent value to participants in remote studies who cannot use electronic transfers.
- T2-R-049 — `compensation/payment-method-finality` — PP — Do not treat an unresolved payment method as a deficiency at the proposal stage.
- T2-R-050 — `compensation/modality-rate` — PP — Allow differential compensation amounts for on-site and remote studies when participation burden varies due to travel or technical preparation.
- T2-R-067 — `compensation/participant-fairness` — OM — Participants judge the fairness of compensation based on the combined burden of session time and required technical and travel preparation.
- T2-R-032 — `review/substantive-pass` — PP — Conduct one review prior to submission focusing solely on the validity of user problems, system interventions, and field evaluation logic.
- T2-R-040 — `review/question-prototype-consistency` — PP — Cross-check whether research questions align with the core functions of the system.
- T2-R-089 — `review/task-measure-consistency` — PP — Cross-check whether field tasks align with representative measures.
- T2-R-090 — `review/evidence-decision-consistency` — PP — Cross-check whether the evidence to be collected aligns with the design and operational decisions to be changed.
- T2-R-045 — `review/logic-consistency` — PP — Finally verify that the user problem, system intervention, field evaluation, and expected contribution form one coherent logical flow.
- T2-R-068 — `review/reviewer-question-prototype-confidence` — OM — HCI reviewers view the validity of design interventions as low if research questions do not connect to system functions.
- T2-R-091 — `review/reviewer-task-measure-confidence` — OM — HCI reviewers view the validity of evaluation plans as low if field tasks fail to generate representative measures.
- T2-R-092 — `review/reviewer-evidence-decision-confidence` — OM — HCI reviewers view the practical utility of contributions as low if collected evidence cannot change design or operational decisions.
- T2-R-093 — `structure/continuous-flow-space-benefit` — PP — Use paragraph transitions instead of extra headings when the repeated labels would consume space needed for the argument itself.
- T2-R-094 — `structure/continuous-flow-bridge` — PP — End each paragraph with the question or consequence that the next paragraph answers.
- T2-R-095 — `structure/continuous-flow-causal-thread` — KB — A continuous sequence of problem, consequence, response, and next step makes the relationship among claims audible without repeating section labels.
- T2-R-096 — `structure/reader-fragmentation-observation` — OM — Readers may experience very short headed sections as an outline because each new label interrupts the connection to the previous paragraph.
- T2-R-097 — `emphasis/primary-deployment-decision` — PP — Highlight one primary field operational decision to be changed by evaluation results as the central claim.
- T2-R-098 — `emphasis/optional-feature-boundary` — PP — Specify prototype features unnecessary for reviewing the primary field problem as secondary scope.
- T2-R-099 — `style/author-sentence-rhythm-preference` — UM — The user understands that short sentences are easier to scan but feels that uniformly segmented prose loses its reading rhythm.
- T2-R-100 — `claim-evidence/workaround-evidence` — PP — Use field cases in which people completed tasks by working around existing tools as evidence for the need for the design.
- T2-R-101 — `claim-evidence/stakeholder-report-observation` — PP — Distinguish between problems reported by operational stakeholders and those directly observed by the researcher as separate forms of evidence.
- T2-R-102 — `claim-evidence/breakdown-log-value` — KB — Field breakdown logs can reveal both system failures and user adaptive behaviors, including their timing and conditions.
- T2-R-103 — `claim-evidence/routine-adaptation` — WM — In field sites introducing new systems, formal procedures often coexist with existing manual routines for a period, making it difficult to isolate the effects of single design changes.
- T2-R-104 — `style/action-first-checklist` — PP — Write procedural sentences so their opening phrase can be reused as a checklist item without changing the step's meaning.
- T2-R-105 — `style/first-person-pronoun-consistency` — PP — The user should choose “I” as an individual author or “we” for a named team and should not mix them when describing the same responsible party.
- T2-R-106 — `style/action-first-reuse` — WM — Action-first procedural sentences can be reordered or copied into a checklist more easily because their subject is the step rather than the proposal author.
- T2-R-107 — `terminology/operational-role-authority` — PP — When introducing an operational role for the first time, define both the decisions it can make and the actions it performs.
- T2-R-108 — `terminology/title-authority-variance` — KB — Individuals holding identical job titles may possess different system modification privileges and data access rights depending on their deployment site.
- T2-R-109 — `terminology/author-user-bucket` — UM — The user tends to group distinct field roles under the single label “user.”
- T2-R-110 — `expression/sequence-table-stable-rows` — PP — Give each step, actor, condition, and outcome a stable row in the sequence table.
- T2-R-111 — `expression/sequence-table-update-cost` — KB — Updating one row in a sequence table is usually faster than redrawing a branching diagram after a procedural change.
- T2-R-112 — `expression/reader-table-overview-limit` — OM — Readers can check sequence tables step by step but may find the overall branching shape less immediate.
- T2-R-113 — `methods/range-minimum-case` — PP — Define what can still be completed at the minimum target instead of treating every number inside the range as operationally identical.
- T2-R-114 — `methods/range-change-absorption` — PP — Use a bounded range to absorb expected confirmation changes without pretending that one early estimate is guaranteed.
- T2-R-115 — `methods/range-schedule-cases` — PP — Show how session count and facilitator time change at the minimum and maximum bounds.
- T2-R-116 — `methods/range-maximum-case` — PP — Define the additional workload or deliverable enabled at the maximum target so the upper bound is not an arbitrary cushion.
- T2-R-117 — `methods/range-budget-tradeoff` — KB — A bounded range preserves uncertainty honestly but makes the final workload and budget less certain than one fixed target.
- T2-R-118 — `style/author-em-dash-confidence` — UM — The user can explain whether an em dash marks an intentional interruption or contrast rather than using it decoratively.
- T2-R-119 — `style/em-dash-rhetorical-function` — WM — An em dash creates a stronger interruption than a comma and can make a deliberate contrast easier to hear in the sentence.
- T2-R-120 — `evaluation/decision-threshold` — PP — Establish decision thresholds indicating at what levels key metrics trigger maintaining, modifying, or discontinuing the design.
- T2-R-121 — `evaluation/work-redistribution` — PP — Evaluate whether reducing workload for one role creates new tasks for other roles through the proposed design changes.
- T2-R-122 — `evaluation/acceptability-usability-separation` — PP — Distinguish usability from organizational adoption intent as separate evaluation outcomes.
- T2-R-123 — `evaluation/implementation-fidelity` — KB — Implementation fidelity indicates whether planned features and operational procedures were delivered in the field according to intended specifications.
- T2-R-124 — `evaluation/novelty-decay` — WM — Initial evaluations and long-term operation do not share identical measurement conditions due to differences in system exposure duration and frequency of repeated use.
- T2-R-125 — `ethics/safe-fallback` — PP — Ensure that participants can safely return to existing work procedures if they discontinue research participation.
- T2-R-126 — `ethics/refusal-nonpenalty` — PP — Specify that organizational members who decline research participation will not face disadvantages in task assignment or performance evaluation.
- T2-R-127 — `ethics/advisor-fallback-risk` — SM — The user's withdrawal risk can be adequately assessed only when a safe alternative procedure exists for field tasks.
- T2-R-128 — `ethics/author-short-session-burden` — UM — The user tends to assume that a short session also entails little burden from work interruption and exposure to a manager.
- T2-R-129 — `scope/transfer-conditions` — PP — Specify the workflow, technical infrastructure, and operational-authority conditions that must match before applying the design guidelines at another field site.
- T2-R-130 — `scope/transfer-boundary-components` — KB — The transferability of field design knowledge depends not only on user characteristics but also on workflow and technological–organizational infrastructure.
- T2-R-131 — `scope/author-overgeneralization` — UM — The user tends to apply results confirmed at one deployment site to all similar organizations.
- T2-R-132 — `safety/stop-rule` — PP — Define the thresholds for participant harm, operational disruption, and data anomalies at which deployment and data collection must cease.
- T2-R-133 — `safety/restoration-plan` — PP — Establish procedures to restore existing systems and workflow states after suspending field deployment.
- T2-R-134 — `safety/advisor-recovery-authority` — SM — The user's stop plan can be judged feasible only when it identifies who has authority to order recovery and who is responsible for carrying it out.
- T2-R-135 — `safety/blame-reporting` — WM — In organizations where error reporting is linked to individual performance evaluations, safety signal records may be separated from research decision logs, potentially breaking the traceability path for the same incident.
- T2-R-136 — `feasibility/partner-commitment` — PP — Document separately the commitments and confirmation status of field partners required for recruitment, installation, and operational support.
- T2-R-137 — `feasibility/maintenance-owner` — PP — Designate a responsible party for software updates, equipment inspections, and user support during the deployment period.
- T2-R-138 — `feasibility/advisor-hidden-dependencies` — SM — The user's deployment readiness can be assessed only when dependencies on external services and field personnel are visible.
- T2-R-139 — `feasibility/site-schedule-change` — WM — Field schedules and assigned personnel may change due to operational factors beyond the researcher’s control.
- T2-R-140 — `reproducibility/config-change-log` — PP — Record changes in system configurations, field procedures, and data collection tools during deployment, along with their timestamps and rationales.
- T2-R-141 — `reproducibility/deployment-provenance` — KB — The history of deployment versions and configuration changes provides necessary evidence for interpreting results from different field sites.
- T2-R-142 — `budget/table-update-cost` — PP — Revise one table row and its subtotal when an estimate changes instead of repeating the new amount across several prose paragraphs.
- T2-R-143 — `budget/table-reading-boundary` — PP — Keep detailed arithmetic out of the main argument when readers can reach the complete table from a clear reference.
- T2-R-144 — `budget/author-prose-enumeration-tendency` — UM — The user tends to interrupt the argument with long cost enumerations when no separate budget table is available.
- T2-R-145 — `compensation/longitudinal-reporting-burden` — PP — In longitudinal studies requiring diary entries and repeated reporting, include out-of-session recording time in compensation calculations.
- T2-R-146 — `compensation/staff-labor-separation` — PP — Distinguish between participant research compensation and labor costs for field staff performing installation and operational support as part of their duties.
- T2-R-147 — `compensation/author-unpaid-preparation` — UM — The user tends to count session time but omit participants’ advance setup and follow-up reporting time.
- T2-R-148 — `review/failure-mode-walkthrough` — PP — Before submission, conduct a sequential walkthrough with field liaisons of installation failures, operational interruptions, and recovery scenarios.
- T2-R-149 — `review/contribution-decision-test` — PP — Verify in one sentence how each proposed contribution could actually alter specific design or operational decisions.
- T2-R-150 — `review/advisor-placeholder-visibility` — SM — The user must distinguish unconfirmed field partners and equipment from finalized ones so remaining execution risks can be assessed.
