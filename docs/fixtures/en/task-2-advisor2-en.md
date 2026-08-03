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

- T2-R-001 — `structure/problem` — PP — Present an unresolved interaction problem in the actual usage environment within the first three sentences of the introduction.
- T2-R-070 — `structure/problem-urgency` — PP — Present the burden this interaction problem imposes on current users or operations within the first three sentences of the introduction.
- T2-R-002 — `structure/research-question-position` — PP — Explicitly specify the users, operational stakeholders, and actual usage environment in the primary HCI research question.
- T2-R-011 — `structure/interaction-step-visual` — PP — Summarize the sequence of steps for unfamiliar interaction procedures in a single flowchart.
- T2-R-071 — `structure/interaction-transition-visual` — PP — Indicate the transition conditions between steps of unfamiliar interaction procedures in the flowchart.
- T2-R-015 — `structure/masters-timeline-phases` — PP — Present the master’s research schedule as phase-specific milestones for field understanding, system implementation, user study, and analysis.
- T2-R-072 — `structure/masters-timeline-deliverables` — PP — Link deliverables that determine entry into the next phase to each milestone of the master’s research.
- T2-R-017 — `structure/gap-contribution-link` — PP — Directly connect the gap in the actual usage context with the proposed design and operational contributions in a single flow.
- T2-R-018 — `structure/two-page-heading-ban` — PP — Do not create additional subheadings if the submission template permits only specified subheadings.
- T2-R-083 — `structure/two-page-continuous-argument` — PP — Within the specified subheadings, connect user problems, design interventions, and evaluation logic into a continuous flow.
- T2-R-024 — `structure/preliminary-result-placement` — PP — Place preliminary results from field observations or technical validations near sentences supporting feasibility claims.
- T2-R-054 — `structure/reviewer-opening-problem` — OM — HCI reviewers identify the user problem and actual usage environment in the first three sentences of the introduction to form their initial framing of the proposal.
- T2-R-080 — `structure/reviewer-opening-urgency` — OM — HCI reviewers judge the burden this problem imposes on current users or operations within the first three sentences of the introduction.
- T2-R-003 — `emphasis/contribution-count` — PP — Do not exceed two primary HCI contributions that readers must remember.
- T2-R-051 — `emphasis/contribution-naming` — PP — Present each design or operational contribution as a single named sentence.
- T2-R-013 — `emphasis/recruitment-primary-constraint` — PP — In studies recruiting organizational members, emphasize workflow constraints.
- T2-R-073 — `emphasis/recruitment-secondary-constraint` — PP — In studies recruiting organizational members, emphasize manager approval constraints.
- T2-R-026 — `emphasis/contribution-type` — PP — Present the primary HCI design contribution of the proposal as design guidelines applicable to practitioners rather than conceptual models.
- T2-R-055 — `emphasis/reviewer-contribution-capacity` — OM — HCI reviewers find it difficult to identify primary contributions when named design and operational contributions exceed two.
- T2-R-004 — `claim-evidence/evidence-adjacency` — PP — Place observational evidence or sources adjacent to claims regarding user needs or field effects.
- T2-R-005 — `claim-evidence/observation-prediction-status` — PP — Distinguish at the sentence level between facts already confirmed in the field and predictions to be examined in the user study.
- T2-R-009 — `claim-evidence/study-directionality` — PP — Express the primary research question of the proposal as an exploratory qualitative question without directional hypotheses.
- T2-R-010 — `claim-evidence/causal-language` — PP — Do not use verbs implying proof of causality if the design does not support causal inference.
- T2-R-012 — `claim-evidence/source-priority` — PP — Prioritize citations of recent systems and field research in rapidly changing HCI topics.
- T2-R-027 — `claim-evidence/design-rationale` — PP — Explain the user or operational stakeholder needs that each design choice aims to address.
- T2-R-041 — `claim-evidence/direct-evidence` — PP — Support each important conclusion with the closest evidence that directly examined it.
- T2-R-056 — `claim-evidence/reviewer-evidence-order` — OM — Reviewers first check direct evidence placed closest to important conclusions.
- T2-R-019 — `style/research-team-voice` — PP — Write repeatable user study procedures so that tasks and steps precede people.
- T2-R-020 — `style/confirmed-procedure-status` — PP — Write system behaviors confirmed in the actual usage environment as observed states.
- T2-R-052 — `style/unconfirmed-procedure-status` — PP — Write system behaviors not yet confirmed in the field as conditional plans.
- T2-R-057 — `style/reviewer-voice-interpretation` — OM — HCI reviewers easily identify repeatable user study procedures in sentences where tasks and steps precede people.
- T2-R-006 — `terminology/term-consistency` — PP — Do not change names referring to the same user roles, system functions, or operational stages midway.
- T2-R-021 — `terminology/abbreviation-eligibility` — PP — Use abbreviations only for long recurring terms in a two-page proposal.
- T2-R-082 — `terminology/abbreviation-definition` — PP — Present the full term and abbreviation together when using an abbreviation for the first time.
- T2-R-042 — `terminology/participant-role-language` — PP — Refer to participants based on the roles they perform in the study rather than their status.
- T2-R-058 — `terminology/reviewer-undefined-abbreviation` — OM — Reviewers from different subfields find it difficult to infer an abbreviation from context alone when it is not defined at first use.
- T2-R-033 — `expression/prototype-fidelity-separation` — KB — The visual fidelity of a prototype and its level of connection to actual data and services may differ.
- T2-R-081 — `expression/interaction-state-change` — KB — Service flow diagrams indicate human-system transitions that are not revealed by individual screens alone.
- T2-R-059 — `expression/reviewer-caption-scan` — OM — HCI reviewers often scan system structure and service flow diagrams before the main text.
- T2-R-007 — `methods/question-evidence-analysis` — PP — Specify field and user data sources and analysis procedures corresponding to all HCI research questions.
- T2-R-014 — `methods/primary-evaluation-setting` — PP — Design the primary evaluation of the proposal as a field deployment study in the actual usage environment.
- T2-R-074 — `methods/lab-evaluation-scope` — PP — If the primary contribution changes actual operational decisions, do not judge solely by controlled laboratory evaluations.
- T2-R-016 — `methods/preregistration-change-condition` — PP — In preregistered studies, clarify the criteria for judging plan changes.
- T2-R-075 — `methods/preregistration-change-record` — PP — In preregistered studies, clarify the location for recording plan changes.
- T2-R-022 — `methods/sample-size-form` — PP — Present the target number of participants as a single value or justified range based on grounds for recruitment feasibility.
- T2-R-028 — `methods/data-collection-tool` — PP — Specify the observation records, system logs, or interview tools used to collect each type of field and user data.
- T2-R-076 — `methods/data-collection-timing` — PP — Specify whether each type of field and user data will be collected before, during, or after deployment.
- T2-R-034 — `methods/recruitment-funnel-visibility` — SM — The agent cannot review the realism of recruitment plans without expected attrition stages from contact targets to final participants.
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
- T2-R-023 — `budget/body-detail-placement` — PP — Summarize only the correspondence between field HCI research phases and major cost categories in the main text.
- T2-R-031 — `budget/personnel-work-time` — PP — List work time by role for field deployment and user study in personnel costs.
- T2-R-079 — `budget/personnel-rate-basis` — PP — Provide the rationale for calculating unit rates by role in on-site deployment and user research within the personnel costs.
- T2-R-066 — `budget/finance-activity-trace` — OM — The finance reviewer determines budget validity by tracing how total budget and detailed costs connect to specific HCI research phases.
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
- T2-R-093 — `structure/decision-chain` — PP — Present an unbroken path from user problems to field evidence, design interventions, evaluation results, and operational decisions.
- T2-R-094 — `structure/deployment-handoff` — PP — Include in the research flow who inherits the system under what conditions after the research phase concludes.
- T2-R-095 — `structure/field-decision-argument` — KB — The logic of field deployment research connects not only to whether the design works but also to how its results support operational decisions.
- T2-R-096 — `structure/advisor-operational-owner-visibility` — SM — The agent cannot assess the sustainability of proposed interventions if the operational owner post-deployment is not visible.
- T2-R-097 — `emphasis/primary-deployment-decision` — PP — Highlight one primary field operational decision to be changed by evaluation results as the central claim.
- T2-R-098 — `emphasis/optional-feature-boundary` — PP — Specify prototype features unnecessary for reviewing the primary field problem as secondary scope.
- T2-R-099 — `emphasis/author-novelty-bias` — UM — The author of this proposal tends to prioritize novel interaction features over operational fit.
- T2-R-100 — `claim-evidence/workaround-evidence` — PP — Use field cases in which people completed tasks by working around existing tools as evidence for the need for the design.
- T2-R-101 — `claim-evidence/stakeholder-report-observation` — PP — Distinguish between problems reported by operational stakeholders and those directly observed by the researcher as separate forms of evidence.
- T2-R-102 — `claim-evidence/breakdown-log-value` — KB — Field breakdown logs can reveal both system failures and user adaptive behaviors, including their timing and conditions.
- T2-R-103 — `claim-evidence/routine-adaptation` — WM — In field sites introducing new systems, formal procedures often coexist with existing manual routines for a period, making it difficult to isolate the effects of single design changes.
- T2-R-104 — `style/field-actor-action` — PP — When describing field interactions, explicitly specify the actor, action, and target system at each step.
- T2-R-105 — `style/advisor-passive-responsibility` — SM — The agent cannot identify who is responsible for error handling in field procedures written exclusively in passive voice.
- T2-R-106 — `style/partner-provisional-language` — WM — Because operational procedures and user roles remain undefined, the mechanisms behind expected behavioral changes are provisional when conditional features have not yet been approved by field partners.
- T2-R-107 — `terminology/operational-role-authority` — PP — When introducing an operational role for the first time, define both the decisions it can make and the actions it performs.
- T2-R-108 — `terminology/title-authority-variance` — KB — Individuals holding identical job titles may possess different system modification privileges and data access rights depending on their deployment site.
- T2-R-109 — `terminology/author-user-bucket` — UM — The user writing this proposal tends to group distinct field roles under the single label “user.”
- T2-R-110 — `expression/intervention-baseline-figure` — PP — In service flow diagrams, clearly distinguish between steps modified by the design and those retained as baseline.
- T2-R-111 — `expression/walkthrough-screen-difference` — KB — While screen images display interface states, field walkthroughs reveal actual handoff processes between people and systems.
- T2-R-112 — `expression/advisor-screen-decision-gap` — SM — The agent cannot infer how operational decisions change based solely on a sequence of screen images.
- T2-R-113 — `methods/pilot-main-transition` — PP — Predefine criteria for functional stability, operational readiness, and safety conditions before transitioning from pilot to full deployment.
- T2-R-114 — `methods/shadow-deployment-fallback` — PP — If there is a risk of disrupting actual work, design shadow deployment phases that maintain existing procedures while comparing outcomes.
- T2-R-115 — `methods/time-coverage-sampling` — PP — Schedule field observations to include time periods with varying workload levels and participant compositions.
- T2-R-116 — `methods/operator-workaround-capture` — PP — Specify data collection methods for recording instances where operators bypass the system or perform manual recovery actions.
- T2-R-117 — `methods/interview-observation-complement` — KB — Interviews reveal participants’ perceived reasons, while field observations show actual procedures and workarounds performed in practice.
- T2-R-118 — `methods/author-convenience-recruitment` — UM — The user writing this proposal tends to choose participants who are easier to recruit over roles relevant to operational decisions.
- T2-R-119 — `methods/organizational-rhythm` — WM — Workload, staffing configurations, and exception-handling practices may vary by day of the week and time period within field sites.
- T2-R-120 — `evaluation/decision-threshold` — PP — Establish decision thresholds indicating at what levels key metrics trigger maintaining, modifying, or discontinuing the design.
- T2-R-121 — `evaluation/work-redistribution` — PP — Evaluate whether reducing workload for one role creates new tasks for other roles through the proposed design changes.
- T2-R-122 — `evaluation/acceptability-usability-separation` — PP — Distinguish usability from organizational adoption intent as separate evaluation outcomes.
- T2-R-123 — `evaluation/implementation-fidelity` — KB — Implementation fidelity indicates whether planned features and operational procedures were delivered in the field according to intended specifications.
- T2-R-124 — `evaluation/novelty-decay` — WM — Initial evaluations and long-term operation do not share identical measurement conditions due to differences in system exposure duration and frequency of repeated use.
- T2-R-125 — `ethics/safe-fallback` — PP — Ensure that participants can safely return to existing work procedures if they discontinue research participation.
- T2-R-126 — `ethics/refusal-nonpenalty` — PP — Specify that organizational members who decline research participation will not face disadvantages in task assignment or performance evaluation.
- T2-R-127 — `ethics/advisor-fallback-risk` — SM — The agent cannot adequately assess the risk of withdrawal without a safe alternative procedure for field tasks.
- T2-R-128 — `ethics/author-short-session-burden` — UM — The user writing this proposal tends to assume that a short session also entails little burden from work interruption and exposure to a manager.
- T2-R-129 — `scope/transfer-conditions` — PP — Specify the workflow, technical infrastructure, and operational-authority conditions that must match before applying the design guidelines at another field site.
- T2-R-130 — `scope/transfer-boundary-components` — KB — The transferability of field design knowledge depends not only on user characteristics but also on workflow and technological–organizational infrastructure.
- T2-R-131 — `scope/author-overgeneralization` — UM — The user writing this proposal tends to apply results confirmed at one deployment site to all similar organizations.
- T2-R-132 — `safety/stop-rule` — PP — Define the thresholds for participant harm, operational disruption, and data anomalies at which deployment and data collection must cease.
- T2-R-133 — `safety/restoration-plan` — PP — Establish procedures to restore existing systems and workflow states after suspending field deployment.
- T2-R-134 — `safety/advisor-recovery-authority` — SM — The agent cannot judge the feasibility of a stop plan without identifying who has authority to order recovery and who is responsible for carrying it out.
- T2-R-135 — `safety/blame-reporting` — WM — In organizations where error reporting is linked to individual performance evaluations, safety signal records may be separated from research decision logs, potentially breaking the traceability path for the same incident.
- T2-R-136 — `feasibility/partner-commitment` — PP — Document separately the commitments and confirmation status of field partners required for recruitment, installation, and operational support.
- T2-R-137 — `feasibility/maintenance-owner` — PP — Designate a responsible party for software updates, equipment inspections, and user support during the deployment period.
- T2-R-138 — `feasibility/advisor-hidden-dependencies` — SM — The agent cannot assess deployment readiness without visible dependencies on external services and field personnel.
- T2-R-139 — `feasibility/site-schedule-change` — WM — Field schedules and assigned personnel may change due to operational factors beyond the researcher’s control.
- T2-R-140 — `reproducibility/config-change-log` — PP — Record changes in system configurations, field procedures, and data collection tools during deployment, along with their timestamps and rationales.
- T2-R-141 — `reproducibility/deployment-provenance` — KB — The history of deployment versions and configuration changes provides necessary evidence for interpreting results from different field sites.
- T2-R-142 — `budget/onsite-repair-contingency` — PP — Calculate a separate contingency budget for equipment replacement, emergency travel, and technical support during deployment.
- T2-R-143 — `budget/operator-onboarding-cost` — PP — Include personnel hours and material production costs required for field operator training and initial support in the budget.
- T2-R-144 — `budget/author-postdeployment-support` — UM — The user writing this proposal tends to calculate installation costs but omit post-deployment support and maintenance costs.
- T2-R-145 — `compensation/longitudinal-reporting-burden` — PP — In longitudinal studies requiring diary entries and repeated reporting, include out-of-session recording time in compensation calculations.
- T2-R-146 — `compensation/staff-labor-separation` — PP — Distinguish between participant research compensation and labor costs for field staff performing installation and operational support as part of their duties.
- T2-R-147 — `compensation/author-unpaid-preparation` — UM — The user writing this proposal tends to count session time but omit participants’ advance setup and follow-up reporting time.
- T2-R-148 — `review/failure-mode-walkthrough` — PP — Before submission, conduct a sequential walkthrough with field liaisons of installation failures, operational interruptions, and recovery scenarios.
- T2-R-149 — `review/contribution-decision-test` — PP — Verify in one sentence how each proposed contribution could actually alter specific design or operational decisions.
- T2-R-150 — `review/advisor-placeholder-visibility` — SM — The agent cannot distinguish remaining execution risks if unconfirmed field partners and equipment are presented as finalized.
