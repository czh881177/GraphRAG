# Neo4j Schema 设计 v1.0（医药 GraphRAG）

> 制定：组长 A · 生效：2026/9/7 · 变更需评审
> 落地脚本：`scripts/init_schema.py`（幂等，可重复执行）

## 1. 节点（Label）与属性

| Label | 关键属性 | 说明 |
|---|---|---|
| `Document` | id, name, text | 一篇原始文档（如"阿司匹林说明书"） |
| `Chunk` | text, embedding, index | 文本分块，携带 1536 维向量 |
| `药物` | name | 药品/活性成分 |
| `疾病` | name | 疾病/适应症 |
| `症状` | name | 症状表现 |
| `公司` | name | 药企/研发机构 |
| `作用机制` | name | 靶点/机制 |
| `副作用` | name | 不良反应 |

> 实体 Label = 本体类型（中文 Label），`name` 作为实体唯一键。

## 2. 关系（Relationship）

| 关系 | 起点 → 终点 | 说明 |
|---|---|---|
| `PART_OF` | Chunk → Document | 分块属于文档 |
| `FROM_CHUNK` | 实体 → Chunk | 实体在哪个分块中被提及（检索图遍历的关键入口） |
| `研发` / `作用于` / `治疗` / `缓解` / `副作用` / `属于` | 实体 → 实体 | 业务关系，见 DATA_PLAN §5 |

## 3. 约束（Constraints）

```cypher
CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chunk_index IF NOT EXISTS FOR (n:Chunk) REQUIRE n.index IS UNIQUE;
```

> 实体唯一性由 `MERGE (e:Label {name: $name})` 保证（name 索引可加速）。

## 4. 索引（Indexes）

### 4.1 向量索引（用于向量检索，必建）

```cypher
CREATE VECTOR INDEX text_embeddings IF NOT EXISTS
FOR (n:Chunk) ON (n.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};
```

### 4.2 全文索引（用于 hybrid 检索，必建）

```cypher
CREATE FULLTEXT INDEX text_fulltext IF NOT EXISTS
FOR (n:Chunk) ON EACH [n.text];
```

### 4.3 实体 name 索引（建议，加速 MERGE 与检索）

```cypher
CREATE INDEX entity_name IF NOT EXISTS FOR (n:药物) ON (n.name);
CREATE INDEX entity_name2 IF NOT EXISTS FOR (n:疾病) ON (n.name);
CREATE INDEX entity_name3 IF NOT EXISTS FOR (n:症状) ON (n.name);
CREATE INDEX entity_name4 IF NOT EXISTS FOR (n:公司) ON (n.name);
CREATE INDEX entity_name5 IF NOT EXISTS FOR (n:作用机制) ON (n.name);
CREATE INDEX entity_name6 IF NOT EXISTS FOR (n:副作用) ON (n.name);
```

## 5. 图数据模型（示意）

```
(Document) <--PART_OF-- (Chunk) <--FROM_CHUNK-- (药物)
                                                  |  作用于
                                                  v
                                              (作用机制)
                                                  ^  治疗
(公司) --研发--> (药物) --治疗--> (疾病) --症状--> (症状)
                       |--副作用--> (副作用)
```

## 6. 注意

- `Chunk.index` 唯一：同一文档内分块编号唯一；跨文档建议 `{doc_id}_{i}` 或由 B 在写入时保证唯一。
- 建图脚本写入 Chunk 时**必须同时写 embedding**，否则向量索引查询报错。
- 清库用 `MATCH (n) DETACH DELETE n`（仅 B 执行，串行）。
