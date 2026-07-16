"""extract 노드 단위 테스트 — ID 정규화·관계 재배선·실패 분류·재시도(mock)."""
from langchain_core.documents import Document
from langchain_neo4j.graphs.graph_document import GraphDocument, Node, Relationship

from kg.indexer.config.settings import Settings
from kg.indexer.nodes.extract import _classify, extract_node, normalize_graph_document


def _sample_gd() -> GraphDocument:
    src = Document(page_content="txt", metadata={"id": "chunk_0", "chunk_id": "chunk_0"})
    a = Node(id="ReAct", type="Technique")
    b = Node(id="Chain-of-Thought", type="Technique")
    dup = Node(id="react", type="Technique")  # 대소문자만 다른 중복
    rel = Relationship(source=a, target=b, type="EXTENDS")
    return GraphDocument(nodes=[a, b, dup], relationships=[rel], source=src)


def _chunk(cid: str = "chunk_0") -> Document:
    return Document(page_content="t", metadata={"id": cid, "chunk_id": cid})


def test_normalize_ids_and_dedup():
    gd = normalize_graph_document(_sample_gd())
    ids = sorted(n.id for n in gd.nodes)
    assert ids == ["ent_chain_of_thought", "ent_react"]  # react/ReAct 병합
    assert all(n.properties.get("name") for n in gd.nodes)


def test_normalize_relationship_rewire_and_relid():
    gd = normalize_graph_document(_sample_gd())
    r = gd.relationships[0]
    assert r.source.id == "ent_react"
    assert r.target.id == "ent_chain_of_thought"
    assert r.properties["rel_id"] == "rel_react_extends_chain_of_thought"


def test_classify():
    assert _classify(Exception("Error code: 429 too many requests")) == "rate_limit"
    assert _classify(ValueError("RateLimit reached")) == "rate_limit"
    assert _classify(ValueError("bad structured output")) == "parse_error"


class _OkTransformer:
    async def aconvert_to_graph_documents(self, docs):
        return [_sample_gd()]


class _EmptyTransformer:
    async def aconvert_to_graph_documents(self, docs):
        return []


class _ErrTransformer:
    def __init__(self, msg="Error code: 429"):
        self.msg = msg
        self.calls = 0

    async def aconvert_to_graph_documents(self, docs):
        self.calls += 1
        raise RuntimeError(self.msg)


def test_extract_node_ok():
    s = Settings()
    out = extract_node({"chunks": [_chunk()]}, s, _OkTransformer())
    assert len(out["graph_documents"]) == 1
    assert out["empty_chunk_ids"] == []
    assert out["failures"] == []
    assert {n.id for n in out["graph_documents"][0].nodes} == {"ent_react", "ent_chain_of_thought"}


def test_extract_node_empty_not_failure():
    s = Settings()
    out = extract_node({"chunks": [_chunk("chunk_9")]}, s, _EmptyTransformer())
    assert out["graph_documents"] == []
    assert out["empty_chunk_ids"] == ["chunk_9"]   # 빈 추출은 실패가 아님
    assert out["failures"] == []


def test_extract_node_failure_classified_and_retried():
    s = Settings()
    t = _ErrTransformer("Error code: 429")
    out = extract_node({"chunks": [_chunk("chunk_5")]}, s, t)
    assert out["graph_documents"] == []
    assert len(out["failures"]) == 1
    assert out["failures"][0] == {"chunk_id": "chunk_5", "reason": "rate_limit",
                                  "detail": out["failures"][0]["detail"]}
    assert t.calls == 2  # 최초 1회 + 순차 재시도 1회
