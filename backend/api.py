import sys
import os
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from neo4j import GraphDatabase

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import (
    VectorRetriever,
    VectorCypherRetriever,
    HybridRetriever,
    HybridCypherRetriever
)
from graphragexpr.extract.rag_common import build_embedder, build_context, make_retrieval_query, make_text_formatter

app = Flask(__name__)
CORS(app)

# Neo4j 连接配置（读 .env，兼容默认值）
URI = os.getenv("NEO4J_URL", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")
driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

# 初始化 Embedder 和 LLM（Embedder 按 EMBED_* 配置决定外部服务或哈希）
embedder = build_embedder()

llm = OpenAILLM(
    model_name=os.getenv("LLM_MODEL", "deepseek-chat"),
    base_url=os.getenv("LLM_ENDPOINT"),
    api_key=os.getenv("LLM_TOKEN"),
    model_params={"temperature": 0}
)

prompt_template = """
你是一个医药知识助手。请根据以下提供的上下文（文本片段 + 知识图谱三元组）回答问题。
优先使用知识图谱中的关系信息（如：实体[药物] 阿司匹林 -副作用-> 胃肠道出血），文本片段作为补充。
如果上下文中没有相关信息，请直接说"根据现有知识无法回答"，不要编造。

上下文：
{context}

问题：{query}
答案：
"""


def get_retriever(method):
    """根据 method 返回对应的检索器实例"""
    if method == "vector":
        return VectorRetriever(
            driver=driver,
            index_name="text_embeddings",
            embedder=embedder,
            result_formatter=make_text_formatter("node")
        )
    elif method == "vector_cypher":
        return VectorCypherRetriever(
            driver=driver,
            index_name="text_embeddings",
            embedder=embedder,
            retrieval_query=make_retrieval_query(),
            result_formatter=make_text_formatter("text")
        )
    elif method == "hybrid":
        return HybridRetriever(
            driver=driver,
            vector_index_name="text_embeddings",
            fulltext_index_name="text_fulltext",
            embedder=embedder,
            result_formatter=make_text_formatter("node")
        )
    elif method == "hybrid_cypher":
        return HybridCypherRetriever(
            driver=driver,
            vector_index_name="text_embeddings",
            fulltext_index_name="text_fulltext",
            embedder=embedder,
            retrieval_query=make_retrieval_query(),
            result_formatter=make_text_formatter("text")
        )
    else:
        return None


@app.route('/api/graphrag', methods=['POST'])
def graphrag_query():
    """执行 GraphRAG 查询，返回答案和上下文"""
    data = request.get_json() or {}
    question = data.get('question', "")
    method = data.get('method', 'hybrid_cypher')

    if not question:
        return jsonify({"error": "Question is required"}), 400

    try:
        retriever = get_retriever(method)
        if retriever is None:
            return jsonify({"error": f"Unknown method: {method}"}), 400

        result = retriever.search(query_text=question, top_k=8)
        context = build_context(result.items)

        answer = llm.invoke(
            prompt_template.format(context=context, query=question)
        )
        answer_text = getattr(answer, "content", str(answer))

        return jsonify({
            "answer": answer_text,
            "method": method,
            "context": context.split("\n")[:10]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查（验证 Neo4j 连通）"""
    try:
        driver.verify_connectivity()
        return jsonify({"status": "ok", "neo4j": True})
    except Exception:
        return jsonify({"status": "degraded", "neo4j": False}), 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
