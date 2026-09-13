# 任务B交付文档：数据与图谱构建

> 角色：B - 数据 / 图谱
> 日期：2026/9/13
> 项目：医药 GraphRAG・药品 - 疾病 - 靶点知识图谱问答系统

---

## 1. 任务概述

负责医药语料收集与清洗、实体关系抽取、语义向量化、Neo4j 入库与图谱质检，构建完整的医药领域知识图谱。

## 2. 交付文件清单

| 文件 | 说明 | 状态 |
|------|------|------|
| `data/raw/` | 32 篇医药领域原始语料（.txt，gitignore） | ✅ 已完成 |
| `data/processed/` | 清洗分块后的语料（gitignore） | ✅ 已完成 |
| `graphragexpr/extract/build_kg_dyn.py` | 动态建图脚本（实体关系抽取 + 向量化 + 入库） | ✅ 已完成 |
| `graphragexpr/extract/curated_data_a.py` | 精选数据 A（药物-机制-疾病关系） | ✅ 已完成 |
| `graphragexpr/extract/curated_data_b.py` | 精选数据 B（副作用-症状关系） | ✅ 已完成 |
| `graphragexpr/extract/curated_data_c.py` | 精选数据 C（公司-药物关系） | ✅ 已完成 |
| `graphragexpr/extract/curated_data_x.py` | 精选数据 X（补充关系） | ✅ 已完成 |
| `scripts/prepare_corpus.py` | 语料预处理脚本 | ✅ 已完成 |
| `scripts/verify_graph.py` | 图谱质检脚本 | ✅ 已完成 |
| `build_kg_dyn.ps1` | 建图 PowerShell 一键脚本 | ✅ 已完成 |
| `docs/DATA_PLAN.md` | 数据方案文档 | ✅ 已完成 |
| `docs/SCHEMA.md` | 图谱 Schema 设计文档 | ✅ 已完成 |
| `docs/TASK_B_DELIVERABLES.md` | 本交付文档 | ✅ 已完成 |

## 3. 图谱数据规模

| 指标 | 数值 |
|------|------|
| 原始语料 | 32 篇医药领域专业文本 |
| 实体节点 | 361 个 |
| 关系边 | 513 条 |
| 实体类型 | 7 类 |

### 实体类型分布

| 实体类型 | 数量 |
|----------|------|
| 概念 | 78 |
| 疾病 | 63 |
| 副作用 | 59 |
| 症状 | 56 |
| 作用机制 | 48 |
| 药物 | 44 |
| 公司 | 13 |

## 4. 建图流程

### 4.1 语料收集与清洗

- 收集 32 篇医药领域专业文本（药物说明书、药理学教材片段、医药百科等）
- 统一 UTF-8 编码，去除 HTML 标签与无关格式
- 按语义段落分块，每块控制在合理长度

### 4.2 实体关系抽取

- 通过 LLM 结构化抽取实体与关系三元组
- 实体类型限定为 7 类：药物、疾病、症状、作用机制、副作用、公司、概念
- 关系类型包括：作用于、抑制、导致、缓解、研发、属于等
- 人工精选数据（curated_data_a/b/c/x）补充关键关系，确保图谱覆盖核心医药知识

### 4.3 语义向量化

- 使用智谱 embedding-3（1536 维）为每个 Chunk 生成语义向量
- 向量存储于 Chunk 节点的 `embedding` 属性
- 建立 Neo4j 向量索引 `text_embeddings`（1536 维，cosine 相似度）
- 建立全文索引 `text_fulltext` 支持关键词检索

### 4.4 Neo4j 入库

- 创建实体节点（带标签与 name 属性）
- 创建关系边（带关系类型）
- Chunk 节点通过 `FROM_CHUNK` 关系关联到实体
- 建立向量索引与全文索引

### 4.5 图谱质检

- **实体去重合并**：同义写法归一（如"布洛芬"与"IBUPROFEN"）
- **关系类型归一化**：统一关系命名，避免同义关系重复
- **坏边检查**：0 条无效边（无悬空关系、无自环异常）
- **向量完整性**：全部实体附带语义向量，维度一致（1536 维）
- **连通性检查**：核心实体子图连通

## 5. Schema 设计

### 核心标签

| 标签 | 说明 | 关键属性 |
|------|------|----------|
| `药物` | 药品/化合物 | name, description |
| `疾病` | 疾病/病症 | name, description |
| `症状` | 症状表现 | name |
| `作用机制` | 药物作用靶点/机制 | name |
| `副作用` | 不良反应 | name |
| `公司` | 制药公司 | name |
| `概念` | 医药概念/生理过程 | name |
| `Chunk` | 文本块 | text, embedding |
| `Document` | 文档 | title, source |

### 核心关系类型

| 关系 | 说明 | 示例 |
|------|------|------|
| `作用于` | 药物作用于靶点/机制 | 阿司匹林 -[:作用于]-> 环氧合酶 |
| `抑制` | 实体抑制另一实体 | 阿司匹林 -[:抑制]-> 环氧合酶 |
| `导致` | 实体导致症状/副作用 | 布洛芬 -[:导致]-> 胃肠道不适 |
| `缓解` | 药物缓解症状 | 对乙酰氨基酚 -[:缓解]-> 头痛 |
| `研发` | 公司研发药物 | 拜耳 -[:研发]-> 阿司匹林 |
| `属于` | 实体属于类别 | 阿司匹林 -[:属于]-> 非甾体抗炎药 |
| `FROM_CHUNK` | 实体来源于文本块 | 阿司匹林 <-[:FROM_CHUNK]- Chunk |

## 6. 建图命令

```powershell
# 一键建图（语料清洗 → 抽取 → 向量化 → 入库）
.\build_kg_dyn.ps1

# 或分步执行
.\.venv\Scripts\python.exe scripts\prepare_corpus.py
.\.venv\Scripts\python.exe graphragexpr\extract\build_kg_dyn.py

# 质检
.\.venv\Scripts\python.exe scripts\verify_graph.py
```

## 7. 数据约定

- 原始语料只放 `data/raw/`，不提交 Git（见 .gitignore）
- 清洗后语料放 `data/processed/`，不提交 Git
- 图谱数据存储于 Neo4j，不导出为文件提交
- 写库由 B 串行执行，避免并发覆盖

---

*文档版本：v1.0 · 2026-09-13*
