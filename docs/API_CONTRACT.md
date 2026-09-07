# 接口契约表（API Contract）v1.0

> 制定：组长 A · 生效：2026/9/7 · 变更需组长评审后更新本文件
> 所有接口基于 `backend/api.py`（Flask，端口 5000），已开启 CORS。
> 调用方（API 客户端 / 汇报演示脚本）通过 `http://localhost:5000/api` 调用。

## 通用约定

- Base URL：`http://localhost:5000/api`
- 响应格式：`application/json`；出错返回 `{"error": "<消息>"}`，HTTP 状态码 4xx/5xx
- 实体 ID：Neo4j `elementId(n)`（如 `4:abc123...`），**调用方视为不透明字符串**，不得解析格式

## 端点清单

| # | 方法 | 路径 | 用途 | 主责 |
|---|---|---|---|---|
| 1 | GET | `/api/health` | 健康检查（验证 Neo4j 连通） | D |
| 2 | GET | `/api/graph` | 获取完整知识图谱（实体+关系，不含 Chunk/Document） | D |
| 3 | GET | `/api/entities?type=药物` | 按类型/全部获取实体列表 | D |
| 4 | GET | `/api/entity/<entity_id>` | 获取单实体详情与连接 | D |
| 5 | GET | `/api/stats` | 图谱统计（节点/关系/按类型计数） | D |
| 6 | GET | `/api/search?q=<词>` | 按名称模糊搜索实体（最多 20 条） | D |
| 7 | POST | `/api/graphrag` | **GraphRAG 问答**（核心） | C+D |

---

## 1. GET /api/health

请求：无

```json
// 200
{ "status": "ok", "message": "Connected to Neo4j" }
// 500（Neo4j 不可达）
{ "status": "error", "message": "<异常详情>" }
```

## 2. GET /api/graph

请求：无

```json
// 200
{
  "nodes": [
    { "id": "4:xxx", "label": "阿司匹林", "type": "药物" },
    { "id": "4:yyy", "label": "拜耳公司", "type": "公司" }
  ],
  "edges": [
    { "source": "4:yyy", "target": "4:xxx", "type": "研发" }
  ]
}
```

> 注意：只返回实体间关系（排除 `:Chunk` / `:Document` 节点）。

## 3. GET /api/entities

| 参数 | 必填 | 说明 |
|---|---|---|
| type | 否 | 实体类型过滤（如 `药物`）；缺省返回全部 |

```json
// 200
{ "entities": [ { "id": "4:xxx", "type": "药物", "name": "阿司匹林" } ] }
```

## 4. GET /api/entity/<entity_id>

路径参数：`entity_id`（elementId）

```json
// 200
{
  "id": "4:xxx",
  "type": "药物",
  "properties": { "name": "阿司匹林" },
  "connections": [
    { "node": "环氧合酶", "relationship": "作用于", "direction": "outgoing" }
  ]
}
// 404（不存在）
{ "error": "Entity not found" }
```

## 5. GET /api/stats

请求：无

```json
// 200
{
  "total_nodes": 512,
  "total_relationships": 910,
  "nodes_by_type": { "药物": 120, "疾病": 80, "症状": 66, "公司": 30, "作用机制": 50, "副作用": 40, "概念": 126 },
  "relationships_by_type": { "研发": 30, "作用于": 120, "治疗": 90, "副作用": 66 }
}
```

## 6. GET /api/search

| 参数 | 必填 | 说明 |
|---|---|---|
| q | 是 | 搜索关键词（大小写不敏感，包含匹配） |

```json
// 200
{ "results": [ { "id": "4:xxx", "type": "药物", "name": "阿司匹林" } ] }
// 400（缺 q）
{ "error": "Query parameter 'q' is required" }
```

## 7. POST /api/graphrag（核心）

请求体：

| 字段 | 必填 | 说明 |
|---|---|---|
| question | 是 | 用户问题（中文） |
| method | 否 | 检索方式，默认 `vector_cypher`；枚举见下 |

```json
// 请求
{ "question": "哪些药物通过抑制环氧合酶发挥作用？", "method": "vector_cypher" }

// 200
{
  "answer": "根据上下文，通过抑制环氧合酶发挥作用的药物有……",
  "method": "vector_cypher",
  "subgraph": {
    "nodes": [ { "id": "4:xxx", "label": "阿司匹林", "type": "药物" } ],
    "edges": [ { "source": "4:xxx", "target": "4:yyy", "type": "作用于" } ]
  }
}
// 400（缺 question / 未知 method）
{ "error": "Question is required" }
```

### method 枚举

| method | 召回策略 | 是否图遍历 | 说明 |
|---|---|---|---|
| `vector` | 向量检索 | 否 | 仅返回相关文本块 |
| `vector_cypher`（默认） | 向量检索 | 是 | 向量召回 + 1~2 跳图扩展，返回文本+三元组 |
| `hybrid` | 向量 + 全文 | 否 | 需全文索引 text_fulltext |
| `hybrid_cypher` | 向量 + 全文 | 是 | 混合召回 + 图扩展 |

### subgraph 约定

- 仅 `vector_cypher` / `hybrid_cypher` 返回非空 subgraph；
- 可视化层用 `subgraph.nodes` / `subgraph.edges` 的 `id` 与全图做**金色高亮**；
- 若图谱无可召回数据，subgraph 为 `{ "nodes": [], "edges": [] }`。

---

## 接口验收检查清单（D 完成后用 curl/Postman 对照）

- [ ] `GET /api/graph` 返回完整图谱 JSON（实体+关系，不含 Chunk/Document）
- [ ] `POST /api/graphrag` 返回答案，且 `vector_cypher` / `hybrid_cypher` 带非空 subgraph
- [ ] `GET /api/search?q=<词>` 返回命中实体列表
- [ ] 异常场景（Neo4j 断开、空 question）有明确错误提示
