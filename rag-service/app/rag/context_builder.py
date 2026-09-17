"""上下文构造: 将检索片段编号拼装进 Prompt, 支撑引用溯源。"""
from app.rag.retriever import RetrievedChunk


def build_context(chunks: list[RetrievedChunk], max_chars: int = 8000) -> str:
    """构造带编号的知识上下文, 编号与 sources 返回顺序一致(引用即 [n])。

    总长度超限时从尾部截断, 保证 Prompt 不超过模型上下文。
    """
    parts: list[str] = []
    used = 0
    for idx, chunk in enumerate(chunks, start=1):
        source_line = f"[{idx}] 来源: {chunk.source}"
        if chunk.page is not None:
            source_line += f", 第 {chunk.page} 页"
        block = f"{source_line}\n{chunk.content}"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)
