-- H2(MySQL 模式)测试库结构: 与 sql/init.sql 保持字段一致, 省略 MySQL 专有语法
CREATE TABLE IF NOT EXISTS `role` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `code` VARCHAR(50) NOT NULL,
    `name` VARCHAR(50) NOT NULL,
    `description` VARCHAR(255),
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `user` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL,
    `password` VARCHAR(100) NOT NULL,
    `nickname` VARCHAR(50),
    `email` VARCHAR(100),
    `avatar` VARCHAR(255),
    `role_id` BIGINT NOT NULL DEFAULT 2,
    `status` TINYINT DEFAULT 1,
    `last_login_at` DATETIME,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `knowledge_base` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `description` VARCHAR(500),
    `category` VARCHAR(50),
    `cover_color` VARCHAR(20) DEFAULT '#409EFF',
    `doc_count` INT DEFAULT 0,
    `chunk_count` INT DEFAULT 0,
    `status` TINYINT DEFAULT 1,
    `created_by` BIGINT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `document` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `knowledge_base_id` BIGINT NOT NULL,
    `name` VARCHAR(255) NOT NULL,
    `file_type` VARCHAR(20),
    `file_size` BIGINT DEFAULT 0,
    `file_path` VARCHAR(500),
    `chunk_count` INT DEFAULT 0,
    `char_count` INT DEFAULT 0,
    `status` VARCHAR(20) DEFAULT 'PENDING',
    `error_msg` VARCHAR(1000),
    `created_by` BIGINT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `conversation` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `title` VARCHAR(255) DEFAULT '新对话',
    `knowledge_base_id` BIGINT,
    `message_count` INT DEFAULT 0,
    `last_message_at` DATETIME,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `message` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `conversation_id` BIGINT NOT NULL,
    `role` VARCHAR(10) NOT NULL,
    `content` TEXT,
    `sources` TEXT,
    `trace` TEXT,
    `retrieval_time` INT DEFAULT 0,
    `generation_time` INT DEFAULT 0,
    `total_tokens` INT DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `qa_record` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT,
    `conversation_id` BIGINT,
    `knowledge_base_id` BIGINT,
    `question` TEXT,
    `answer` TEXT,
    `sources` TEXT,
    `trace` TEXT,
    `retrieval_time` INT DEFAULT 0,
    `generation_time` INT DEFAULT 0,
    `total_time` INT DEFAULT 0,
    `total_tokens` INT DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `feedback` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `message_id` BIGINT,
    `qa_record_id` BIGINT,
    `rating` TINYINT DEFAULT 1,
    `comment` VARCHAR(500),
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `rag_config` (
    `id` BIGINT PRIMARY KEY,
    `chunk_size` INT DEFAULT 512,
    `chunk_overlap` INT DEFAULT 100,
    `top_k` INT DEFAULT 5,
    `temperature` DECIMAL(3,2) DEFAULT 0.30,
    `score_threshold` DECIMAL(4,3) DEFAULT 0.300,
    `enable_reranker` TINYINT DEFAULT 0,
    `rerank_top_n` INT DEFAULT 3,
    `retrieval_strategy` VARCHAR(16) DEFAULT 'vector',
    `history_window` INT DEFAULT 6,
    `adaptive_enabled` TINYINT DEFAULT 0,
    `updated_by` BIGINT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `evaluation_dataset` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `description` VARCHAR(500),
    `item_count` INT DEFAULT 0,
    `created_by` BIGINT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `evaluation_item` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `dataset_id` BIGINT NOT NULL,
    `question` TEXT NOT NULL,
    `reference_answer` TEXT,
    `expected_keywords` VARCHAR(500),
    `expected_source` VARCHAR(255),
    `category` VARCHAR(50),
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `evaluation_task` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `mode` VARCHAR(20) NOT NULL,
    `knowledge_base_id` BIGINT,
    `dataset_id` BIGINT NOT NULL,
    `top_k` INT,
    `chunk_size` INT,
    `chunk_overlap` INT,
    `temperature` DECIMAL(3,2),
    `enable_reranker` TINYINT DEFAULT 0,
    `retrieval_strategy` VARCHAR(16) DEFAULT 'vector',
    `adaptive_enabled` TINYINT DEFAULT NULL,
    `entity_boost` TINYINT DEFAULT NULL,
    `rerank_gating` TINYINT DEFAULT NULL,
    `dynamic_context` TINYINT DEFAULT NULL,
    `use_caches` TINYINT DEFAULT NULL,
    `total` INT DEFAULT 0,
    `completed` INT DEFAULT 0,
    `failed` INT DEFAULT 0,
    `status` VARCHAR(20) DEFAULT 'PENDING',
    `metrics` TEXT,
    `error_msg` VARCHAR(1000),
    `created_by` BIGINT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `evaluation_result` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `task_id` BIGINT NOT NULL,
    `item_id` BIGINT NOT NULL,
    `question` TEXT NOT NULL,
    `mode` VARCHAR(20) NOT NULL,
    `answer` TEXT,
    `sources` TEXT,
    `trace` TEXT,
    `retrieval_time` INT DEFAULT 0,
    `generation_time` INT DEFAULT 0,
    `total_time` INT DEFAULT 0,
    `prompt_tokens` INT DEFAULT 0,
    `completion_tokens` INT DEFAULT 0,
    `error` VARCHAR(500),
    `retrieval_hit` TINYINT,
    `precision_at_k` DECIMAL(5,4),
    `recall_at_k` DECIMAL(5,4),
    `ndcg_at_k` DECIMAL(5,4),
    `mrr` DECIMAL(5,4),
    `keyword_hit_rate` DECIMAL(5,4),
    `citation_matched` TINYINT,
    `route` VARCHAR(20),
    `rerank_used` TINYINT,
    `context_tokens` INT,
    `manual_correctness` TINYINT DEFAULT 0,
    `manual_relevance` TINYINT DEFAULT 0,
    `manual_completeness` TINYINT DEFAULT 0,
    `manual_hallucination` TINYINT DEFAULT 0,
    `manual_scored` TINYINT DEFAULT 0,
    `manual_comment` VARCHAR(500),
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `deleted` TINYINT DEFAULT 0
);
