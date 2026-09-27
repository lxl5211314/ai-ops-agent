import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.chunking import chunk_text, extract_keywords  # noqa: E402


def test_chunk_text_by_heading():
    text = "# 标题A\n\n" + "甲" * 900 + "\n\n# 标题B\n\n短内容"
    chunks = chunk_text(text)
    assert chunks
    headings = {h for h, _ in chunks}
    assert "标题A" in headings
    assert any("标题B" in h for h in headings)


def test_chunk_text_empty():
    assert chunk_text("   ") == []


def test_extract_keywords_mixed():
    kws = extract_keywords("服务 response 变慢 timeout 如何排查")
    assert any(k.lower() == "response" for k in kws)
    assert any("服务" in k or "变慢" in k for k in kws)


def test_locate_finds_buggy_file():
    from services.bug_analysis import locate

    root = Path(__file__).resolve().parents[1] / "fixtures" / "sample-bug-project"
    results = locate(root, "登录 KeyError token 缺失")
    assert results
    assert results[0]["file"] == "app.py"
