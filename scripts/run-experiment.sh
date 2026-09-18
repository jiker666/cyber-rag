#!/usr/bin/env bash
# 运行 D/E4 对照实验(基于 KB4 评测综合知识库 + 数据集1, 与 E1 基线同配置)
# 用法: run-experiment.sh [all|d|e4|poll <taskId>]   默认 all
#   d    仅运行混合检索实验; e4 仅运行重排实验
#   poll 对已存在的任务轮询到底并导出 CSV/指标
set -euo pipefail
cd "$(dirname "$0")/.."

MODE=${1:-all}

TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | sed -E 's/.*"token":"([^"]+)".*/\1/')
AUTH="Authorization: Bearer $TOKEN"

wait_task() {  # $1 task id
  local status completed total failed
  for i in $(seq 1 120); do
    sleep 5
    st=$(curl -s "http://localhost:8080/api/evaluation/tasks/$1/summary" -H "$AUTH" \
      | python3 -c "
import json,sys
d=json.load(sys.stdin)['data']
t=d.get('task') or {}
print(t.get('status'), t.get('completed'), t.get('total'), t.get('failed'))")
    read -r status completed total failed <<< "$st"
    echo "  [$i] status=$status completed=$completed/$total failed=$failed"
    if [ "$status" = "COMPLETED" ] || [ "$status" = "FAILED" ]; then break; fi
  done
  [ "$status" = "COMPLETED" ] || { echo "  任务未完成: $status, 终止后续步骤"; exit 1; }
}

export_task() {  # $1 task id  导出 CSV + 打印汇总指标
  curl -s "http://localhost:8080/api/evaluation/tasks/$1/export" -H "$AUTH" \
    -o "docs/experiments/eval_task_${1}.csv"
  echo "  csv saved: docs/experiments/eval_task_${1}.csv"
  curl -s "http://localhost:8080/api/evaluation/tasks/$1/summary" -H "$AUTH" \
    | python3 -c "
import json,sys
d=json.load(sys.stdin)['data']
m=d.get('metrics') or (d.get('task') or {}).get('metrics') or {}
for k in ('retrievalHitRate','precisionAtK','recallAtK','mrr','answerKeywordAccuracy','citationValidity','avgRetrievalTimeMs','avgTotalTimeMs'):
    v=m.get(k)
    print(f'  {k}: {v if v is None else round(v,4)}')"
}

run_task() {  # $1 name $2 strategy $3 reranker
  local id
  id=$(curl -s -X POST http://localhost:8080/api/evaluation/tasks \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"name\":\"$1\",\"mode\":\"RAG_LLM\",\"knowledgeBaseId\":4,\"datasetId\":1,
         \"topK\":5,\"retrievalStrategy\":\"$2\",\"enableReranker\":$3}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['id'] if d['code']==0 else d)")
  echo "task id: $id ($1)"
  wait_task "$id"
  export_task "$id"
}

case "$MODE" in
  d)    run_task "混合检索实验-Hybrid-KB4" "hybrid" "false" ;;
  e4)   run_task "重排实验-Reranker-KB4" "vector" "true" ;;
  poll) wait_task "$2"; export_task "$2" ;;
  *)    echo "== Experiment D: 混合检索(hybrid) vs 向量基线 =="
        run_task "混合检索实验-Hybrid-KB4" "hybrid" "false"
        echo
        echo "== Experiment E4: 向量+Reranker vs 向量基线 =="
        run_task "重排实验-Reranker-KB4" "vector" "true" ;;
esac
