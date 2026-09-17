#!/usr/bin/env bash
# 运行 D/E4 实验: 混合检索 / Reranker 对照(基于 KB4 + 数据集1, 与 E1 基线同配置)
set -euo pipefail
cd "$(dirname "$0")/.."

TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | sed -E 's/.*"token":"([^"]+)".*/\1/')
AUTH="Authorization: Bearer $TOKEN"

run_task() {  # $1 name $2 strategy $3 reranker
  local id
  id=$(curl -s -X POST http://localhost:8080/api/evaluation/tasks \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"name\":\"$1\",\"mode\":\"RAG_LLM\",\"knowledgeBaseId\":4,\"datasetId\":1,
         \"topK\":5,\"retrievalStrategy\":\"$2\",\"enableReranker\":$3}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['id'] if d['code']==0 else d)")
  echo "task id: $id ($1)"
  for i in $(seq 1 120); do
    sleep 5
    st=$(curl -s http://localhost:8080/api/evaluation/tasks/$id/summary -H "$AUTH" \
      | python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print(d['status'], d['completed'], d['total'], d['failed'])")
    set -- $st
    echo "  [$i] status=$1 completed=$2/$3 failed=$4"
    [ "$1" = "COMPLETED" ] || [ "$1" = "FAILED" ] && break
  done
  curl -s "http://localhost:8080/api/evaluation/tasks/$id/export" -H "$AUTH" \
    -o "docs/experiments/eval_task_${id}.csv"
  echo "  csv saved: docs/experiments/eval_task_${id}.csv"
  curl -s http://localhost:8080/api/evaluation/tasks/$id/summary -H "$AUTH" \
    | python3 -c "
import json,sys
d=json.load(sys.stdin)['data']
m=d.get('metrics') or {}
for k in ('retrievalHitRate','precisionAtK','recallAtK','mrr','answerKeywordAccuracy','citationAccuracy','avgRetrievalTimeMs','avgTotalTimeMs'):
    v=m.get(k)
    print(f'  {k}: {v if v is None else round(v,4)}')"
}

echo "== Experiment D: 混合检索(hybrid) vs 向量基线 =="
run_task "混合检索实验-Hybrid-KB4" "hybrid" "false"
echo
echo "== Experiment E4: 向量+Reranker vs 向量基线 =="
run_task "重排实验-Reranker-KB4" "vector" "true"
