# Semantic Operation Criteria: Original and English Translation

## Original

예시 사례를 넣어도 되니? /compact는 좋은 세만틱 오퍼레이션이야. 그러니까 원래는 프롬프트로 요약해줘… 길게 작상하던 걸 /compact라는 아주 짧은 커맨드로 할 수 있고, 사실 기능 자체도 skills를 이용해서 기존앤 그냥 요약만 ㄷ]하던 걸 보다 깊은 구조화 기능으로 성능을 끌어올릴수도 있잖아? 이런 식으로 개선의 기준을 음..

1. 보다 적은 글자수로 동일한 기능을 구현할 것
2. (선택) 가능하다면 베이스라인: 유저가 일일히 300words 선에서 요구사항을 타이핑하는 것보다 디테일한 (유저빌리티 측면에서 유저가 명확히 차이를 느낄 수 있는). 결과를 제공할것 e.g. compact가 사실상 summarize 이상의 이저누대화 인덱싱이나 이런 걸 통해 내용을 압축하고 실제로도 이전의 결과물들을 잘 끌어올수있는것처럼) 결괴물을 제공할 것.
3. 모든 커맨드들이 실제로 작동하되 유저가 인지하는 커맨드와 실질적으로 같은 의미의 기능을 제공할 것
4. 시나리오를 하나 줄건데 이 시나리오 상에서 유저가 손으로 모든 것을 바이브코딩 + 일반적으로 컴퓨터 틀들 이용할 때보다 이 커맨드들을 이용할 때 명확히 처리 단계수가 줄면서도 동일하거나 그 이상 수준의ㅣ provenance를 제공하게 할 것.
5. 각 커맨드에 방식 + 이 커맨드의 의더와 사용예시 실제적인 얘시사례를 1개씩 쵀소 포한할것

Baseline이 아까 사례 윗부분 개선목표를 아릿부분과 같은 (일치하지 안하도ㅠ되는) 으로 히자. /compact의 사리를 좋은 완성사례 (이유도 앞서처럼) 해주고, 각각의 커맨드가 앞서 언급한 4가지 요소들을 지니기 해줘

## English Translation

Can we include example cases? `/compact` is a good semantic operation. Originally, a user would have to write a long prompt such as “please summarize this...” but `/compact` lets the user do that with a very short command. Also, the function itself can use skills, so instead of only doing a simple summary, it could improve performance by doing deeper structuring. In that sense, the improvement criteria could be something like:

1. The same function should be achievable with fewer characters.
2. Optional, if possible: compared with a baseline where the user manually types around 300 words of requirements, the operation should provide a more detailed result where the user can clearly feel a usability difference. For example, `compact` is effectively more than `summarize`: by indexing prior conversation or doing something similar, it can compress content and also recover previous outputs well.
3. All commands should actually work, and they should provide functionality that has substantially the same meaning as the command the user perceives.
4. I will provide one scenario. In that scenario, compared with the user manually doing everything through vibe coding plus ordinary computer tools, using these commands should clearly reduce the number of processing steps while providing the same or a higher level of provenance.
5. Each command should include at least one method, the intent of the command, a usage example, and a concrete practical example case.

For the baseline, let us use the upper part of the earlier scenario, and let the improvement goals be similar to the lower part, although they do not have to match exactly. Use `/compact` as a good completed example, including the reason as above. Also make each command include the four elements mentioned earlier.
