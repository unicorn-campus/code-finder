/**
 * Mock SSE 스트림 — 백엔드 미기동 시 동일 계약 스키마로 테스트용 데이터 제공.
 * VITE_USE_MOCK=true일 때 활성화됨.
 * 3종 샘플 질의에 대해 서로 다른 결과를 반환함:
 *   1. "LangGraph StateGraph" — missing_sources 존재, 코드 1건
 *   2. "RAG 임베딩" — 코드 여러 건, missing 없음
 *   3. 기타 — 기본 결과
 */

import type { SearchAnswer, SseCallbacks } from './types'

interface MockScenario {
  answer: SearchAnswer
  /** 이벤트 방출 간 지연(ms) */
  delay: number
}

const SCENARIO_LANGGRAPH: MockScenario = {
  delay: 300,
  answer: {
    query: 'LangGraph에서 StateGraph 만드는 법',
    summary:
      'StateGraph는 LangGraph의 핵심 클래스로, 노드(함수)를 등록하고 State(TypedDict + Reducer)로 상태를 공유함. add_node()로 노드 등록, add_edge()로 연결 후 compile()로 실행 가능한 그래프 생성.',
    code_examples: [
      {
        lang: 'python',
        code: `from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from operator import add

class State(TypedDict):
    messages: Annotated[list[str], add]

def chatbot(state: State) -> dict:
    return {"messages": ["안녕하세요!"]}

graph = StateGraph(State)
graph.add_node("chatbot", chatbot)
graph.add_edge(START, "chatbot")
graph.add_edge("chatbot", END)
app = graph.compile()`,
        explain:
          'State를 TypedDict로 정의하고 Reducer(add)로 메시지 누적. chatbot 노드를 등록하고 START→chatbot→END로 연결 후 compile()로 실행 준비 완료.',
        source: 'examples/langgraph/state_graph.py#build_state_graph#12',
      },
    ],
    sources: [
      { type: 'textbook', ref: 'ent_state_graph', score: 0.91 },
      { type: 'code', ref: 'examples/langgraph/state_graph.py#build_state_graph#12', score: 0.88 },
      { type: 'web', url: 'https://langchain-ai.github.io/langgraph/', score: 0.72, fetched_at: '2026-07-16T00:00:00Z' },
    ],
    missing_sources: ['youtube'],
    used_models: { summary: 'claude-sonnet-4-20250514', code: 'claude-sonnet-4-20250514' },
  },
}

const SCENARIO_RAG: MockScenario = {
  delay: 250,
  answer: {
    query: 'RAG 임베딩 방법',
    summary:
      'RAG(Retrieval-Augmented Generation)에서 임베딩은 텍스트를 고차원 벡터로 변환하여 의미 기반 유사도 검색을 가능하게 함. OpenAI text-embedding-3-small, Cohere embed-v3 등 다양한 모델 사용 가능.',
    code_examples: [
      {
        lang: 'python',
        code: `from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(documents, embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})`,
        explain: 'OpenAI 임베딩 모델로 문서를 벡터화하고 Chroma에 저장. as_retriever()로 유사도 검색기 생성.',
        source: 'examples/rag/embedding_basic.py#setup_retriever#8',
      },
      {
        lang: 'python',
        code: `from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\\n\\n", "\\n", " "]
)
chunks = splitter.split_documents(documents)`,
        explain: '임베딩 전 문서를 청크로 분할. chunk_size와 overlap 설정으로 문맥 보존.',
        source: 'examples/rag/text_splitter.py#split_docs#5',
      },
      {
        lang: 'python',
        code: `# 코사인 유사도 기반 검색 예시
results = retriever.invoke("RAG 파이프라인 구성 방법")
for doc in results:
    print(f"[{doc.metadata.get('source', 'N/A')}] {doc.page_content[:100]}...")`,
        explain: 'invoke()로 질의 벡터와 가장 유사한 문서 청크 검색. 메타데이터에서 출처 확인 가능.',
        source: 'examples/rag/retrieval.py#search#3',
      },
    ],
    sources: [
      { type: 'textbook', ref: 'ent_rag_embedding', score: 0.95 },
      { type: 'code', ref: 'examples/rag/embedding_basic.py#setup_retriever#8', score: 0.92 },
      { type: 'code', ref: 'examples/rag/text_splitter.py#split_docs#5', score: 0.85 },
      { type: 'web', url: 'https://python.langchain.com/docs/concepts/embedding_models/', score: 0.78, fetched_at: '2026-07-16T00:00:00Z' },
      { type: 'youtube', url: 'https://youtu.be/example-rag-embed', score: 0.65, fetched_at: '2026-07-16T00:00:00Z' },
    ],
    missing_sources: [],
    used_models: { summary: 'gpt-4o', code: 'claude-sonnet-4-20250514' },
  },
}

const SCENARIO_DEFAULT: MockScenario = {
  delay: 200,
  answer: {
    query: '',
    summary:
      'Agentic AI는 자율적으로 도구를 호출하고 판단하는 AI 에이전트 패턴. ReAct(Reasoning+Acting), Plan-and-Execute, Multi-Agent 등 다양한 아키텍처가 존재함.',
    code_examples: [
      {
        lang: 'python',
        code: `from langchain.agents import create_react_agent, AgentExecutor
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")
agent = create_react_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
result = executor.invoke({"input": "서울 날씨 알려줘"})`,
        explain: 'ReAct 패턴 에이전트 생성. LLM이 도구 호출 여부를 판단하고 결과를 종합해 응답 생성.',
        source: 'examples/agents/react_agent.py#create_agent#10',
      },
    ],
    sources: [
      { type: 'textbook', ref: 'ent_agentic_ai', score: 0.82 },
      { type: 'web', url: 'https://www.anthropic.com/engineering/building-effective-agents', score: 0.75, fetched_at: '2026-07-16T00:00:00Z' },
    ],
    missing_sources: ['code', 'youtube'],
    used_models: { summary: 'gemini-2.5-flash', code: 'gemini-2.5-flash' },
  },
}

/** 질의 키워드로 시나리오 선택 */
function selectScenario(query: string): MockScenario {
  const q = query.toLowerCase()
  if (q.includes('langgraph') || q.includes('stategraph')) {
    return SCENARIO_LANGGRAPH
  }
  if (q.includes('rag') || q.includes('임베딩') || q.includes('embedding')) {
    return SCENARIO_RAG
  }
  const scenario = { ...SCENARIO_DEFAULT, answer: { ...SCENARIO_DEFAULT.answer, query } }
  return scenario
}

/** 지연 유틸 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Mock SSE 스트림 실행.
 * 실제 백엔드와 동일한 이벤트 순서(missing→source→summary→code→done)로 방출.
 * AbortSignal 지원.
 */
export async function executeMockStream(
  query: string,
  callbacks: SseCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const scenario = selectScenario(query)
  const { answer } = scenario
  const d = scenario.delay

  // 실제 query 반영
  const finalAnswer: SearchAnswer = { ...answer, query: query || answer.query }

  // missing
  await delay(d)
  if (signal?.aborted) return
  callbacks.onMissing(finalAnswer.missing_sources)

  // source(N)
  for (const src of finalAnswer.sources) {
    await delay(d * 0.5)
    if (signal?.aborted) return
    callbacks.onSource(src)
  }

  // summary
  await delay(d)
  if (signal?.aborted) return
  callbacks.onSummary(finalAnswer.summary)

  // code(N)
  for (const ce of finalAnswer.code_examples) {
    await delay(d * 0.7)
    if (signal?.aborted) return
    callbacks.onCode(ce)
  }

  // done
  await delay(d * 0.5)
  if (signal?.aborted) return
  callbacks.onDone(finalAnswer)
}
