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
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from graphragexpr.custom_embedder import CustomEmbedder

app = Flask(__name__)
CORS(app)

# Neo4j 连接配置
URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "12345678"
driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

# 初始化 Embedder 和 LLM
embedder = CustomEmbedder(
    external=OpenAIEmbeddings(
        model="text-embedding-3-small",
        base_url=os.getenv("LLM_ENDPOINT"),
        api_key=os.getenv("LLM_TOKEN")
    )
)

llm = OpenAILLM(
    model_name=os.getenv("LLM_MODEL", "deepseek-chat"),
    base_url=os.getenv("LLM_ENDPOINT"),
    api_key=os.getenv("LLM_TOKEN"),
    model_params={"temperature": 0}
)

# 图遍历查询（1~2跳）
retrieval_query = """
MATCH (node) WHERE id(node) = $id
OPTIONAL MATCH (node)-[r1]-(neighbor1)
OPTIONAL MATCH (neighbor1)-[r2]-(neighbor2) WHERE neighbor2 <> node
RETURN node, r1, neighbor1, r2, neighbor2
LIMIT 20
"""

prompt_template = """
你是一个医药知识助手。请根据以下提供的上下文（文本片段 + 知识图谱三元组）回答问题。
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
            embedder=embedder
        )
    elif method == "vector_cypher":
        return VectorCypherRetriever(
            driver=driver,
            index_name="text_embeddings",
            embedder=embedder,
            retrieval_query=retrieval_query
        )
    elif method == "hybrid":
        return HybridRetriever(
            driver=driver,
            vector_index_name="text_embeddings",
            fulltext_index_name="text_fulltext",
            embedder=embedder
        )
    elif method == "hybrid_cypher":
        return HybridCypherRetriever(
            driver=driver,
            vector_index_name="text_embeddings",
            fulltext_index_name="text_fulltext",
            embedder=embedder,
            retrieval_query=retrieval_query
        )
    else:
        return None


@app.route('/api/graphrag', methods=['POST'])
def graphrag_query():
    """执行 GraphRAG 查询，返回答案和子图"""
    data = request.get_json()
    question = data.get('question', "")
    method = data.get('method', 'vector_cypher')

    if not question:
        return jsonify({"error": "Question is required"}), 400

    try:
        retriever = get_retriever(method)
        if retriever is None:
            return jsonify({"error": f"Unknown method: {method}"}), 400

        result = retriever.search(question, top_k=5)

        context_parts = []
        for item in result.items:
            context_parts.append(item.content)
            if hasattr(item, 'metadata') and item.metadata:
                context_parts.append(str(item.metadata))
        context = "\n".join(context_parts)

        answer = llm.invoke(
            prompt_template.format(context=context, query=question)
        )

        return jsonify({
            "answer": answer,
            "method": method,
            "context": context_parts[:5]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)