
# 프롬프트 개발 요청 수행 가이드 
## 섹션별 필수 포함 항목 
### '[입력]'섹션 
- 관련 교재 추가: `~/workspace/aistudy/agentic-ai/textbook/*.md` 교재 앞단의 아젠다만 보고 개발에 필요한 정보 추출 

### '[처리]' 섹션 골격
- 앱 개발
  - 워크플로우
  - 기술적 요구사항
    - API Key: `.env` 파일 참조
    - Config와 소스 분리
- 테스트 및 버그 수정
- README.md 작성
  - 개요: 목적 및 주요 기능
  - 가상환경 설정 및 실행
  - Graph 구성 가시화: Mermaid 스크립트 사용
  - 디렉토리 구조와 주요 소스 설명

### '[제약조건]' 섹션 
- MUST
  - 프롬프트 작성 가이드 준용
  - 반드시 "context7 MCP" 사용
  - 반드시 의존성을 requirements.txt에 정의
  - README.md의 가상환경 활성화는 Window GitBash, Window PowerShell, Linux/Mac별로 명령어 안내
  - 추가정보나 의사결정이 필요하면 사용자에게 반드시 문의 
- MUST NOT
  - 추측하여 생성하지 말고 데이터에 기반하여 수행
- 완료조건
  - 모든 출력물 생성 완료
  - 테스트 통과
  - 정상 결과 확인

---

## LangChain 사용
- 프롬프트는 시스템 프롬프트와 유저 프롬프트 명확히 분리
- MemorySaver로 노드간 데이터 공유와 트랜잭션 분리
- LCEL 체인 사용. 실행은 동기/비동기/동기스트리밍/비동기스트리밍 중 최적안 선택하여 적용
- Output Parser 대신 Structured Output 사용
- LangGraph로 단일 MAS 워크플로우 구현 

## Tool 인터페이스
  - create_agent 함수로 ReAct 루프 구현 

## RAG/GraphRAG 공통
- Pre Techniques 적용: Query Rewriting, Multi Query, Hyde, Step-back 중 최적안을 조합하여 적용
- Post Technique 적용: Re-ranking (모델은 Cohere 리랭킹 모델 사용)

## RAG
- Indexer
  - 인덱싱 대상 코드: `~/workspace/aistudy/hands-on/*`
  - 임베딩 모델: `OpenAI text-embedding-3-large`
  - 청킹 사이즈 500, 오버랩 사이즈 100
  - 구분자는 소스 파악 후 최적안으로 결정
  - VectorDB는 Chroma DB 사용
- Retriever
  - 하이브리드 서치: BM25 + Vector DB. 가중치는 0.4/0.6으로 함
  - 벡터DB 서치타입: mmr, top-k: 5, fetch-k: 10 

## GraphRAG
- 개발 프레임워크: LangChain + Neo4j
- Indexer  
  - 대상 소스: `~/workspace/aistudy/agentic-ai/textbook/*.md` 
  - 비동기 병렬 수행, Entity Types 제한
- Retriever
  - Local, Global, Hybrid 중 Query에 따라 최적안 선택 

## Web서치
- DuckDuckGo + BeautfulSoup
- 최근 6개월 데이터만 검색
- 최대 결과수: 10

## YouTube 서치
- 영상검색: 
  - YouTube Data API
  - 최근 6개월 + 조회수 최소 1000개 이상인 영상만 검색
  - 최대 결과수: 10
- 자막 로드
  - YouTubeLoader 사용   

## LLM
- Groq LPU 사용
- 모델은 OpenAI gpt-oss-120b

## 개발 디렉토리
- 프론트엔드: `front/`
- 백엔드: `app/{service}`, `app/common/` 
- RAG: `rag/indexer`, `rag/retriever`, `rag/store`
- GraphRAG: `kg/indexer`, `kg/retriver`, `kg/store`
