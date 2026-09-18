# FINAL_AUDIT — 答辩前最终工程与论文一致性审计

> 审计日期: 2026-09-18。范围: 全仓配置一致性、评测指标学术口径、实验数据可溯源、
> 论文/README/前端/代码四方一致性、可复现性与演示闭环。
> 原则: **不新增功能; 不修改任何真实实验原始数据(CSV 一字未动); 指标口径变更保留旧口径记录。**

## 0. 最终验证结果

| 验证项 | 结果 |
|---|---|
| rag-service 全量 pytest | **77 passed**(20.4s, 离线 Fake 栈) |
| backend 全量 mvn test(JDK 21) | **39/39, BUILD SUCCESS** |
| frontend `npm run build`(vue-tsc + vite) | **通过**(5.26s) |
| 实验数据完整性 | `docs/experiments/eval_task_*.csv` 全部未修改(git diff 为空) |

---

## P0-1 全仓配置一致性

### 问题 1: docker-compose 与 README/.env.example 默认值互相矛盾
- **发现**: compose 中 rag 服务默认 `openai-compatible + text-embedding-3-small + 1536 维`,
  而 README/.env.example 声称默认本地 BGE; `LLM_PROVIDER`、`RERANKER_MODEL`、
  `RAG_RETRIEVAL_STRATEGY` 未透传; backend 健康检查探测的 `/api/health` 接口不存在
  (healthcheck 永远失败)。
- **修改**: `docker-compose.yml`(统一默认 local/BAAI/bge-m3/1024, 补齐
  LLM_PROVIDER/RERANKER_*/RAG_RETRIEVAL_STRATEGY/MAX_FILE_SIZE_MB/HF_ENDPOINT 透传,
  新增 `rag-models` 具名卷), `rag-service/Dockerfile`(非 root 用户预建 /app/models_cache),
  `.env.example`(注明论文实验用 bge-small-zh-v1.5/512 维, 维度须与远端模型一致)。
- **原因**: Docker 与本机启动必须得到同一系统。
- **验证**: 逐变量比对 compose/env/`config.py` 默认值; 新增 embedding 工厂别名测试。
- **数据影响**: 无(实验均在本机环境运行)。

### 问题 2: 上传大小上限三处定义、数值不一致
- **发现**: `Constants.MAX_FILE_SIZE_MB`(20, 已废弃常量)、Spring `@Value` 默认值、
  nginx `client_max_body_size 100m` 三处独立硬编码。
- **修改**: `DocumentServiceImpl` 改经 `AppProperties` 读取 `APP_UPLOAD_MAX_FILE_SIZE_MB`
  (compose 透传 MAX_FILE_SIZE_MB), `application.yml` multipart 同源,
  `frontend/docker/nginx.conf` 调整为 25m 并修正注释, 删除死常量与死配置
  `timeout-seconds`/`AppProperties.Rag.timeoutSeconds`。
- **验证**: 新增 `upload_rejects_file_over_configured_size_limit`(20MB+1 字节 → 413)。
- **数据影响**: 无。

### 问题 3: rag_config 检索策略不入库
- **发现**: 前端可设 vector/hybrid, 但 `RagConfigServiceImpl.update()` 未持久化
  `retrievalStrategy`(仅建表列存在), 保存后静默回落 vector。
- **修改**: `RagConfigServiceImpl` update/default 均持久化并归一化(非法值 400);
  `sql/init.sql` 补 INSERT 默认值与列注释。
- **验证**: 新增 `RagConfigServiceTest` 3 项(持久化 hybrid、非法值拒绝、空值回落 vector)。
- **数据影响**: 无(实验 D/E4 经请求级参数指定策略, 不依赖全局配置)。

### 问题 4: embedding 工厂不接受 `openai-compatible` 写法
- **修改**: `app/embedding/factory.py` 接受别名; 新增 `test_embedding_factory.py` 3 项
  (含本地模型延迟加载断言)。
- **数据影响**: 无。

---

## P0-2 Precision@K 学术口径

- **发现**: 旧实现分母为 `len(sources)`(实际返回条数), 阈值过滤后返回 < K 时
  P@K 被高估, 非标准定义(标准 P@K 分母固定为 K)。
- **修改**: `app/evaluation/metrics.py` 改为 `relevant / max(top_k,1)`;
  新增边界回归测试 4 项(0 返回 / 返回数<K 断言 1/10 而非 1/9 / 恰为 K / 多条相关片段)。
- **对既有数据的影响(逐题复核, 程序化执行)**: 查询 `evaluation_result.sources`,
  120 题中 119 题 len(sources)=K, 两口径一致; **仅任务 8 题 8**(K=10, 阈值过滤返回 9 条)
  受影响: 单题 0.111→0.100, 任务 8 聚合 P@10 0.254→0.253。
  **处置**: 原始 CSV 与该题落库单题值保持原样(历史记录不改写); 论文 06 §4.1 增"口径说明"
  (2026-09-18 修正, 受影响范围), §7.2 表格改用 0.253 并加旧口径脚注; README 汇总表
  K=10 P@K 保留两位小数 0.25(两口径四舍五入相同)。

---

## P0-3 "引用准确率"表述夸大 → 引用编号有效率

- **发现**: 旧名"引用准确率"暗示语义/事实层面的引用正确, 实际实现仅校验回答中 `[n]`
  编号是否指向真实返回来源(≤ 来源数), 不验证被引文本是否语义支持结论。
- **修改(兼容层保留, 不破坏历史任务展示)**:
  - `metrics.py`: 函数改名 `citation_validity` + docstring 声明局限, 保留
    `citation_accuracy` 向后兼容别名; 汇总 key 改 `citation_validity`;
  - `runner.py`: LLM_ONLY 组检索/引用类指标记 NULL(旧版记 0.0, 与"不适用"语义不符),
    新增回归测试断言 NULL;
  - `schemas.py`/`EvalBatchResponse.java`/`frontend/src/api/evaluation.ts`:
    字段 `citationValidity`(camelCase 契约), 前端 `citationOf()` 对历史任务落库的
    `citationAccuracy` key 做回退读取;
  - 前端 `EvaluationView.vue` 与 `scripts/run-experiment.sh`: 显示名改"引用编号有效率",
    tooltip 注明"仅校验编号有效性, 不验证语义支持"; 逐题列注明">0.5 二值化"口径
    (与 `evaluation_result.citation_matched` 入库口径一致);
  - 文档改名 sweep: README、thesis 01/06/07/08/10、dataset/evaluation/README.md;
  - `init.sql` 两处列注释改为准确口径。
- **数据影响**: 数值本身不变(同一计算), 仅名称与解释修正。
  历史报告 `docs/PROJECT_AUDIT.md`、`docs/FINAL_ACCEPTANCE_REPORT.md` 保留旧名
  **作为带日期的审计轨迹不改写**(见 §未解决问题 3)。

---

## P0-4 实验数字 ↔ 原始数据 ↔ 论文逐项核对

- 全部论文数字(06 篇 §7.1-7.6)程序化重算并与 CSV/DB 对账通过:
  Hit/P@K/R@K/MRR(含 `scripts/recompute-mrr.py` 补算链路与任务 11 自校验
  0.9000=0.9000)/关键词命中率(按答案+数据集 JSON 重算, 含 q_match=15 题断言)/
  引用有效率(DB 连续值 0.9938/0.9968/0.9958 → 论文 0.994/0.997/0.996)/tokens/耗时;
- 异常值处置透明: 任务 7 题 6 LLM 读超时保留失败记录; 任务 12/13(reranker 静默失效
  与修复中间运行)的失效→修复→重跑记录保留在 06 §7.4/§7.6, **未删除任何原始数据**;
- **CSV 与 DB 逐题记录零修改**(git status 确认)。

---

## P1-5 结论措辞收敛 + 有效性威胁

- thesis 06 新增 §6.1"有效性威胁"(样本规模 15 题/无重复试验与显著性检验/单一模型栈/
  关键词词面匹配局限/引用编号有效率≠事实一致性/耗时环境敏感/E3 文档形态前提);
- §7.x 结论统一加"在本数据集上"限定; 删除可被质疑的普适化表述;
- thesis 08 "量化证明"→"量化验证", "显著减少语义割裂"→"更贴合中文语义边界";
- 全文检索确认无"统计显著"类无检验支撑表述(实验为单次运行)。

## P1-6 可复现性

- 新增 `docs/experiments/ENVIRONMENT.md`: 硬件(M3 Pro/18GB/macOS 14)、运行时
  (Python 3.13.13 本机 vs 3.11 Docker、JDK 21.0.11 及 JDK 25-Lombok 陷阱、Node 22、
  MySQL 8.4.9)、关键依赖版本表、模型与统一实验参数、复现步骤; 不含任何密钥;
- 新增 `rag-service/requirements.lock.txt`(pip freeze 全量 123 项快照);
- README 实验节链接上述两文件; 测试命令注明 JDK 21 前置。

## P1-7 演示闭环

- 新增公开 `GET /api/health`(免鉴权, compose 健康检查/演示前探活用) + 测试;
- `RagServiceClient` 连接超时 10s(读超时保持无限并注释原因: 批量评测长阻塞);
- compose `rag-models` 具名卷支持预下载模型后离线演示; FAQ/错误路径文案核对。

## P2-8 清理

- 死代码/死配置: `Constants.MAX_FILE_SIZE_MB`、`Rag.timeoutSeconds`、multipart 重复项;
- `schemas.py` ChatRequest 重复 `retrieval_strategy` 字段删除;
- 误跟踪构建产物 `frontend/vite.config.js` 取消跟踪并加入 .gitignore
  (源文件 `vite.config.ts` 保留);
- README/thesis 07/08 测试计数更新为终版 39/77。

---

## 修改文件清单(本轮)

代码: `rag-service/app/evaluation/{metrics,runner}.py`、`app/models/schemas.py`、
`app/embedding/factory.py`、`app/tests/{test_metrics,test_api}.py`、
`app/tests/test_embedding_factory.py`(新)、`rag-service/Dockerfile`、
`backend/.../{RagConfigServiceImpl,DocumentServiceImpl,Constants,AppProperties,
WebConfig,RagServiceClient,EvalBatchResponse,EvaluationServiceImpl}.java`、
`HealthController.java`(新)、`HealthApiTest.java`/`RagConfigServiceTest.java`(新)、
`DocumentServiceTest`/`EvaluationServiceTest`.java、`application.yml`;
配置: `docker-compose.yml`、`.env.example`、`sql/init.sql`、`frontend/docker/nginx.conf`、
`.gitignore`; 前端: `src/api/evaluation.ts`、`src/views/EvaluationView.vue`;
脚本: `scripts/run-experiment.sh`; 文档: README.md、thesis 01/06/07/08/10、
dataset/evaluation/README.md、`docs/experiments/ENVIRONMENT.md`(新)、
`rag-service/requirements.lock.txt`(新)、本文件。

## 未解决 / 已知遗留

1. **任务 8 题 8 落库单题 P@K 仍为旧口径 0.1111**(分母 9): 属历史原始记录, 按"不改写
   原始数据"原则保留; 论文引用 0.253(标准口径)并脚注说明差异来源;
2. **历史 LLM_ONLY 任务(任务 5)CSV 中检索类指标为 0**(旧版行为): 现版代码记 NULL,
   前端/论文均按"—(无检索)"呈现, 旧 CSV 不回写;
3. **`docs/FINAL_ACCEPTANCE_REPORT.md` 存在与事实不符的陈述**: 其第 38 行附近称
   "init.sql 已更新(retrieval_strategy)"——该修改实际在本轮才完成。作为带日期的
   历史验收记录保留原文, 以本文件为准;
4. compose 中 `EMBEDDING_API_BASE/KEY`、`LLM_API_KEY` 无默认值——设计如此(密钥不落盘);
5. JDK 25 下 Lombok 注解处理失效致 mvn 编译失败, 须 JDK 21(已在 ENVIRONMENT.md/README
   注明; backend/Dockerfile 本就是 temurin-21, 仅本机开发需注意)。

## 论文(最终稿)须同步的段落

1. 指标定义表: P@K 标准公式(分母 K)+ 引用编号有效率及其"≠事实一致性"限定(同 thesis 06 §4.1);
2. Top-K 实验表: K=10 P@K 由 0.254 → **0.253** + 新旧口径脚注;
3. 新增"有效性威胁"小节(可直接采用 thesis 06 §6.1 的 7 条);
4. 全文"引用准确率"→"引用编号有效率"(含图表坐标/图例);
5. 测试数字: 后端 39 项、RAG 服务 77 项;
6. 实验结论措辞: 所有比较级结论加"在本实验数据集/当前配置下"限定, 删除"证明/显著"表述;
7. 环境说明: 引用 ENVIRONMENT.md 的版本快照(建议附录)。
