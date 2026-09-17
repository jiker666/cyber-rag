# 评测数据集

## 文件说明

- `cyber_security_qa_15.json` — 正式评测集(15 题), 从系统数据库导出的真实数据,
  与 `dataset/` 下 48 篇安全知识文档一一对应, 已用于论文 E1-E3 实验。
- `evaluation_questions.example.json` — 标准格式示例(前 3 题)。

## 题目格式

```json
{
  "id": "q001",
  "question": "什么是 SQL 注入?如何防御?",
  "referenceAnswer": "参考答案要点...",
  "expectedKeywords": ["参数化查询", "预编译"],
  "expectedSources": ["SQL注入防护指南.md"],
  "category": "Web安全"
}
```

| 字段 | 用途 | 对应指标 |
|---|---|---|
| `question` | 送入 RAG / LLM Only 的问题 | — |
| `referenceAnswer` | 人工评分参考 | 人工评分 |
| `expectedKeywords` | 答案应覆盖的知识点 | Keyword Coverage |
| `expectedSources` | 期望命中的来源文档 | Hit@K / Precision@K / Recall@K / MRR |
| `category` | 题目分类 | 分组统计 |

## 扩充说明(正式评测数据生成方法)

1. 从 `dataset/`(或自建)知识文档中选题: 每篇文档派生 3-5 个可验证问题;
2. `expectedKeywords` 取文档中的关键技术词(可程序化抽取, 人工校对);
3. `expectedSources` 填写文档文件名(与上传时的文件名一致);
4. 通过系统「RAG 实验」页创建数据集并导入, 或调用
   `POST /api/evaluation/datasets/{id}/items` 批量写入;
5. 论文目标 100-200 题: 按上述流程逐步扩充, 系统不限制题目规模(单批上限 100 题)。

> 重要: 所有指标(Hit@K/P@K/R@K/MRR/关键词覆盖/引用准确率)均由程序依据
> `expectedSources` / `expectedKeywords` 与真实检索结果计算, 不使用 LLM 生成指标。
