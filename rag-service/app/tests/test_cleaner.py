"""文本清洗测试。"""
from app.document.cleaner import clean_text


def test_removes_control_characters():
    assert clean_text("hello\x00\x01world") == "helloworld"


def test_compresses_whitespace():
    assert clean_text("a    b\t\tc") == "a b c"


def test_removes_page_numbers():
    text = "正文内容\n- 12 -\n更多内容"
    cleaned = clean_text(text)
    assert "12" not in cleaned.split("正文内容")[1].split("更多内容")[0]
    assert "正文内容" in cleaned
    assert "更多内容" in cleaned


def test_removes_decoration_lines():
    text = "标题\n==========\n内容"
    cleaned = clean_text(text)
    assert "====" not in cleaned
    assert "标题" in cleaned and "内容" in cleaned


def test_compresses_blank_lines():
    assert clean_text("a\n\n\n\n\nb") == "a\n\nb"


def test_empty_and_none_safety():
    assert clean_text("") == ""
