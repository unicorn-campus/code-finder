# code-finder 프론트엔드(Vue 3) 개발 프롬프트

[목표]
학습자 질문 입력 화면과 4종 소스(교재·코드·웹·영상) 통합 검색 결과를 렌더링하는 Vue 3 기반  
프론트엔드 SPA를 개발함.

[역할]
당신은 마켓컬리 프론트엔드 개발자 경력 4년의 프론트엔드 개발자이며,  
Vue 3(Composition API)·Vite 기반 SPA 구축과 Google 검색 수준의 미니멀 결과 UX, 접근성·성능,  
로딩·부분결과 상태 설계에 능함.

[맥락]
- 내 상황: code-finder는 학습자 질문에 맞는 핵심 내용과 예제 코드를 한 화면에 제공해야 함.  
  백엔드 검색 파이프라인(GraphRAG·RAG·웹·유튜브 + 멀티 LLM)은 별도 개발 중이며, 학습자가 질문을  
  던지고 결과를 빠르게 스캔하는 단일 화면 UX가 없음. Google 검색의 단순함이 기준점임.
- 결과물 독자: 프론트엔드 개발자(미니멀), 서비스 기획자(브릿지), QA 엔지니어(체커), 오케스트레이터(클로니)
- 후속 연계: 백엔드 검색 API(`prompts/backend.md`에서 정의) 계약을 소비함.  
  계약 미확정 부분은 본 프롬프트 [예시]의 잠정 스펙과 mock으로 개발 후 확정 시 교체함

[입력]
- 백엔드 API 계약: `prompts/backend.md` (미완 시 본 프롬프트 [예시]의 잠정 API 스펙을 임시 계약으로 사용)
- UX 기준: `AGENTS.md`의 서비스 기획자·프론트엔드 persona (Google-like 단순함, 핵심 요약 → 코드 → 출처 순)
- 개발 가이드: `references/dev-prompt-guide_v2.md` §3.9, `references/prompt-guide.md` 8섹션 표준
- 관련 교재(선택): `~/workspace/aistudy/agentic-ai/textbook/*.md` — 도메인 용어·예시 질문 확보용, 앞단 아젠다만 참조
- 환경변수: `.env`의 `VITE_API_BASE_URL` (백엔드 검색 API base URL)

[처리]
- 앱 개발
  - 기술 스택 [고정]
    - Vue 3(Composition API, `<script setup>`) + TypeScript + Vite
    - 라우팅 Vue Router, 상태관리 Pinia
    - HTTP 통신은 표준 fetch 기반 api 모듈로 래핑
  - 워크플로우(화면 흐름)
    - 질문 입력 → 검색 요청 → 로딩/부분결과 → 통합 결과 카드 렌더 → 출처 이동
  - 화면 구성
    - 질문 입력 화면: 중앙 단일 검색창(Google-like), 예시 질문 칩, 엔터·버튼 검색,  
      LLM 선택 드롭다운(Claude/OpenAI/Gemini, 백엔드 지원 시 노출)
    - 결과 화면: 상단 질문 에코 → 핵심 요약 → 예제 코드(문법 하이라이트 + 복사 버튼) → 소스별 출처 카드
    - 소스별 출처 카드: 소스 유형 배지(교재/코드/웹/영상), 관련도·신뢰도 표시, 원문·영상 링크
    - 상태 처리: 로딩 스켈레톤, 부분결과 스트리밍(소스 도착 순 렌더), 빈 결과·에러·재시도 상태
  - 백엔드 연동 [기준]
    - 백엔드가 SSE 스트리밍 응답 → `fetch` 스트림/`EventSource`로 부분결과 순차 렌더
    - 백엔드가 단발 JSON 응답 → 일반 `fetch`로 일괄 렌더
    - 선택 결과와 근거를 README에 기록
  - 기술적 요구사항
    - API base URL 등 config는 `.env`(`VITE_` 접두)에서 로드, Config와 소스 분리
    - api 클라이언트·타입 정의 모듈화, 공통 에러 처리·요청 타임아웃(기본 30초) 적용
    - 접근성: 키보드 검색·포커스 관리, 결과 영역 `aria-live`로 부분결과 도착 안내
- 테스트 및 버그 수정
  - Vitest + Vue Test Utils로 컴포넌트·스토어 단위 테스트
  - 백엔드 호출은 MSW로 mock, 실제 호출·E2E(Playwright)는 integration 마커로 분리
- README.md 작성
  - 개요, 설치·실행(패키지 매니저 명시), 화면 흐름 Mermaid, 디렉토리 구조·주요 소스 설명
  - 실행 명령과 패키지 매니저를 별도 기재 (Node 설치 → 의존성 설치 → dev → build)
- 출력파일: Vue 프로젝트 소스, `package.json`, `.env.example`, `README.md`
- 톤앤매너: UI 문구·주석·문서는 명사체, 로딩·에러 문구는 학습자 눈높이의 짧은 안내문
- 작성 규칙:
  - 의존성은 `package.json`에 정의 (프론트엔드는 requirements.txt 대상 아님)
  - 실재하는 API 계약만 호출 — 미확정 계약은 mock + 주석으로 명시, 추측 확정 금지

[출력]
- 프론트엔드 프로젝트: `front/`
  - `front/src/views/` — 질문 입력 화면·결과 화면
  - `front/src/components/` — 검색창, 결과 카드, 코드 블록, 상태(스켈레톤/에러) 컴포넌트
  - `front/src/stores/` — Pinia 검색 상태 스토어
  - `front/src/api/` — 백엔드 검색 API 클라이언트·타입
  - `front/src/router/` — 라우트 정의
- 환경 예시: `front/.env.example`
- 실행 문서: `front/README.md`

[제약조건]
- MUST: context7 MCP로 Vue 3·Vite·Pinia·Vue Router 최신 API 확인 후 구현
- MUST: `.env`(`VITE_` 접두)로 API base URL 관리, 소스에 URL·키 하드코딩 금지
- MUST: 백엔드 검색 API 계약(`prompts/backend.md`)과 요청·응답 스키마를 일치시킴
- MUST: README의 실행 안내는 Windows GitBash·Windows PowerShell·Linux/Mac별 명령을 구분 기재
- MUST NOT: 프론트에서 Claude/OpenAI/Gemini LLM API Key를 직접 사용 — 백엔드 프록시만 호출
- MUST NOT: 추측으로 API 계약을 확정 — 미확정분은 mock + 주석 표기
- 완료조건 — 검증 가능한 증거 기준
  - dev 서버 기동 로그(`vite` dev) 확인
  - 샘플 질의 3건의 결과 화면 렌더를 스크린샷·로그로 확인 (핵심 요약·코드·출처 표시)
  - Vitest 실행 로그(실패 0건) 첨부
  - 프로덕션 빌드(`vite build`) 성공 로그 확인

[예시]
(잠정 검색 API 계약 — `backend.md` 확정 전 임시 사용)
```
POST /api/search
Request: {"query": "LangGraph에서 StateGraph 만드는 법", "llm": "claude"}
Response(SSE, event별 부분결과):
  event: summary  data: {"text": "StateGraph는 상태를 공유하는 그래프 실행 단위임 ..."}
  event: code     data: {"lang": "python", "code": "def build_state_graph(...):", "source_chunk_id": "code_042"}
  event: source   data: {"type": "textbook", "title": "...", "url": "...", "score": 0.82}
  event: source   data: {"type": "youtube", "title": "...", "url": "...", "score": 0.71}
  event: done     data: {}
```
(통합 결과 카드 렌더 순서)
```
[질문] LangGraph에서 StateGraph 만드는 법
─ 핵심 요약: 2 ~ 3문장 개념 설명
─ 예제 코드: python 블록(문법 하이라이트 + 복사 버튼)
─ 출처: 📘교재 · 💻코드 · 🌐웹 · ▶️영상 카드 (관련도순)
```
