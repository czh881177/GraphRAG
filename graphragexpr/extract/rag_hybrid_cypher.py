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

    # 限流图展开：绑定召回 chunk → 实体 → 1 跳邻居（每实体≤12 邻居，每 chunk≤25 实体）
    retrieval_query = """
    WITH node
    MATCH (node)<-[:FROM_CHUNK]-(entity)
    OPTIONAL MATCH (entity)-[r]-(neighbor)
    WHERE NOT neighbor:Chunk AND NOT neighbor:Document AND neighbor <> entity
    WITH node, entity, neighbor, r
    WHERE r IS NOT NULL
    ORDER BY coalesce(entity.name, '')
    WITH node, entity, collect(DISTINCT {
        target: coalesce(neighbor.name, ''),
        rel: type(r)
    })[..12] AS neighbors
    RETURN
        node.text AS info,
        collect(DISTINCT {
            entity: coalesce(entity.name, ''),
            type: labels(entity)[0],
            neighbors: neighbors
        })[..25] AS graph_data
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
                # 辅助函数：利用 LLM 提取问题中的实体
            def extract_entities_with_llm(query):
                # 使用简单的提示词让 LLM 提取实体
                extraction_prompt = f"请从以下问题中提取所有医药实体（如药物名、疾病名），用逗号分隔，不要有多余的字符：{query}"
                try:
                    res = llm.invoke(extraction_prompt)
                    return [e.strip() for e in res.content.split(',') if e.strip()]
                except Exception:
                    return [query] # 提取失败则把整个问题当实体

            # 替换原有的 retriever.search 逻辑
            print(f"\n🔍 正在执行多实体图增强检索...")
            try:
                # 1. 提取实体
                entities = extract_entities_with_llm(query)
                print(f"检测到实体: {entities}")

                # 2. 针对每个实体，手动查询图谱（不再依赖向量检索）
                context_parts = []
                with driver.session() as session:
                    for entity in entities:
                        # 直接通过名称模糊匹配找到实体，并获取其邻居
                        cypher = """
                        MATCH (p) WHERE p.name CONTAINS $entity AND NOT p:Chunk AND NOT p:Document
                        OPTIONAL MATCH (p)-[r]-(neighbor)
                        WHERE NOT neighbor:Chunk AND NOT neighbor:Document
                        RETURN p.name AS entity, type(r) AS rel, neighbor.name AS target LIMIT 15
                        """
                        result = session.run(cypher, entity=entity)
                        records = [record for record in result]
                
                        if not records:
                            context_parts.append(f"实体: {entity} (未在图谱中找到)")
                        else:
                            # 转为自然语言
                            for record in records:
                                context_parts.append(f"{record['entity']} -[{record['rel']}]-> {record['target']}}")

                # 3. 如果没有图谱上下文，退回到原有的向量+全文检索
                if not context_parts:
                    result = retriever.search(query_text=query, top_k=5)
                    for item in result.items:
                        context_parts.append(item.content)

                context = "\n".join(context_parts)

                # 4. 发送给 LLM 获得最终答案
                response = llm.invoke(
                    prompt_template.format(context=context, query=query)
                )
                print(f"\n✅ 答案: {response}")
            except Exception as e:
                print(f"❌ 检索失败: {e}")

if __name__ == "__main__":
    hybrid_cypher_search()