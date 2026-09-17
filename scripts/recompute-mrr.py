#!/usr/bin/env python3
"""回填历史评测任务的 MRR 指标(第二轮新增指标, 适用于已完成任务)。

依据: evaluation_result.sources 存有每次检索的真实排序结果(JSON, 按相关度降序),
      evaluation_item.expected_source 为人工标注的期望来源文档。
算法: MRR = 1 / first_rank(expected_source in sources), 未命中记 0。

自校验: 对已有 MRR 的任务(如混合检索实验)重算, 与落库值比对, 不一致则中止。
说明: 仅补算指标, 不改动任何答案/来源/时间等原始数据。
"""
import json
import os
import sys

import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k] = v
    return env


def item_mrr(sources_json, expected):
    chunks = json.loads(sources_json) if sources_json else []
    for rank, c in enumerate(chunks, 1):
        if c.get('source') == expected:
            return round(1.0 / rank, 4)
    return 0.0


def main():
    env = load_env(os.path.join(ROOT, '.env'))
    conn = pymysql.connect(host=env['MYSQL_HOST'], port=int(env['MYSQL_PORT']),
                           user=env['MYSQL_USER'], password=env['MYSQL_PASSWORD'],
                           database=env['MYSQL_DATABASE'], charset='utf8mb4')
    cur = conn.cursor()
    cur.execute("""SELECT id, mode, metrics FROM evaluation_task
                   WHERE deleted=0 AND status='COMPLETED' ORDER BY id""")
    for task_id, mode, metrics_json in cur.fetchall():
        if mode != 'RAG_LLM':
            continue
        cur.execute("""SELECT r.id, r.item_id, r.sources, r.mrr FROM evaluation_result r
                       WHERE r.task_id=%s AND r.deleted=0""", (task_id,))
        rows = cur.fetchall()
        recomputed = []
        for rid, iid, sources, stored in rows:
            cur.execute("SELECT expected_source FROM evaluation_item WHERE id=%s", (iid,))
            expected = cur.fetchone()[0]
            recomputed.append((rid, item_mrr(sources, expected), stored))
        agg = round(sum(v for _, v, _ in recomputed) / len(recomputed), 4) if recomputed else None

        metrics = json.loads(metrics_json) if metrics_json else {}
        stored_agg = metrics.get('mrr')

        if stored_agg is not None and abs(stored_agg - agg) > 1e-6:
            print(f'!! task {task_id}: 自校验失败 stored={stored_agg} recomputed={agg}, 中止')
            sys.exit(1)

        if all(stored is not None for _, _, stored in recomputed) and stored_agg is not None:
            print(f'task {task_id}: mrr 已存在且一致 ({agg}), 跳过')
            continue

        for rid, v, stored in recomputed:
            if stored is None:
                cur.execute("UPDATE evaluation_result SET mrr=%s WHERE id=%s", (v, rid))
        metrics['mrr'] = agg
        cur.execute("UPDATE evaluation_task SET metrics=%s WHERE id=%s",
                    (json.dumps(metrics, ensure_ascii=False), task_id))
        conn.commit()
        print(f'task {task_id}: mrr 回填完成, 聚合={agg}')
    conn.close()


if __name__ == '__main__':
    main()
