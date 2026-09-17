-- 测试初始数据
INSERT INTO `role` (`id`, `code`, `name`) VALUES (1, 'ADMIN', '管理员'), (2, 'USER', '普通用户');
INSERT INTO `user` (`id`, `username`, `password`, `nickname`, `role_id`, `status`) VALUES
(1, 'admin', '$2a$10$6ErA0Q/ZgX7484q0/apwsOp9VjnWLLc5RuX4b/NlV/2JdYZyIo5eS', '系统管理员', 1, 1),
(2, 'user', '$2a$10$6ErA0Q/ZgX7484q0/apwsOp9VjnWLLc5RuX4b/NlV/2JdYZyIo5eS', '演示用户', 2, 1);
INSERT INTO `knowledge_base` (`id`, `name`, `description`, `category`, `created_by`) VALUES
(1, 'Web安全知识库', '测试知识库', 'Web安全', 1);
INSERT INTO `rag_config` (`id`, `chunk_size`, `chunk_overlap`, `top_k`, `temperature`, `score_threshold`)
VALUES (1, 512, 100, 5, 0.30, 0.300);
INSERT INTO `evaluation_dataset` (`id`, `name`, `created_by`) VALUES (1, '测试数据集', 1);
INSERT INTO `evaluation_item` (`id`, `dataset_id`, `question`, `expected_keywords`, `expected_source`) VALUES
(1, 1, '如何防御SQL注入?', '参数化查询', 'SQL注入防护指南'),
(2, 1, '什么是XSS?', '输出转义', 'XSS防护指南');
