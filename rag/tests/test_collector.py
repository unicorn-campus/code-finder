"""collector 단위 테스트: 수집 필터·언어판별·해시."""

from __future__ import annotations

from pathlib import Path

from indexer.collector import compute_sha256, iter_code_files
from indexer.config import Settings


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_collect_filters_excluded_dirs_and_types(tmp_path: Path) -> None:
    base = tmp_path / "hands-on"
    _write(base / "a.py", "print('a')\n")
    _write(base / "sub" / "b.js", "console.log('b')\n")
    _write(base / ".venv" / "lib.py", "print('venv')\n")  # 제외
    _write(base / "node_modules" / "x.js", "x\n")  # 제외
    _write(base / "readme.md", "# doc\n")  # 미지원 확장자
    _write(base / "big.min.js", "var a=1;\n")  # 접미사 제외

    settings = Settings(base_dir=base)
    records = list(iter_code_files(settings))
    rels = sorted(r.rel_path for r in records)

    assert rels == ["a.py", "sub/b.js"]
    langs = {r.rel_path: r.lang for r in records}
    assert langs["a.py"] == "python"
    assert langs["sub/b.js"] == "javascript"


def test_sha256_matches_content(tmp_path: Path) -> None:
    base = tmp_path / "hands-on"
    content = "def f():\n    return 1\n"
    _write(base / "a.py", content)
    settings = Settings(base_dir=base)
    rec = next(iter(iter_code_files(settings)))
    assert rec.sha256 == compute_sha256(content.encode("utf-8"))


def test_excludes_explain_data_js_by_default(tmp_path: Path) -> None:
    base = tmp_path / "hands-on"
    _write(base / "03.summary/kobart/explain/data.js", "export const x = 1;\n")  # 제외 대상
    _write(base / "03.summary/kobart/app.py", "print('app')\n")  # 유지
    _write(base / "explain/data.js", "top level\n")  # 접미 매칭 제외
    settings = Settings(base_dir=base)
    rels = sorted(r.rel_path for r in iter_code_files(settings))
    assert rels == ["03.summary/kobart/app.py"]


def test_custom_exclude_glob(tmp_path: Path) -> None:
    base = tmp_path / "hands-on"
    _write(base / "keep.py", "print('keep')\n")
    _write(base / "drop/skip.py", "print('drop')\n")
    settings = Settings(base_dir=base, exclude_globs=("drop/skip.py",))
    rels = sorted(r.rel_path for r in iter_code_files(settings))
    assert rels == ["keep.py"]


def test_skips_empty_and_oversized(tmp_path: Path) -> None:
    base = tmp_path / "hands-on"
    _write(base / "empty.py", "")
    _write(base / "big.py", "x = 1\n" * 200_000)  # max_file_bytes 초과
    settings = Settings(base_dir=base)
    assert list(iter_code_files(settings)) == []
