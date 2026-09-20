-- =====================================================================
-- 第四轮迁移: Security-Aware Adaptive RAG
-- 适用于已按 init.sql 建库的存量环境; 新库直接用最新 init.sql 即可。
-- 2026-09-18
-- =====================================================================

USE `cyber_rag`;

-- 消息/问答记录: 保存本次 RAG 决策轨迹(阶段耗时/路由/门控/缓存)
ALTER TABLE `message`
    ADD COLUMN `trace` TEXT COMMENT '本次 RAG 决策轨迹 JSON(阶段耗时/路由/门控/缓存)' AFTER `sources`;
ALTER TABLE `qa_record`
    ADD COLUMN `trace` TEXT COMMENT '本次 RAG 决策轨迹 JSON(阶段耗时/路由/门控/缓存)' AFTER `sources`;

-- RAG 配置: Adaptive 总开关
ALTER TABLE `rag_config`
    ADD COLUMN `adaptive_enabled` TINYINT NOT NULL DEFAULT 0
        COMMENT 'Adaptive RAG 总开关(查询分析+路由+门控+动态上下文): 0关 1开' AFTER `history_window`;

-- 评测结果: nDCG@K + Performance Detail(自适应模式)
ALTER TABLE `evaluation_result`
    ADD COLUMN `ndcg_at_k` DECIMAL(5,4) DEFAULT NULL COMMENT 'nDCG@K 折扣累计增益(二值相关性标准实现)' AFTER `recall_at_k`;
ALTER TABLE `evaluation_result`
    ADD COLUMN `route` VARCHAR(20) DEFAULT NULL COMMENT 'Performance Detail: 自适应路由(非自适应为NULL)' AFTER `citation_matched`;
ALTER TABLE `evaluation_result`
    ADD COLUMN `rerank_used` TINYINT DEFAULT NULL COMMENT 'Performance Detail: 是否触发重排(非自适应为NULL)' AFTER `route`;
ALTER TABLE `evaluation_result`
    ADD COLUMN `context_tokens` INT DEFAULT NULL COMMENT 'Performance Detail: 上下文 token 数(启发式估算)' AFTER `rerank_used`;

-- 评测任务: 记录每轮实验的 Adaptive/消融开关(NULL = 跟随 rag-service 全局配置)
ALTER TABLE `evaluation_task`
    ADD COLUMN `adaptive_enabled` TINYINT DEFAULT NULL COMMENT 'Adaptive RAG 总开关: 1开 0关 NULL跟随全局' AFTER `retrieval_strategy`,
    ADD COLUMN `entity_boost`      TINYINT DEFAULT NULL COMMENT '消融: 实体精确加权' AFTER `adaptive_enabled`,
    ADD COLUMN `rerank_gating`     TINYINT DEFAULT NULL COMMENT '消融: 置信度门控重排' AFTER `entity_boost`,
    ADD COLUMN `dynamic_context`   TINYINT DEFAULT NULL COMMENT '消融: 动态上下文预算' AFTER `rerank_gating`,
    ADD COLUMN `use_caches`        TINYINT DEFAULT NULL COMMENT '消融: Embedding/检索缓存' AFTER `dynamic_context`;
