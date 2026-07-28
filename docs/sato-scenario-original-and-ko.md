# Sato Scenario: Original and Korean Translation

## Original

Based on our interviews, we present a fictional scenario involving an investment team at a financial firm. The scenario illustrates the challenges of managing and sharing AI memory, and how Memlab may address them.

Mr. Sato is an analyst at an investment firm. His job here is to analyze East Asian semiconductor companies affected by AI-driven demand and make recommendations about how the firm should invest.

Although he already knows this market well and has his own view, he also needs to align his view with the firm’s position, because inconsistent opinions across the firm could reduce clients’ trust.

To avoid such conflicts while still contributing new insights, (1) Sato first needs to understand the firm’s existing view on this market. (2) He then compares it with his own view to identify conflicts, gaps, and points that require further validation to decide which parts should be aligned with the firm’s position and which parts can be proposed as updates. (3) He also needs to decide who should receive each update and at what level of detail, since some information, especially negative or speculative assessments, could harm the firm if shared with the wrong audience or without proper context.

At the same time, Sato uses an AI agent throughout this work, so the agent also needs to stay synchronized with his current context to support his judgment appropriately, avoid introducing outdated or irrelevant assumptions, and reduce the burden of repeatedly correcting the agent’s context.

Retrieving memory. Sato first tries to understand what position his firm has already taken. He begins by reading recent notes, briefings, updates, and discussion threads about the topic from the channels he already knows. At first, he does not find any recent related issue, but he is not confident that this means no such view exists, because relevant information may still be hidden in materials he has not read.

To reduce this uncertainty, he tries several additional strategies. He first asks the AI agent whether the firm has an existing view on the topic. The agent says no, but Sato withholds judgment because he cannot verify what sources it searched, how it searched them, or whether it properly understood what he was looking for and why.

He then searches the firm’s intranet using keyword combinations such as “East Asia,” “semiconductor,” and “AI demand.” Many posts appear, but he soon realizes that more than half are irrelevant to his actual interest. Even when a post seems only slightly related, he still has to open and read it to check whether it contains a useful firm view. With no better option, he reviews the results one by one within a specific time range and eventually saves three or four relevant posts.

By this point, Sato has spent considerable time reading unnecessary or weakly relevant materials just to find potentially useful documents. He treats this as a necessary cost of importing the firm’s memory, but before he can compare these materials with his own view, it is already time for a meeting. He postpones the deeper analysis until afterward.

Importing memory. After returning from the meeting, Sato realizes that he no longer remembers the details of the posts he had saved. He reopens them, but because he does not clearly remember where the important points were, he ends up rereading many parts that are not directly relevant.

He treats this as part of the work, but decides to reduce the chance of having to repeat the same process again. This time, as he rereads the materials, he manually marks the relevant passages and copies key points into a scratchpad. After going through the documents this way, the actually relevant content is reduced to only two or three pages of notes. When he compresses it further, the firm’s existing view can be summarized in three points

- the firm has paid attention to the rise of the Korean market over the past year
- it has been especially interested in Samsung Electronics and SK hynix as the two companies leading Korea’s semiconductor sector
- and this interest has been based on expectations of long-term demand growth driven by the chips needed to run AI models.

Sato also realizes that most of the roughly sixty pages he reviewed were not directly relevant to his current question. Still, he treats the time spent reading them as useful background-building, since maintaining broad market context is also part of being an analyst.

He also adds the three-point summary to the project’s Agent.md file. In addition, he places the three-page intermediate summary and the original documents in the project folder, thinking that the agent may later use them to recover where each point came from. By doing so, Sato assumes that the relevant memory has now been imported into the agent’s working context. However, he does not realize that the agent may not automatically read these files in full because of token and context-window limits. Unless Sato explicitly reminds the agent where the relevant information is and asks it to consult those files, much of this material may remain unused in future interactions.

Merging and refining memory. As Sato reviews the imported materials, he notices that the firm’s existing analysis focuses mostly on the global industry perspective, while he believes that domestic sentiment and policy dynamics have also contributed to the stock-price rise. Sato decides to write a report that adds his own perspective to the firm’s view, but this creates the same problem again. He has to search for materials, read through many partially relevant sources, compare them with the firm’s prior analysis, and verify which points are strong enough to include. As he moves between the new materials and the documents he imported earlier, he also begins to forget some details from the first set of documents and has to revisit them.

Sato accepts that he should remain responsible for the final judgment, but he also feels that some parts of this process could, in principle, be delegated to the agent. In practice, however, he still does most of the work manually, because explaining how the agent should use each file, interpret each detail, and connect each piece of evidence to the current argument often takes longer than doing the task himself. Even reusable skills would need to be revised for each report, since the relevant materials, claims, and standards keep changing. As a result, Sato uses the agent only mainly as a search aid or grammar-refinement tool.

Sharing memory toward different audiences. After summarizing the information, Sato begins preparing a polished version for the firm and its clients, because the working list is still too rough and contains many blunt, speculative, or negative points. He therefore manually creates multiple versions: a candid version for the team, a safer version for broader internal use, and a polished version for clients. At the same time, he cannot discard the raw version, because it may still be useful when he revisits the analysis or when teammates ask about details and unresolved concerns.

Sato considers turning these versions into agent-readable memory for others as well, but the versioning work already takes substantial time. He can only hope that others will adapt the right version and feed the necessary context into their own agents later.

Through this process, Sato experiences several challenges and frictions:

* Explaining Memory The agent’s answers are difficult to trust because there is not enough provenance about what evidence and methods it used. Even when memory is added to the agent, it is not reliably used in the right situations. To use it properly, Sato must explain each memory’s relationships, context, and criteria, but this is demanding, so he rarely uses the agent for deeper analysis.
* Searching Memory Search results contain a lot of noise, and relevance must be judged manually. Extracting important parts is also demanding. When information is missing, it is hard to know whether it truly does not exist or was simply not found. Delegating this to the agent without the explanation above risks losing details, but explaining it takes too much time.
* Sharing Memory Memory must be shared differently by audience, and adjusting each version to the right level also takes time. In practice, detailed adjustment is difficult, so Sato settles for making only a few versions. Of course he does not have enough time to prepare “memory for AI agents” for each purpose.

## Korean Translation

인터뷰를 바탕으로, 우리는 금융 회사의 투자팀을 다루는 가상의 시나리오를 제시한다. 이 시나리오는 AI 메모리를 관리하고 공유하는 데 따르는 어려움과 Memlab이 이를 어떻게 다룰 수 있는지를 보여준다.

Sato 씨는 투자 회사의 애널리스트다. 그의 업무는 AI-driven demand의 영향을 받는 동아시아 반도체 기업을 분석하고, 회사가 어떻게 투자해야 할지 추천하는 것이다.

그는 이미 이 시장을 잘 알고 있고 자신의 관점도 가지고 있지만, 회사의 입장과도 관점을 맞춰야 한다. 회사 안에서 서로 일관되지 않은 의견이 나오면 고객의 신뢰가 낮아질 수 있기 때문이다.

그런 충돌을 피하면서도 새로운 인사이트를 기여하기 위해, (1) Sato는 먼저 이 시장에 대한 회사의 기존 관점을 이해해야 한다. (2) 그다음 자신의 관점과 비교해 충돌, 공백, 추가 검증이 필요한 지점을 찾아야 한다. 이를 통해 어떤 부분은 회사의 입장과 맞추고, 어떤 부분은 업데이트로 제안할 수 있는지 결정한다. (3) 또한 각 업데이트를 누구에게, 어느 정도의 상세함으로 전달해야 하는지도 결정해야 한다. 특히 부정적이거나 추측적인 평가는 잘못된 청중에게, 또는 충분한 맥락 없이 공유될 경우 회사에 해를 끼칠 수 있다.

동시에 Sato는 이 작업 전반에서 AI 에이전트를 사용한다. 따라서 에이전트도 그의 현재 맥락과 동기화되어 있어야 한다. 그래야 그의 판단을 적절히 지원하고, 오래되었거나 관련 없는 가정을 도입하지 않으며, Sato가 에이전트의 맥락을 반복해서 고쳐야 하는 부담을 줄일 수 있다.

메모리 검색. Sato는 먼저 회사가 이미 어떤 입장을 가지고 있는지 이해하려고 한다. 그는 자신이 이미 알고 있는 채널에서 이 주제와 관련된 최근 노트, 브리핑, 업데이트, 토론 스레드를 읽기 시작한다. 처음에는 최근 관련 이슈를 찾지 못하지만, 이것이 그런 관점이 없다는 뜻이라고 확신하지 못한다. 관련 정보가 자신이 아직 읽지 않은 자료 안에 숨어 있을 수도 있기 때문이다.

이 불확실성을 줄이기 위해 그는 몇 가지 추가 전략을 시도한다. 먼저 AI 에이전트에게 이 주제에 대한 회사의 기존 관점이 있는지 묻는다. 에이전트는 없다고 답하지만, Sato는 판단을 보류한다. 에이전트가 어떤 출처를 검색했는지, 어떻게 검색했는지, 자신이 무엇을 왜 찾고 있는지 제대로 이해했는지 검증할 수 없기 때문이다.

그다음 그는 회사 인트라넷에서 “East Asia,” “semiconductor,” “AI demand” 같은 키워드 조합으로 검색한다. 많은 게시물이 나오지만, 곧 절반 이상이 자신의 실제 관심사와 무관하다는 것을 알게 된다. 어떤 게시물이 약간 관련 있어 보일 때에도, 유용한 회사 관점을 담고 있는지 확인하려면 직접 열어 읽어야 한다. 더 나은 선택지가 없기 때문에 그는 특정 시간 범위 안의 결과를 하나씩 검토하고, 결국 관련 게시물 세네 개를 저장한다.

이 시점에서 Sato는 잠재적으로 유용한 문서를 찾기 위해 불필요하거나 약하게 관련된 자료를 읽는 데 상당한 시간을 썼다. 그는 이것을 회사의 메모리를 가져오기 위한 필요한 비용으로 받아들인다. 하지만 이 자료들을 자신의 관점과 비교하기 전에 이미 회의 시간이 되었고, 더 깊은 분석은 회의 이후로 미룬다.

메모리 가져오기. 회의에서 돌아온 뒤 Sato는 자신이 저장했던 게시물의 세부 내용을 더 이상 기억하지 못한다는 것을 깨닫는다. 그는 게시물을 다시 열지만, 중요한 지점이 어디였는지 분명히 기억하지 못하기 때문에 직접 관련 없는 부분까지 많이 다시 읽게 된다.

그는 이것도 작업의 일부로 받아들이지만, 같은 과정을 다시 반복할 가능성을 줄이기로 한다. 이번에는 자료를 다시 읽으면서 관련 구절을 수동으로 표시하고 핵심 내용을 스크래치패드에 복사한다. 이런 방식으로 문서를 검토한 뒤, 실제 관련 내용은 두세 쪽의 노트로 줄어든다. 이를 더 압축하면 회사의 기존 관점은 세 가지로 요약될 수 있다.

- 회사는 지난 1년 동안 한국 시장의 상승에 주목해 왔다
- 회사는 한국 반도체 섹터를 이끄는 두 기업인 Samsung Electronics와 SK hynix에 특히 관심을 가져 왔다
- 그리고 이러한 관심은 AI 모델을 구동하는 데 필요한 칩에 의해 장기 수요가 증가할 것이라는 기대에 기반해 왔다.

Sato는 자신이 검토한 약 60쪽의 대부분이 현재 질문과 직접 관련되지 않았다는 것도 깨닫는다. 그래도 넓은 시장 맥락을 유지하는 것도 애널리스트의 일이라고 생각하기 때문에, 그 자료들을 읽은 시간을 유용한 배경지식 형성으로 받아들인다.

그는 세 가지 요약을 프로젝트의 Agent.md 파일에도 추가한다. 또한 세 쪽짜리 중간 요약과 원본 문서를 프로젝트 폴더에 넣어 둔다. 나중에 에이전트가 각 요점이 어디서 왔는지 복구하는 데 쓸 수 있다고 생각하기 때문이다. 이렇게 함으로써 Sato는 관련 메모리가 에이전트의 working context로 가져와졌다고 가정한다. 그러나 토큰과 context-window 제한 때문에 에이전트가 이 파일들을 자동으로 전부 읽지 않을 수도 있다는 점은 깨닫지 못한다. Sato가 관련 정보가 어디 있는지 명시적으로 알려 주고 그 파일들을 참조하라고 요청하지 않는 한, 이 자료의 상당 부분은 이후 상호작용에서 사용되지 않을 수 있다.

메모리 병합과 정제. 가져온 자료를 검토하면서 Sato는 회사의 기존 분석이 주로 글로벌 산업 관점에 집중되어 있다는 것을 발견한다. 반면 그는 국내 sentiment와 policy dynamics도 주가 상승에 기여했다고 본다. Sato는 자신의 관점을 회사의 관점에 추가하는 보고서를 쓰기로 하지만, 이로 인해 같은 문제가 다시 생긴다. 그는 자료를 검색하고, 부분적으로만 관련된 많은 출처를 읽고, 이를 회사의 기존 분석과 비교하며, 어떤 지점이 포함될 만큼 충분히 강한지 검증해야 한다. 새로운 자료와 이전에 가져온 문서 사이를 오가면서, 그는 첫 번째 문서 집합의 세부 내용을 일부 잊기 시작하고 다시 방문해야 한다.

Sato는 최종 판단의 책임이 자신에게 있어야 한다는 점을 받아들인다. 하지만 이 과정의 일부는 원칙적으로 에이전트에게 위임될 수 있다고 느낀다. 그러나 실제로는 여전히 대부분의 작업을 수동으로 한다. 에이전트가 각 파일을 어떻게 사용해야 하는지, 각 세부 사항을 어떻게 해석해야 하는지, 각 근거를 현재 주장과 어떻게 연결해야 하는지 설명하는 일이 직접 하는 것보다 오래 걸리는 경우가 많기 때문이다. 재사용 가능한 skill도 각 보고서마다 수정되어야 할 것이다. 관련 자료, 주장, 기준이 계속 바뀌기 때문이다. 결과적으로 Sato는 에이전트를 주로 검색 보조나 문법 다듬기 도구로만 사용한다.

서로 다른 청중을 향한 메모리 공유. 정보를 요약한 뒤 Sato는 회사와 고객을 위한 다듬어진 버전을 준비하기 시작한다. 작업 목록은 아직 너무 거칠고, 직설적이거나 추측적이거나 부정적인 지점이 많기 때문이다. 그래서 그는 여러 버전을 수동으로 만든다. 팀을 위한 솔직한 버전, 더 넓은 내부 공유를 위한 안전한 버전, 고객을 위한 다듬어진 버전이다. 동시에 그는 원시 버전을 버릴 수 없다. 나중에 분석을 다시 볼 때나 팀원들이 세부 사항과 미해결 우려를 물어볼 때 여전히 유용할 수 있기 때문이다.

Sato는 이 버전들을 다른 사람들을 위한 agent-readable memory로 바꾸는 것도 고려하지만, 버전 작업 자체에 이미 상당한 시간이 걸린다. 그는 다른 사람들이 나중에 알맞은 버전을 조정하고 필요한 맥락을 자신의 에이전트에 넣어 주기를 바랄 수밖에 없다.

이 과정을 통해 Sato는 몇 가지 어려움과 마찰을 겪는다.

* 메모리 설명. 에이전트의 답변은 어떤 근거와 방법을 사용했는지에 대한 provenance가 충분하지 않아 신뢰하기 어렵다. 메모리가 에이전트에 추가되더라도 적절한 상황에서 안정적으로 사용되지 않는다. 이를 제대로 사용하려면 Sato가 각 메모리의 관계, 맥락, 기준을 설명해야 하지만, 이 작업은 부담이 크기 때문에 그는 에이전트를 깊은 분석에 거의 사용하지 않는다.
* 메모리 검색. 검색 결과에는 노이즈가 많고, 관련성은 수동으로 판단해야 한다. 중요한 부분을 추출하는 일도 부담스럽다. 정보가 없을 때는 그것이 실제로 존재하지 않는 것인지, 아니면 단지 찾지 못한 것인지 알기 어렵다. 위의 설명 없이 이를 에이전트에게 위임하면 세부 사항을 잃을 위험이 있지만, 설명하는 데 시간이 너무 많이 든다.
* 메모리 공유. 메모리는 청중에 따라 다르게 공유되어야 하고, 각 버전을 적절한 수준으로 조정하는 데도 시간이 든다. 실제로는 세부 조정이 어렵기 때문에 Sato는 몇 가지 버전만 만드는 것으로 만족한다. 물론 각 목적에 맞는 “AI agent를 위한 memory”를 준비할 시간은 충분하지 않다.
