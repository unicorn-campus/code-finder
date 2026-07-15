# RAG(코드 Vector DB) 테스트 Query셋 생성 프롬프트

[목표]
예제 코드 Vector DB(유사도 검색)의 검색 품질을 RAGAS(Context Precision·Recall,  
Faithfulness·Answer Relevancy)로 측정하기 위한 정답(ground truth) 포함 테스트 Query셋 파일을 생성함.

[역할]
당신은 검색 품질 평가 체계(precision/recall 대시보드) 구축 경력 3년의 QA 엔지니어이며,  
코드 임베딩·하이브리드 검색(키워드+벡터)의 재현율 실측과 "나쁜 질문" 설계에 능한 검색 평가 전문가입니다.

[맥락]
- 내 상황: code-finder의 코드 검색은 Vector DB 유사도 검색으로 구축됨. 코드는 자연어와 임베딩 특성이  
  달라, 자연어→코드·코드→코드 검색의 재현율을 실측으로 검증해야 함. 하이브리드(키워드+벡터) 튜닝  
  효과를 비교할 표준 Query셋이 없어 검색 튜닝 전후 비교가 불가능함.
- 결과물 독자: 검색엔진(Vector DB) 엔지니어(벡터), 오케스트레이터(클로니), 검색 파이프라인 회귀 테스트 스크립트
- RAGAS 연계: 본 Query셋은 `dev-prompt-guide_v2.md` §3.7 평가 입력으로 사용됨  
  - `query` → RAGAS user_input, `expected_answer` → RAGAS reference(정답 기준)
  - `gt_chunk_ids` → reference_contexts (평가 시 코드 인덱스에서 청크 텍스트로 해석)

[입력]
- 코드 인덱스: 예제 코드 임베딩·인덱싱 산출물(코드 청크 ID, 함수·파일 메타데이터)
- 예제 코드 원본: 인덱싱에 사용된 Agentic AI 예제 코드(스니펫·함수 단위)
- 인덱싱 프롬프트: `prompts/indexing-code.md` (청크 단위·메타데이터 기준 참조)
- 코드 인덱스 요약을 직접 임베딩할 때는 아래 태그로 감쌀 것

<code_index>
{코드 청크 ID·함수 시그니처·언어·경로 요약을 여기에 붙여넣기}
</code_index>

[처리]
- 실제 학습자(주니어 개발자·취준생)가 던질 법한 질문을 5개 질의 유형으로 분류하여 생성
  - NL2CODE(자연어→코드): "{동작}을 하는 예제 코드 보여줘" — 의미 기반 코드 검색
  - CODE2CODE(코드→유사코드): 스니펫 입력 → 유사 구현 검색 — 유사도 검색
  - API_USAGE(사용법): "{라이브러리/함수} 어떻게 써?" — 특정 API 호출 예제 검색
  - HYBRID(키워드+의미): 정확한 함수·클래스명 + 자연어 의도 혼합 — 하이브리드 검색 검증용
  - ADVERSARIAL(나쁜 질문): 오타·언어 혼용·존재하지 않는 API·모호한 요청 — 오검색 방지 검증용
- 각 질의마다 정답(ground truth)을 명시
  - 정답 코드 청크 ID 목록(관련도 순), 정답 함수/파일 경로 목록
  - 기대 핵심 설명 요지(무엇을 하는 코드인지, 2~3문장, 명사체)
  - ADVERSARIAL 은 정답을 빈 배열로 두고 `expected_behavior`에 "무결과/유사 대안 제시" 명시
- 질의 난이도(easy/medium/hard)와 유형을 각 항목에 태그로 부여
- CODE2CODE·HYBRID 는 질의에 실제 코드 스니펫을 포함 (문자열 이스케이프 처리)
- 인덱스에 실재하는 코드 청크만 정답으로 사용 — 존재하지 않는 스니펫은 정답에 포함하지 않음
- 유형별 최소 개수: NL2CODE·API_USAGE 각 8개, CODE2CODE·HYBRID 각 6개, ADVERSARIAL 5개 (총 33개 이상)
- 출력파일: testset-rag.jsonl
- 톤앤매너: 질의문은 학습자의 실제 말투(구어체 허용), 정답·메타데이터는 명사체
- 작성 규칙:
  - 1줄 1질의의 JSONL 형식, UTF-8, 코드 스니펫 내 개행·따옴표는 JSON 이스케이프
  - 스키마 고정: `id`, `query`, `type`, `difficulty`, `lang`, `gt_chunk_ids`,
    `gt_paths`, `expected_answer`, `expected_behavior`, `note`
  - 정답 ID는 코드 인덱스의 실제 청크 ID와 문자열이 정확히 일치해야 함

[출력]
- `datasets/testset-rag.jsonl`

[제약조건]
- MUST: 모든 정답 청크 ID·경로가 코드 인덱스에 실재함을 확인 후 기록
- MUST: 5개 유형이 모두 최소 개수를 충족, CODE2CODE·HYBRID 는 코드 스니펫을 질의에 포함
- MUST NOT: 인덱스에 없는 코드·API를 추측으로 정답에 기입
- 완료조건: `datasets/testset-rag.jsonl` 파일이 생성되고, 33행 이상이며,  
  각 행이 JSON 파싱에 성공하고 스키마 필드를 모두 포함함을 실제 파싱 실행으로 확인

[예시]
{"id":"rag-nl-001","query":"LangGraph로 상태 공유하는 에이전트 그래프 만드는 예제 있어?","type":"NL2CODE","difficulty":"medium","lang":"python","gt_chunk_ids":["code_042","code_045"],"gt_paths":["examples/langgraph/state_graph.py"],"expected_answer":"StateGraph에 노드를 추가하고 State/Reducer로 노드 간 데이터를 공유하는 예제임. compile 후 invoke로 실행함.","expected_behavior":"","note":"자연어 의도 기반 코드 검색"}
{"id":"rag-adv-002","query":"langgraph.super_agent() 이거 사용법 알려줘","type":"ADVERSARIAL","difficulty":"hard","lang":"python","gt_chunk_ids":[],"gt_paths":[],"expected_answer":"","expected_behavior":"존재하지 않는 API로 판단, 무결과 처리 또는 유사 기능 대안 제시","note":"존재하지 않는 API 질의"}
