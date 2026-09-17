"""Chunk 切分测试: 大小/重叠/页码/全局编号。"""
from app.document.parser import DocumentPage
from app.rag.chunker import chunk_pages, chunk_text


def test_chunk_size_respected():
    text = "这是一个很长的网络安全知识文档。" * 60  # 约 960 字
    chunks = chunk_pages([DocumentPage(text=text, page=1)], chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(len(c.content) <= 100 for c in chunks)


def test_overlap_exists():
    text = "第一句话讲SQL注入原理。第二句话讲防御措施。第三句话讲代码示例。" * 5
    chunks = chunk_pages([DocumentPage(text=text, page=1)], chunk_size=50, chunk_overlap=10)
    if len(chunks) >= 2:
        # 相邻 Chunk 应存在重叠(至少一个字符相同片段)
        assert any(
            chunks[i].content[-5:] and chunks[i].content[-5:] in chunks[i + 1].content[:30]
            or chunks[i + 1].content[:5] in chunks[i].content[-30:]
            for i in range(len(chunks) - 1)
        ) or len(chunks) == 1


def test_page_number_preserved():
    pages = [
        DocumentPage(text="第一页内容 " * 40, page=1),
        DocumentPage(text="第二页内容 " * 40, page=2),
    ]
    chunks = chunk_pages(pages, chunk_size=100, chunk_overlap=10)
    assert {c.page for c in chunks} == {1, 2}


def test_global_chunk_index():
    pages = [DocumentPage(text=f"第{i}页 " * 30, page=i) for i in range(1, 4)]
    chunks = chunk_pages(pages, chunk_size=60, chunk_overlap=10)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_invalid_params():
    import pytest

    with pytest.raises(ValueError):
        chunk_pages([DocumentPage(text="x", page=1)], chunk_size=0)
    with pytest.raises(ValueError):
        chunk_pages([DocumentPage(text="x", page=1)], chunk_size=100, chunk_overlap=100)


def test_chunk_text_no_page():
    chunks = chunk_text("SQL注入是一种常见的Web安全漏洞。", chunk_size=20, chunk_overlap=5)
    assert all(c.page is None for c in chunks)
    assert len(chunks) >= 1
