# 任务C交付文档：检索与生成

> 角色：C - 检索 / 生成
> 日期：2026/9/13
> 项目：医药 GraphRAG・药品 - 疾病 - 靶点知识图谱问答系统

---

## 1. 任务概述

负责四类检索器实现、LLM 接入、Embedding 接入与修复、40 条自动化评估，实现 GraphRAG 核心检索与生成链路。

## 2. 交付文件清单

| 文件 | 说明 | 状态 |
|------|------|------|
| `graphragexpr/extract/rag_vector.py` | 向量检索器（VectorRetriever） | ✅ 已完成 |
| `graphragexpr/extract/rag_graph.py` | 图遍历检索器（VectorCypherRetriever） | ✅ 已完成 |
| `graphragexpr/extract/rag_hybrid.py` | 混合检索器（HybridRetriever） | ✅ 已完成 |
| `graphragexpr/extract/rag_hybrid_cypher.py` | 混合+Cypher 检索器（HybridCypherRetriever + 多实体图增强） | ✅ 已完成 |
| `graphragexpr/external_embedder.py` | 外部 Embedding（智谱 embedding-3，OpenAI 兼容，哈希降级） | ✅ 已完成 |
| `graphragexpr/custom_embedder.py` | 哈希 Embedder（离线 fallback） | ✅ 已完成 |
| `evaluate_all.py` | 40 条自动评估脚本（4 检索器 × 10 问题） | ✅ 已完成 |
| `docs/EVALUATION_RESULTS.txt` | 40 条评估结果输出 | ✅ 已完成 |
| `tests/test_retrieval.py` | 检索器单元测试（4 项） | ✅ 已完成 |
| `tests/test_embedder.py` | Embedder 单元测试（8 项） | ✅ 已完成 |
| `tests/evaluation_template.py` | 评估模板 | ✅ 已完成 |
| `docs/TASK_C_DELIVERABLES.md` | 本交付文档 | ✅ 已完成 |

## 3. 四类检索器

### 3.1 向量检索（rag_vector.py）

- **类名**：`VectorRetriever`
- **原理**：问题经 Embedding 向量化后，在 Neo4j 向量索引 `text_embeddings` 中按 cosine 相似度召回 top-k 个 Chunk
- **返回**：文本片段内容
- **适用**：语义匹配强的问题，如"阿司匹林的作用机制是什么？"

### 3.2 图遍历检索（rag_graph.py）

- **类名**：`VectorCypherRetriever`
- **原理**：向量召回 Chunk 后，通过自定义 Cypher retrieval_query 沿 `FROM_CHUNK` 关系扩展到实体，再获取实体的一跳邻居（每实体≤12 邻居，每 chunk≤25 实体）
- **返回**：文本片段 + 图结构数据（实体、类型、邻居关系）
- **适用**：需要多跳关联的问题，如"哪些药物通过抑制环氧合酶发挥作用？"

### 3.3 混合检索（rag_hybrid.py）

- **类名**：`HybridRetriever`
- **原理**：向量检索 + 全文关键词检索结果融合排序，兼顾语义匹配与字面匹配
- **返回**：文本片段内容
- **适用**：包含专有名词或需要精确匹配的问题，如"拜耳公司研发了哪些药物？"

### 3.4 混合+Cypher 检索（rag_hybrid_cypher.py）

- **类名**：`HybridCypherRetriever` + 多实体图增强
- **原理**：
  1. LLM 从问题中提取医药实体（药物名、疾病名等）
  2. 针对每个实体，手动 Cypher 查询图谱获取其邻居关系（每实体≤15 条）
  3. 若无图谱上下文，退回到 HybridRetriever 向量+全文检索
  4. 拼接上下文后发送 LLM 生成答案
- **返回**：基于图关系的自然语言答案
- **适用**：推荐默认检索方式，兼顾语义召回与图结构上下文

### retrieval_query 限流设计

```cypher
WITH node
MATCH (node)<-[:FROM_CHUNK]-(entity)
OPTIONAL MATCH (entity)-[r]-(neighbor)
WHERE NOT neighbor:Chunk AND NOT neighbor:Document AND neighbor <> entity
WITH node, entity, neighbor, r
WHERE r IS NOT NULL
ORDER BY coalesce(entity.name, '')
WITH node, entity, collect(DISTINCT {
    target: coalesce(neighbor.name, ''),
    rel: type(r)
})[..12] AS neighbors
RETURN
    node.text AS info,
    collect(DISTINCT {
        entity: coalesce(entity.name, ''),
        type: labels(entity)[0],
        neighbors: neighbors
    })[..25] AS graph_data
```

- 每实体最多 12 个邻居
- 每 Chunk 最多 25 个实体
- 控制上下文体积，避免 LLM 输入超限

## 4. Embedding 方案

### 4.1 外部 Embedding（external_embedder.py）

- **服务**：智谱 embedding-3（OpenAI 兼容接口）
- **维度**：1536 维
- **配置**：`EMBED_ENDPOINT`、`EMBED_MODEL`、`EMBED_TOKEN`、`EMBED_DIMENSION`
- **降级机制**：外部服务调用失败时，自动降级为本地哈希 Embedder

### 4.2 哈希 Embedder（custom_embedder.py）

- **原理**：基于文本哈希生成固定维度向量（离线 fallback）
- **特点**：确定性、无需网络、不含语义信息
- **用途**：仅在外部 Embedding 不可用时降级使用，语义召回效果差

### 4.3 Embedding 修复历程

| 阶段 | 状态 | 现象 |
|------|------|------|
| 初期 | 外部 Embedding 调用失败 | 降级为哈希向量，3 个检索器返回「无法回答」 |
| 排查 | 确认哈希向量无语义信息 | 向量检索近似随机，相关实体无法召回 |
| 修复 | 接入智谱 embedding-3（1536 维） | 重建全库向量，语义召回恢复 |
| 验证 | 10 题标准测试集 | 四种检索器全部答对，回归通过 |

## 5. LLM 生成

- **模型**：DeepSeek（deepseek-chat）
- **接口**：OpenAI 兼容（`LLM_ENDPOINT`、`LLM_TOKEN`、`LLM_MODEL`）
- **参数**：temperature=0（保证答案稳定性）
- **Prompt 模板**：

```
你是一个专业的医药知识问答助手。
请仅根据提供的上下文回答用户问题。
上下文可能包含：
1. 医药文本片段
2. 知识图谱关系
3. 实体之间的关联信息
如果上下文不足以回答问题，请明确说明信息不足，
不要自行编造医学事实。

# 用户问题
{query_text}

# 上下文
{context}

# 回答
```

## 6. 40 条评估

### 6.1 评估脚本（evaluate_all.py）

- 自动运行 4 检索器 × 10 问题 = 40 条问答
- 通过子进程调用各检索器脚本，管道发送问题
- 正则提取答案，输出汇总表格
- 结果保存于 `docs/EVALUATION_RESULTS.txt`

### 6.2 10 个测试问题

| # | 问题 | 类型 |
|---|------|------|
| 1 | 阿司匹林的作用机制是什么？ | 单跳 |
| 2 | 哪些药物通过抑制环氧合酶发挥作用？ | 多跳 |
| 3 | 布洛芬有哪些副作用？ | 单跳 |
| 4 | 拜耳公司研发了哪些药物？ | 单跳 |
| 5 | 服用阿司匹林会引发什么症状？ | 多跳 |
| 6 | 拜耳公司研发的药物有哪些副作用？ | 多跳 |
| 7 | 环氧合酶与哪些药物有关？ | 多跳 |
| 8 | 对乙酰氨基酚的作用机制与布洛芬有什么不同？ | 对比 |
| 9 | 哪些药物可以治疗头痛？ | 多跳 |
| 10 | 长期服用布洛芬有什么风险？ | 风险 |

### 6.3 评估结果

四个检索器（vector / graph / hybrid / hybrid_cypher）均能正常输出答案，无「无法回答」或「未解析」情况。详细结果见 `docs/EVALUATION_RESULTS.txt`。

## 7. 单元测试

| 测试文件 | 用例数 | 覆盖范围 |
|----------|--------|----------|
| `tests/test_retrieval.py` | 4 | 向量索引创建、Cypher reduce、图遍历查询、检索查询格式 |
| `tests/test_embedder.py` | 8 | 哈希 Embedder 初始化、维度、归一化、确定性、不同文本、中文、空串 |

全部通过（pytest 33 项整体通过）。

## 8. 检索器使用方式

### 命令行交互

```powershell
# 向量检索
.\.venv\Scripts\python.exe graphragexpr\extract\rag_vector.py

# 图遍历检索
.\.venv\Scripts\python.exe graphragexpr\extract\rag_graph.py

# 混合检索
.\.venv\Scripts\python.exe graphragexpr\extract\rag_hybrid.py

# 混合+Cypher（推荐）
.\.venv\Scripts\python.exe graphragexpr\extract\rag_hybrid_cypher.py
```

### API 调用

```powershell
curl -X POST http://localhost:5000/api/graphrag `
  -H "Content-Type: application/json" `
  -d '{\"question\":\"阿司匹林的作用机制是什么？\",\"method\":\"hybrid_cypher\"}'
```

支持 method：`vector` / `vector_cypher` / `hybrid` / `hybrid_cypher`

---

*文档版本：v1.0 · 2026-09-13*
