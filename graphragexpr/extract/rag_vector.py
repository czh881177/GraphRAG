import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import VectorRetriever
from custom_embedder import build_embedder

load_dotenv()

def vector_rag_search():
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

    print("正在初始化向量检索器...")
    embedder = build_embedder()

    try:
        test_vec = embedder.embed_query("测试")
        print(f"✅ Embedding 测试成功，向量维度: {len(test_vec)}")
    except Exception as e:
        print(f"❌ Embedding 测试失败: {e}")
        return

    retriever = VectorRetriever(
        driver=driver,
        index_name="text_embeddings",
        embedder=embedder
    )

    llm = OpenAILLM(
        model_name=os.getenv("LLM_MODEL", "deepseek-chat"),
        base_url=os.getenv("LLM_ENDPOINT"),
        api_key=os.getenv("LLM_TOKEN"),
        model_params={"temperature": 0}
    )

    prompt_template = """
你是一个医药知识助手。请仅根据以下提供的上下文回答问题。
如果上下文中没有相关信息，请直接说"根据现有知识无法回答"，不要编造。

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

        print(f"\n🔍 正在检索：{query}")
        try:
            query_vector = embedder.embed_query(query)
            result = retriever.search(query_vector=query_vector, top_k=5)
            context = "\n".join([item.content for item in result.items])
            response = llm.invoke(
                prompt_template.format(context=context, query=query)
            )
            print(f"\n✅ 答案：{response}")
        except Exception as e:
            print(f"❌ 检索失败: {e}")

if __name__ == "__main__":
    vector_rag_search()