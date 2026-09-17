"""文档解析与文件校验测试。"""
import pytest

from app.document.parser import DocumentPage, parse_document, validate_file


def _write(tmp_path, name, content: bytes):
    p = tmp_path / name
    p.write_bytes(content)
    return p


def test_parse_txt(tmp_path):
    p = _write(tmp_path, "安全规范.txt", "SQL 注入防御: 使用参数化查询。".encode("utf-8"))
    pages = parse_document(p, "安全规范.txt")
    assert len(pages) == 1
    assert "参数化查询" in pages[0].text
    assert pages[0].page is None


def test_parse_md(tmp_path):
    p = _write(tmp_path, "owasp.md", "# OWASP Top 10\n\nA01 失效的访问控制。".encode("utf-8"))
    pages = parse_document(p, "owasp.md")
    assert "OWASP" in pages[0].text


def test_parse_gb18030_txt(tmp_path):
    p = _write(tmp_path, "legacy.txt", "中文编码测试".encode("gb18030"))
    pages = parse_document(p, "legacy.txt")
    assert "中文编码测试" in pages[0].text


def test_rejects_dangerous_extension():
    with pytest.raises(Exception):
        validate_file("shell.jsp", 100)
    with pytest.raises(Exception):
        validate_file("payload.exe", 100)


def test_rejects_empty_file():
    with pytest.raises(Exception):
        validate_file("a.txt", 0)


def test_rejects_oversize():
    with pytest.raises(Exception):
        validate_file("a.txt", 100 * 1024 * 1024, max_size_mb=20)


def test_allows_supported_extensions():
    for ext in (".pdf", ".txt", ".md", ".docx"):
        assert validate_file(f"doc{ext}", 1024) == ext


def test_unknown_extension_parse(tmp_path):
    p = _write(tmp_path, "x.html", b"<html></html>")
    with pytest.raises(Exception):
        parse_document(p, "x.html")


def test_empty_document_rejected(tmp_path):
    p = _write(tmp_path, "empty.txt", b"   \n \n")
    with pytest.raises(Exception):
        parse_document(p, "empty.txt")
