import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import HybridCypherRetriever
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from graphragexpr.custom_embedder import CustomEmbedder

load_dotenv()

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "12345678"
driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

embedder = CustomEmbedder(
    external=OpenAIEmbeddings(
        model="text-embedding-3-small",
        base_url=os.getenv("LLM_ENDPOINT"),
        api_key=os.getenv("LLM_TOKEN"),
        dimensions=1536
    )
)

llm = OpenAILLM(
    model_name=os.getenv("LLM_MODEL", "deepseek-chat"),
    base_url=os.getenv("LLM_ENDPOINT"),
    api_key=os.getenv("LLM_TOKEN"),
    model_params={"temperature": 0}
)

# 定义图遍历查询：从命中的节点出发，向外扩展1~2跳（纯Cypher，不用APOC）
retrieval_query = """
MATCH (node) WHERE id(node) = $id
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
    retrieval_query=retrieval_query,
)

prompt_template = """
你是一个医药知识助手。请根据以下提供的上下文（文本片段 + 知识图谱三元组）回答问题。
优先使用知识图谱中的关系信息，文本片段作为补充。

上下文：
{context}

问题：{query}
答案：
"""

def hybrid_cypher_search(query_text: str, top_k: int = 5):
    print(f"\n🔍 正在执行Hybrid+Cypher检索（向量+全文+图遍历）...")
    result = retriever.search(query_text, top_k=top_k)
    
    # 提取文本和三元组信息
    context_parts = []
    for item in result.items:
        context_parts.append(f"文本: {item.content}")
        if hasattr(item, 'metadata') and item.metadata:
            context_parts.append(f"关系: {item.metadata}")
    
    context = "\n".join(context_parts)
    response = llm.invoke(
        prompt_template.format(context=context, query=query_text)
    )
    print(f"\n✅ 答案：{response}")
    # 打印子图节点数（方便你向D板块同学联调）
    print(f"📊 子图节点数（粗略估算）：{len(result.items) * 2}")
    return response

if __name__ == "__main__":
    while True:
        q = input("\n请输入问题（输入exit退出）：")
        if q.lower() == "exit":
            break
        hybrid_cypher_search(q)