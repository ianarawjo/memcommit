# Mem Help Content Review

Status: working draft, 2026-08-15

This document freezes the current review copy before it is promoted into the
runtime Help catalog. It contains the same 58 operations in two separate
tables: English first and Korean second.

Field provenance:

- Flow and Explanation started from the current English Help catalog wording;
  reviewed rows may contain proposed replacements until they are promoted.
- LLM is projected from the current execution classification.
- Boundary is a review draft synthesized from the current effect and range.
- Best For is a required runtime Help field; wording that has not been
  individually reviewed remains a review draft in the canonical catalog.
- The Korean table translates the corresponding English review row; it is not
  a separate behavioral specification.

Review invariant: revise the English row first, then keep the Korean row
semantically aligned. Approved wording should be moved into the canonical Help
catalog rather than parsed from this document.

## English review table

| Category | Name | LLM | Flow | Explanation | Boundary | Best For |
|---|---|---|---|---|---|---|
| Contexts | status | NO | Current Context → status report | Show current Context counts, recent Memories, and checkpoints. | Read-only; limited to the current exact Context. | Quickly checking the state and recent activity of the current Context. |
| Contexts | pwd | NO | Current Context pointer → canonical name | Print the current canonical Context name without loading its contents. | Reads only the pointer; Context content is not loaded. | Confirming the active Context in a script or terminal. |
| Contexts | contexts | NO | Profile access → readable Context catalog | Browse local Contexts and readable cross-Profile Context views without switching. | Read-only; includes all readable names and does not switch Context. | Exploring every Context currently available to the Profile. |
| Contexts | list | NO | Context → Context and direct-item listing | Browse child Contexts and direct items; ls is the equivalent compact spelling. | Read-only; covers one exact Context or its lexical descendants. | Inspecting the structure and direct contents of a Context. |
| Contexts | show | NO | Context or direct item → rendered content | Show a Memory, reference, embedded Context, or the direct contents of a current/explicit Context. | Read-only; accepts one exact Context or one direct item. | Reading the complete content of a known item or Context. |
| Contexts | switch | NO | Context locator → current Context pointer | Enter the interactive Context picker, or switch to an explicit Context. | Changes only the current pointer; the destination must already exist. | Moving the working position to another existing Context. |
| Contexts | checkout | NO | Context locator → current Context or new branch | Switch Contexts using Git-style syntax; with -b, create and switch to a new Context branch. | Switches Context; -b additionally creates a branch. | Using a Git-like workflow to switch or create a branch. |
| Contexts | init | NO | New Context name → Context | Create a named Context, optionally ensure its parents, and switch to it. | Requires a fresh exact name; may create lexical parents. | Starting a new empty Context hierarchy. |
| Contexts | branch | NO | Context → new Context branch | Copy a Context or subtree into a new branch and switch to it. | Creates a copied Context or subtree and changes the current pointer. | Experimenting without modifying the original Context tree. |
| Contexts | import | NO | External resource → local owned copy | Import a clean-baseline Profile, Context tree, or Memory by value while preserving resource identity. | Creates or changes local owned resources; does not retain external ownership. | Bringing externally supplied material into a locally managed store. |
| Contexts | embed | NO | Child Context → parent Context placement | Place a Child Context inside a target while retaining its identity and ownership. | Changes target structure; Child identity and ownership remain intact. | Reusing a Context inside another Context without copying it. |
| Memories | add | NO | Text or file → Context Memories | Add one or more Memories to the current or explicit Context. | Changes one exact target Context. | Saving new facts, instructions, or source material. |
| Memories | reference | NO | Source Memory → Target Context reference | Add a read-only Memory pointer; the Target stores identity metadata rather than copying content. | Adds metadata only; the Source must be one direct Memory. | Reusing a Memory while keeping one authoritative copy. |
| Memories | edit | NO | Memory → replacement Memory content | Replace direct Memory content by UID or prefix in the current or explicit Context. | Changes exactly one direct Memory. | Correcting or revising a known Memory in place. |
| Memories | chunk | NO | Memory → ordered Memory chunks | Preview and split one direct Memory by headers, paragraphs, or sentences. | Changes the Source Context only after confirmation. | Mechanically splitting a long Memory at structural boundaries. |
| Memories | forget | YES · CACHE OR PROVIDER | Context + instruction → reviewed curation batch | Review keep/edit/delete decisions for one instruction, then apply the accepted batch. | Evaluates one complete direct Source frame; Source changes only after acceptance. | Removing or transforming material according to a semantic criterion. |
| Memories | delete | NO | Context or direct item → removed | Select a Context or direct item to delete, or name it by locator, name, or UID. | Destructive; removes one exact Context or direct item after confirmation. | Removing a specific Context or item that is no longer needed. |
| Memories | clear | NO | Context direct items → empty Context | Remove all direct items from the current or explicit Context after confirmation. | Destructive; affects all direct items in one exact Context. | Emptying a Context while retaining the Context itself. |
| Search & Explain | find | YES · CACHE OR PROVIDER | Context set + query → ranked Memories | Search selected Contexts with explicit lexical-descendant and embedded-Context reach. | Read-only; lexical and embedded reach are controlled independently. | Finding relevant Memories across a selected Context scope. |
| Search & Explain | query | YES · CACHE OR PROVIDER | Readable source + question → answer with references | Ask readable Context knowledge or an authorized concealed query-only view. | Does not change Context content; a visible transcript may be retained. | Getting a cited answer from readable or query-authorized knowledge. |
| Search & Explain | summarize | YES · CACHE OR PROVIDER | Context → summary | Show what Mem understands from a Context's visible ordinary Memories. | Read-only; may use the exact Context or descendants and embedded Contexts. | Obtaining a concise overview of a Context or subtree. |
| Search & Explain | trace | NO | Memory → retained lineage | Trace one retained Memory through its recorded lineage. | Read-only; requires one current or historical Memory. | Determining where a Memory came from and how it changed. |
| Search & Explain | rationale | DEPENDS ON FORM | Memory provenance → rationale | Explain one Memory from recorded provenance and, when needed, inference. | Read-only; inference is used only when recorded provenance is insufficient. | Understanding why a Memory exists or reached its current form. |
| Search & Explain | find-duplicates | YES · CACHE OR PROVIDER | Context Memories → duplicate report | Report duplicate direct Memories in the current or explicit Context; no Context changes. | Analyzes one exact direct Context and does not modify it. | Locating semantically redundant Memories before cleanup. |
| Search & Explain | find-ambiguities | YES · CACHE OR PROVIDER | Context Memories → ambiguity report | Report ambiguous direct Memories in the current or explicit Context; no Context changes. | Analyzes one exact direct Context and does not modify it. | Finding Memories that permit unclear or multiple interpretations. |
| Search & Explain | find-conflicts | YES · CACHE OR PROVIDER | Context Memories → conflict report | Report conflicting direct Memory pairs in the current or explicit Context; no Context changes. | Analyzes one exact direct Context and does not modify it. | Finding mutually incompatible claims or instructions. |
| Analyze & Transform | audit | YES · CACHE OR PROVIDER | Context → saved quality report | Run Duplicate, Ambiguity, and Conflict checks and review one saved report. | Read-only analysis of one exact direct Context. | Performing a combined quality review before revising a Context. |
| Analyze & Transform | atomize | YES · CACHE OR PROVIDER | Context Memories → reviewed atomic Memories | Split composite Memories for review; --evaluate performs an issue-scoped directional meld. | Material changes occur only after explicit acceptance. | Separating a composite Memory into independently reviewable requirements. |
| Analyze & Transform | distill | YES · EXACT PREPARED OR PROVIDER | Case/Example Context + Goal? → reviewed Rules | Derive reusable Rules from Case or Example propositions in a selected Context scope, using an optional Goal to focus relevance. | Source and Ground stay unchanged; standalone Apply may create a new Result. | Extracting reusable rules from evidence-rich source material. |
| Analyze & Transform | elaborate | YES · EXACT PREPARED OR PROVIDER | Goal → suggested Rules; Rules → suggested Case propositions | Propose candidate Rules from a Goal, or concrete Case propositions from existing Rules. | Read-only; every proposal remains suggested and unverified. | An abstract Goal needs starter Rule candidates, or existing Rules need additional concrete Case propositions for review. |
| Analyze & Transform | compare | YES · CACHE OR PROVIDER | Context ↔ Context → comparison report | Compare Memories in two Contexts and report what they share, what differs, and what appears only on one side. | Neither Context changes or serves as the authority; each may be exact or include readable descendants. | Comparing two Contexts as a whole to understand where they align and differ. |
| Analyze & Transform | impact | DEPENDS ON FORM | Operation inputs or session → impact report | Preview or inspect operation Impact; no Context changes occur before its reviewed Apply handoff. | Impact is read-only; applying remains a separate reviewed action. | Checking expected consequences before accepting a transformation. |
| Analyze & Transform | review | DEPENDS ON FORM | Saved analysis → review responses | Enter an interactive Review session or stage semantic review responses; never apply Memories. | Records review responses but never materializes Memory changes. | Resolving issues in a saved analysis before a later Apply. |
| Analyze & Transform | meld | YES · CACHE OR PROVIDER | PEER A + PEER B → RESULT; INCOMING → BASELINE | Combine two Contexts and resolve their differences, either into a separate Result or into one authoritative Baseline. | Symmetric mode requires a distinct empty Result; directional mode changes only the Baseline after reviewed Apply. | Combining independently edited Contexts into one shared version, or incorporating proposed changes into the current baseline. |
| Analyze & Transform | update | YES · CACHE OR PROVIDER | Source Context → Target Context | Update Memories in the Target Context from Memories in the Source Context, asking the user to review and choose when needed. | Only the local Target changes after Apply. | Updating an existing Context using newly verified Memories. |
| Analyze & Transform | sever | YES · CACHE OR PROVIDER | Source Context + Criteria Context → new Result Context | Review Source against Criteria and create a derived Result while leaving Source unchanged. | Creates a new reviewed Result; Source remains unchanged. | Selecting or transforming part of a Source according to reusable criteria. |
| Analyze & Transform | translate | YES · CACHE OR PROVIDER | Context or Memory → translated view or materialization | Show and save a reusable translation view; materialize it only through an explicit route. | Source remains unchanged; materialization requires an explicit action. | Translating material while preserving the original source. |
| Analyze & Transform | merge | NO | A · Source Context → B · current Target Context | Perform an identity-aware structural merge: add Source-only items, skip unchanged shared items, and review content, type, reference, or placement collisions; recursive mode aligns descendant Context paths. | This is not a three-way or semantic merge. Every collision requires an explicit deterministic Source/Target decision; Merge never synthesizes custom content or removes Target-only items. | Returning branch additions while explicitly resolving stored-identity collisions before changing the current Context. |
| History & Recovery | log | DEPENDS ON FORM | Recorded history or query → history report | Browse Context checkpoints, inspect one Memory lineage with --memory, search history, or list Profile command attempts. | Read-only; scope depends on the selected history form. | Investigating previous operations, checkpoints, or Memory history. |
| History & Recovery | diff | NO | Recorded change → diff report | Inspect recorded Context or Update changes without applying them. | Read-only; compares one exact Context history or active Update. | Verifying exactly what a recorded operation changed. |
| History & Recovery | checkpoint | NO | Context state → checkpoint | Save the current Context as a manual recovery point for Diff or Revert. | Adds history metadata without changing Context content. | Creating a recovery point before risky work. |
| History & Recovery | undo | NO | Command history → reversed Context effects | Undo the most recent recorded Context command across its affected Contexts. | Changes every Context affected by the selected command. | Reversing the latest recorded mutation as one operation. |
| History & Recovery | redo | NO | Undo history → restored command effects | Redo the most recently undone recorded Context command. | Restores the affected Context set from the most recent Undo. | Reapplying a command that was undone accidentally. |
| History & Recovery | revert | DEPENDS ON FORM | Checkpoint → restored Context state | Select a checkpoint and review restoration of one local Context. | Changes one exact local Context after restoration review. | Restoring a Context to a deliberately saved recovery point. |
| Ground & Evaluation | ground | YES · CACHE OR PROVIDER | Dialogue + evidence → reviewed Ground | Create or continue a reviewed Goal-Rules-Memories Ground workbench. | Changes Ground records; Context changes require separate commands. | Building a reviewed evaluation or behavior contract from evidence. |
| Ground & Evaluation | fit | YES · CACHE OR PROVIDER | Ground Rules + Examples → revision-bound Fit receipt | Fit every active Ground Example against its active Rules and save an immutable receipt. | Read-only Ground judgment; saves only a derived receipt. | Re-evaluating active Ground Examples after its Rules or Cases change. |
| Ground & Evaluation | check-conformance | YES · CACHE OR PROVIDER | Rules + Ground Memories or Context → Conformance report | Check Ground examples or one Context against explicit Rules. | Read-only; no Rule, Ground, Context, or Memory changes. | Checking a Context or saved Ground against explicit Rules. |
| Ground & Evaluation | init-study | NO | Study baseline → isolated Study Profiles | Copy one Study baseline into an isolated participant/authority Profile pair. | Creates isolated Profile stores and switches the active Profile. | Preparing a reproducible, isolated user-study environment. |
| Ground & Evaluation | eval | DEPENDS ON FORM | Evaluation fixtures → campaign results | Run and inspect staged semantic evaluation campaigns. | Changes evaluation ledgers, not Context content. | Measuring operation behavior against repeatable fixtures. |
| Profile & Sharing | profile | NO | Profile registry ↔ Profile administration | Enter the interactive Profile selector, or manage complete local MemoryStore Profiles. | May switch, create, import, rename, or remove entire Profiles. | Managing separate users, environments, or Memory stores. |
| Profile & Sharing | rename | NO | Managed Profile name → new Profile name | Rename the current or an explicit managed Profile without moving or rewriting its store; mem profile rename is the explicit equivalent. | Changes registry metadata only; store contents remain in place. | Giving an existing managed Profile a clearer name. |
| Profile & Sharing | share | NO | Owned Context → receiver endpoint | Send one ordinary Context through a grant-backed receiver endpoint. | External delivery of one exact ordinary Context; Source remains unchanged. | Delivering an owned Context to an authorized receiver. |
| Profile & Sharing | lock | NO | Resource → write-protected resource | Lock the current Context, a recursive Context set, Memory, or Profile. | Changes protection metadata for an exact resource or recursive Context set. | Preventing accidental modification of stable material. |
| Profile & Sharing | unlock | NO | Protected resource → writable resource | Unlock the current Context, a recursive set, Memory, or Profile. | Removes protection metadata from the selected resource scope. | Reopening protected material for intentional revision. |
| System | help | NO | Operation catalog → usage guidance | Enter the interactive command browser and open syntax help. | Read-only; does not execute the selected operation. | Discovering available operations and their invocation forms. |
| System | provider | NO | Provider configuration ↔ status or probe | Select and verify Codex, Ollama, or OpenRouter semantic execution. | May change configuration or send an explicit probe request. | Selecting and validating the semantic execution backend. |
| System | shell-init | NO | Shell name → integration script | Print opt-in shell integration for interactive command prefill. | Read-only output; installation requires explicit shell evaluation. | Enabling optional shell-specific conveniences. |
| System | config | NO | Configuration key ↔ value | Read and write global configuration. | May change global settings; does not directly modify Context content. | Inspecting or changing persistent MemCommit settings. |

## Korean review table

| 범주 | 이름 | LLM | 흐름 | 설명 | 경계 | 적합한 상황 |
|---|---|---|---|---|---|---|
| Context | status | 없음 | 현재 Context → 상태 보고서 | 현재 Context의 개수, 최근 Memory 및 checkpoint를 보여줍니다. | 읽기 전용이며 현재의 정확한 Context만 다룹니다. | 현재 Context의 상태와 최근 활동을 빠르게 확인할 때. |
| Context | pwd | 없음 | 현재 Context 포인터 → 정규 이름 | 내용을 불러오지 않고 현재 Context의 정규 이름을 출력합니다. | 포인터만 읽으며 Context 내용은 불러오지 않습니다. | 스크립트나 터미널에서 현재 Context를 확인할 때. |
| Context | contexts | 없음 | Profile 접근 권한 → 읽을 수 있는 Context 목록 | 전환하지 않고 로컬 Context와 다른 Profile에서 읽을 수 있는 Context를 탐색합니다. | 읽기 전용이며 현재 Context를 변경하지 않습니다. | 현재 Profile에서 접근 가능한 모든 Context를 살펴볼 때. |
| Context | list | 없음 | Context → 하위 Context 및 직접 항목 목록 | 하위 Context와 직접 항목을 탐색합니다. ls는 동일한 축약형입니다. | 읽기 전용이며 정확한 Context 하나 또는 그 하위 범위를 다룹니다. | Context의 구조와 직접 포함된 항목을 확인할 때. |
| Context | show | 없음 | Context 또는 직접 항목 → 렌더링된 내용 | Memory, reference, embedded Context 또는 Context의 직접 내용을 보여줍니다. | 정확한 Context 하나 또는 직접 항목 하나를 읽기만 합니다. | 알고 있는 항목이나 Context의 전체 내용을 읽을 때. |
| Context | switch | 없음 | Context locator → 현재 Context 포인터 | Context picker를 열거나 명시한 Context로 전환합니다. | 기존 Context로 현재 포인터만 변경합니다. | 작업 위치를 다른 기존 Context로 옮길 때. |
| Context | checkout | 없음 | Context locator → 현재 Context 또는 새 branch | Git과 유사한 문법으로 Context를 전환하며 -b 사용 시 branch를 만들고 전환합니다. | Context를 전환하며 -b는 새 branch도 생성합니다. | Git과 비슷한 방식으로 전환하거나 branch를 만들 때. |
| Context | init | 없음 | 새 Context 이름 → Context | 이름이 지정된 Context를 만들고 필요하면 상위 Context도 보장한 뒤 전환합니다. | 새로운 정확한 이름이 필요하며 상위 경로를 만들 수 있습니다. | 새로운 빈 Context 계층을 시작할 때. |
| Context | branch | 없음 | Context → 새 Context branch | Context 또는 subtree를 새 branch로 복사하고 그곳으로 전환합니다. | 복사본을 만들고 현재 Context도 변경합니다. | 원본을 수정하지 않고 실험할 때. |
| Context | import | 없음 | 외부 리소스 → 로컬 소유 복사본 | Profile, Context tree 또는 Memory를 identity를 보존하며 값으로 가져옵니다. | 로컬 소유 리소스를 생성하거나 변경합니다. | 외부 자료를 로컬에서 관리할 수 있는 형태로 가져올 때. |
| Context | embed | 없음 | Child Context → Parent Context 배치 | Child Context의 identity와 ownership을 유지한 채 Target 안에 배치합니다. | Target 구조만 변경되며 Child의 identity와 ownership은 유지됩니다. | Context를 복사하지 않고 다른 Context 안에서 재사용할 때. |
| Memory | add | 없음 | 텍스트 또는 파일 → Context Memory | 현재 또는 명시한 Context에 하나 이상의 Memory를 추가합니다. | 정확한 Target Context 하나를 변경합니다. | 새로운 사실, 지침 또는 원본 자료를 저장할 때. |
| Memory | reference | 없음 | Source Memory → Target Context reference | 내용을 복사하지 않고 identity metadata를 보관하는 읽기 전용 포인터를 추가합니다. | 직접 Source Memory 하나에 대한 metadata만 추가합니다. | 하나의 원본 Memory를 여러 Context에서 재사용할 때. |
| Memory | edit | 없음 | Memory → 대체 Memory 내용 | UID 또는 prefix로 지정한 직접 Memory의 내용을 교체합니다. | 직접 Memory 하나만 변경합니다. | 알려진 Memory를 그 자리에서 수정할 때. |
| Memory | chunk | 없음 | Memory → 순서가 있는 Memory 조각 | 직접 Memory 하나를 제목, 문단 또는 문장 기준으로 미리 보고 나눕니다. | 확인 후 Source Context를 변경합니다. | 긴 Memory를 구조적인 경계에 따라 기계적으로 나눌 때. |
| Memory | forget | 있음 · 캐시 또는 Provider | Context + 지시 → 검토 가능한 선별 batch | 하나의 지시에 대한 유지·편집·삭제 결정을 검토하고 승인한 batch를 적용합니다. | 완전한 직접 Source frame을 한 번에 평가하며 승인 후에만 Source가 변경됩니다. | 의미 기준에 따라 자료를 제거하거나 변환할 때. |
| Memory | delete | 없음 | Context 또는 직접 항목 → 제거 | Context나 직접 항목을 선택하거나 locator, 이름 또는 UID로 지정해 삭제합니다. | 파괴적 작업이며 확인 후 정확한 항목 하나를 제거합니다. | 더 이상 필요하지 않은 특정 Context나 항목을 제거할 때. |
| Memory | clear | 없음 | Context 직접 항목 → 빈 Context | 확인 후 현재 또는 명시한 Context의 모든 직접 항목을 제거합니다. | Context 자체는 유지하지만 모든 직접 항목을 제거합니다. | Context는 남겨두고 그 안의 직접 내용만 비울 때. |
| 검색 및 설명 | find | 있음 · 캐시 또는 Provider | Context 집합 + query → 순위가 매겨진 Memory | 선택한 Context에서 lexical descendant와 embedded Context 범위를 명시적으로 지정해 검색합니다. | 읽기 전용이며 lexical 범위와 embedded 범위는 독립적입니다. | 선택한 Context 범위에서 관련 Memory를 찾을 때. |
| 검색 및 설명 | query | 있음 · 캐시 또는 Provider | 읽을 수 있는 Source + 질문 → reference가 포함된 답변 | 읽을 수 있는 Context 지식이나 승인된 query-only view에 질문합니다. | Context 내용은 변경하지 않으며 보이는 대화 기록은 유지될 수 있습니다. | 읽을 수 있거나 질의 권한이 있는 지식에서 근거 있는 답을 받을 때. |
| 검색 및 설명 | summarize | 있음 · 캐시 또는 Provider | Context → 요약 | Context에서 보이는 일반 Memory를 Mem이 어떻게 이해하는지 보여줍니다. | 읽기 전용이며 현재 Context, 하위 Context 및 embedded Context 범위를 사용할 수 있습니다. | Context나 subtree의 간결한 개요를 얻을 때. |
| 검색 및 설명 | trace | 없음 | Memory → 보존된 lineage | 기록된 lineage를 따라 현재 또는 과거의 Memory 하나를 추적합니다. | 읽기 전용이며 Memory 하나만 다룹니다. | Memory의 출처와 변경 과정을 확인할 때. |
| 검색 및 설명 | rationale | 형식에 따라 다름 | Memory provenance → 근거 설명 | 기록된 provenance와 필요한 경우 추론을 사용해 Memory 하나를 설명합니다. | 읽기 전용이며 기록만으로 부족할 때만 추론합니다. | Memory가 존재하거나 현재 형태가 된 이유를 이해할 때. |
| 검색 및 설명 | find-duplicates | 있음 · 캐시 또는 Provider | Context Memory → 중복 보고서 | 현재 또는 명시한 Context의 직접 Memory 중 중복을 보고합니다. | 정확한 직접 Context 하나를 분석하며 내용을 변경하지 않습니다. | 정리 전에 의미상 중복된 Memory를 찾을 때. |
| 검색 및 설명 | find-ambiguities | 있음 · 캐시 또는 Provider | Context Memory → 모호성 보고서 | 현재 또는 명시한 Context에서 모호한 직접 Memory를 보고합니다. | 정확한 직접 Context 하나를 분석하며 내용을 변경하지 않습니다. | 여러 해석이 가능한 불명확한 Memory를 찾을 때. |
| 검색 및 설명 | find-conflicts | 있음 · 캐시 또는 Provider | Context Memory → 충돌 보고서 | 현재 또는 명시한 Context에서 서로 충돌하는 직접 Memory 쌍을 보고합니다. | 정확한 직접 Context 하나를 분석하며 내용을 변경하지 않습니다. | 양립할 수 없는 주장이나 지침을 찾을 때. |
| 분석 및 변환 | audit | 있음 · 캐시 또는 Provider | Context → 저장된 품질 보고서 | 중복, 모호성 및 충돌 검사를 실행하고 하나의 저장된 보고서로 검토합니다. | 정확한 직접 Context 하나를 읽기 전용으로 분석합니다. | Context를 수정하기 전에 종합적인 품질 검사를 수행할 때. |
| 분석 및 변환 | atomize | 있음 · 캐시 또는 Provider | Context Memory → 검토 가능한 원자적 Memory | 복합 Memory를 검토 가능한 단위로 나눕니다. --evaluate는 issue 범위의 directional meld를 수행합니다. | 명시적으로 승인한 후에만 자료가 변경됩니다. | 복합 Memory의 요구사항을 독립적으로 검토할 수 있게 나눌 때. |
| 분석 및 변환 | distill | 있음 · 정확한 준비 결과 또는 Provider | Case/Example Context + 선택적 Goal → 검토 가능한 Rule | 선택한 Context 범위의 Case 또는 Example 명제에서 재사용 가능한 Rule을 도출하며, 선택적인 Goal로 관련성의 초점을 맞춥니다. | Source와 Ground는 유지되며 독립 실행의 Apply만 새 Result를 만들 수 있습니다. | 근거가 풍부한 자료에서 재사용 가능한 규칙을 추출할 때. |
| 분석 및 변환 | elaborate | 있음 · 정확한 준비 결과 또는 Provider | Goal → 제안된 Rule; Rule → 제안된 Case 명제 | Goal에서 후보 Rule을, 기존 Rule에서 구체적인 Case 명제를 제안합니다. | 읽기 전용이며 모든 제안은 제안 상태이자 미검증 상태로 남습니다. | 추상적인 Goal에 출발점이 될 Rule 후보가 필요하거나, 기존 Rule을 검토할 구체적인 Case 명제가 더 필요할 때. |
| 분석 및 변환 | compare | 있음 · 캐시 또는 Provider | Context ↔ Context → 비교 보고서 | 두 Context의 Memory를 비교해 공통점, 차이점, 한쪽에만 있는 내용을 보고합니다. | 두 Context 모두 변경하지 않으며 어느 쪽도 기준으로 삼지 않습니다. 각 범위는 정확한 Context 또는 읽을 수 있는 하위 Context를 포함할 수 있습니다. | 두 Context를 전체적으로 비교해 어디가 같고 다른지 이해할 때. |
| 분석 및 변환 | impact | 형식에 따라 다름 | Operation 입력 또는 session → 영향 보고서 | Operation의 영향을 미리 보거나 검사하며 검토된 Apply로 넘기기 전에는 Context를 변경하지 않습니다. | Impact 자체는 읽기 전용이며 Apply는 별도의 검토 작업입니다. | 변환을 승인하기 전에 예상되는 영향을 확인할 때. |
| 분석 및 변환 | review | 형식에 따라 다름 | 저장된 분석 → 검토 응답 | 대화형 Review session에 들어가거나 의미 검토 응답을 기록하며 Memory를 적용하지 않습니다. | 응답만 기록하며 Memory 변경을 materialize하지 않습니다. | 이후 Apply 전에 저장된 분석의 문제를 해결할 때. |
| 분석 및 변환 | meld | 있음 · 캐시 또는 Provider | PEER A + PEER B → RESULT; INCOMING → BASELINE | 두 Context를 결합하고 차이를 조정해 별도의 Result 또는 하나의 권위 있는 Baseline에 반영합니다. | 대칭 모드는 서로 구별되는 빈 Result가 필요하며, 방향 모드는 검토된 Apply 후 Baseline만 변경합니다. | 독립적으로 편집한 Context들을 하나의 공유 버전으로 합치거나, 제안된 변경사항을 현재 Baseline에 반영할 때. |
| 분석 및 변환 | update | 있음 · 캐시 또는 Provider | Source Context → Target Context | Source Context의 Memory를 바탕으로 Target Context의 Memory를 업데이트하고, 필요할 때 사용자에게 검토와 선택을 요청합니다. | Apply 후 로컬 Target만 변경됩니다. | 새롭게 검증된 Memory를 바탕으로 기존 Context를 업데이트할 때. |
| 분석 및 변환 | sever | 있음 · 캐시 또는 Provider | Source Context + Criteria Context → 새 Result Context | Source를 Criteria에 따라 검토하고 Source를 유지한 채 파생 Result를 생성합니다. | 검토된 새 Result를 만들며 Source는 변경하지 않습니다. | 재사용 가능한 기준에 따라 Source 일부를 선별하거나 변환할 때. |
| 분석 및 변환 | translate | 있음 · 캐시 또는 Provider | Context 또는 Memory → 번역 view 또는 materialization | 재사용 가능한 번역 view를 보여주고 저장하며 명시적인 경로로만 materialize합니다. | Source는 유지되며 materialization은 별도 명시 작업이 필요합니다. | 원본을 보존하면서 자료를 번역할 때. |
| 분석 및 변환 | merge | 없음 | A · Source Context → B · 현재 Target Context | Identity를 인식하는 구조적 merge를 수행합니다. Source에만 있는 항목은 추가하고, 변경되지 않은 공유 항목은 건너뛰며, 내용·타입·reference·placement 충돌은 검토합니다. Recursive 모드에서는 하위 Context 경로를 대응시킵니다. | 3-way 또는 semantic merge가 아닙니다. 모든 충돌은 Source/Target 중 하나를 결정론적으로 선택해야 하며, custom 내용을 합성하거나 Target에만 있는 항목을 삭제하지 않습니다. | Branch의 추가분을 되돌리면서 저장 identity 충돌은 현재 Context를 변경하기 전에 명시적으로 해결해야 할 때. |
| 기록 및 복구 | log | 형식에 따라 다름 | 기록된 history 또는 query → history 보고서 | Context checkpoint, Memory lineage, history 검색 또는 Profile command 시도를 조회합니다. | 읽기 전용이며 선택한 history 형식에 따라 범위가 달라집니다. | 이전 작업, checkpoint 또는 Memory 기록을 조사할 때. |
| 기록 및 복구 | diff | 없음 | 기록된 변경 → diff 보고서 | 기록된 Context 또는 Update 변경을 적용하지 않고 검사합니다. | 읽기 전용이며 정확한 Context history 또는 활성 Update를 비교합니다. | 기록된 작업이 정확히 무엇을 변경했는지 확인할 때. |
| 기록 및 복구 | checkpoint | 없음 | Context 상태 → checkpoint | 현재 Context를 Diff 또는 Revert에 사용할 수동 복구 지점으로 저장합니다. | Context 내용은 변경하지 않고 history metadata만 추가합니다. | 위험한 작업 전에 복구 지점을 만들 때. |
| 기록 및 복구 | undo | 없음 | Command history → 되돌린 Context 효과 | 가장 최근에 기록된 Context command가 영향을 준 모든 Context에서 효과를 되돌립니다. | 해당 command의 모든 영향 Context를 변경합니다. | 최근 mutation 전체를 하나의 작업으로 되돌릴 때. |
| 기록 및 복구 | redo | 없음 | Undo history → 복구된 command 효과 | 가장 최근에 Undo한 Context command를 다시 실행합니다. | 최근 Undo가 영향을 준 Context 집합을 복구합니다. | 실수로 되돌린 작업을 다시 적용할 때. |
| 기록 및 복구 | revert | 형식에 따라 다름 | Checkpoint → 복구된 Context 상태 | checkpoint를 선택하고 로컬 Context 하나의 복구 내용을 검토합니다. | 검토 후 정확한 로컬 Context 하나를 변경합니다. | Context를 의도적으로 저장한 복구 지점으로 되돌릴 때. |
| Ground 및 평가 | ground | 있음 · 캐시 또는 Provider | 대화 + 근거 → 검토 가능한 Ground | 검토 가능한 Goal–Rules–Memories Ground workbench를 생성하거나 이어갑니다. | Ground record를 변경하며 Context 변경에는 별도 command가 필요합니다. | 근거를 바탕으로 검토 가능한 평가 또는 행동 계약을 만들 때. |
| Ground 및 평가 | fit | 있음 · 캐시 또는 Provider | Ground Rule + Example → revision에 연결된 Fit receipt | 활성 Ground Example을 활성 Rule에 맞춰 평가하고 변경할 수 없는 receipt를 저장합니다. | Ground를 변경하지 않고 판단하며 파생 receipt만 저장합니다. | Rule이나 Case가 변경된 뒤 활성 Ground Example 전체를 다시 평가할 때. |
| Ground 및 평가 | check-conformance | 있음 · 캐시 또는 Provider | Rule + Ground Memory 또는 Context → Conformance 보고서 | Ground example 또는 Context 하나가 명시적인 Rule을 따르는지 검사합니다. | Rule, Ground, Context 및 Memory를 변경하지 않는 읽기 전용 작업입니다. | Context 또는 저장된 Ground를 명시적인 Rule에 맞춰 검사할 때. |
| Ground 및 평가 | init-study | 없음 | Study baseline → 격리된 Study Profile | Study baseline을 격리된 participant/authority Profile 쌍으로 복사합니다. | 격리된 Profile store를 생성하고 활성 Profile을 전환합니다. | 재현 가능하고 격리된 사용자 연구 환경을 준비할 때. |
| Ground 및 평가 | eval | 형식에 따라 다름 | 평가 fixture → campaign 결과 | 단계적인 semantic evaluation campaign을 실행하고 검사합니다. | Context가 아니라 evaluation ledger를 변경합니다. | 반복 가능한 fixture로 operation 행동을 측정할 때. |
| Profile 및 공유 | profile | 없음 | Profile registry ↔ Profile 관리 | 대화형 Profile selector에 들어가거나 전체 로컬 MemoryStore Profile을 관리합니다. | Profile을 전환, 생성, import, rename 또는 remove할 수 있습니다. | 사용자, 환경 또는 Memory store를 분리해 관리할 때. |
| Profile 및 공유 | rename | 없음 | 관리되는 Profile 이름 → 새 Profile 이름 | Store를 이동하거나 다시 쓰지 않고 현재 또는 명시한 Profile의 이름을 변경합니다. | Registry metadata만 변경하며 store 내용은 유지합니다. | 기존 Profile에 더 명확한 이름을 부여할 때. |
| Profile 및 공유 | share | 없음 | 소유 Context → 수신 endpoint | Grant 기반 receiver endpoint를 통해 일반 Context 하나를 전송합니다. | 정확한 일반 Context 하나를 외부로 전달하며 Source는 유지됩니다. | 소유한 Context를 승인된 수신자에게 전달할 때. |
| Profile 및 공유 | lock | 없음 | Resource → 쓰기 보호된 resource | 현재 Context, recursive Context 집합, Memory 또는 Profile을 잠급니다. | 선택한 정확한 resource 또는 recursive 범위의 보호 metadata를 변경합니다. | 안정된 자료가 실수로 변경되는 것을 막을 때. |
| Profile 및 공유 | unlock | 없음 | 보호된 resource → 쓰기 가능한 resource | Context, recursive 집합, Memory 또는 Profile의 잠금을 해제합니다. | 선택한 범위에서 보호 metadata를 제거합니다. | 보호된 자료를 의도적으로 다시 수정할 때. |
| 시스템 | help | 없음 | Operation catalog → 사용 안내 | 대화형 command browser에 들어가 syntax help를 엽니다. | 읽기 전용이며 선택한 operation을 실행하지 않습니다. | 사용할 수 있는 operation과 호출 형식을 찾을 때. |
| 시스템 | provider | 없음 | Provider 설정 ↔ 상태 또는 probe | Codex, Ollama 또는 OpenRouter semantic execution을 선택하고 검증합니다. | 설정을 변경하거나 명시적인 probe 요청을 보낼 수 있습니다. | Semantic execution backend를 선택하고 동작을 검증할 때. |
| 시스템 | shell-init | 없음 | Shell 이름 → integration script | 대화형 command prefill을 위한 선택적 shell integration을 출력합니다. | 출력은 읽기 전용이며 설치에는 명시적인 shell 실행이 필요합니다. | 선택적인 shell 편의 기능을 활성화할 때. |
| 시스템 | config | 없음 | Configuration key ↔ 값 | 전역 configuration을 읽고 씁니다. | 전역 설정을 변경할 수 있지만 Context 내용은 직접 변경하지 않습니다. | MemCommit의 영구 설정을 확인하거나 변경할 때. |

## Merge implementation target

Status: implemented in the working tree; automated verification complete,
ordered real-terminal evidence pending.

Merge keeps one conditional review boundary across its Python, CLI, and TUI
adapters:

1. Freeze and classify the complete direct or recursive plan before mutation.
2. Classify Source-only identities as `NEW`, equivalent shared items as
   `UNCHANGED`, and actionable collisions as `CONTENT_DIVERGENCE`,
   `TYPE_COLLISION`, `REFERENCE_COLLISION`, or `PLACEMENT_COLLISION` under one
   deterministic `CONFLICT` obligation.
3. When there are no `CONFLICT` items, skip the Resolution workbench. A
   bare TTY invocation continues directly to the existing exact frozen-plan
   review; a complete non-interactive invocation applies through its ordinary
   CLI path.
4. Show `ITEMS` and `RESPONSES` only when at least one `CONFLICT` exists. Every
   conflict requires an explicit, valid deterministic Source/Target decision
   before Apply becomes available.
5. A non-interactive invocation with a complete typed decision set also skips
   the TUI. An absent or incomplete decision set fails before persistence and
   reports the unresolved Memory UIDs.
6. Recursive Merge aggregates divergence across every frozen Context mapping.
   One unresolved item prevents every addition and resolution from being
   published; Apply remains atomic.
7. Revalidate the frozen Source/Target identities, digests, subtree membership,
   and complete decision set before writing.

This first target is deterministic and provider-free. It does not infer a
common ancestor or label every two-way content difference as a three-way
conflict. A later ancestry-aware contract may automate Source-only or
Target-only edits only when a common Base is explicitly provable.

### Merge TUI parity checklist

The conflict-aware Merge flow should preserve the interaction contracts already
used by the shared Resolution Session and the migrated Merge setup.

Required shared behavior:

- Keep the existing `A · SOURCE` selector and frozen `B · CURRENT TARGET`.
  Source remains the only editable endpoint, and direct versus recursive reach
  remains one coupled setup choice.
- Build the complete deterministic plan before rendering decisions. `NEW` and
  `UNCHANGED` counts belong in the report; only actionable deterministic
  `CONFLICT` items belong in the Items list.
- When no required divergence exists, do not construct empty `ITEMS` or
  `RESPONSES` frames. Continue to the existing exact frozen-plan review.
- When divergence exists, start on the complete Viewer report. Before opening
  an item the visible Tab order is `VIEWER → ITEMS → TO DO → VIEWER`. After an
  item is opened it is `VIEWER → RESPONSES → ITEMS → TO DO → VIEWER`.
- Show `RESPONSES` only for the currently opened conflict. All conflicts are
  `REQUIRED`; To Do opens the first unanswered item and must not expose Apply
  while any required choice is open.
- Render `KEEP TARGET` and `TAKE SOURCE` through the common flat selection
  state: a check mark is the staged choice, blue is keyboard focus, and moving
  between frames restores the cursor to the staged choice. Selecting the
  staged choice again may clear it and must make the item unresolved again.
- Do not fabricate an `Other` choice. If the shared Response box remains
  visible, its text is an optional retained comment and never satisfies the
  required exact choice or invents replacement Memory content.
- Present classification before evidence. One detail shows the exact Context
  mapping, shared Memory UID, Target content, Source content, and a
  deterministic line/word diff. Reuse the presentation-neutral Memory diff
  records rather than reconstructing differences from rendered terminal text.
- Keep report labels and chrome neutral. Individual Memory contents use the
  shared light-lavender Memory style; only the active control uses the shared
  blue focus treatment. Sanitize terminal control text and retain full content
  in the scrollable detail even when list labels are shortened.
- Stage every choice without mutation. On the per-item path, after all required
  choices are staged, To Do opens a separate final review summarizing `NEW`,
  `UNCHANGED`, every conflict class, `KEEP TARGET`, `TAKE SOURCE`, Contexts to
  create, and checkpoints. A whole-set bulk card may fuse this review with its
  Apply action, but both paths confirm the exact frozen plan and complete
  decision set once.
- Escape and Backspace unwind one read-only layer at a time: final review to
  report, opened detail to report, then root close. Backspace remains ordinary
  deletion in a writable optional comment. Cancel at every layer publishes no
  partial additions or decisions.
- After Apply, keep a visible durable receipt with Source, Target, reach,
  per-disposition counts, changed Context count, and checkpoint identities.
  A stale Source, Target, subtree, or decision binding fails without partial
  publication and requires a freshly frozen plan.
- A bare TTY invocation may enter this conditional workbench. An explicit CLI
  invocation stays non-interactive: a complete typed decision set applies,
  while an absent or incomplete set reports stable unresolved locators and
  exits before persistence.
- Keep Merge provider-free. No loading indicator, provider status, semantic
  cache label, free-form incorporation turn, or hidden semantic retry belongs
  in this deterministic flow.

Merge-specific decisions and boundaries:

- **No-op persistence.** A Merge with no effective Target content change still
  freezes and revalidates the complete boundary and records an explicit
  `NO TARGET CHANGE` session/receipt. It must distinguish the verified no-op
  from an operation that never ran. Its zero-delta command-unit behavior must
  not conceal or partially consume an earlier undoable mutation.
- **Operation-level recovery.** Direct and recursive Merge, including Contexts
  created by recursive reach and edits selected through divergence resolution,
  require one complete command unit. Undo atomically restores every updated
  Context and removes every Context created by that Merge; Redo recreates and
  reapplies the same complete unit. Partial recursive Undo is not acceptable.
- **Decision identity.** A bare Memory UID is insufficient when recursive
  mappings or repeated placements can expose the same UID more than once. Each
  decision needs a stable mapping-qualified identity, while the screen may show
  a short UID for readability.
- **Authority.** Existing Merge requires Target `CREATE` because it only adds.
  `TAKE SOURCE` edits an existing Target Memory and therefore also needs the
  operation's reviewed `UPDATE`/accept-derived authority and write-protection
  checks before the decision UI promises that action.
- **Structural and reference conflicts.** Same-UID unlike durable item types,
  duplicate logical references under different stored identities, and
  incompatible Context-like placements are required deterministic conflict
  classes rather than silent skips. Each exposes only resolutions that can be
  validated and applied without breaking pointer, authority, or placement
  invariants.
- **Decision retention (intentional limitation).** Current Merge review is process-local. Decide whether
  many staged divergence choices should survive closing and reopening. Any
  retained decision receipt must be bound to the exact Source/Target digests
  and become unusable when either side changes.
- **Bulk choices (implemented).** Explicit `KEEP ALL TARGET` and `TAKE ALL SOURCE`
  strategies over the complete unresolved set. A bulk action retains per-item
  accounting and shows the exact count, mappings, permissions, creations, and
  replacements it will commit. Confirming that complete bulk card is the final
  approval boundary, so it may Apply directly without a second duplicate Final
  Review screen. It must never mutate from an unreviewed shortcut key.
- **No custom content (implemented).** Merge offers only typed deterministic Source/Target
choices. It never synthesizes or accepts a combined replacement; semantic or
custom reconciliation remains Meld's responsibility. The current Merge shell
does not expose a free-form comment; if one is added later, it may retain
rationale only and must never become replacement content.
- **Shared clipboard (implemented).** The migrated shared Resolution workbench has the
  `y` focused / `Y` complete plain-text clipboard contract used by Summarize and
  Query. The binding is inactive in writable input, returns a visible copy or
  failure receipt, and is not implemented as a Merge-only variant.
- **Verification evidence (implemented).** Ordered 180×52 color PTY evidence under
  `docs/screenshots/mem-merge-conflict-resolution-20260815/` covers divergent
  direct and recursive paths, choice selection and clearing, individual and
  bulk final approval, durable receipts, operation-unit Undo/Redo,
  cancellation, stale-plan failure without partial Target publication, and an
  explicit no-op checkpoint/receipt with read-only verification.
