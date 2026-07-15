# 교재 GraphRAG 인덱서 개발 프롬프트

[목표]
Agentic AI 학습 교재(마크다운)를 개념(엔티티)·관계(엣지)·원문 청크로 정제하여 Neo4j 지식그래프로  
적재하는 GraphRAG 인덱서(Indexer)를 개발함. 이후 검색·평가 단계가 소비할 KG 인덱스 산출이 목표임.

[역할]
당신은 LangChain + Neo4j 기반 GraphRAG 인덱싱 파이프라인 구축 경력 8년의 지식그래프 아키텍트입니다.  
비정형 교재 텍스트를 개념-관계 스키마로 정제하는 데 능하며, 근거 없는 엔티티·관계는 절대 승인하지 않습니다.

[맥락]
- 내 상황: code-finder는 교재 검색을 GraphRAG(개념·관계 탐색)로 구축함. 검색·평가(`testset-graphrag.md`)를  
  수행하려면 그 입력이 되는 지식그래프 인덱스가 먼저 있어야 하나, 현재 인덱서가 없어 KG가 비어 있음.  
  단순 키워드 검색과 달리 멀티홉·연관 탐색을 지원하려면 개념 간 관계까지 명시적으로 적재해야 함.
- 결과물 독자: GraphRAG 아키텍트(그래프), 검색엔진 엔지니어, 오케스트레이터(클로니).  
  이 인덱서의 산출물은 검색 Retriever와 회귀 평가 스크립트가 그대로 소비함.

[입력]
- 인덱싱 대상 교재: `~/workspace/aistudy/agentic-ai/textbook/*.md`  
  (AI 앱 개요·멀티턴·RAG·GraphRAG·MCP·MAS 등 16개 장 구성. 개발 필요 정보는 각 장 앞단 아젠다·용어집에서 추출)
- 개념 용어집: `~/workspace/aistudy/agentic-ai/textbook/glossary/glossary.json`  
  (약 957개 도메인 용어. 엔티티 타입 후보·정규화 사전으로 활용)
- 프롬프트 작성 가이드: `references/prompt-guide.md`, `references/dev-prompt-guide_v2.md`
- 후속 소비처(참조): `prompts/testset-graphrag.md`  
  (본 인덱서의 엔티티 ID·관계 ID·청크 ID를 정답 기준으로 사용하므로 ID 체계를 안정적으로 유지)
- 샘플 청크·엔티티 후보를 프롬프트에 직접 임베딩할 때는 아래 태그로 감쌀 것

<textbook_sample>
{교재 청크 또는 엔티티·관계 후보 목록을 여기에 붙여넣기}
</textbook_sample>

[처리]
- 앱 개발 (GraphRAG 인덱싱 파이프라인)
  - 워크플로우: LangGraph 단일 워크플로우로 아래 노드를 구성, 노드 간 데이터는 StateGraph의 State(Reducer)로 공유
    - load: `textbook/*.md` 로드 — 파일명(장 번호·제목)을 source 메타데이터로 보존
    - split: 마크다운 헤더 기준 분할(헤더 경로를 청크 메타데이터로 유지) 후 청크 크기 보정  
      각 청크에 `chunk_id`(안정적·재현 가능한 규칙), `source`, `heading_path` 메타데이터 부여
    - extract: LLM으로 엔티티·관계 추출 — LangChain `LLMGraphTransformer` 사용, 비동기 병렬 수행  
      허용 엔티티/관계 타입(allowed_nodes/allowed_relationships)으로 추출 범위를 제한
    - load_graph: `Neo4jGraph`로 적재 — 원문 청크 노드 + 엔티티 노드 + MENTIONS·개념 간 관계 엣지  
      원문 소스 포함(include_source), 엔티티 기본 라벨 부여(baseEntityLabel)로 청크↔엔티티 역추적 보장
    - community: 커뮤니티 탐지(Louvain/Leiden 등) 후 커뮤니티별 LLM 요약을 생성·적재  
      (주제 요약형 Global 검색 지원용 인덱싱 단계)
    - verify: 노드·엣지·커뮤니티 통계 집계 및 청크↔엔티티 매핑 무결성 검증
  - 기술적 요구사항
    - 프레임워크: LangChain + Neo4j(그래프 저장·조회), LangGraph(파이프라인 오케스트레이션)
    - LLM: Groq LPU, 모델 OpenAI gpt-oss-120b — 엔티티·관계 추출 및 커뮤니티 요약에 사용  
      기본 파라미터: temperature 0(재현성 우선), timeout 30초, 429 응답 시 지수 백오프 재시도 2회
    - 프롬프트는 시스템 프롬프트와 유저 프롬프트를 명확히 분리
    - 추출 결과는 Output Parser 대신 Structured Output(스키마 강제)으로 수신
    - 엔티티/관계 타입 제한: 교재 샘플 청크와 용어집에서 후보를 추출한 뒤 사용자 검토로 확정하고 설정 파일로 관리  
      (엔티티 예: 개념·기법·도구/라이브러리·모델·프레임워크 / 관계 예: 확장·사용·선행·구성요소·대안)
    - 세션 체크포인트(중단 복구·재개)용 Saver는 MemorySaver(InMemory)·SqliteSaver(로컬파일) 중 사용자 선택 적용
    - Local 검색용 엔티티·청크 벡터 인덱스 생성 여부·임베딩 모델은 확정 전 사용자 문의  
      (프로젝트 표준 후보: `OpenAI text-embedding-3-large`)
    - API Key: `.env` 파일 참조, Config(모델·타입 목록·Neo4j 접속정보)와 소스 코드를 분리
    - 재실행 시 중복 적재 방지(멱등성): 동일 `chunk_id`·엔티티는 MERGE 기준으로 갱신
- 테스트 및 버그 수정
  - 프레임워크: pytest, 모듈별 단위 테스트 작성(로더·스플리터·추출·적재·검증 각각)
  - 외부 API(LLM)·Neo4j 호출은 Mock/fixture로 대체, 실제 호출 테스트는 integration 마커로 분리
- README.md 작성
  - 개요: 목적 및 주요 기능(교재→지식그래프 인덱싱)
  - 가상환경 설정 및 실행 방법
  - 그래프 파이프라인 구성 가시화: Mermaid 스크립트로 노드 흐름 표현
  - 디렉토리 구조와 주요 소스 설명, 엔티티/관계 타입 설정 파일 위치·수정 방법
- 톤앤매너: 코드 주석·문서는 명사체, 로그는 단계·건수를 수치로 명시
- 작성 규칙:
  - 한국어로 문서·주석 작성
  - 엔티티/관계 타입 목록은 코드가 아닌 설정 파일에서 로드(하드코딩 금지)

[출력]
- 인덱서 소스: `kg/indexer/`
- 그래프 스토어 연동·스키마: `kg/store/`
- 엔티티/관계 타입 설정 파일(예: `kg/indexer/config/graph_schema.yaml` 또는 동등물)
- 의존성 정의: `requirements.txt`
- 실행·구조 안내: `kg/indexer/README.md`

[제약조건]
- MUST
  - 프롬프트 작성 가이드(`references/prompt-guide.md`) 준용
  - 반드시 "context7 MCP" 사용 — LangChain GraphRAG·Neo4j·LangGraph 최신 API 사양 확인 후 구현
  - 반드시 의존성을 `requirements.txt`에 정의
  - README.md의 가상환경 활성화는 Windows GitBash, Windows PowerShell, Linux/Mac별로 명령어 안내
  - 엔티티/관계 타입 확정, 체크포인트 Saver 선택, 벡터 인덱스·임베딩 모델 등 의사결정이 필요하면 사용자에게 반드시 문의
  - 청크 ID·엔티티 ID 규칙은 `testset-graphrag.md` 정답과 일치하도록 안정적·재현 가능하게 정의
- MUST NOT
  - 추측하여 생성하지 말고 데이터(교재·용어집)에 기반하여 수행
  - 교재에 근거 없는 엔티티·관계를 그래프에 적재하지 않음
- 완료조건 (검증 가능한 증거 기준)
  - 모든 출력물 생성 완료: 산출 경로(`kg/indexer/`, `kg/store/`)의 파일 목록 제시
  - 테스트 통과: pytest 실행 로그(실패 0건) 첨부
  - 실제 인덱싱 확인: `textbook/*.md` 인덱싱 실행 로그와 Neo4j 노드·엣지·커뮤니티 건수(모두 0 초과) 첨부
  - 매핑 무결성 확인: 임의 엔티티→원문 청크 역추적 Cypher 조회 결과 최소 3건(요청→응답) 첨부

[예시]
- 엔티티/관계 타입 설정(발췌, 교재 도메인 기준):

<textbook_sample>
allowed_nodes: [Concept, Technique, Tool, Model, Framework]
allowed_relationships:
  - [Technique, EXTENDS, Technique]      # 예: ReAct EXTENDS Chain-of-Thought
  - [Concept, PREREQUISITE_OF, Concept]  # 예: Embedding PREREQUISITE_OF RAG
  - [Technique, USES, Tool]              # 예: GraphRAG USES Neo4j
  - [Concept, PART_OF, Framework]        # 예: StateGraph PART_OF LangGraph
</textbook_sample>

- 매핑 무결성 검증 Cypher(예):
  `MATCH (e:Concept {id:"ent_react"})<-[:MENTIONS]-(c:Document) RETURN c.chunk_id, c.source LIMIT 5`  
  → 기대 결과: `ent_react`를 언급하는 원문 청크 ID·출처 장 목록이 1건 이상 반환됨
