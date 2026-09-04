# 医药 GraphRAG・药品 - 疾病 - 靶点知识图谱问答系统

> 课程实践项目・5 人小组・2026/9/7 – 2026/9/20（两周）
> 主题：基于 Neo4j + DeepSeek 的医药领域图增强检索生成（GraphRAG）问答系统
> 基线代码：tjudb/2026graphrag（复用其 Neo4j 建图、检索器、Flask API、D3 可视化技术栈）



***

## 1. 项目简介

输入自然语言问题（如 "哪些药物通过抑制环氧合酶发挥作用？"），系统通过**向量检索 + 知识图谱遍历**召回相关证据（文本片段 + 实体关系三元组），交给 LLM 生成答案，并在前端可视化中高亮 "答案依据的子图"。



* **图数据库**：Neo4j 5.x（Community）

* **LLM / Embedding**：DeepSeek（deepseek-chat，OpenAI 兼容接口）

* **后端**：Flask（端口 5000）+ flask-cors

* **前端**：D3.js 力导向图 + 原生 HTML/CSS

* **环境**：conda（graphragexpr 环境）+ Python 3.12

## 2. 目录结构



```
graphRAG/

├── backend/            # Flask API（7 个端点）

├── frontend/           # D3.js 可视化 + 问答面板

├── graphragexpr/       # 核心实现

│   ├── extract/        #   图谱构建 / 检索 / 样本数据

│   ├── vis/            #   独立可视化生成

│   ├── external\_embedder.py   # OpenAI 兼容 Embedding（哈希降级）

│   └── custom\_embedder.py     # 哈希 Embedder（离线 fallback）

├── lib/                # 本地前端库（vis-network / tom-select）

├── tests/              # pytest（embedder/KG/检索/集成）

├── data/

│   ├── raw/            # 原始医药语料（组长约定，gitignore）

│   └── processed/      # 清洗分块后的语料

├── docs/               # 契约 / 数据方案 / Schema / 汇报框架

├── scripts/            # 环境检查 / Schema 初始化

├── \*.ps1               # build\_kg / start\_backend / run\_tests / generate\_visualization

└── .env.example        # 环境变量模板（复制为 .env 并填写）
```

## 3. 快速开始（5 步）



```
\# 1. 配置环境变量

copy .env.example .env        # 然后编辑 .env 填入 Neo4j / DeepSeek 凭据

\# 2. 启动 Neo4j（本机或 Docker），确认 7687 端口可连

\# 3. 初始化数据库 Schema 与索引（幂等）

python scripts/init\_schema.py

\# 4. 构建医药知识图谱（语料放入 data/raw/）

\#    （B 完成 data/processed 后）python graphragexpr/extract/build\_kg\_dyn.py

\# 5. 启动后端 + 打开前端

./start\_backend.ps1           # http://localhost:5000

\# 浏览器打开 frontend/index.html
```

## 4. 团队协作约定（组长 A 制定）



| 项目     | 约定                                                    |
| ------ | ----------------------------------------------------- |
| 分支     | `main`（稳定，仅组长合并）；功能分支 `feat/<模块>`（如 `feat/retrieval`） |
| 提交     | `feat:` / `fix:` / `docs:` / `test:` 前缀 + 一句话说明（英文）   |
| 接口     | 以 `docs/API_CONTRACT.md` 为准，改动需组长评审后更新契约              |
| Schema | 以 `docs/SCHEMA.md` 为准，禁止各自改标签 / 关系类型                  |
| 数据     | 原始语料只放 `data/raw/`，不提交 Git（见 .gitignore）              |
| 站会     | 每天 10 分钟：昨日完成 / 今日计划 / 阻塞                             |
| 写库     | 由 B 串行执行（避免并发覆盖），其余成员只读                               |

## 5. 成员分工速览



| 角色        | 职责              | 第一周红线                  |
| --------- | --------------- | ---------------------- |
| A 组长 / 架构 | 环境・契约・Schema・联调 | 工程底座 + 汇报框架            |
| B 数据 / 图谱 | 语料・抽取 Prompt・建图 | 图谱入库（9/13）             |
| C 检索 / 生成 | 4 检索器・LLM・评估    | 命令行问答跑通（9/13）          |
| D 后端      | Flask 端点・子图回查   | /api/graphrag 可用（9/13） |
| E 前端      | D3 可视化・问答面板     | 图可视化可展示（9/13）          |

详细分工见 `docs/WEEK1_REPORT.md` 与团队计划。