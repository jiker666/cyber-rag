#!/usr/bin/env bash
# =====================================================================
# 第四轮实验结果收集: 拉取 E5/消融/小到大任务的汇总指标 + 导出逐题 CSV。
# 前置: run_round4_experiments.sh 已跑完(或部分跑完, 只收集已完成任务)。
# 产出:
#   docs/experiments/eval_task_<id>.csv     逐题原始数据(含 route/rerankUsed/contextTokens)
#   终端打印汇总表(粘入 docs/thesis/06-实验设计.md E5 节)
# =====================================================================
set -uo pipefail
BASE=http://127.0.0.1:8080/api
cd "$(dirname "$0")/.." || exit 1

TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["token"])')
[ -z "$TOKEN" ] && { echo "登录失败"; exit 1; }

# 1. 导出已完成任务的逐题 CSV
for id in $(mysql -uroot --protocol=tcp -h127.0.0.1 -N cyber_rag \
  -e "SELECT id FROM evaluation_task WHERE id>=15 AND status='COMPLETED' ORDER BY id" 2>/dev/null); do
  curl -s "http://127.0.0.1:8080/api/evaluation/tasks/$id/export" \
    -H "Authorization: Bearer $TOKEN" -o "docs/experiments/eval_task_$id.csv"
  echo "已导出 eval_task_$id.csv ($(wc -l < docs/experiments/eval_task_$id.csv) 行)"
done

# 2. 汇总表: 任务名 + 关键指标(metrics JSON 展开)
echo
mysql -uroot --protocol=tcp -h127.0.0.1 cyber_rag -e "
SELECT t.id,
       t.name,
       t.status,
       CONCAT(t.completed,'/',t.total) AS done,   -- 18/19 因宿主机睡眠大面积超时, 数据失效仅供参考
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"retrievalHitRate\"'))      AS hit,
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"precisionAtK\"'))          AS p_at_k,
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"recallAtK\"'))             AS r_at_k,
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"ndcgAtK\"'))               AS ndcg,
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"mrr\"'))                   AS mrr,
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"answerKeywordAccuracy\"')) AS kw,
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"citationValidity\"'))      AS cite,
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"rerankActivationRate\"'))  AS rerank_rate,
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"avgContextTokens\"'))      AS ctx_tok,
       ROUND(JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"avgRetrievalTimeMs\"'))/1000,2) AS retr_s,
       ROUND(JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"avgTotalTimeMs\"'))/1000,2)     AS total_s,
       JSON_UNQUOTE(JSON_EXTRACT(t.metrics,'$.\"avgTotalTokens\"'))        AS tokens
FROM evaluation_task t WHERE t.id>=15 ORDER BY t.id\G" 2>/dev/null

# 3. 自适应任务的路由分布(逐题 route 计数)
echo "== 路由分布(自适应任务) =="
mysql -uroot --protocol=tcp -h127.0.0.1 cyber_rag -e "
SELECT task_id, route, COUNT(*) n FROM evaluation_result
WHERE task_id>=15 AND route IS NOT NULL AND route<>'' GROUP BY task_id, route ORDER BY task_id" 2>/dev/null
