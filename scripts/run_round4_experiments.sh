#!/usr/bin/env bash
# =====================================================================
# 第四轮实验驱动: 顺序提交 E5 对比 / 消融 / 小到大评测任务。
#
# 评测执行器单线程(backend evalExecutor pool=1), 但提交后仍逐个等待完成,
# 保证全程无并发 LLM 调用——延迟与 token 统计不被互相干扰。
# 数据集固定 evaluation_dataset=1(15 题), KB4(20 篇文档), topK=5, temperature=0.3。
# 小到大实验: KB5=256 / KB4=512(复用 E5-A) / KB6=1024 / KB7=parent-child。
#
# 用法: bash scripts/run_round4_experiments.sh [--phase all|e5|ablation|s2l|r]
#   all      首次全量(E5 4 任务 + 消融 4 + 小到大 3)
#   e5       仅 E5 四配置
#   ablation 仅消融四组
#   s2l      仅小到大三组
#   r        断点重跑: E5-D + 消融 + 小到大(E5-A/B/C 已完成时用)
# 建议 nohup + caffeinate -is 包裹执行, 防止机器睡眠导致 LLM 调用批量超时
# (2026-09-18 首跑: 任务 18/19 因宿主机睡眠大面积超时作废, 以重跑任务为准)。
# 产出: evaluation_task 表任务记录, 前端"评测任务"可查看/导出 CSV。
# =====================================================================
set -uo pipefail

BASE=http://127.0.0.1:8080/api
DATASET=1
LOG=docs/experiments/round4_driver.log
PHASE="${1:---phase}"
[ "$PHASE" = "--phase" ] && PHASE="${2:-all}"
case "$PHASE" in
  all|e5|ablation|s2l|r) ;;
  *) echo "未知 phase: $PHASE (all|e5|ablation|s2l|r)"; exit 1 ;;
esac

TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["token"])')
[ -z "$TOKEN" ] && { echo "登录失败"; exit 1; }

run_task() { # $1=name $2=kb $3..=额外 JSON 片段
  local name=$1 kb=$2; shift 2
  local extra="$*"
  local body="{\"name\":\"$name\",\"mode\":\"RAG_LLM\",\"datasetId\":$DATASET,\"knowledgeBaseId\":$kb,\"topK\":5,\"temperature\":0.3${extra}}"
  local id
  id=$(curl -s -X POST $BASE/evaluation/tasks -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' -d "$body" \
    | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["data"]["id"] if d["code"]==0 else "")')
  if [ -z "$id" ]; then echo "[$(date +%H:%M:%S)] 提交失败: $name" | tee -a "$LOG"; return 1; fi
  echo "[$(date +%H:%M:%S)] task#$id 已提交: $name" | tee -a "$LOG"
  while :; do
    sleep 20
    local st
    st=$(curl -s "$BASE/evaluation/tasks" -H "Authorization: Bearer $TOKEN" \
      | python3 -c "import sys,json;ts=json.load(sys.stdin)['data'];print(next((t['status'] for t in ts if t['id']==$id),'GONE'))")
    case $st in
      COMPLETED) echo "[$(date +%H:%M:%S)] task#$id COMPLETED: $name" | tee -a "$LOG"; return 0 ;;
      FAILED|GONE) echo "[$(date +%H:%M:%S)] task#$id $st: $name (继续)" | tee -a "$LOG"; return 1 ;;
    esac
  done
}

cd "$(dirname "$0")/.." || exit 1

run_e5() {
  run_task "E5-A-向量Top5-KB4"        4 ',"retrievalStrategy":"vector","adaptive":false'
  run_task "E5-B-混合Top5-KB4"        4 ',"retrievalStrategy":"hybrid","adaptive":false'
  run_task "E5-C-混合重排Top5-KB4"    4 ',"retrievalStrategy":"hybrid","enableReranker":true,"adaptive":false'
  run_task "E5-D-Adaptive无缓存-KB4"  4 ',"retrievalStrategy":"hybrid","adaptive":true,"useCaches":false'
}

run_ablation() {
  # 消融(相对 Adaptive Full 各关一模块; -Cache 即 E5-D 口径, 不单列)
  run_task "消融-Full全开"        4 ',"adaptive":true,"useCaches":true,"entityBoost":true,"rerankGating":true,"dynamicContext":true'
  run_task "消融-无实体加权"      4 ',"adaptive":true,"useCaches":true,"entityBoost":false'
  run_task "消融-无门控重排"      4 ',"adaptive":true,"useCaches":true,"rerankGating":false,"enableReranker":true'
  run_task "消融-无动态上下文"    4 ',"adaptive":true,"useCaches":true,"dynamicContext":false'
}

run_s2l() {
  # 小到大(E5-A 即 KB4=512 口径, 不重跑)
  run_task "小到大-Chunk256-KB5"       5 ',"retrievalStrategy":"vector","adaptive":false'
  run_task "小到大-Chunk1024-KB6"      6 ',"retrievalStrategy":"vector","adaptive":false'
  run_task "小到大-ParentChild-KB7"    7 ',"retrievalStrategy":"vector","adaptive":false'
}

case "$PHASE" in
  e5)       run_e5 ;;
  ablation) run_ablation ;;
  s2l)      run_s2l ;;
  # 断点重跑: 任务 18(E5-D 3/15)/19(Full 0/15) 因宿主机睡眠作废, 20+ 未提交
  r)        run_task "E5-D重跑-Adaptive无缓存-KB4" 4 ',"retrievalStrategy":"hybrid","adaptive":true,"useCaches":false'
            run_ablation; run_s2l ;;
  all)      run_e5; run_ablation; run_s2l ;;
esac

echo "[$(date +%H:%M:%S)] 全部实验任务完成 (phase=$PHASE)" | tee -a "$LOG"
