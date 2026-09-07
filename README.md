# 医药 GraphRAG・药品 - 疾病 - 靶点知识图谱问答系统

> 课程实践项目・5 人小组・2026/9/7 – 2026/9/20（两周）
> 主题：基于 Neo4j + DeepSeek 的医药领域图增强检索生成（GraphRAG）问答系统
> 基线代码：tjudb/2026graphrag（复用其 Neo4j 建图、检索器、Flask API、D3 可视化技术栈）



***

## 1. 项目简介

输入自然语言问题（如 "哪些药物通过抑制环氧合酶发挥作用？"），系统通过**向量检索 + 知识图谱遍历**召回相关证据（文本片段 + 实体关系三元组），交给 LLM 生成答案，并在图谱可视化中高亮 "答案依据的子图"。



* **图数据库**：Neo4j 5.x（Community）

* **LLM / Embedding**：DeepSeek（deepseek-chat，OpenAI 兼容接口）

* **后端**：Flask（端口 5000）+ flask-cors

* **图谱可视化**：D3.js（`generate_visualization.ps1` 生成独立 HTML 图谱视图）

* **环境**：Python 3.12（`.venv` 推荐 / conda `graphragexpr` 备选）+ Neo4j 5.x（Docker）

## 2. 目录结构



```
graphRAG/

├── backend/            # Flask API（问答/健康检查）

├── graphragexpr/       # 核心实现

│   ├── extract/        #   图谱构建 / 检索 / 样本数据

│   ├── vis/            #   独立可视化生成

│   ├── external_embedder.py   # OpenAI 兼容 Embedding（哈希降级）

│   └── custom_embedder.py     # 哈希 Embedder（离线 fallback）

├── tests/              # pytest（embedder/KG/检索/集成）

├── data/

│   ├── raw/            # 原始医药语料（组长约定，gitignore）

│   └── processed/      # 清洗分块后的语料

├── docs/               # 契约 / 数据方案 / Schema / 准备清单

├── scripts/            # 环境检查 / Schema 初始化

├── *.ps1               # build_kg / start_backend / run_tests / generate_visualization

└── .env.example        # 环境变量模板（复制为 .env 并填写）
```


## 3. 团队协作约定（组长 A 制定）



| 项目     | 约定                                                    |
| ------ | ----------------------------------------------------- |
| 分支     | `main`（稳定，仅组长合并）；功能分支 `feat/<模块>`（如 `feat/retrieval`） |
| 提交     | `feat:` / `fix:` / `docs:` / `test:` 前缀 + 一句话说明（英文）   |
| 接口     | 以 `docs/API_CONTRACT.md` 为准，改动需组长评审后更新契约              |
| Schema | 以 `docs/SCHEMA.md` 为准，禁止各自改标签 / 关系类型                  |
| 数据     | 原始语料只放 `data/raw/`，不提交 Git（见 .gitignore）              |
| 站会     | 每天 10 分钟：昨日完成 / 今日计划 / 阻塞                             |
| 写库     | 由 B 串行执行（避免并发覆盖），其余成员只读                               |

## 4. 成员分工速览



| 角色        | 职责              | 第一周红线                  |
| --------- | --------------- | ---------------------- |
| A 组长 / 架构 | 环境・契约・Schema・联调 | 工程底座 + 汇报框架            |
| B 数据 / 图谱 | 语料・抽取 Prompt・建图 | 图谱入库             |
| C 检索 / 生成 | 4 检索器・LLM・评估    | 命令行问答跑通          |
| D 后端      | Flask 端点・子图回查   | /api/graphrag 可用 |
| E 可视化/汇报 | 图谱可视化・汇报 Demo     | 图谱可视化可展示        |

详细分工见 `docs/PREP_CHECKLIST.md` 与团队计划。

## 5. 项目前准备清单（组员必读）

> 完整版见 `docs/PREP_CHECKLIST.md`。以下为要点，卡住第一时间在群里提出。

### 5.1 全员通用准备

| # | 事项 | 验收标准 |
|---|---|---|
| A1 | 安装 Git 并配置身份 | `git --version` 有输出 |
| A2 | Git 账号加入仓库（用户名发组长） | 能 `git clone` 仓库 |
| A3 | 安装 VS Code / PyCharm（含 Python 插件） | 能打开 `D:\code\graphRAG` |
| A4 | **Python 3.12 环境**（任选其一）<br>① `.venv`（组长同款，推荐）：装 Python 3.12 → 项目内建 `.venv`<br>② Miniconda：`conda create -n graphragexpr python=3.12`<br>**勿用 3.14** | `python --version` 显示 3.12.x |
| A5 | 安装依赖：`python -m pip install -r requirements.txt`<br>（`.venv` 则用 `.venv\Scripts\python.exe -m pip ...`） | `import flask, neo4j, openai` 成功 |
| A6 | **Docker Desktop**（跑 Neo4j）：安装并启动，确认引擎 Running。<br>拉不动镜像的解法见 5.4「常见坑」 | `docker ps` 有输出 |
| A7 | **通读 docs/ 下文档**（README / API_CONTRACT / DATA_PLAN / SCHEMA） | 组会能说出自己模块的输入/输出 |

**自检**（装完上面 A1–A6 后依次执行）：

```
git clone https://github.com/czh881177/GraphRAG.git
powershell -ExecutionPolicy Bypass -File .\setup.ps1          # 4/4 全绿
.\start_neo4j.ps1                                              # 起 Neo4j（幂等）
.\.venv\Scripts\python.exe scripts\init_schema.py              # 建索引
.\start_backend.ps1                                            # 后端 http://localhost:5000
```

### 5.2 角色专项准备

| 角色 | 专项要点 |
|---|---|
| **B 数据/图谱** | 定 20–40 篇医药语料来源并收集到 `data/raw/`（每篇一个 .txt）；装 pandas；准备 6 类本体类型表初稿；会 Neo4j Browser 查数（`MATCH (n) RETURN n LIMIT 25`） |
| **C 检索/生成** | 拿 DeepSeek key 并各测 1 次 chat 调用；测 embedding（不可用则走哈希降级）；通读 `rag_graph.py` / `rag_vector.py` / `external_embedder.py`；备 10 个测试问题（单跳/多跳/跨实体） |
| **D 后端 API** | 通读 `backend/api.py`；装 Postman/curl；Neo4j 起来后跑通 `GET /api/health`；精读 `API_CONTRACT.md` |
| **E 可视化/汇报** | 通读 `graphragexpr/vis/visualize_standalone.py`；会用 `generate_visualization.ps1` 生成图谱 HTML；准备汇报 Demo 演示脚本 |

### 5.3 验收

- [ ] 全员 clone 到本地
- [ ] 每人 `setup.ps1` 跑一遍，4 项检查全绿
- [ ] Neo4j 启动，`python scripts/init_schema.py` 成功
- [ ] `.env` 已配置
- [ ] 组会完成：任务认领、本体类型表初稿、10 个测试问题初稿、站会时间确定

### 5.4 常见坑（提前避雷）

| 坑 | 解决 |
|---|---|
| conda 命令找不到 | 用 **Anaconda Prompt** 打开再 `conda activate graphragexpr` |
| Python 版本装错 | 环境必须是 **3.12**（3.14 会导致部分库不兼容） |
| **Docker 拉不动 neo4j 镜像** | 国内直连 Docker Hub 常被墙、部分加速器已失效（Docker Desktop 的 containerd 模式下 daemon 镜像源不生效）。**改用镜像前缀拉取**：<br>`docker pull docker.m.daocloud.io/library/neo4j:5-community`<br>`docker tag docker.m.daocloud.io/library/neo4j:5-community neo4j:5-community`<br>再运行 `start_neo4j.ps1` |
| Neo4j 密码不一致 | 默认 `neo4j/12345678`；改密码须同步 `.env` |
| 向量索引查询报错 | Chunk 写入时必须带 `embedding` 属性（见 SCHEMA §6） |
| API key 泄漏 | `.env` 不入库；不截图发群；泄露立即在控制台重置 |
| 中文乱码 | 脚本已设 `PYTHONIOENCODING=utf-8`；文本文件统一 UTF-8 |