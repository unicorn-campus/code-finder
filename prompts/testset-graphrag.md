# GraphRAG 테스트 Query셋 생성 프롬프트

[목표]
교재 GraphRAG(지식그래프 검색)의 검색 품질을 RAGAS(Context Precision·Recall,  
Faithfulness·Answer Relevancy)와 NDCG(순위 품질, RAGAS 외 별도 계산)로 측정하기 위한  
정답(ground truth) 포함 테스트 Query셋 파일을 생성함.

[역할]
당신은 검색 품질 평가 체계(precision/recall 대시보드) 구축 경력 3년의 QA 엔지니어이며,  
GraphRAG 지식그래프 스키마(엔티티·관계)를 이해하고 "나쁜 질문"까지 설계하는 검색 평가 전문가입니다.

[맥락]
- 내 상황: code-finder의 교재 검색은 GraphRAG로 구축됨. 개념(엔티티)과 개념 간 관계(엣지)를  
  탐색하는 검색이므로, 단순 키워드 검색과 다른 멀티홉·관계형 질의의 정확도를 별도로 검증해야 함.  
  현재 회귀 테스트에 쓸 표준 Query셋이 없어 평가가 주관적임.
- 결과물 독자: GraphRAG 아키텍트(그래프), 오케스트레이터(클로니), 검색 파이프라인 회귀 테스트 자동화 스크립트
- RAGAS 연계: 본 Query셋은 `dev-prompt-guide_v2.md` §3.7 평가 입력으로 사용됨  
  - `query` → RAGAS user_input, `expected_answer` → RAGAS reference(정답 기준)
  - `gt_chunk_ids` → reference_contexts (평가 시 지식그래프 인덱스에서 청크 텍스트로 해석)
  - NDCG는 Local 질의 순위 평가용으로 `gt_entities`·`gt_chunk_ids` 관련도 순서를 사용

[입력]
- 지식그래프 스키마·인덱스: GraphRAG 인덱싱 산출물(엔티티 목록, 관계 목록, 원문 청크 매핑)
- 교재 원문: 인덱싱에 사용된 Agentic AI 학습 교재 텍스트
- 인덱싱 프롬프트: `prompts/indexing-textbook.md` (엔티티·관계 정의 기준 참조)
- 지식그래프 요약을 직접 임베딩할 때는 아래 태그로 감쌀 것

<knowledge_graph>
{엔티티·관계·청크 매핑 요약을 여기에 붙여넣기}
</knowledge_graph>

[처리]
- 실제 학습자(주니어 개발자·취준생)가 던질 법한 질문을 5개 질의 유형으로 분류하여 생성
  - FACTOID(단일 엔티티): "{개념} 이란 무엇인가" — 단일 노드로 답 가능
  - RELATIONAL(1홉 관계): "{개념 A}와 {개념 B}는 어떤 관계인가" — 엣지 1개 탐색
  - MULTI_HOP(2홉 이상): "{개념 A}를 이해하려면 먼저 알아야 할 선행 개념은" — 경로 탐색
  - EXPLORATORY(연관 탐색): "{개념}과 함께 학습하면 좋은 관련 개념은" — 이웃 노드 집합
  - ADVERSARIAL(나쁜 질문): 오타·모호어·전문용어 혼용·범위 밖 질문 — 오검색 방지 검증용
- 각 질의마다 정답(ground truth)을 명시
  - 정답 엔티티 ID 목록, 정답 관계(엣지) 목록, 근거 원문 청크 ID 목록
  - 기대 핵심 답변 요지(2~3문장, 명사체)
  - ADVERSARIAL 은 정답을 빈 배열로 두고 `expected_behavior`에 "무응답/재질문 유도" 명시
- 질의 난이도(easy/medium/hard)와 유형을 각 항목에 태그로 부여
- 근거 없는 엔티티·관계는 정답에 절대 포함하지 않음 — 그래프에 실제 존재하는 것만 사용
- 유형별 최소 개수: FACTOID·RELATIONAL·MULTI_HOP 각 8개, EXPLORATORY·ADVERSARIAL 각 5개 (총 34개 이상)
- 출력파일: testset-graphrag.jsonl
- 톤앤매너: 질의문은 학습자의 실제 말투(구어체 허용), 정답·메타데이터는 명사체
- 작성 규칙:
  - 1줄 1질의의 JSONL 형식, UTF-8, 한국어 질의
  - 스키마 고정: `id`, `query`, `type`, `difficulty`, `gt_entities`, `gt_relations`,
    `gt_chunk_ids`, `expected_answer`, `expected_behavior`, `note`
  - 정답 ID는 지식그래프 인덱스의 실제 ID와 문자열이 정확히 일치해야 함

[출력]
- `datasets/testset-graphrag.jsonl`

[제약조건]
- MUST: 모든 정답 엔티티·관계·청크 ID가 지식그래프 인덱스에 실재함을 확인 후 기록
- MUST: 5개 유형이 모두 최소 개수를 충족
- MUST NOT: 그래프에 없는 개념·관계를 추측으로 정답에 기입
- 완료조건: `datasets/testset-graphrag.jsonl` 파일이 생성되고, 34행 이상이며,  
  각 행이 JSON 파싱에 성공하고 스키마 필드를 모두 포함함을 실제 파싱 실행으로 확인

[예시]
{"id":"gr-rel-001","query":"ReAct랑 Chain-of-Thought는 무슨 관계예요?","type":"RELATIONAL","difficulty":"medium","gt_entities":["ent_react","ent_cot"],"gt_relations":["rel_react_extends_cot"],"gt_chunk_ids":["chunk_112","chunk_118"],"expected_answer":"ReAct는 CoT의 추론 과정에 도구 사용(Act)을 결합한 확장 기법임. 추론과 행동을 번갈아 수행함.","expected_behavior":"","note":"1홉 관계 탐색"}
{"id":"gr-adv-003","query":"에이전트 그거 그냥 gpt 아님?","type":"ADVERSARIAL","difficulty":"hard","gt_entities":[],"gt_relations":[],"gt_chunk_ids":[],"expected_answer":"","expected_behavior":"모호한 질문으로 판단하여 재질문 유도 또는 낮은 신뢰도 표기","note":"범위 밖·모호 질의"}
