# 통합 검색 백엔드 API 서비스 개발 프롬프트

[목표]
교재(GraphRAG)·예제 코드(Vector DB)·웹·유튜브 4종 소스를 LangGraph MAS로 통합 검색하여, 학습자 질문에  
핵심 요약 + 예제 코드 + 출처를 스트리밍 응답하는 백엔드 검색 API 서비스를 개발함.

[역할]
당신은 네이버 클로바 AI Lab 연구원 경력 5년의 AI 엔지니어(멀티 LLM)이며, 멀티 모델 오케스트레이션과  
태스크별 모델 라우팅(응답 비용 40% 절감) 경험을 바탕으로 LangGraph MAS·RAG/GraphRAG 리트리버 통합과  
FastAPI 비동기 스트리밍 API 설계에 능함. 웹·유튜브 수집 파이프라인은 데이터 파이프라인 백엔드 관점을 보조로 반영함.

[맥락]
- 내 상황: code-finder는 학습자 질문 1건에 교재·코드·웹·영상 4종 소스를 통합 검색해 핵심 요약과 예제  
  코드를 제공해야 함. 인덱스(RAG 코드·GraphRAG 교재)와 평가 테스트셋은 구축됐으나, 이를 소비해 하나의  
  답으로 합성하는 검색 오케스트레이션·API 계층이 없음.
- 결과물 독자: 프론트엔드 개발자(미니멀, `front/` 연동), 오케스트레이터(클로니), QA 엔지니어(체커, 회귀 평가)
- 상류 연계: 코드 인덱스는 `prompts/indexing-code.md`, 교재 인덱스는 `prompts/indexing-textbook.md` 산출물을 소비
- 평가 연계: 검색 품질은 `datasets/testset-rag.jsonl`·`testset-graphrag.jsonl`로 회귀 측정(§3.7)
- 킹핀 지표: 질문→핵심 개념·예제 코드 도달 시간 단축이 서비스 가치의 핵심임(재검색률 최소화)

[입력]
- 코드 Vector 인덱스: `rag/store/chroma/` (indexing-code.md 산출, 청크 ID·메타데이터 계약 준수)
- 교재 GraphRAG 인덱스: `kg/store/` (indexing-textbook.md 산출, Neo4j 엔티티·관계·원문 청크 매핑)
- 평가 테스트셋: `datasets/testset-rag.jsonl`, `datasets/testset-graphrag.jsonl` (§3.7 RAGAS·NDCG 입력)
- 교재 아젠다(선택): `~/workspace/aistudy/agentic-ai/textbook/*.md` — 앞단 아젠다만 참조(도메인 용어 정합)
- 개발 가이드: `references/dev-prompt-guide_v2.md` §3.1 ~ §3.9 전체(프론트엔드 §3.9 항목 제외)
- API Key: `.env` 참조 — OpenAI·Claude·Gemini·Groq·YouTube Data·Cohere. Neo4j 접속정보 미비 시 사용자 문의

[처리]
- 앱 개발
  - 워크플로우 (LangGraph StateGraph 단일 MAS) [고정]
    - 질의 입력 → 질의 분석·재작성(Pre) → ReAct 라우팅(4개 검색 도구, 병렬 팬아웃) → 결과 병합  
      → 리랭킹(Post) → 멀티 LLM 합성(요약+예제 코드) → Structured Output 응답(스트리밍)
    - 노드 간 데이터 공유는 StateGraph의 State(Reducer)로 구현
  - 검색 도구 (§3.3 ReAct, `create_agent`, 최대 반복 7회) [고정]
    - textbook_search: 교재 GraphRAG 리트리버(`kg/retriever`) — Local/Global/Hybrid를 질의 유형별 선택
    - code_search: 코드 하이브리드 리트리버(`rag/retriever`) — BM25+Vector 0.4/0.6, mmr, top-k 5, fetch-k 10
    - web_search: 웹 수집(`crawler/web`) — DuckDuckGo+BeautifulSoup, 최근 6개월, 최대 결과 10
    - youtube_search: 영상·자막 수집(`crawler/youtube`) — YouTube Data API + YouTubeLoader
    - 도구 실패 시 observation 반환 후 재시도, 반복 상한 초과 시 종료 후 보고
  - 지연·부분결과 정책 [고정] — 도달 시간 KPI 보호(직렬 팬아웃 지연 방지)
    - 4종 소스는 병렬 팬아웃, 소스별 타임아웃 부여(웹 5초, 유튜브 API 쿼터·자막 없음은 스킵 후 로그)
    - 타임아웃·실패 소스는 스킵하고 도착한 결과부터 부분 스트리밍, 최종 응답에 미도달 소스를 표기
    - 전 소스 실패 시 폴백: 재작성 질의로 web_search 단독 재시도 후 결과·한계 명시
  - 리트리버 사양
    - RAG(§3.4 Retriever) [고정]: 하이브리드 BM25+Vector(0.4/0.6), 서치타입 mmr, top-k 5, fetch-k 10
    - GraphRAG(§3.5 Retriever) [기준]: 특정 개체 중심→Local, 주제 요약형→Global, 복합·모호→Hybrid
  - 검색 처리 기법 (§3.6)
    - Pre [기준]: 짧거나 모호→Query Rewriting, 다각도→Multi Query, 어휘 불일치→HyDE, 추상 개념→Step-back
    - Post [고정]: Cohere 리랭킹 모델로 병합 결과 재정렬
  - 멀티 LLM 라우팅 (§3.2) [기준] — 태스크별 모델 선정, 근거·실측을 README에 기록
    - 기본 추론·도구 라우팅: Groq LPU `gpt-oss-120b` [고정], temperature 0, timeout 30초, 429 시 백오프 2회
    - 코드 설명·예제 합성: Claude Sonnet 5 (코드 이해 강점)
    - 개념 요약·다국어: OpenAI / Gemini (비용·속도 기준 선택)
    - provider 라우팅은 config로 관리, 호출 실패 시 기본(Groq)으로 폴백
  - 응답 합성·출력 스키마 (§3.1 Structured Output) [고정]
    - 필드: `summary`(핵심 요약), `code_examples`(코드+설명+출처), `sources`(소스별 URL·신뢰도),  
      `missing_sources`(타임아웃·실패로 미도달한 소스 배열), `used_models`
    - 소스별 신뢰도·`fetched_at` 표기, 근거 없는 내용 생성 금지(환각 차단)
  - API 계층 [기준] — FastAPI 기본(비동기·스트리밍 적합), 변경 필요 시 사용자 문의
    - `POST /search`: 질의 입력 → 부분 결과 스트리밍(SSE), 최종 Structured Output 반환
    - `GET /health`: 상태 점검
    - 실행 방식 [고정]: UI 스트리밍+병렬 도구 호출이므로 LCEL 비동기 스트리밍(astream) 사용
  - 세션·기술 요구사항
    - 세션 체크포인트 [고정]: MemorySaver(InMemory) / SqliteSaver(로컬파일) 중 사용자 선택
    - 프롬프트는 시스템/유저 프롬프트 명확히 분리 [고정]
    - API Key는 `.env`에서 로드, Config와 소스 분리
    - 수집 데이터에 `fetched_at` 메타데이터 기록, 신선도 필터(6개월)는 이 필드 기준 적용
- 테스트 및 버그 수정
  - pytest, 모듈별 단위 테스트. 외부 API(LLM·웹·YouTube·Neo4j·Chroma·Cohere)는 Mock/fixture로 대체
  - 실제 호출 테스트는 integration 마커로 분리
- 검색 품질 평가 (§3.7)
  - `datasets/testset-rag.jsonl`·`testset-graphrag.jsonl`로 RAGAS(Context Recall·Precision,  
    Faithfulness·Answer Relevancy) 측정, GraphRAG Local 질의는 NDCG를 별도 계산
  - 평가 리포트에 지표별 실측값 기록(회귀 비교 가능하게 버전·일시 포함)
- README.md 작성
  - 개요(목적·주요 기능), 가상환경 설정·실행, MAS 그래프 구성 Mermaid, 디렉토리 구조·주요 소스 설명
  - 멀티 LLM 라우팅 정책과 선택 근거, GraphRAG 검색 모드 선택 규칙 기록
- 출력파일: 검색 서비스 코드, 리트리버·크롤러 코드, FastAPI 진입점, eval-report.json, README.md
- 톤앤매너: 코드 주석·문서는 명사체, 실행 로그는 단계·처리 건수·선택 경로(라우팅·검색 모드)를 명확히 표기
- 작성 규칙:
  - 시스템/유저 프롬프트 분리, 합성·요약 태스크는 Structured Output 사용
  - 의존성은 requirements.txt에 정의
  - 인덱스·수집 결과에 실재하는 근거만 답변에 사용 — 추측 생성 금지

[출력]
- 통합 검색 서비스: `app/search/` (LangGraph MAS, ReAct 에이전트, 노드·State 정의)
- 공통 모듈: `app/common/` (`.env` 로더, 멀티 LLM 라우터, 공통 스키마, 로깅)
- API 진입점: `app/main.py` (FastAPI, `POST /search` SSE 스트리밍, `GET /health`)
- 코드 리트리버: `rag/retriever/`
- 교재 GraphRAG 리트리버: `kg/retriever/`
- 수집 파이프라인: `crawler/web/`, `crawler/youtube/`
- 평가 리포트: `datasets/eval-report.json` (RAGAS 지표별 값·GraphRAG Local NDCG 실측값)
- 실행 문서: `app/README.md`
- 의존성: `requirements.txt`

[제약조건]
- MUST: context7 MCP로 LangChain·LangGraph·FastAPI·Chroma·Neo4j·Cohere 최신 API 확인 후 구현
- MUST: 코드 인덱스 청크 ID·메타데이터 계약을 `indexing-code.md`와 일치,  
  교재 인덱스 엔티티·관계·청크 스키마를 `indexing-textbook.md`와 일치
- MUST: 멀티 LLM(Claude/OpenAI/Gemini) 연동 및 태스크별 라우팅 정책을 config로 관리하고 README에 근거 기록
- MUST: `.env`로 키 관리, Config·소스 분리.  
  README 가상환경 활성화는 Windows GitBash·Windows PowerShell·Linux/Mac별 명령어 안내
- MUST: 추가정보·의사결정 필요 시(체크포인터 선택, Neo4j 접속정보, API 프레임워크 변경) 사용자에게 문의
- MUST NOT: 인덱스·수집 결과에 없는 개념·코드·출처를 추측으로 답변에 포함
- 완료조건 — 검증 가능한 증거 기준
  - FastAPI 기동 로그와 `GET /health` 200 응답 확인
  - 샘플 질의 최소 3건의 `POST /search` 실행 로그(요청→4종 소스 병렬 검색→합성 응답) 첨부,  
    각 응답에 `summary`·`code_examples`·`sources` 필드 존재 확인
  - RAGAS 실측 점수표(지표별 값)와 GraphRAG Local NDCG 실측값을 `eval-report.json`으로 첨부
  - pytest 실행 로그(실패 0건) 첨부
  - `app/`·`rag/retriever/`·`kg/retriever/`·`crawler/` 산출 파일 목록 제시

[예시]
(POST /search 최종 Structured Output 응답 — 4종 소스 통합)
```json
{
  "query": "LangGraph로 상태 공유하는 멀티 에이전트 어떻게 만들어요?",
  "summary": "StateGraph에 노드를 등록하고 State(Reducer)로 노드 간 데이터를 공유함. compile 후 astream으로 실행함.",
  "code_examples": [
    {"lang":"python","code":"graph = StateGraph(State)...","explain":"State/Reducer로 상태 공유","source":"rag:examples/langgraph/state_graph.py#build_state_graph#12"}
  ],
  "sources": [
    {"type":"textbook","ref":"ent_state_graph","score":0.91},
    {"type":"code","ref":"code_042","score":0.88},
    {"type":"web","url":"https://...","fetched_at":"2026-07-16T00:00:00Z","score":0.72},
    {"type":"youtube","url":"https://youtu.be/...","fetched_at":"2026-07-16T00:00:00Z","score":0.65}
  ],
  "missing_sources": [],
  "used_models": {"routing":"groq/gpt-oss-120b","code_synthesis":"claude-sonnet-5"}
}
```
(라우팅·부분결과 로그 예 — 검색 모드·선택 경로·타임아웃 가시화)
```
[query] "state 공유 에이전트" → rewrite="LangGraph StateGraph 상태 공유 멀티 에이전트 예제"
[react] fanout: code_search(top5) | textbook_search(mode=Local) | web_search(6mo) | youtube_search
[timeout] youtube_search 5s 초과 → skip (missing_sources=[youtube])
[rerank] cohere: 24→8 chunks   [synthesis] model=claude-sonnet-5
```
