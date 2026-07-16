# 예제 코드 Vector DB 인덱싱 파이프라인 개발 프롬프트

[목표]
Agentic AI 예제 코드를 함수·클래스 단위로 청킹·임베딩하여 유사도 검색용 Chroma Vector DB로 구축하는  
인덱싱 파이프라인을 개발함.

[역할]
당신은 코드 검색 스타트업 백엔드 엔지니어 경력 6년의 검색엔진(Vector DB) 엔지니어이며,  
Pinecone/Milvus 기반 대규모 코드 임베딩 운영과 임베딩 품질·검색 지연(latency) 트레이드오프 튜닝에 능함.

[맥락]
- 내 상황: code-finder는 학습자 질문에 맞는 예제 코드를 제공해야 함. 코드는 자연어와 임베딩 특성이 달라  
  함수·클래스 경계 기반 청킹과 코드 특화 전처리가 필요함. 검색 튜닝·회귀 테스트의 기준이 될 안정적 인덱스가 없음.
- 결과물 독자: 검색엔진(Vector DB) 엔지니어(벡터), Retriever 개발자, 오케스트레이터(클로니)
- 후속 연계: 본 인덱스는 `prompts/testset-rag.md`가 참조하는 청크 ID·메타데이터의 출처가 됨

[입력]
- 인덱싱 대상 코드: `~/workspace/aistudy/hands-on/*` (Agentic AI 예제 코드, 하위 디렉토리 재귀 수집)
- 관련 교재(선택): `~/workspace/aistudy/agentic-ai/textbook/*.md` — 코드 설명 보강용, 앞단 아젠다만 참조
- 개발 가이드: `references/dev-prompt-guide_v2.md` §3.1·§3.2·§3.4·§3.9
- API Key: `.env` 파일 참조 (OpenAI)

[처리]
- 앱 개발
  - 워크플로우
    - 코드 파일 수집 → 언어 판별 → 함수·클래스 경계 청킹 → 임베딩 전처리 → 임베딩 → Chroma 적재 → 인덱싱 리포트
  - 수집 규칙 [기준]
    - 가상환경·패키지 캐시·빌드 산출물(`.venv`·`node_modules`·`__pycache__`·`dist` 등) 제외
    - 실행 코드가 아닌 콘텐츠 데이터 파일은 경로 글로브로 제외  
      (예: `explain/data.js` — 예제 설명 페이지 콘텐츠 데이터로 검색 결과 편중 유발. `--exclude` 옵션으로 패턴 추가)
    - 빈 파일·초대형 파일(미니파이·데이터 덤프) 스킵, 파일 내용 해시로 증분 판별
  - 청킹 규칙 [고정]
    - 청킹 사이즈 500토큰, 오버랩 100토큰
    - 구분자: 코드 파일은 함수·클래스 경계 우선(언어별 스플리터), 미지원 언어만 문자 기준 분할로 폴백
    - 함수·클래스 경계 밖 모듈 레벨(top-level) 코드도 `<module>` 세그먼트로 수집  
      (절차형 스크립트 예제 누락 방지 — 실제 예제 다수가 함수로 감싸지 않은 스크립트임)
    - 단일 심볼이 청킹 사이즈 초과 시 언어 스플리터로 하위 분할하되 심볼 메타데이터 유지
    - 언어별 처리: Python은 AST로 심볼·시그니처·라인 정밀 추출, JS/TS는 언어 스플리터+정규식으로  
      심볼 best-effort 추출(미확인 시 `<module>`), `.ipynb`는 코드 셀 추출(매직 `%`·셸 `!` 라인 주석화)
  - 임베딩 전처리 [고정]
    - 각 청크 앞에 `함수 시그니처 + 독스트링 + 파일 경로`를 프리픽스로 결합한 뒤 임베딩
  - 임베딩 [고정]: OpenAI `text-embedding-3-large`
  - 저장 [고정]: Chroma DB에 영속화, 청크별 메타데이터 부여
    - 메타데이터: `chunk_id`, `path`, `lang`, `symbol`(함수/클래스명), `signature`, `start_line`, `end_line`, `indexed_at`
    - `chunk_id`는 재현 가능한 결정적 규칙으로 생성 (예: `{상대경로}#{symbol}#{start_line}`, 충돌 시 접미로 유일화)
    - Chroma upsert는 최대 배치 상한(약 5,461) 미만으로 분할 적재(초과 시 InternalError 발생)
  - 기술적 요구사항
    - API Key는 `.env`에서 로드, Config와 소스 분리
    - 실행 전 API Key 유효성 사전 검증(최소 1건 임베딩 호출)으로 무효 키(401)를 조기 차단
    - 배치 처리이므로 비동기 임베딩(`aembed_documents`) 사용, 배치·동시성 제한·지수 백오프 재시도 적용
    - 재시도 정책: 429·타임아웃·5xx만 재시도, 인증(401)·잘못된 요청(400)은 즉시 실패(재시도 무의미)
    - 증분 인덱싱 지원: 파일 해시 비교로 변경분만 갱신, 삭제 파일 청크는 컬렉션에서 제거
    - 산출물 경로(매니페스트·리포트)는 store 디렉토리 기준으로 파생하여 테스트 격리 보장  
      (통합 테스트가 실제 인덱스를 오염하지 않도록 함)
- 테스트 및 버그 수정
  - pytest, 모듈별 단위 테스트, OpenAI/Chroma 호출은 Mock/fixture로 대체, 실제 호출은 integration 마커로 분리
- README.md 작성
  - 개요, 가상환경 설정·실행, 파이프라인 구성 Mermaid, 디렉토리 구조·주요 소스 설명
- 출력파일: 인덱서 코드, chroma 스토어, index-report.json, README.md
- 톤앤매너: 코드 주석·문서는 명사체, 실행 로그는 진행 단계·처리 건수를 명확히 표기
- 작성 규칙:
  - 시스템/유저 프롬프트 분리, 요약·설명 태스크 시 Structured Output 사용
  - 의존성은 requirements.txt에 정의
  - 인덱스에 실재하는 코드만 적재 — 추측 생성 금지

[출력]
- 인덱서 코드: `rag/indexer/`
- 벡터 스토어: `rag/store/chroma/` (Chroma 영속 디렉토리)
- 인덱싱 리포트: `rag/store/index-report.json` (파일 수·청크 수·언어 분포·소요시간)
- 청크 매니페스트: `rag/store/chunks-manifest.jsonl` (청크별 메타데이터 — `testset-rag.md` 대조용)
- 증분 매니페스트: `rag/store/file-manifest.json` (파일 해시·청크 ID)
- 실행 문서: `rag/README.md`

[제약조건]
- MUST: context7 MCP로 LangChain·Chroma·OpenAI 임베딩 최신 API 확인 후 구현
- MUST: 청크 메타데이터에 `chunk_id`·`path`·`symbol`을 포함하여 `testset-rag.md`의 `gt_chunk_ids`와 대조 가능하게 함
- MUST: `.env`로 키 관리, Config·소스 분리, 실행 전 키 유효성 사전 검증
- MUST: 실행 코드가 아닌 콘텐츠 데이터 파일(예: `explain/data.js`)은 인덱싱에서 제외
- MUST NOT: 인덱스에 없는 코드·심볼을 메타데이터에 임의 기입
- 완료조건 — 검증 가능한 증거 기준
  - API Key 유효성 사전 검증 통과(무효 키면 즉시 중단·보고)
  - 인덱서 실행 로그: 처리 파일 수·생성 청크 수 출력 확인
  - `rag/store/chroma/`에 영속 파일 생성, 컬렉션 count > 0 을 실행 로그 외 독립 조회로 재확인
  - 샘플 질의 3건으로 top-5 검색 결과가 반환되고, 콘텐츠 데이터가 아닌 실제 예제 코드(심볼)가  
    상위에 노출됨을 확인
  - pytest 실행 로그(실패 0건, 단위+통합) 첨부

[예시]
(청크 임베딩 입력 텍스트 — 시그니처+독스트링+경로 프리픽스 결합 형태)
```
# path: examples/langgraph/state_graph.py
# signature: def build_state_graph(tools: list) -> StateGraph
# doc: 도구 목록을 받아 StateGraph를 구성하고 컴파일하여 반환함
def build_state_graph(tools):
    ...
```
(Chroma 메타데이터 레코드)
{"chunk_id":"examples/langgraph/state_graph.py#build_state_graph#12","path":"examples/langgraph/state_graph.py","lang":"python","symbol":"build_state_graph","signature":"def build_state_graph(tools: list) -> StateGraph","start_line":12,"end_line":41,"indexed_at":"2026-07-16T00:00:00Z"}
