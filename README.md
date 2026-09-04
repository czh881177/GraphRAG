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

* **环境**：Python 3.12（`.venv` 推荐 / conda `graphragexpr` 备选）+ Neo4j 5.x（Docker）

## 2. 目录结构



```
graphRAG/

├── backend/            # Flask API（7 个端点）

├── frontend/           # D3.js 可视化 + 问答面板

├── graphragexpr/       # 核心实现

│   ├── extract/        #   图谱构建 / 检索 / 样本数据

│   ├── vis/            #   独立可视化生成

│   ├── external_embedder.py   # OpenAI 兼容 Embedding（哈希降级）

│   └── custom_embedder.py     # 哈希 Embedder（离线 fallback）

├── lib/                # 本地前端库（vis-network / tom-select）

├── tests/              # pytest（embedder/KG/检索/集成）

├── data/

│   ├── raw/            # 原始医药语料（组长约定，gitignore）

│   └── processed/      # 清洗分块后的语料

├── docs/               # 契约 / 数据方案 / Schema / 准备清单 / 汇报框架

├── scripts/            # 环境检查 / Schema 初始化

├── *.ps1               # build_kg / start_backend / run_tests / generate_visualization

└── .env.example        # 环境变量模板（复制为 .env 并填写）
```

## 3. 快速开始（5 步）

> 组员开工前：请先完成 `docs/PREP_CHECKLIST.md` 中的准备项（通用准备 + 角色专项），再按下列步骤执行。
>
> **一句话理解整个流程**：装好依赖 → 启动图数据库 Neo4j → 建好"表结构和索引" → 把医药语料灌进图里 → 启动问答服务。

### 第 1 步：配置环境变量（告诉程序"连哪个库、用哪把钥匙"）

把模板复制成 `.env`（真实的配置文件，不会提交到 Git）：

```
copy .env.example .env
```

然后打开 `.env`，确认/填写：
- Neo4j 账号密码：默认 `neo4j / 12345678`，没改过密码就不用动
- `LLM_TOKEN`：你的 **DeepSeek API key**（必填，否则问答生成不了）

> ✅ 验证：`.env` 里 `NEO4J_URL` / `NEO4J_USER` / `NEO4J_PASSWORD` / `LLM_TOKEN` 都有值。

### 第 2 步：启动图数据库 Neo4j（跑在 Docker 里）

```
powershell -ExecutionPolicy Bypass -File .\start_neo4j.ps1
```

脚本会自动：检查 Docker → 找到/创建 `neo4j` 容器 → 启动并等它就绪（已运行则直接跳过，可反复执行）。
如果 Docker 拉不到镜像，用 6.4「常见坑」里的镜像前缀命令。

> ✅ 验证：看到「Neo4j 就绪」；浏览器打开 `http://localhost:7474` 能登录（`neo4j / 12345678`）。

### 第 3 步：初始化数据库结构（建"表"和"索引"）

```
.\.venv\Scripts\python.exe scripts\init_schema.py
```

（conda 用户用：`python scripts/init_schema.py`）
这个脚本建好约束、向量索引、全文索引和 6 类实体索引，**可反复执行**（幂等）。

> ✅ 验证：输出里各项全部打勾（✓），无红叉。

### 第 4 步：构建医药知识图谱（把语料灌进图里）【B 负责，9/13 前】

⚠ 当前 `build_kg_dyn.py` 仍是《红楼梦》的占位逻辑，B 正在按 `docs/DATA_PLAN.md` / `docs/SCHEMA.md` 改造成医药版。改造完成后执行：

```
python graphragexpr/extract/build_kg_dyn.py
```

> ✅ 验证：脚本末尾显示「总节点数 / 总关系数」，目标 ≥300 实体 / ≥500 关系。

### 第 5 步：启动后端 + 打开前端（看效果）

```
.\start_backend.ps1
```

再在浏览器打开 `frontend/index.html`，就可以浏览知识图谱、提问问答。

> ✅ 验证：后端启动后访问 `http://localhost:5000/api/health` 返回 `{"status":"ok"}`。

> **组长机环境状态（2026-09-04 已就绪）**：本机 `.venv`（Python 3.12.10）依赖已装全，`.env` 已填 DeepSeek key，Neo4j 容器（`neo4j:5-community`，端口 7474/7687，`neo4j/12345678`）运行中，`init_schema.py` 已建索引。以后重开电脑只需两步：
> 1. 打开 Docker Desktop → 运行 `powershell -ExecutionPolicy Bypass -File .\start_neo4j.ps1`（幂等，已在运行则跳过）
> 2. 启动后端 `.\start_backend.ps1`
>
> 团队其他成员按第 3 节 5 步自行配置（Docker 拉不到镜像时，用镜像前缀：`docker pull docker.m.daocloud.io/library/neo4j:5-community` 后 `docker tag` 成 `neo4j:5-community`）。

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
| B 数据 / 图谱 | 语料・抽取 Prompt・建图 | 图谱入库             |
| C 检索 / 生成 | 4 检索器・LLM・评估    | 命令行问答跑通          |
| D 后端      | Flask 端点・子图回查   | /api/graphrag 可用 |
| E 前端      | D3 可视化・问答面板     | 图可视化可展示          |

详细分工见 `docs/PREP_CHECKLIST.md` 与团队计划。

## 6. 项目前准备清单（组员必读）

> 完整版见 `docs/PREP_CHECKLIST.md`。以下为要点，卡住第一时间在群里提出。

### 6.1 全员通用准备

| # | 事项 | 验收标准 |
|---|---|---|
| A1 | 安装 Git 并配置身份 | `git --version` 有输出 |
| A2 | Git 账号加入仓库（用户名发组长） | 能 `git clone` 仓库 |
| A3 | 安装 VS Code / PyCharm（含 Python 插件） | 能打开 `D:\code\graphRAG` |
| A4 | **Python 3.12 环境**（任选其一）<br>① `.venv`（组长同款，推荐）：装 Python 3.12 → 项目内建 `.venv`<br>② Miniconda：`conda create -n graphragexpr python=3.12`<br>**勿用 3.14** | `python --version` 显示 3.12.x |
| A5 | 安装依赖：`python -m pip install -r requirements.txt`<br>（`.venv` 则用 `.venv\Scripts\python.exe -m pip ...`） | `import flask, neo4j, openai` 成功 |
| A6 | **Docker Desktop**（跑 Neo4j）：安装并启动，确认引擎 Running。<br>拉不动镜像的解法见 6.4「常见坑」 | `docker ps` 有输出 |
| A7 | **通读 docs/ 下文档**API_CONTRACT / DATA_PLAN / SCHEMA） 

**自检**（装完上面 A1–A6 后依次执行）：

```
git clone https://github.com/czh881177/GraphRAG.git
powershell -ExecutionPolicy Bypass -File .\setup.ps1          # 4/4 全绿
.\start_neo4j.ps1                                              # 起 Neo4j（幂等）
.\.venv\Scripts\python.exe scripts\init_schema.py              # 建索引
.\start_backend.ps1                                            # 后端 http://localhost:5000
```

### 6.2 角色专项准备

| 角色 | 专项要点 |
|---|---|
| **B 数据/图谱** | 定 20–40 篇医药语料来源并收集到 `data/raw/`（每篇一个 .txt）；装 pandas；准备 6 类本体类型表初稿；会 Neo4j Browser 查数（`MATCH (n) RETURN n LIMIT 25`） |
| **C 检索/生成** | 拿 DeepSeek key 并各测 1 次 chat 调用；测 embedding（不可用则走哈希降级）；通读 `rag_graph.py` / `rag_vector.py` / `external_embedder.py`；备 10 个测试问题（单跳/多跳/跨实体） |
| **D 后端 API** | 通读 `backend/api.py`；装 Postman/curl；Neo4j 起来后跑通 `GET /api/health`；精读 `API_CONTRACT.md` |
| **E 前端可视化** | 通读 `frontend/index.html`；会用 Chrome DevTools；复习 D3 力导向图 API；确认 `lib/` 本地库存在 |

### 6.3 验收

- [ ] 全员 clone 到本地
- [ ] 每人 `setup.ps1` 跑一遍，4 项检查全绿
- [ ] Neo4j 启动，`python scripts/init_schema.py` 成功
- [ ] `.env` 已配置
- [ ] 组会完成：任务认领、本体类型表初稿、10 个测试问题初稿、站会时间确定

### 6.4 常见坑（提前避雷）

| 坑 | 解决 |
|---|---|
| conda 命令找不到 | 用 **Anaconda Prompt** 打开再 `conda activate graphragexpr` |
| Python 版本装错 | 环境必须是 **3.12**（3.14 会导致部分库不兼容） |
| **Docker 拉不动 neo4j 镜像** | 国内直连 Docker Hub 常被墙、部分加速器已失效（Docker Desktop 的 containerd 模式下 daemon 镜像源不生效）。**改用镜像前缀拉取**：<br>`docker pull docker.m.daocloud.io/library/neo4j:5-community`<br>`docker tag docker.m.daocloud.io/library/neo4j:5-community neo4j:5-community`<br>再运行 `start_neo4j.ps1` |
| Neo4j 密码不一致 | 默认 `neo4j/12345678`；改密码须同步 `.env` |
| 向量索引查询报错 | Chunk 写入时必须带 `embedding` 属性（见 SCHEMA §6） |
| API key 泄漏 | `.env` 不入库；不截图发群；泄露立即在控制台重置 |
| 中文乱码 | 脚本已设 `PYTHONIOENCODING=utf-8`；文本文件统一 UTF-8 |