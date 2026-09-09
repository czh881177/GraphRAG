# 任务D交付文档：后端 API 开发

> 角色：D - 后端 API  
> 负责人：[你的名字]  
> 日期：2026/9/6  
> 项目：医药 GraphRAG・药品 - 疾病 - 靶点知识图谱问答系统

---

## 1. 任务概述

负责 Flask 后端 API 开发，提供 7 个端点服务于知识图谱问答系统，实现数据查询、实体搜索和 GraphRAG 问答核心功能。

## 2. 交付文件清单

| 文件 | 说明 | 状态 |
|------|------|------|
| `backend/api.py` | Flask API 主文件，包含 7 个端点实现 | ✅ 已完成 |
| `docs/TASK_D_DELIVERABLES.md` | 本交付文档 | ✅ 已完成 |
| `docs/TASK_D_COMPLETION_REPORT.md` | 任务完成报告 | ✅ 已完成 |
| `tests/test_api_d.py` | 7 个端点的离线单元测试（Fake Neo4j Driver） | ✅ 已完成 |

## 3. 已实现的 API 端点

### 3.1 GET /api/health - 健康检查

- **功能**：验证 Neo4j 数据库连通性
- **成功响应 (200)**：
```json
{ "status": "ok", "message": "Connected to Neo4j" }
```
- **失败响应 (500)**：
```json
{ "status": "error", "message": "<异常详情>" }
```

### 3.2 GET /api/graph - 获取完整知识图谱

- **功能**：返回知识图谱的节点和边（排除 Chunk/Document 节点）
- **响应格式**：
```json
{
  "nodes": [{"id": "4:xxx", "label": "阿司匹林", "type": "药物"}],
  "edges": [{"source": "4:yyy", "target": "4:xxx", "type": "作用于"}]
}
```

### 3.3 GET /api/entities - 实体列表

- **功能**：按类型过滤获取实体列表
- **参数**：`type`（可选）- 实体类型过滤
- **白名单**：药物、疾病、症状、公司、作用机制、副作用、概念
- **响应**：
```json
{ "entities": [{"id": "4:xxx", "type": "药物", "name": "阿司匹林"}] }
```

### 3.4 GET /api/entity/<entity_id> - 实体详情

- **功能**：获取单实体详情与连接关系
- **参数**：`entity_id` - Neo4j elementId
- **响应**：
```json
{
  "id": "4:xxx",
  "type": "药物",
  "properties": {"name": "阿司匹林"},
  "connections": [{"node": "环氧合酶", "relationship": "作用于", "direction": "outgoing"}]
}
```

### 3.5 GET /api/stats - 图谱统计

- **功能**：返回图谱统计信息（与 `/api/graph` 口径一致，排除 Chunk/Document 节点及与其相关的关系）
- **响应**：
```json
{
  "total_nodes": 512,
  "total_relationships": 910,
  "nodes_by_type": {"药物": 120, "疾病": 80},
  "relationships_by_type": {"研发": 30, "作用于": 120}
}
```

### 3.6 GET /api/search - 实体搜索

- **功能**：按名称模糊搜索实体（最多20条）
- **参数**：`q`（必填）- 搜索关键词
- **响应**：
```json
{ "results": [{"id": "4:xxx", "type": "药物", "name": "阿司匹林"}] }
```

### 3.7 POST /api/graphrag - GraphRAG 问答核心（与C合作）

- **功能**：执行 GraphRAG 查询并返回答案与子图
- **请求体**：
```json
{ "question": "哪些药物通过抑制环氧合酶发挥作用？", "method": "vector_cypher" }
```
- **method 枚举**：`vector` | `vector_cypher`(默认) | `hybrid` | `hybrid_cypher`
- **响应**：
```json
{
  "answer": "根据上下文，通过抑制环氧合酶发挥作用的药物有……",
  "method": "vector_cypher",
  "subgraph": {
    "nodes": [{"id": "4:xxx", "label": "阿司匹林", "type": "药物"}],
    "edges": [{"source": "4:xxx", "target": "4:yyy", "type": "作用于"}]
  }
}
```

## 4. 技术实现要点

### 4.1 安全考虑
- **SQL注入防护**：Cypher 标签使用白名单校验，防止注入攻击
- **API Key管理**：通过 `.env` 文件管理敏感信息，不提交到 Git

### 4.2 错误处理
- 所有端点均包含 try-catch 错误处理
- 统一错误响应格式：`{"error": "<消息>"}`
- 使用 HTTP 状态码区分成功/失败

### 4.3 性能优化
- 使用 Neo4j `elementId` 作为节点唯一标识
- 搜索结果限制返回数量（LIMIT 20）
- 图谱查询排除 Chunk/Document 节点减少数据量

### 4.4 跨域支持
- 使用 flask-cors 启用 CORS，支持前端跨域调用

## 5. 验收检查清单

| 检查项 | 状态 |
|--------|------|
| GET /api/health 响应正常 | ✅ |
| GET /api/graph 返回图谱数据 | ✅ |
| GET /api/entities 支持类型过滤 | ✅ |
| GET /api/entity/<id> 返回实体详情 | ✅ |
| GET /api/stats 返回统计数据 | ✅ |
| GET /api/search 支持模糊搜索 | ✅ |
| POST /api/graphrag 支持4种检索方法 | ✅ |
| 错误处理完善 | ✅ |
| CORS 已启用 | ✅ |
| 符合 API_CONTRACT.md 契约 | ✅ |

## 6. 启动说明

```bash
# 1. 确保 Neo4j 已启动
.\start_neo4j.ps1

# 2. 启动后端服务
.\start_backend.ps1

# 3. 验证服务
# 访问 http://localhost:5000/api/health
```

## 7. 与前后端的协作

### 与前端（E）协作
- 提供符合 API_CONTRACT.md 的接口
- 确保 subgraph 数据格式与前端高亮逻辑兼容
- 联调测试：图谱渲染、问答高亮、搜索、异常处理

### 与检索/生成（C）协作
- `/api/graphrag` 端点集成 C 实现的检索器
- 支持 4 种检索方法：vector、vector_cypher、hybrid、hybrid_cypher
- 返回 subgraph 数据供前端可视化高亮

---

## 8. 自测命令（curl 示例）

```bash
# 健康检查
curl http://localhost:5000/api/health

# 获取图谱
curl http://localhost:5000/api/graph

# 搜索实体
curl "http://localhost:5000/api/search?q=阿司匹林"

# GraphRAG 问答
curl -X POST http://localhost:5000/api/graphrag \
  -H "Content-Type: application/json" \
  -d '{"question": "哪些药物通过抑制环氧合酶发挥作用？", "method": "vector_cypher"}'
```

---

*文档版本：v1.0*  
*最后更新：2026/9/6*
