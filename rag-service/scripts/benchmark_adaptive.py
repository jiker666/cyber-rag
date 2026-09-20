#!/usr/bin/env python3
"""Adaptive RAG 性能基准: 真实调用 rag-service 流式接口, 采集延迟分解/TTFT/门控/缓存指标。

用法:
    .venv/bin/python scripts/benchmark_adaptive.py [--rounds N] [--configs A,B,C,D_nocache,D_cache]
    环境变量: RAG_SERVICE_URL(默认 http://127.0.0.1:8000), RAG_INTERNAL_TOKEN

设计口径(与论文 E5/性能实验对齐):
- 固定知识库/数据集/LLM/Embedding/temperature, 仅切换检索配置;
- 走 /api/chat/stream(与前端一致), 服务端 trace 为权威计时(TTFT=llmTtftMs);
- retrieval_ms = trace.vectorSearchMs+bm25SearchMs+fusionMs+rerankMs+embeddingMs(检索总开销);
- P50/P95 为最近邻秩法(ceil(0.95n)), 小样本下如实记录, 不外推;
- 诚实原则: 只记录真实观测值。某配置失败时该行记 error, 汇总排除, 绝不造数。

输出(docs/experiments/):
- benchmark_adaptive_runs.csv    逐请求明细
- benchmark_adaptive_summary.csv 配置级汇总(P50/P95/激活率/缓存命中率)
"""
import argparse
import csv
import json
import math
import os
import statistics
import sys
import time
import urllib.request

BASE_URL = os.environ.get("RAG_SERVICE_URL", "http://127.0.0.1:8000")
TOKEN = os.environ.get("RAG_INTERNAL_TOKEN", "")

# 与 MySQL evaluation_dataset=1(网络安全问答基准集, 15 题)一一对应, 基准独立运行不依赖 DB。
# 该集全部为复杂题(概念/流程/对比), 与 E5 质量实验同口径。
QUESTIONS_EVAL15 = [
    "什么是 SQL 注入?如何防御?",
    "MyBatis 中 #{} 和 ${} 的区别是什么?",
    "XSS 有哪几种类型?分别如何防御?",
    "CSRF 攻击的原理是什么?有哪些防御手段?",
    "SSRF 是什么?云环境中最典型的危害是什么?",
    "JWT 常见的安全风险有哪些?",
    "文件上传功能有哪些安全风险?如何防范?",
    "BOLA 和 BFLA 的区别是什么?",
    "为什么不能使用 MD5 存储密码?应该用什么?",
    "RAG 系统的完整流程是什么?",
    "Java 反序列化漏洞的原理是什么?",
    "Spring Boot 项目有哪些常见安全加固措施?",
    "如何安全地配置 CORS?",
    "OWASP API Security Top 10 中排名第一的风险是什么?",
    "防止路径穿越攻击的正确做法是什么?",
]

# 真实聊天负载(性能基准主口径): 简单事实 6 + 精确实体 3 + 复杂 6。
# 评测集 15 题无简单事实/实体题, FAST/EXACT 路径永不触发, 无法反映路由收益;
# 性能目标(P50/激活率)应在贴近真实问答流量的混合负载上度量。
# 实体题锚点取自 KB4 文档实际出现的标识符: CWE-352(CSRF)/CWE-918(SSRF)/CWE-502(反序列化)。
QUESTIONS_MIXED = [
    # 简单事实(期望 FACTUAL → FAST: 向量 Top-3 直出, 高置信跳过 BM25/重排)
    "什么是 CSRF 攻击?",
    "SSRF 是什么意思?",
    "JWT 由哪几部分组成?",
    "BOLA 是什么漏洞?",
    "RAG 是什么技术?",
    "什么是路径穿越?",
    # 精确实体(期望 EXACT_ENTITY → EXACT: BM25 精确优先 + 实体加权)
    "CWE-352 对应什么攻击?如何防御?",
    "CWE-918 是什么漏洞?",
    "CWE-502 反序列化漏洞怎么防御?",
    # 复杂(期望 CONCEPT/PROCEDURAL → HYBRID + 门控)
    "MyBatis 中 #{} 和 ${} 的区别是什么?",
    "XSS 有哪几种类型?分别如何防御?",
    "BOLA 和 BFLA 的区别是什么?",
    "Spring Boot 项目有哪些常见安全加固措施?",
    "文件上传功能有哪些安全风险?如何防范?",
    "Java 反序列化漏洞的原理是什么?",
]
QUESTION_SETS = {"eval15": QUESTIONS_EVAL15, "mixed": QUESTIONS_MIXED}

# 基准知识库 = 评测综合知识库(与 E5 实验同一 KB, 20 篇文档)
KB_ID = int(os.environ.get("BENCH_KB_ID", "4"))

# E5 四配置 + 缓存开启变体。参数名与 rag-service ChatRequest 字段一致。
CONFIGS: dict[str, dict] = {
    # A: 纯向量 Top-5(基线)
    "A_vector_top5": {"retrievalStrategy": "vector", "adaptive": False},
    # B: 混合检索 Top-5(无重排)
    "B_hybrid_top5": {"retrievalStrategy": "hybrid", "adaptive": False},
    # C: 混合检索 + 固定重排(质量上界参照)
    "C_hybrid_rerank": {"retrievalStrategy": "hybrid", "adaptive": False, "enableReranker": True},
    # D: Adaptive RAG, 缓存关闭(E5 对比实验口径, 测真实检索开销)
    "D_adaptive_nocache": {"adaptive": True, "useCaches": False},
    # D 变体: Adaptive + 缓存开启(第二遍为热缓存, 观测命中率与延迟收益)
    "D_adaptive_cache": {"adaptive": True, "useCaches": True},
}
# 缓存配置跑两遍: pass1 冷缓存 / pass2 热缓存, 汇总按 pass 分行。
WARMUP_PASSES = {"D_adaptive_cache": 2}


def sse_stream(payload: dict):
    """POST /api/chat/stream, 逐事件 yield; 异常时抛出(调用方记 error, 不造数)。"""
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/chat/stream", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Internal-Token": TOKEN},
    )
    events = []
    with urllib.request.urlopen(req, timeout=300) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            try:
                events.append(json.loads(line[5:].strip()))
            except json.JSONDecodeError:
                continue
    return events


def run_one(question: str, cfg: dict) -> dict:
    """单次流式问答 → 从 done.trace 提取性能字段。"""
    payload = {
        "question": question, "knowledgeBaseIds": [KB_ID], "topK": 5, "temperature": 0.3, **cfg,
    }
    client_start = time.perf_counter()
    events = sse_stream(payload)
    wall_ms = int((time.perf_counter() - client_start) * 1000)
    done = next((e for e in events if e.get("type") == "done"), None)
    if done is None:
        raise RuntimeError("流结束但缺少 done 事件(可能中途 error)")
    tr = done["result"]["trace"]
    retrieval_ms = (tr["embeddingMs"] + tr["vectorSearchMs"] + tr["bm25SearchMs"]
                    + tr["fusionMs"] + tr["rerankMs"])
    return {
        "route": tr["route"], "query_type": tr["queryType"],
        "retrieval_ms": retrieval_ms,
        "embedding_ms": tr["embeddingMs"], "vector_ms": tr["vectorSearchMs"], "bm25_ms": tr["bm25SearchMs"],
        "fusion_ms": tr["fusionMs"], "rerank_ms": tr["rerankMs"], "ctx_build_ms": tr["contextBuildMs"],
        "ttft_ms": tr["llmTtftMs"], "generation_ms": tr["generationMs"], "total_ms": tr["totalMs"],
        "wall_ms": wall_ms,
        "reranker_used": tr["rerankerUsed"], "emb_cache": tr["embeddingCacheHit"],
        "retr_cache": tr["retrievalCacheHit"],
        "ctx_tokens": tr["contextTokens"], "final_chunks": tr["finalContextCount"],
        "candidates": tr["candidateCount"],
    }


def pct_nearest_rank(values: list[float], p: float) -> int:
    """最近邻秩法分位数: 排序后取第 ceil(p*n) 个(向上取整保证保守)。"""
    if not values:
        return -1
    s = sorted(values)
    k = max(1, math.ceil(p * len(s)))
    return int(s[k - 1])


def summarize(rows: list[dict]) -> dict:
    def col(name): return [r[name] for r in rows]

    routes: dict[str, int] = {}
    for r in rows:
        routes[r["route"] or "-"] = routes.get(r["route"] or "-", 0) + 1
    return {
        "n": len(rows),
        "retrieval_p50": pct_nearest_rank(col("retrieval_ms"), 0.50),
        "retrieval_p95": pct_nearest_rank(col("retrieval_ms"), 0.95),
        "ttft_p50": pct_nearest_rank(col("ttft_ms"), 0.50),
        "ttft_p95": pct_nearest_rank(col("ttft_ms"), 0.95),
        "total_p50": pct_nearest_rank(col("total_ms"), 0.50),
        "total_p95": pct_nearest_rank(col("total_ms"), 0.95),
        "rerank_rate": round(statistics.fmean(col("reranker_used")), 4),
        "emb_cache_rate": round(statistics.fmean(col("emb_cache")), 4),
        "retr_cache_rate": round(statistics.fmean(col("retr_cache")), 4),
        "avg_ctx_tokens": round(statistics.fmean(col("ctx_tokens")), 1),
        "routes": " ".join(f"{k}x{v}" for k, v in sorted(routes.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=1, help="每配置重复轮数(默认 1)")
    ap.add_argument("--configs", type=str, default=",".join(CONFIGS), help="逗号分隔配置名")
    ap.add_argument("--limit", type=int, default=0, help="仅跑前 N 题(0=全部; 快速验证用)")
    ap.add_argument("--questions", type=str, default="both", choices=["eval15", "mixed", "both"],
                    help="题集: eval15=评测集同款(全复杂题) / mixed=真实聊天负载(简单+实体+复杂) / both")
    args = ap.parse_args()

    if not TOKEN:
        print("缺少 RAG_INTERNAL_TOKEN 环境变量", file=sys.stderr)
        return 2
    names = [n.strip() for n in args.configs.split(",") if n.strip() in CONFIGS]
    set_names = list(QUESTION_SETS) if args.questions == "both" else [args.questions]

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "docs", "experiments")
    out_dir = os.path.normpath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    for set_name in set_names:
        questions = QUESTION_SETS[set_name][: args.limit] if args.limit else QUESTION_SETS[set_name]
        suffix = "" if len(set_names) == 1 else f"_{set_name}"
        runs_path = os.path.join(out_dir, f"benchmark_adaptive_runs{suffix}.csv")
        summary_path = os.path.join(out_dir, f"benchmark_adaptive_summary{suffix}.csv")
        _run_set(set_name, questions, names, runs_path, summary_path)
    return 0


def _run_set(set_name: str, questions: list[str], names: list[str],
             runs_path: str, summary_path: str) -> None:
    """跑一个题集 × 全部配置, 写 runs/summary 两个 CSV。"""
    run_rows: list[dict] = []
    summaries: list[dict] = []
    for name in names:
        passes = WARMUP_PASSES.get(name, 1)
        for p in range(1, passes + 1):
            tag = f"{name}/pass{p}" if passes > 1 else name
            rows = []
            for i, q in enumerate(questions, 1):
                try:
                    row = run_one(q, CONFIGS[name])
                    row.update({"config": name, "pass": p, "question": q, "error": ""})
                    rows.append(row)
                    print(f"[{tag}] {i:2d}/{len(questions)} {q[:24]:26s} route={row['route']:8s} "
                          f"retr={row['retrieval_ms']:4d}ms ttft={row['ttft_ms']:6d}ms "
                          f"total={row['total_ms']:6d}ms rerank={'Y' if row['reranker_used'] else 'N'} "
                          f"ctx={row['ctx_tokens']}tok", flush=True)
                except Exception as e:  # 失败如实记录, 不中断整个基准
                    print(f"[{tag}] {i:2d}/{len(questions)} ERROR: {e}", flush=True)
                    run_rows.append({"config": name, "pass": p, "question": q, "error": str(e)})
            if rows:
                s = summarize(rows)
                s.update({"config": tag})
                summaries.append(s)
                print(f"[{tag}] 汇总: retrieval P50/P95={s['retrieval_p50']}/{s['retrieval_p95']}ms "
                      f"total P50/P95={s['total_p50']}/{s['total_p95']}ms "
                      f"rerank率={s['rerank_rate']:.0%} 缓存(emb/retr)={s['emb_cache_rate']:.0%}/{s['retr_cache_rate']:.0%} "
                      f"ctx={s['avg_ctx_tokens']}tok routes={s['routes']}", flush=True)
            # 成功样本明细统一入 run_rows(error 行已在循环内直接 append)
            run_rows.extend(rows)

    # 统一落盘(成功与失败行都写入 runs; 汇总只含成功样本)
    fieldnames = ["config", "pass", "question", "route", "query_type", "retrieval_ms", "embedding_ms",
                  "vector_ms", "bm25_ms", "fusion_ms", "rerank_ms", "ctx_build_ms", "ttft_ms",
                  "generation_ms", "total_ms", "wall_ms", "reranker_used", "emb_cache", "retr_cache",
                  "ctx_tokens", "final_chunks", "candidates", "error"]
    with open(runs_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in run_rows:
            w.writerow(r)
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
        cols = ["config", "n", "retrieval_p50", "retrieval_p95", "ttft_p50", "ttft_p95",
                "total_p50", "total_p95", "rerank_rate", "emb_cache_rate", "retr_cache_rate",
                "avg_ctx_tokens", "routes"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(summaries)
    print(f"\n已写出: {runs_path}\n已写出: {summary_path}")


if __name__ == "__main__":
    sys.exit(main())
