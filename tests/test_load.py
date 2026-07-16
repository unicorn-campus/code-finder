"""load 노드 단위 테스트 — 파일 로드·정렬·source 보존."""
from kg.indexer.config.settings import Settings
from kg.indexer.nodes.load import _source_name, load_documents, load_node


def _settings(glob_pattern: str) -> Settings:
    s = Settings()
    s.textbook_glob = glob_pattern
    return s


def test_source_name():
    assert _source_name("/x/14.GraphRAG.md") == "14.GraphRAG"


def test_load_documents_sorted(tmp_path):
    (tmp_path / "02.b.md").write_text("B", encoding="utf-8")
    (tmp_path / "01.a.md").write_text("A", encoding="utf-8")
    docs = load_documents(_settings(str(tmp_path / "*.md")))
    assert [d["source"] for d in docs] == ["01.a", "02.b"]
    assert docs[0]["text"] == "A"


def test_load_node_limit_chapters(tmp_path):
    for i in range(3):
        (tmp_path / f"0{i}.c.md").write_text("x", encoding="utf-8")
    out = load_node({"limit_chapters": 2}, _settings(str(tmp_path / "*.md")))
    assert len(out["raw_docs"]) == 2
    assert out["log"] and "로드" in out["log"][0]
