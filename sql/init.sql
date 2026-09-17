-- =====================================================================
-- 基于 RAG 的网络安全知识智能问答系统 - 数据库初始化脚本
-- MySQL 8.0+ / utf8mb4
-- =====================================================================

CREATE DATABASE IF NOT EXISTS cyber_rag DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cyber_rag;

-- ---------------------------------------------------------------------
-- 角色表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `role`;
CREATE TABLE `role` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `code`        VARCHAR(50)  NOT NULL COMMENT '角色编码: ADMIN / USER',
    `name`        VARCHAR(50)  NOT NULL COMMENT '角色名称',
    `description` VARCHAR(255) DEFAULT NULL COMMENT '角色描述',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`     TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`)
) ENGINE = InnoDB COMMENT ='角色表';

-- ---------------------------------------------------------------------
-- 用户表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `username`      VARCHAR(50)  NOT NULL COMMENT '用户名',
    `password`      VARCHAR(100) NOT NULL COMMENT 'BCrypt 密码哈希',
    `nickname`      VARCHAR(50)  DEFAULT NULL COMMENT '昵称',
    `email`         VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
    `avatar`        VARCHAR(255) DEFAULT NULL COMMENT '头像地址',
    `role_id`       BIGINT       NOT NULL DEFAULT 2 COMMENT '角色ID, 1管理员 2普通用户',
    `status`        TINYINT      NOT NULL DEFAULT 1 COMMENT '状态: 1启用 0禁用',
    `last_login_at` DATETIME     DEFAULT NULL COMMENT '最后登录时间',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`       TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_role` (`role_id`)
) ENGINE = InnoDB COMMENT ='用户表';

-- ---------------------------------------------------------------------
-- 知识库表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `knowledge_base`;
CREATE TABLE `knowledge_base` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `name`        VARCHAR(100) NOT NULL COMMENT '知识库名称',
    `description` VARCHAR(500) DEFAULT NULL COMMENT '简介',
    `category`    VARCHAR(50)  DEFAULT NULL COMMENT '分类: Web安全/Java安全/OWASP/CWE/API安全/认证授权/其他',
    `cover_color` VARCHAR(20)  DEFAULT '#409EFF' COMMENT '封面颜色',
    `doc_count`   INT          NOT NULL DEFAULT 0 COMMENT '文档数量',
    `chunk_count` INT          NOT NULL DEFAULT 0 COMMENT 'Chunk 数量',
    `status`      TINYINT      NOT NULL DEFAULT 1 COMMENT '状态: 1启用 0停用',
    `created_by`  BIGINT       DEFAULT NULL COMMENT '创建人',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`     TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    KEY `idx_category` (`category`)
) ENGINE = InnoDB COMMENT ='网络安全知识库表';

-- ---------------------------------------------------------------------
-- 文档表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `document`;
CREATE TABLE `document` (
    `id`                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `knowledge_base_id` BIGINT       NOT NULL COMMENT '所属知识库ID',
    `name`              VARCHAR(255) NOT NULL COMMENT '文档名称',
    `file_type`         VARCHAR(20)  DEFAULT NULL COMMENT '类型: pdf/txt/md/docx',
    `file_size`         BIGINT       NOT NULL DEFAULT 0 COMMENT '文件大小(字节)',
    `file_path`         VARCHAR(500) DEFAULT NULL COMMENT '存储路径(随机文件名)',
    `chunk_count`       INT          NOT NULL DEFAULT 0 COMMENT 'Chunk 数量',
    `char_count`        INT          NOT NULL DEFAULT 0 COMMENT '清洗后字符数',
    `status`            VARCHAR(20)  NOT NULL DEFAULT 'PENDING' COMMENT '状态: PENDING/PARSING/EMBEDDING/COMPLETED/FAILED',
    `error_msg`         VARCHAR(1000) DEFAULT NULL COMMENT '处理失败错误信息',
    `created_by`        BIGINT       DEFAULT NULL COMMENT '上传人',
    `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`           TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    KEY `idx_kb` (`knowledge_base_id`),
    KEY `idx_status` (`status`)
) ENGINE = InnoDB COMMENT ='知识文档表';

-- ---------------------------------------------------------------------
-- 会话表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `conversation`;
CREATE TABLE `conversation` (
    `id`                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id`           BIGINT       NOT NULL COMMENT '所属用户ID',
    `title`             VARCHAR(255) DEFAULT '新对话' COMMENT '会话标题',
    `knowledge_base_id` BIGINT       DEFAULT NULL COMMENT '关联知识库ID',
    `message_count`     INT          NOT NULL DEFAULT 0 COMMENT '消息数量',
    `last_message_at`   DATETIME     DEFAULT NULL COMMENT '最后消息时间',
    `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`           TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    KEY `idx_user` (`user_id`)
) ENGINE = InnoDB COMMENT ='对话会话表';

-- ---------------------------------------------------------------------
-- 消息表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `message`;
CREATE TABLE `message` (
    `id`              BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
    `conversation_id` BIGINT   NOT NULL COMMENT '会话ID',
    `role`            VARCHAR(10) NOT NULL COMMENT '角色: user/assistant',
    `content`         TEXT COMMENT '消息内容',
    `sources`         JSON     DEFAULT NULL COMMENT '引用来源JSON',
    `retrieval_time`  INT      NOT NULL DEFAULT 0 COMMENT '检索耗时(ms)',
    `generation_time` INT      NOT NULL DEFAULT 0 COMMENT '生成耗时(ms)',
    `total_tokens`    INT      NOT NULL DEFAULT 0 COMMENT 'Token 使用量',
    `created_at`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`         TINYINT  NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    KEY `idx_conversation` (`conversation_id`)
) ENGINE = InnoDB COMMENT ='会话消息表';

-- ---------------------------------------------------------------------
-- 问答记录表(用于统计与实验分析)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `qa_record`;
CREATE TABLE `qa_record` (
    `id`                BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id`           BIGINT   DEFAULT NULL COMMENT '提问用户ID',
    `conversation_id`   BIGINT   DEFAULT NULL COMMENT '会话ID',
    `knowledge_base_id` BIGINT   DEFAULT NULL COMMENT '知识库ID',
    `question`          TEXT COMMENT '问题',
    `answer`            TEXT COMMENT '回答',
    `sources`           JSON     DEFAULT NULL COMMENT '引用来源JSON',
    `retrieval_time`    INT      NOT NULL DEFAULT 0 COMMENT '检索耗时(ms)',
    `generation_time`   INT      NOT NULL DEFAULT 0 COMMENT '生成耗时(ms)',
    `total_time`        INT      NOT NULL DEFAULT 0 COMMENT '总耗时(ms)',
    `total_tokens`      INT      NOT NULL DEFAULT 0 COMMENT 'Token 使用量',
    `created_at`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`           TINYINT  NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    KEY `idx_user` (`user_id`),
    KEY `idx_created` (`created_at`)
) ENGINE = InnoDB COMMENT ='问答记录表';

-- ---------------------------------------------------------------------
-- 用户反馈表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `feedback`;
CREATE TABLE `feedback` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id`     BIGINT       NOT NULL COMMENT '用户ID',
    `message_id`  BIGINT       DEFAULT NULL COMMENT '消息ID',
    `qa_record_id` BIGINT      DEFAULT NULL COMMENT '问答记录ID',
    `rating`      TINYINT      NOT NULL DEFAULT 1 COMMENT '评价: 1有用 -1无用',
    `comment`     VARCHAR(500) DEFAULT NULL COMMENT '评论内容',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`     TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    KEY `idx_user` (`user_id`),
    KEY `idx_message` (`message_id`)
) ENGINE = InnoDB COMMENT ='用户反馈表';

-- ---------------------------------------------------------------------
-- RAG 参数配置表(单行配置, id=1)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `rag_config`;
CREATE TABLE `rag_config` (
    `id`                BIGINT        NOT NULL COMMENT '主键, 固定为1',
    `chunk_size`        INT           NOT NULL DEFAULT 512 COMMENT 'Chunk 大小(字符)',
    `chunk_overlap`     INT           NOT NULL DEFAULT 100 COMMENT 'Chunk 重叠(字符)',
    `top_k`             INT           NOT NULL DEFAULT 5 COMMENT '检索 Top-K',
    `temperature`        DECIMAL(3,2) NOT NULL DEFAULT 0.30 COMMENT 'LLM Temperature',
    `score_threshold`   DECIMAL(4,3)  NOT NULL DEFAULT 0.300 COMMENT '相似度阈值',
    `enable_reranker`   TINYINT       NOT NULL DEFAULT 0 COMMENT '是否启用 Reranker: 0否 1是',
    `rerank_top_n`      INT           NOT NULL DEFAULT 3 COMMENT '重排序后保留数量',
    `history_window`    INT           NOT NULL DEFAULT 6 COMMENT '携带历史消息条数',
    `updated_by`        BIGINT        DEFAULT NULL COMMENT '更新人',
    `created_at`        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`)
) ENGINE = InnoDB COMMENT ='RAG 参数配置表';

-- ---------------------------------------------------------------------
-- 评测数据集表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `evaluation_dataset`;
CREATE TABLE `evaluation_dataset` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `name`        VARCHAR(100) NOT NULL COMMENT '数据集名称',
    `description` VARCHAR(500) DEFAULT NULL COMMENT '描述',
    `item_count`  INT          NOT NULL DEFAULT 0 COMMENT '题目数量',
    `created_by`  BIGINT       DEFAULT NULL COMMENT '创建人',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`     TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`)
) ENGINE = InnoDB COMMENT ='评测数据集表';

-- ---------------------------------------------------------------------
-- 评测题目表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `evaluation_item`;
CREATE TABLE `evaluation_item` (
    `id`               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `dataset_id`       BIGINT       NOT NULL COMMENT '数据集ID',
    `question`         TEXT         NOT NULL COMMENT '问题',
    `reference_answer` TEXT COMMENT '参考答案',
    `expected_keywords` VARCHAR(500) DEFAULT NULL COMMENT '期望关键词, 逗号分隔',
    `expected_source`  VARCHAR(255) DEFAULT NULL COMMENT '期望命中的来源文档名',
    `category`         VARCHAR(50)  DEFAULT NULL COMMENT '问题类别',
    `created_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`          TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    KEY `idx_dataset` (`dataset_id`)
) ENGINE = InnoDB COMMENT ='评测题目表';

-- ---------------------------------------------------------------------
-- 评测任务表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `evaluation_task`;
CREATE TABLE `evaluation_task` (
    `id`                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `name`              VARCHAR(100) NOT NULL COMMENT '任务名称',
    `mode`              VARCHAR(20)  NOT NULL COMMENT '模式: LLM_ONLY / RAG_LLM',
    `knowledge_base_id` BIGINT       DEFAULT NULL COMMENT '知识库ID(RAG模式)',
    `dataset_id`        BIGINT       NOT NULL COMMENT '数据集ID',
    `top_k`             INT          DEFAULT NULL COMMENT '实验用 Top-K',
    `chunk_size`        INT          DEFAULT NULL COMMENT '实验用 Chunk Size',
    `chunk_overlap`     INT          DEFAULT NULL COMMENT '实验用 Chunk Overlap',
    `temperature`       DECIMAL(3,2) DEFAULT NULL COMMENT '实验用 Temperature',
    `enable_reranker`   TINYINT      DEFAULT 0 COMMENT '是否启用 Reranker',
    `retrieval_strategy` VARCHAR(16) DEFAULT 'vector' COMMENT '实验用检索策略: vector/hybrid',
    `total`             INT          NOT NULL DEFAULT 0 COMMENT '总题数',
    `completed`         INT          NOT NULL DEFAULT 0 COMMENT '完成数',
    `failed`            INT          NOT NULL DEFAULT 0 COMMENT '失败数',
    `status`            VARCHAR(20)  NOT NULL DEFAULT 'PENDING' COMMENT '状态: PENDING/RUNNING/COMPLETED/FAILED',
    `metrics`           JSON         DEFAULT NULL COMMENT '汇总指标JSON',
    `error_msg`         VARCHAR(1000) DEFAULT NULL COMMENT '错误信息',
    `created_by`        BIGINT       DEFAULT NULL COMMENT '创建人',
    `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`           TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    KEY `idx_dataset` (`dataset_id`)
) ENGINE = InnoDB COMMENT ='评测任务表';

-- ---------------------------------------------------------------------
-- 评测结果表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `evaluation_result`;
CREATE TABLE `evaluation_result` (
    `id`                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `task_id`           BIGINT       NOT NULL COMMENT '任务ID',
    `item_id`           BIGINT       NOT NULL COMMENT '题目ID',
    `question`          TEXT         NOT NULL COMMENT '问题',
    `mode`              VARCHAR(20)  NOT NULL COMMENT '模式: LLM_ONLY / RAG_LLM',
    `answer`            TEXT COMMENT '模型回答',
    `sources`           JSON         DEFAULT NULL COMMENT '引用来源JSON',
    `retrieval_time`    INT          NOT NULL DEFAULT 0 COMMENT '检索耗时(ms)',
    `generation_time`   INT          NOT NULL DEFAULT 0 COMMENT '生成耗时(ms)',
    `total_time`        INT          NOT NULL DEFAULT 0 COMMENT '总耗时(ms)',
    `prompt_tokens`     INT          NOT NULL DEFAULT 0 COMMENT '提示词 Token',
    `completion_tokens` INT          NOT NULL DEFAULT 0 COMMENT '补全 Token',
    `error`             VARCHAR(500) DEFAULT NULL COMMENT '单题失败原因, 成功为NULL',
    `retrieval_hit`     TINYINT      DEFAULT NULL COMMENT '检索是否命中期望来源: 1是 0否 NULL未评',
    `precision_at_k`    DECIMAL(5,4) DEFAULT NULL COMMENT 'Precision@K',
    `recall_at_k`       DECIMAL(5,4) DEFAULT NULL COMMENT 'Recall@K',
    `mrr`               DECIMAL(5,4) DEFAULT NULL COMMENT 'MRR 平均倒数排名',
    `keyword_hit_rate`  DECIMAL(5,4) DEFAULT NULL COMMENT '关键词命中率',
    `citation_matched`  TINYINT      DEFAULT NULL COMMENT '引用是否与检索来源一致: 1是 0否',
    `manual_correctness`   TINYINT   DEFAULT 0 COMMENT '人工正确性评分 1-5, 0未评',
    `manual_relevance`     TINYINT   DEFAULT 0 COMMENT '人工相关性评分 1-5, 0未评',
    `manual_completeness`  TINYINT   DEFAULT 0 COMMENT '人工完整性评分 1-5, 0未评',
    `manual_hallucination` TINYINT   DEFAULT 0 COMMENT '人工幻觉判定: 1存在 0不存在',
    `manual_scored`        TINYINT   DEFAULT 0 COMMENT '是否已人工评分: 0否 1是',
    `manual_comment`       VARCHAR(500) DEFAULT NULL COMMENT '人工评语',
    `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`           TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0否 1是',
    PRIMARY KEY (`id`),
    KEY `idx_task` (`task_id`)
) ENGINE = InnoDB COMMENT ='评测结果表';

-- =====================================================================
-- 初始化数据
-- BCrypt 密码哈希由 scripts/generate_bcrypt.py 生成, 切勿在生产环境使用示例密码
-- admin/admin123, user/user123
-- =====================================================================

INSERT INTO `role` (`id`, `code`, `name`, `description`) VALUES
(1, 'ADMIN', '管理员', '系统管理员, 拥有知识库管理与系统配置权限'),
(2, 'USER', '普通用户', '普通用户, 可进行智能问答');

-- BCrypt('admin123') / BCrypt('user123')
INSERT INTO `user` (`id`, `username`, `password`, `nickname`, `email`, `role_id`, `status`) VALUES
(1, 'admin', '$2a$10$6ErA0Q/ZgX7484q0/apwsOp9VjnWLLc5RuX4b/NlV/2JdYZyIo5eS', '系统管理员', 'admin@cyberrag.local', 1, 1),
(2, 'user', '$2a$10$nQWpoY5RAH3DJ0loIAlS4OLCWjLpZ/mrJ7MlPIy56mdkhC20mcJk6', '演示用户', 'user@cyberrag.local', 2, 1);

INSERT INTO `knowledge_base` (`id`, `name`, `description`, `category`, `cover_color`, `created_by`) VALUES
(1, 'Web安全知识库', '覆盖 OWASP Top 10、SQL 注入、XSS、CSRF、SSRF 等 Web 安全核心知识', 'Web安全', '#F56C6C', 1),
(2, 'Java安全知识库', 'Java 安全编码规范、Spring Boot Security、反序列化、JWT 安全实践', 'Java安全', '#409EFF', 1),
(3, 'API安全知识库', 'OWASP API Security Top 10、BOLA、BFLA、API 认证与限流', 'API安全', '#67C23A', 1);

INSERT INTO `rag_config` (`id`, `chunk_size`, `chunk_overlap`, `top_k`, `temperature`, `score_threshold`,
                          `enable_reranker`, `rerank_top_n`, `history_window`, `updated_by`) VALUES
(1, 512, 100, 5, 0.30, 0.300, 0, 3, 6, 1);

INSERT INTO `evaluation_dataset` (`id`, `name`, `description`, `created_by`) VALUES
(1, '网络安全问答基准集', '覆盖 SQL 注入/XSS/CSRF/JWT/API 安全等核心知识点的评测题目', 1);

-- 评测题目(与 dataset/ 示例文档对应, expected_source 与上传文档名一致)
INSERT INTO `evaluation_item` (`dataset_id`, `question`, `reference_answer`, `expected_keywords`, `expected_source`, `category`) VALUES
(1, '什么是 SQL 注入?如何防御?', 'SQL 注入是将恶意 SQL 语句插入应用查询参数欺骗数据库执行非预期命令的攻击。防御: 参数化查询/预编译语句、ORM 使用 #{} 占位符、输入白名单校验、数据库最小权限、错误信息脱敏。', '参数化查询,预编译,最小权限,白名单', 'SQL注入防护指南.md', 'Web安全'),
(1, 'MyBatis 中 #{} 和 ${} 的区别是什么?', '#{} 是参数化占位符, 会将输入作为数据绑定, 安全; ${} 是字符串直接拼接, 存在 SQL 注入风险, 严禁用于用户可控输入。动态排序字段等场景应使用白名单映射。', '参数化,拼接,注入,白名单', 'SQL注入防护指南.md', 'Web安全'),
(1, 'XSS 有哪几种类型?分别如何防御?', 'XSS 分为反射型(参数回显)、存储型(入库后影响所有访问者)、DOM 型(前端不当操作 DOM)。防御: 输出编码、框架默认转义、避免 v-html/innerHTML、CSP、HttpOnly Cookie、富文本白名单净化。', '反射型,存储型,DOM,输出编码,CSP,HttpOnly', 'XSS防护指南.md', 'Web安全'),
(1, 'CSRF 攻击的原理是什么?有哪些防御手段?', 'CSRF 利用浏览器自动携带 Cookie 的机制, 诱导已登录用户的浏览器发送恶意请求。防御: CSRF Token、SameSite Cookie、校验 Origin/Referer、避免 GET 副作用、敏感操作二次认证。', 'Token,SameSite,Origin,Referer', 'CSRF防御指南.md', 'Web安全'),
(1, 'SSRF 是什么?云环境中最典型的危害是什么?', 'SSRF 指攻击者诱使服务端向指定地址发起请求。云环境典型危害是访问元数据服务(169.254.169.254)获取实例临时凭证进而接管云资源。防御: 目标白名单、禁用危险协议、解析后校验 IP、网络隔离、IMDSv2。', '内网,元数据,白名单,协议,IMDSv2', 'SSRF防御指南.md', 'Web安全'),
(1, 'JWT 常见的安全风险有哪些?', '主要包括: 算法混淆攻击(改 alg 为 none 或 RS256→HS256)、密钥弱或硬编码、Payload 泄露敏感信息(仅 Base64 可逆读)、Token 无法主动失效。防御: 服务端固定算法、强密钥走环境变量、短有效期、黑名单机制。', '算法混淆,密钥,exp,失效,HttpsOnly', 'JWT安全实践指南.md', 'Java安全'),
(1, '文件上传功能有哪些安全风险?如何防范?', '风险: WebShell 上传、目录穿越、超大文件 DoS、恶意文件分发。防御: 扩展名白名单、文件头校验、随机文件名存储、大小限制、规范化路径校验、上传目录禁执行权限、病毒扫描。', '白名单,随机文件名,大小限制,目录穿越', '文件上传安全指南.md', 'Web安全'),
(1, 'BOLA 和 BFLA 的区别是什么?', 'BOLA 是对象级授权失效(水平越权), 如用户 A 读取用户 B 的订单; BFLA 是功能级授权失效(垂直越权), 如普通用户调用管理员接口。防御: 服务端逐对象校验归属、逐接口校验角色, 默认拒绝。', '对象级,功能级,越权,角色,归属', 'BOLA与BFLA越权解析.md', 'API安全'),
(1, '为什么不能使用 MD5 存储密码?应该用什么?', 'MD5 是快速哈希, GPU 每秒可计算数十亿次, 彩虹表与暴力破解极易得手。应使用 BCrypt/Argon2/PBKDF2 等自适应加盐慢哈希, 成本因子可随硬件升级, 相同密码每次哈希结果不同。', 'BCrypt,慢哈希,盐,成本因子', '身份认证与密码安全.md', 'Web安全'),
(1, 'RAG 系统的完整流程是什么?', '离线: 文档解析→清洗→分块→向量化→入向量库。在线: 查询预处理→查询向量化→Top-K 检索→可选重排序→上下文构建→LLM 生成→引用溯源。关键参数: chunk size、overlap、Top-K、score threshold、temperature。', '分块,向量化,检索,重排序,引用', 'RAG技术概念解析.md', '通用'),
(1, 'Java 反序列化漏洞的原理是什么?', '对不可信数据调用反序列化接口时, 恶意对象图中的钩子方法(readObject 等)自动执行, 结合 classpath 中的 gadget 链(如 Commons-Collections、Fastjson)可触发 RCE。防御: 避免原生序列化、JEP 290 白名单过滤、升级组件、隔离高危端口。', 'readObject,gadget,白名单,升级', '反序列化漏洞与Java安全.md', 'Java安全'),
(1, 'Spring Boot 项目有哪些常见安全加固措施?', '密码 BCrypt 存储; JWT 密钥走环境变量且≥32字节; 拦截器统一鉴权+@RequireAdmin 管理接口校验; @Valid 参数校验+全局异常处理; 关闭堆栈回显与生产 API 文档; Actuator 只暴露 health; CORS 精确白名单; 依赖 SCA 扫描。', 'BCrypt,拦截器,参数校验,Actuator,CORS', 'SpringBoot安全加固指南.md', 'Java安全'),
(1, '如何安全地配置 CORS?', '使用精确来源白名单; 严禁 Access-Control-Allow-Origin: * 与 Allow-Credentials: true 组合; 禁止反射任意 Origin; 本地开发用 devServer 代理; OPTIONS 预检需放行并返回正确的 CORS 头。', '白名单,反射,预检,OPTIONS,凭证', 'CORS跨域安全配置.md', 'Web安全'),
(1, 'OWASP API Security Top 10 中排名第一的风险是什么?', 'BOLA(对象级授权失效, Broken Object Level Authorization), API 只做认证未校验资源归属, 导致横向越权访问他人数据, 是数据泄露的最主要根因。', 'BOLA,对象级,授权,越权', 'OWASP-API安全Top10解读.md', 'API安全'),
(1, '防止路径穿越攻击的正确做法是什么?', '对用户输入的文件名先取 Path.getFileName() 或服务端生成随机名; 拼接后 normalize 规范化, 再校验结果必须 startsWith 上传根目录; 白名单校验字符集; 运行账号最小权限。', 'normalize,startsWith,白名单,随机名', '路径穿越与命令注入防御.md', 'Web安全');

-- 同步数据集题量计数
UPDATE `evaluation_dataset` d
SET `item_count` = (SELECT COUNT(*) FROM `evaluation_item` i
                    WHERE i.`dataset_id` = d.`id` AND i.`deleted` = 0);
