# 项目前准备清单（PREP_CHECKLIST）v1.0

> 制定：组长 A · 面向：全体组员（B/C/D/E）· 完成 A 部分
> 原则：任何一项卡住，第一时间在群里提出，由 A 协调，不要自己闷着装。

---

## A. 全员通用准备（每个人）

| # | 事项 | 具体要求 | 验收标准 |
|---|---|---|---|
| A1 | 安装 Git | 安装并配置 user.name / user.email | `git --version` 有输出 |
| A2 | Git 账号 + 加入仓库 | 注册 GitHub 或 Gitee，把用户名发给 A，被加入仓库并授予权限 | 能 `git clone` 仓库 |
| A3 | 代码编辑器 | VS Code（推荐）或 PyCharm；装 Python / PowerShell 插件 | 能打开 `D:\code\graphRAG` |
| A4 | Python 3.12 环境 | **任选其一**：① 装 Python 3.12 → 项目内建 `.venv`（组长同款，推荐）；② 装 Miniconda → `conda create -n graphragexpr python=3.12`。**勿用 3.14** | `python --version` 显示 3.12.x |
| A5 | 安装依赖 | 在环境内执行 `python -m pip install -r requirements.txt`（.venv 则用 `.venv\Scripts\python.exe -m pip ...`） | 无报错；`import flask, neo4j, openai` 成功 |
| A6 | **Docker Desktop**（跑 Neo4j） | 安装并启动 Docker Desktop，确认引擎 Running。**拉不到镜像的坑见下"常见坑"表** | `docker ps` 有输出 |
| A7 | 通读 4 份文档 | 必读（见下方"必读清单"），每人至少读到自己角色相关章节 | 组会能说出自己模块的输入/输出 |

**必读清单（仓库 `docs/` 目录）**
- `README.md` —— 项目全貌 + 协作约定（分支/提交/站会）
- `API_CONTRACT.md` —— 接口契约（D/E 精读，B/C 了解）
- `DATA_PLAN.md` —— 医药数据方案（B 精读，其余了解）
- `SCHEMA.md` —— Neo4j Schema（B/C 精读，其余了解）

---

## B. 按角色专项准备

### B · 数据 / 图谱构建
| # | 事项 | 说明 |
|---|---|---|
| B1 | 确定语料来源 | 按 DATA_PLAN §1，列出 20–40 篇医药文本候选（公开说明书/科普），发 A 审核 |
| B2 | 开始收集 | 存到 `data/raw/`（每篇一个 .txt）；会上报篇数与总字数 |
| B3 | 装 pandas | 清洗用：`python -m pip install pandas` |
| B4 | 准备本体类型表初稿 | 6 类本体 + 各自典型实体示例（各 3–5 个），组会讨论定稿 |
| B5 | 学会 Neo4j Browser 查数 | 会用 `MATCH (n) RETURN n LIMIT 25` 看数据；确认本机浏览器能开 `http://localhost:7474` |

### C · 检索 / 生成
| # | 事项 | 说明 |
|---|---|---|
| C1 | 拿到 DeepSeek API key | 与 A 确认使用团队 key（或自己注册），**先各测 1 次 chat 调用**确认可用 |
| C2 | 测 embedding | 确认 embedding 端点可用；不可用则确认走哈希降级（离线 demo 可用） |
| C3 | 通读检索代码 | `graphragexpr/extract/rag_graph.py`、`rag_vector.py`、`external_embedder.py`，弄清 4 种检索器差异 |
| C4 | 准备 10 个测试问题 | 单跳/多跳/跨实体各若干（医药主题），组会评审 |

### D · 后端 API
| # | 事项 | 说明 |
|---|---|---|
| D1 | 通读 backend/api.py | 弄清 7 个端点与 Cypher 逻辑 |
| D2 | 装接口测试工具 | Postman 或 curl；会用 GET/POST 调 JSON 接口 |
| D3 | 跑通骨架 | 环境就绪后执行 `./start_backend.ps1`，`GET /api/health` 有响应（Neo4j 起来后） |
| D4 | 精读 API_CONTRACT | 逐条核对请求/响应字段 |

### E · 前端可视化
| # | 事项 | 说明 |
|---|---|---|
| E1 | 通读 frontend/index.html | 弄清 D3 力导向图、问答面板、搜索三个模块 |
| E2 | 浏览器调试 | 会用 Chrome DevTools（Network / Console）；确认本机能访问 d3js CDN |
| E3 | D3.js 基础 | 复习力导向图（forceSimulation / forceLink / forceManyBody）API |
| E4 | 本地库确认 | 确认 `lib/` 下 vis-network 等资源存在（已复制） |

---

## 验收

- [ ] 全员 clone 到本地（A 确认仓库可访问）
- [ ] 每人 `setup.ps1` 跑一遍，**4 项检查全绿**（或明确记录哪一项由 A 统一解决）
- [ ] Neo4j 已启动，`python scripts/init_schema.py` 执行成功（A 或 B 操作）
- [ ] `.env` 已配置（A 统一填写，或各自 copy 后填）
