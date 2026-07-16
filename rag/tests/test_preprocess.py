"""preprocess 단위 테스트: 임베딩 프리픽스 결합."""

from __future__ import annotations

from indexer.chunker import Chunk
from indexer.preprocess import build_embed_text


def test_prefix_contains_path_signature_doc() -> None:
    text = 'def foo(a):\n    """Foo 요지 설명."""\n    return a\n'
    chunk = Chunk(
        path="pkg/m.py", lang="python", symbol="foo",
        signature="def foo(a)", start_line=1, end_line=3, text=text,
    )
    out = build_embed_text(chunk)
    assert "# path: pkg/m.py" in out
    assert "# signature: def foo(a)" in out
    assert "# doc: Foo 요지 설명." in out
    assert out.rstrip().endswith("return a")


def test_module_chunk_has_path_only_prefix() -> None:
    chunk = Chunk(
        path="m.py", lang="python", symbol="<module>",
        signature="", start_line=1, end_line=2, text="x = 1\ny = 2\n",
    )
    out = build_embed_text(chunk)
    assert out.startswith("# path: m.py")
    assert "# signature:" not in out
