import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import HybridCypherRetriever
from custom_embedder import build_embedder

load_dotenv()

def hybrid_cypher_search():
    print("正在连接到 Neo4j 数据库...")
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URL", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "12345678"))
    )
    try:
        driver.verify_connectivity()
        print("✅ Neo4j 数据库连接成功")
    except Exception as e:
        print(f"❌ Neo4j 连接失败: {e}")
        return

    print("正在初始化 Hybrid+Cypher 检索器（Hybrid + 图展开）...")
    embedder = build_embedder()

    try:
        test_vec = embedder.embed_query("测试")
        print(f"✅ Embedding 测试成功，向量维度: {len(test_vec)}")
    except Exception as e:
        print(f"❌ Embedding 测试失败: {e}")
        return

    # 无参数版本，直接使用 node 变量
    retrieval_query = """
    MATCH (node)
    OPTIONAL MATCH (node)-[r1]-(neighbor1)
    OPTIONAL MATCH (neighbor1)-[r2]-(neighbor2) WHERE neighbor2 <> node
    RETURN node, r1, neighbor1, r2, neighbor2
    LIMIT 20
    """

    retriever = HybridCypherRetriever(
        driver=driver,
        vector_index_name="text_embeddings",
        fulltext_index_name="text_fulltext",
        embedder=embedder,
        retrieval_query=retrieval_query
    )

    llm = OpenAILLM(
        model_name=os.getenv("LLM_MODEL", "deepseek-chat"),
        base_url=os.getenv("LLM_ENDPOINT"),
        api_key=os.getenv("LLM_TOKEN"),
        model_params={"temperature": 0}
    )

    prompt_template = """
你是一个医药知识助手。请根据以下提供的上下文（文本片段 + 知识图谱三元组）回答问题。
优先使用知识图谱中的关系信息，文本片段作为补充。

上下文：
{context}

问题：{query}
答案：
"""

    while True:
        query = input("\n请输入问题（输入 exit 退出）：")
        if query.lower() == "exit":
            break
        if not query.strip():
            print("⚠️ 输入不能为空，请重新输入")
            continue

        print(f"\n🔍 正在执行 Hybrid+Cypher 检索（向量+全文+图遍历）...")
        try:
            result = retriever.search(query_text=query, top_k=5)

            context_parts = []
            for item in result.items:
                context_parts.append(item.content)
                if hasattr(item, 'metadata') and item.metadata:
                    context_parts.append(str(item.metadata))
            context = "\n".join(context_parts)

            response = llm.invoke(
                prompt_template.format(context=context, query=query)
            )
            print(f"\n✅ 答案：{response}")
        except Exception as e:
            print(f"❌ 检索失败: {e}")

if __name__ == "__main__":
    hybrid_cypher_search()