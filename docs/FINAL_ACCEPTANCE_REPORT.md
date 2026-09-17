# 最终验收报告(第二轮开发)

> 日期: 2026-09-17 | 本报告如实记录, 未完成项明确标注, 不以推测代替实测。

## 1. 项目概况

基于 RAG 的网络安全知识智能问答系统(本科毕业设计)。三服务架构:
Spring Boot 3 后端(:8080) + FastAPI RAG 服务(:8000) + Vue 3 前端(:5173),
MySQL 8 存业务数据, Chroma 持久化向量, glm-5.3-flash 生成, bge-small-zh-v1.5 嵌入,
bge-reranker-base 可选重排。本轮为第二轮开发: 审计、混合检索、重排实验、MRR 指标、
论文文档、答辩材料与一轮真实对照实验。

## 2. 当前架构

```
前端(Vue3+ElementPlus+ECharts, claude.ai 风格主题)
  ↕ REST(JWT Bearer)
后端(Spring Boot, MyBatis-Plus, H2 单测)
  ↕ REST(X-Internal-Token 内部令牌)
RAG 服务(FastAPI: 预处理→嵌入→检索[vector|hybrid]→可选重排→上下文→LLM→引用)
  ├─ Chroma(每知识库独立 Collection, cosine)
  ├─ BM25(自研分词: ASCII 词元+CJK 二元组, RRF k=60 融合)
  └─ CrossEncoder 重排(懒加载, 进程级单例, 4×K 候选池)
```

跨服务契约: camelCase 别名(pydantic populate_by_name), 新增 retrievalStrategy/mrr 字段
双侧同步(Java DTO/实体/CSV/H2 schema ↔ pydantic 模型), 数据库列已 ALTER 并更新 init.sql。

## 3. 已完成功能

- 认证与权限(JWT+BCrypt, admin/user), 用户管理, 操作留痕
- 知识库 CRUD(Chroma 独立 Collection, 删除需清空且级联删向量)
- 文档上传(白名单/UUID 落盘/异步摄取状态机), 解析→清洗→中文语义分块→向量化
- 智能问答: 多轮对话、历史窗口、引用来源可展开核对(文档/页码/相似度/原文),
  无知识拒答(阈值过滤+系统提示, 已实测"夸克禁闭"问题正确拒答)
- 检索策略: vector(默认)/hybrid(BM25+RRF), 可选 CrossEncoder 重排; RAG 配置页可视化调参
- 评测体系: 数据集管理、LLM_ONLY/RAG_LLM 双模式、任务级参数覆盖(strategy/reranker/K/温度)、
  自动指标(Hit@K/P@K/R@K/MRR/关键词覆盖/引用准确率)、人工评分、任务对比、CSV 导出
- Dashboard 真实 SQL 聚合统计与问答趋势
- 前端 Markdown 渲染 + 代码高亮 + 复制按钮(markdown-it html:false, XSS 安全)
- 论文配套: 架构/数据库/RAG 流程 Mermaid 图、检索策略设计、实验设计与真实数据、答辩演示流程

## 4. 本轮发现的问题

1. **reranker 静默失效(严重)**: get_reranker() 工厂仅读全局 RAG_RERANKER_ENABLED,
   请求级 enableReranker=true 被忽略并返回 NoopReranker——首轮"重排实验"(任务12)
   15/15 全部"成功"但实际未执行任何重排, 通过逐题 sources 无 rerankScore 发现;
2. CrossEncoder 以模型名构造时联网做 HF etag 检查, 网络不可达时长时间挂起(任务12 首题停滞 ~6 分钟);
3. 每请求新建 reranker 实例, 懒加载缓存失效, 逐题重复加载模型(~3s/题);
4. /api/retrieval/search 未透传 retrievalStrategy(策略参数被忽略, 实测两种策略返回完全一致而暴露);
5. 后端 CORS 为 allowedOriginPatterns("*")+allowCredentials(true) 组合, 不符合生产安全基线;
6. 前端评测发起表单已有策略/重排控件但未随请求发送(死控件);
7. run-experiment.sh 轮询解析字段路径错误(data.status 应为 data.task.status);
8. 历史任务(4-10)缺 MRR 指标列(指标为第二轮新增);
9. 本机默认 JDK 25 下 Lombok 注解处理静默失效(须 JDK 21, run-local.sh 已固定)。

## 5. 本轮修复的问题

对应第 4 节逐项:
1. get_reranker(enabled) 支持请求级覆盖 + 回归测试 test_get_reranker_request_level_override;
   删除任务 12 数据, 修复后重跑;
2. _resolve_local_path() 优先解析本地 HF 缓存快照, 完全离线加载(实测 17s 冷加载);
3. CrossEncoder 改为进程级单例(热路径检索 416ms, 此前 3-4s/题);
4. /api/retrieval/search 补传 retrievalStrategy, 实测 hybrid 与 vector 返回出现可观测差异;
5. CORS 收紧为 app.cors.allowed-origins 白名单(默认仅本地前端, 环境变量可扩展),
   实测白名单外 Origin 无 Access-Control-Allow-Origin 头;
6. onRun 补传 retrievalStrategy/enableReranker;
7. 脚本改为解析 data.task.* 并支持 d/e4/poll 子命令;
8. scripts/recompute-mrr.py 依据已落库真实检索排序程序化补算(以任务11 落库值自校验一致后执行);
9. 文档明确 JDK 21 要求。
中间运行任务 13(含逐题模型重载)数据一并删除, E4 以任务 14 为正式结果(论文 7.6 节有完整记录)。

## 6. RAG 实现说明

真实链路(全部实测验证): 预处理(去控制字符/压缩空白/截断) → bge-small-zh-v1.5 嵌入 →
Chroma kb_{id} 余弦检索(阈值 0.3 过滤保持拒答语义) → [hybrid] BM25(连字符词元保留,
CWE-918 为单一 token)+RRF(k=60) 融合, 仅 BM25 命中候选记"关键词命中" →
[可选] CrossEncoder 重排 4×K 候选(逐题 rerankScore 落库) → 编号上下文 →
glm-5.3-flash(Anthropic 兼容协议) → 带 [1][2] 引用的回答, 引用严格来自检索片段。
无知识场景实测: "量子色动力学夸克禁闭"问题返回"当前知识库中未找到充分依据"并如实说明片段主题。

## 7. Evaluation 实现说明

- 数据集: dataset/evaluation/cyber_security_qa_15.json(15 题, expectedKeywords/expectedSources 人工标注);
- 指标全部程序化计算(app/evaluation/metrics.py), 不用 LLM 评 LLM:
  Hit@K/P@K/R@K/MRR 依据 expectedSources 与真实检索排序; 关键词覆盖依据 expectedKeywords;
  引用准确率校验回答中引用编号均指向真实片段;
- 实验矩阵(全部真实运行, CSV 落盘 docs/experiments/):
  E1 模式对照(4/5)、E2 Top-K(6/7/7/8)、E3 分块(9/10)、D 混合检索(11)、E4 重排(14);
  关键结果: RAG 关键词命中 0.840 vs 直答 0.659; hybrid P@5 0.32→0.40;
  rerank P@5 0.40/MRR 0.889/关键词 0.927(全程最高);
- 复现: 登录后 RAG 实验页发起, 或 scripts/run-experiment.sh [d|e4]。

## 8. 测试结果

- 后端: mvn test 34/34 通过(H2 + Mockito, schema 已含新列)
- RAG 服务: pytest 68/68 通过(离线 Fake 栈, 含 BM25/RRF/MRR/请求级重排回归)
- 前端: vue-tsc 类型检查 + vite build 通过
- 在线实测: 登录/看板统计/混合检索差异/重排 rerankScore 落库/无知识拒答/CORS 白名单 全部通过

## 9. 构建结果

- 后端 mvn compile/test: 成功(JDK 21; 注意本机默认 JDK 25 会使 Lombok 失效)
- 前端 npm run build: 成功(dist ~gzip 408KB 主包)
- RAG 服务依赖安装 + uvicorn 启动: 成功; reranker 模型离线缓存 1.1GB 已就位

## 10. Docker 状态

docker-compose.yml 校验通过(mysql/backend/rag/frontend 四服务 + 依赖与健康检查),
README 提供 docker 一键启动路径。诚实说明: 本项目全部开发与验证基于本机原生三服务,
容器化部署路径未做实测, 答辩演示以本机运行为准。

## 11. 当前已知限制

- 问答为非流式(一次性返回, 平均 ~25s), 未实现 SSE/打字机效果;
- 评测批次为单条长请求, 任务进度在批次结束才更新(中途 0/N 属正常);
- Chroma 为单机嵌入式, 无横向扩展; reranker 推理为 CPU/MPS, 无 GPU 加速;
- 正式评测集 15 题, 未达论文目标 100-200 题(扩充流程已在 dataset/evaluation/README.md 说明);
- Docker 部署未实测(见第 10 节)。

## 12. 答辩演示步骤

见 docs/thesis/10-答辩演示流程.md(13 步演示表 + 三个核心问题口径 + 风险预案)。
关键演示点均有本轮实测数据支撑: 引用可溯源(第 6 节)、拒答(第 6 节)、
对照实验量化(第 7 节)、混合检索/重排增强(任务 11/14)。

## 13. 后续可优化项

- SSE 流式输出(架构已预留, 前端 Markdown 渲染组件可直接复用);
- 评测集扩充至 100-200 题并引入分组统计;
- HyDE/Multi-Query 查询改写、Agentic RAG、Graph RAG(本轮明确不做, 防止范围蔓延);
- reranker 批量推理 GPU 化与 ONNX 量化; Docker 部署实测与 CI 流水线。
