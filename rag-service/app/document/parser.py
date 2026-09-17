"""文档文本提取: 支持 PDF / TXT / Markdown / DOCX。"""
import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import DocumentParseError

logger = logging.getLogger("cyber-rag.document.parser")

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".docx"}
MAX_FILE_SIZE_MB_DEFAULT = 20


@dataclass
class DocumentPage:
    """文档中的一页/一段原文; PDF 保留页码, 其他类型 page=None。"""

    text: str
    page: int | None = None


def validate_file(filename: str, file_size: int, max_size_mb: int = MAX_FILE_SIZE_MB_DEFAULT) -> str:
    """校验文件名与扩展名, 返回规范化扩展名; 防止非法类型与目录穿越。"""
    name = Path(filename).name  # 丢弃任何路径部分, 防目录穿越
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentParseError(f"不支持的文件类型: {ext or '(无扩展名)'}, 仅支持 pdf/txt/md/docx")
    if file_size <= 0:
        raise DocumentParseError("文件为空")
    if file_size > max_size_mb * 1024 * 1024:
        raise DocumentParseError(f"文件超过大小限制 {max_size_mb}MB")
    return ext


def parse_document(file_path: str | Path, filename: str) -> list[DocumentPage]:
    """根据扩展名分派解析器, 返回页/段列表。"""
    ext = Path(filename).suffix.lower()
    parsers = {
        ".pdf": _parse_pdf,
        ".txt": _parse_txt,
        ".md": _parse_md,
        ".markdown": _parse_md,
        ".docx": _parse_docx,
    }
    parser = parsers.get(ext)
    if parser is None:
        raise DocumentParseError(f"不支持的文件类型: {ext}")
    pages = parser(Path(file_path))
    pages = [p for p in pages if p.text and p.text.strip()]
    if not pages:
        raise DocumentParseError("未能从文档中提取到有效文本(可能为扫描件或空文档)")
    logger.info("解析文档 %s (%s): %d 个文本段", filename, ext, len(pages))
    return pages


def _parse_pdf(path: Path) -> list[DocumentPage]:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise DocumentParseError("pypdf 未安装, 无法解析 PDF") from e
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as e:
                raise DocumentParseError("PDF 已加密且无法解密") from e
        pages = []
        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(DocumentPage(text=text, page=idx))
        return pages
    except DocumentParseError:
        raise
    except Exception as e:
        logger.exception("PDF 解析异常: %s", path.name)
        raise DocumentParseError(f"PDF 解析失败: {e}") from e


def _parse_txt(path: Path) -> list[DocumentPage]:
    return _read_text_file(path)


def _parse_md(path: Path) -> list[DocumentPage]:
    return _read_text_file(path)


def _read_text_file(path: Path) -> list[DocumentPage]:
    """TXT/Markdown: 尝试常见编码, 整体作为一段。"""
    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise DocumentParseError(f"无法识别文件编码: {path.name}")
    return [DocumentPage(text=text, page=None)]


def _parse_docx(path: Path) -> list[DocumentPage]:
    try:
        from docx import Document as DocxDocument
    except ImportError as e:  # pragma: no cover
        raise DocumentParseError("python-docx 未安装, 无法解析 DOCX") from e
    try:
        doc = DocxDocument(str(path))
        # 按分页符分段, 否则整体一段
        segments: list[str] = []
        current: list[str] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            has_page_break = any("PAGE" in (run._element.xml or "") for run in para.runs)
            current.append(text)
            if has_page_break:
                segments.append("\n".join(current))
                current = []
        if current:
            segments.append("\n".join(current))
        if not segments:
            return [DocumentPage(text="", page=None)]
        return [DocumentPage(text=seg, page=i + 1) for i, seg in enumerate(segments)]
    except Exception as e:
        logger.exception("DOCX 解析异常: %s", path.name)
        raise DocumentParseError(f"DOCX 解析失败: {e}") from e
