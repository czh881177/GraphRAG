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
from external_embedder import ExternalEmbedder
from sample_data_dyn import TEXT, CHUNKNUM

load_dotenv()

# Sample text data

def extract_entities_and_relations(text, client):
    """Use LLM to extract entities and relationships"""
    prompt = f"""请从以下文本中提取实体和关系。

文本：
{text}

你需要自行决定本体类型和关系类型，尽可能地提取更多的实体和关系，不要局限于明显的部分，也需要推断语义潜在的实体和关系。

请以JSON格式返回，格式如下：
{{
  "entities": [
    {{"name": "实体名称", "type": "实体类型"}}
  ],
  "relationships": [
    {{"source": "源实体", "target": "目标实体", "type": "关系类型"}}
  ]
}}

只返回JSON，不要其他说明文字。"""

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    result_text = response.choices[0].message.content.strip()

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0].strip()
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(result_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Response: {result_text}")
        return {"entities": [], "relationships": []}

def build_knowledge_graph():
    """Build knowledge graph manually"""
    print("正在连接到 Neo4j 数据库...")

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URL"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )

    try:
        driver.verify_connectivity()
        print("✓ Neo4j 数据库连接成功")
    except Exception as e:
        print(f"✗ 无法连接到 Neo4j: {e}")
        return

    print("正在初始化 LLM...")
    client = OpenAI(
        api_key=os.getenv("LLM_TOKEN"),
        base_url=os.getenv("LLM_ENDPOINT", "https://api.deepseek.com")
    )

    print("正在使用 LLM 提取实体和关系...")
    data = extract_entities_and_relations(TEXT, client)

    print(f"✓ 提取到 {len(data['entities'])} 个实体和 {len(data['relationships'])} 个关系")

    # Create embedder
    embedder = ExternalEmbedder(dimension=1536)
    text_embedding = embedder.embed_query(TEXT)

    print("正在将数据写入 Neo4j...")

    with driver.session() as session:
        # Create Document and Chunk nodes
        session.run("""
            CREATE (d:Document {id: 'docCHUNKNUM', text: $text})
            CREATE (c:Chunk {id: 'chunkCHUNKNUM', text: $text, embedding: $embedding})
            CREATE (c)-[:PART_OF]->(d)
        """.replace("CHUNKNUM", str(CHUNKNUM)), text=TEXT, embedding=text_embedding)

        # Create entity nodes
        entity_map = {}
        for entity in data['entities']:
            name = entity['name']
            entity_type = entity['type']

            result = session.run(f"""
                MERGE (e:`{entity_type}` {{name: $name}})
                RETURN elementId(e) AS id
            """, name=name)

            entity_map[name] = result.single()['id']

        # Link entities to chunk
        for entity_name in entity_map.keys():
            session.run("""
                MATCH (e) WHERE elementId(e) = $entity_id
                MATCH (c:Chunk {id: 'chunkCHUNKNUM'})
                MERGE (e)-[:FROM_CHUNK]->(c)
            """.replace("CHUNKNUM", str(CHUNKNUM)), entity_id=entity_map[entity_name])

        # Create relationships
        for rel in data['relationships']:
            source = rel['source']
            target = rel['target']
            rel_type = rel['type']

            if source in entity_map and target in entity_map:
                session.run(f"""
                    MATCH (s) WHERE elementId(s) = $source_id
                    MATCH (t) WHERE elementId(t) = $target_id
                    MERGE (s)-[:`{rel_type}`]->(t)
                """, source_id=entity_map[source], target_id=entity_map[target])

    # Verify data
    print("\n正在验证数据...")
    with driver.session() as session:
        count_result = session.run("MATCH (n) RETURN count(n) as count")
        node_count = count_result.single()["count"]
        print(f"✓ 总节点数: {node_count}")

        rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        rel_count = rel_result.single()["count"]
        print(f"✓ 总关系数: {rel_count}")

    driver.close()
    print("\n✓ 知识图谱构建完成!")
    print("可以在 Neo4j Browser 中运行以下查询查看结果:")
    print("  MATCH (n) RETURN n LIMIT 100;")

if __name__ == "__main__":
    build_knowledge_graph()
