import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import HybridRetriever
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from graphragexpr.custom_embedder import CustomEmbedder

load_dotenv()

# 1. 连接Neo4j
URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "12345678"
driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

# 2. 初始化Embedder（使用外部DeepSeek Embedding，降级到哈希）
embedder = CustomEmbedder(
    external=OpenAIEmbeddings(
        model="text-embedding-3-small",
        base_url=os.getenv("LLM_ENDPOINT"),
        api_key=os.getenv("LLM_TOKEN"),
        dimensions=1536
    )
)

# 3. 初始化LLM
llm = OpenAILLM(
    model_name=os.getenv("LLM_MODEL", "deepseek-chat"),
    base_url=os.getenv("LLM_ENDPOINT"),
    api_key=os.getenv("LLM_TOKEN"),
    model_params={"temperature": 0}
)

# 4. 创建HybridRetriever（使用向量索引+全文索引）
retriever = HybridRetriever(
    driver=driver,
    vector_index_name="text_embeddings",   # 向量索引
    fulltext_index_name="text_fulltext",   # 全文索引（已由init_schema创建）
    embedder=embedder,
)

# 5. 定义Prompt模板
prompt_template = """
你是一个医药知识助手。请仅根据以下提供的上下文（可能包含文本片段）回答问题。
如果上下文中没有相关信息，请直接说"根据现有知识无法回答"，不要编造。

上下文：
{context}

问题：{query}
答案：
"""

# 6. 检索+生成函数
def hybrid_search(query_text: str, top_k: int = 5):
    print(f"\n🔍 正在执行Hybrid检索（向量+全文）...")
    # 检索
    result = retriever.search(query_text, top_k=top_k)
    
    # 拼接上下文
    context = "\n".join([item.content for item in result.items])
    
    # 调用LLM
    response = llm.invoke(
        prompt_template.format(context=context, query=query_text)
    )
    print(f"\n✅ 答案：{response}")
    return response

if __name__ == "__main__":
    while True:
        q = input("\n请输入问题（输入exit退出）：")
        if q.lower() == "exit":
            break
        hybrid_search(q)