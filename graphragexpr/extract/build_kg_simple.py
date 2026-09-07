# build_kg_simple.py
"""
Simplified knowledge graph builder that works with DeepSeek API
Manually extracts entities and relationships without using SimpleKGPipeline
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI
import json
from custom_embedder import CustomEmbedder
from neo4j_graphrag.embeddings import OpenAIEmbeddings

# 加载环境变量
load_dotenv()

# 使用内置示例文本（如果有 sample_data 则优先使用）
try:
    from sample_data import TEXT
    print("✅ 使用 sample_data.TEXT")
except ImportError:
    print("⚠️ 使用内置示例文本")
    TEXT = """
阿司匹林是一种非甾体抗炎药，通过抑制环氧合酶（COX）发挥解热镇痛作用。
布洛芬也是一种非甾体抗炎药，同样通过抑制COX发挥作用。
拜耳公司研发了阿司匹林，而布洛芬最初由Boots公司研发。
"""


def extract_entities_and_relations(text, client):
    """Use LLM to extract entities and relationships"""
    prompt = f"""
请从以下文本中提取医药相关的实体和关系。

文本：
{text}

请以JSON格式输出，格式如下：
{{
    "entities": [
        {{"name": "实体名", "type": "实体类型"}}
    ],
    "relationships": [
        {{"source": "源实体名", "target": "目标实体名", "type": "关系类型"}}
    ]
}}

只输出JSON，不要有其他内容。
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        result_text = response.choices[0].message.content.strip()
        print(f"📝 LLM 原始响应: {result_text[:200]}...")

        # 处理 markdown 代码块
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        data = json.loads(result_text)
        print(f"🔍 解析到 {len(data.get('entities', []))} 个实体，{len(data.get('relationships', []))} 个关系")
        return data
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        print(f"原始响应: {result_text}")
        return {"entities": [], "relationships": []}
    except Exception as e:
        print(f"❌ LLM 调用失败: {e}")
        return {"entities": [], "relationships": []}


def build_knowledge_graph():
    """Build knowledge graph manually"""
    print("=" * 50)
    print("🔄 开始构建知识图谱...")
    print("=" * 50)

    # 连接 Neo4j
    neo4j_url = os.getenv("NEO4J_URL", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "12345678")

    print(f"📌 连接到 Neo4j: {neo4j_url}")

    driver = GraphDatabase.driver(
        neo4j_url,
        auth=(neo4j_user, neo4j_password)
    )

    try:
        driver.verify_connectivity()
        print("✅ Neo4j 连接成功")
    except Exception as e:
        print(f"❌ Neo4j 连接失败: {e}")
        return

    # 初始化 LLM
    print("📌 初始化 LLM...")
    client = OpenAI(
        api_key=os.getenv("LLM_TOKEN"),
        base_url=os.getenv("LLM_ENDPOINT", "https://api.deepseek.com/v1")
    )

    # 用 LLM 抽取实体关系
    print("📌 正在用 LLM 抽取实体和关系...")
    data = extract_entities_and_relations(TEXT, client)

    entities = data.get("entities", [])
    relationships = data.get("relationships", [])

    print(f"✅ 抽取完成: {len(entities)} 个实体, {len(relationships)} 个关系")

    if len(entities) == 0:
        print("⚠️ 没有抽取到任何实体，请检查 LLM 响应")
        driver.close()
        return

    # 生成文本向量
    print("📌 生成文本向量...")
    embedder = CustomEmbedder(
        external=OpenAIEmbeddings(
            model="text-embedding-3-small",
            base_url=os.getenv("LLM_ENDPOINT"),
            api_key=os.getenv("LLM_TOKEN")
        )
    )
    text_embedding = embedder.embed_query(TEXT)

    # 写入 Neo4j
    print("📌 正在写入 Neo4j...")
    with driver.session() as session:
        # 清空现有数据
        session.run("MATCH (n) DETACH DELETE n")
        print("   ✅ 已清空现有数据")

        # 创建 Document 和 Chunk
        result = session.run(
            """
            CREATE (d:Document {id: 'doc2', text: $text})
            CREATE (c:Chunk {id: 'chunk2', text: $text, embedding: $embedding})
            CREATE (c)-[:PART_OF]->(d)
            RETURN elementId(c) AS chunk_id
            """,
            text=TEXT,
            embedding=text_embedding
        )
        chunk_id = result.single()["chunk_id"]
        print(f"   ✅ 创建了 Document 和 Chunk (ID: {chunk_id})")

        # 创建实体节点
        entity_map = {}
        for entity in entities:
            name = entity["name"]
            entity_type = entity["type"]
            try:
                result = session.run(
                    f"""
                    MERGE (e:{entity_type} {{name: $name}})
                    RETURN elementId(e) AS id
                    """,
                    name=name
                )
                entity_map[name] = result.single()["id"]
            except Exception as e:
                print(f"   ⚠️ 创建实体 {name} 失败: {e}")
        print(f"   ✅ 创建了 {len(entity_map)} 个实体节点")

        # 链接实体到 Chunk
        for entity_name, entity_id in entity_map.items():
            session.run(
                """
                MATCH (e) WHERE elementId(e) = $entity_id
                MATCH (c:Chunk) WHERE elementId(c) = $chunk_id
                MERGE (e)-[:FROM_CHUNK]->(c)
                """,
                entity_id=entity_id,
                chunk_id=chunk_id
            )
        print("   ✅ 实体链接到 Chunk 完成")

        # 创建关系
        rel_count = 0
        for rel in relationships:
            source = rel["source"]
            target = rel["target"]
            rel_type = rel["type"]
            if source in entity_map and target in entity_map:
                try:
                    session.run(
                        f"""
                        MATCH (s) WHERE elementId(s) = $source_id
                        MATCH (t) WHERE elementId(t) = $target_id
                        MERGE (s)-[:{rel_type}]->(t)
                        """,
                        source_id=entity_map[source],
                        target_id=entity_map[target]
                    )
                    rel_count += 1
                except Exception as e:
                    print(f"   ⚠️ 创建关系 {source}-{rel_type}-{target} 失败: {e}")
        print(f"   ✅ 创建了 {rel_count} 个关系")

        # 验证数据
        print("📌 验证数据...")
        count_result = session.run("MATCH (n) RETURN count(n) AS count")
        node_count = count_result.single()["count"]
        print(f"   ✅ 节点总数: {node_count}")

        rel_result = session.run("MATCH ()-[r]->() RETURN count(r) AS count")
        rel_count_total = rel_result.single()["count"]
        print(f"   ✅ 关系总数: {rel_count_total}")

    driver.close()
    print("=" * 50)
    print("🎉 知识图谱构建完成！")
    print("📌 可在 Neo4j Browser 中查看: MATCH (n) RETURN n LIMIT 100;")
    print("=" * 50)


if __name__ == "__main__":
    build_knowledge_graph()
