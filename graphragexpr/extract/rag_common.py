# graphragexpr/extract/rag_common.py
"""
检索器公共工具（A 统一修复版）
- build_embedder: 按 .env 的 EMBED_* 决定外部服务或纯哈希（无 404 噪音）
- build_context: 上下文构建 + 截断（防止 token 爆炸）
- make_retrieval_query: 标准图展开查询（Chunk -> 实体 -> 1 跳）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_embedder import CustomEmbedder


def build_embedder():
    """按 .env 配置构建 embedder：
    - EMBED_ENDPOINT/EMBED_MODEL/EMBED_TOKEN 三项齐全 -> 使用外部 embedding 服务
    - 否则 -> 纯哈希（CustomEmbedder(external=None)，不打印任何报错噪音）
    注意：DeepSeek 官方不提供 embedding API，请勿把 EMBED_* 指向 api.deepseek.com
    """
    endpoint = os.getenv("EMBED_ENDPOINT", "").strip()
    model = os.getenv("EMBED_MODEL", "").strip()
    token = os.getenv("EMBED_TOKEN", "").strip()

    if endpoint and model and token:
        try:
            from neo4j_graphrag.embeddings import OpenAIEmbeddings
            external = OpenAIEmbeddings(model=model, base_url=endpoint, api_key=token)
            print(f"✅ 使用外部 Embedding 服务: {endpoint} / {model}")
            return CustomEmbedder(external=external)
        except Exception as e:
            print(f"⚠️ 外部 Embedding 初始化失败，降级为哈希: {e}")
            return CustomEmbedder(external=None)

    print("ℹ️ 未配置 EMBED_*，使用哈希 Embedder（离线演示模式）")
    return CustomEmbedder(external=None)


def build_context(result_items, max_chars=9000, per_item=1200):
    """将检索结果拼成上下文，控制总长度避免 token 爆炸"""
    parts = []
    total = 0
    for item in result_items:
        content = (item.content or "").strip()
        if not content:
            continue
        if len(content) > per_item:
            content = content[:per_item] + "…"
        if total + len(content) > max_chars:
            parts.append("…（上下文过长，已截断）")
            break
        parts.append(content)
        total += len(content)
    return "\n".join(parts)


def make_retrieval_query():
    """标准图展开查询（基于 neo4j_graphrag 1.19 模板语义）：
    向量检索的命中节点在 retrieval_query 中可直接用 node 变量引用（无需 $id）。
    流程：命中 Chunk 节点 -> 沿 FROM_CHUNK 找到实体 -> 实体 1 跳展开业务关系
    只保留业务关系（过滤 FROM_CHUNK 噪音行），返回紧凑三元组文本。
    """
    return """
    MATCH (node)-[:FROM_CHUNK]-(e)
    WITH collect(DISTINCT e) AS entities
    UNWIND entities AS e
    OPTIONAL MATCH (e)-[r]-(n)
    WHERE n IS NOT NULL AND n <> e AND type(r) <> 'FROM_CHUNK'
    WITH e, r, n
    LIMIT 50
    RETURN '实体[' + coalesce(labels(e)[0], '') + '] ' + coalesce(e.name, '') +
           ' -' + type(r) + '-> ' + coalesce(n.name, '') AS text
    """


def make_text_formatter(mode="text"):
    """自定义 result_formatter，避免默认 formatter 输出 <Record ...> 包装
    - mode="text": 提取检索 RETURN 的 text 字段（VectorCypher / HybridCypher）
    - mode="node": 提取向量命中节点 node.text（Vector / Hybrid）
    """
    from neo4j_graphrag.types import RetrieverResultItem

    if mode == "node":
        def f(record):
            node = record.get("node")
            if isinstance(node, dict):
                content = node.get("text", "")
            elif node is not None:
                content = str(node)
            else:
                content = record.get("text") or ""
            return RetrieverResultItem(
                content=content,
                metadata={"score": record.get("score")},
            )
        return f

    def f(record):
        return RetrieverResultItem(content=record.get("text") or "", metadata=None)

    return f
