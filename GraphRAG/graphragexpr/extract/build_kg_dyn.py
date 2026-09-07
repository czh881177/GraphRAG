"""
Build knowledge graph dynamically from source text (医药 GraphRAG).

⚠ TODO（B 数据/图谱 负责，9/13 红线前完成）：
本文件为基线占位，仍沿用《红楼梦》抽取逻辑，需按 docs/DATA_PLAN.md 与 docs/SCHEMA.md 改造：
  1. 数据源：改读 data/processed/chunks.json（原 sample_data_dyn.get_chunks 仅为占位）
  2. 本体：实体类型收敛为 6 类（药物/疾病/症状/公司/作用机制/副作用），
     允许 + 必要时“概念”；删除人物/地点/物品等红楼梦类型
  3. 关系：使用 DATA_PLAN §5 建议关系（研发/作用于/治疗/缓解/副作用/属于）
  4. Document：name/id 改为医药文档（如 “aspirin.txt” / 文档文件名），勿用 ‘hongloumeng’
  5. Chunk.index 保证全局唯一（满足约束 chunk_index），写入时必须带 1536 维 embedding
  6. 实体↔Chunk 关联建议改用抽取结果定位（当前按 name in chunk_text 匹配，误匹配率高）
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import external_embedder
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI
import json
from extract.sample_data_dyn import get_chunks
from external_embedder import ExternalEmbedder

load_dotenv()


def build_knowledge_graph():
    """Build knowledge graph from 红楼梦 text"""
    print("正在连接到 Neo4j 数据库...")

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URL"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )

    try:
        driver.verify_connectivity()
        print("✓ Neo4j 数据库连接成功")
    except Exception as e:
        print(f"✗ Neo4j 连接失败: {e}")
        return

    # Clear existing data
    print("正在清理现有数据...")
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("✓ 数据库已清空")

    # Get chunks from 红楼梦
    print("正在从《红楼梦》提取文本分块...")
    try:
        chunks = get_chunks()
        print(f"✓ 提取到 {len(chunks)} 个文本块")
    except Exception as e:
        print(f"✗ 文本提取失败: {e}")
        driver.close()
        return

    # Initialize LLM
    print("正在初始化 LLM...")
    client = OpenAI(
        api_key=os.getenv("LLM_TOKEN"),
        base_url=os.getenv("LLM_ENDPOINT", "https://api.deepseek.com")
    )

    # Process chunks and extract entities/relationships
    print("正在使用 LLM 提取实体和关系...")

    all_entities = []
    all_relationships = []

    for i, chunk_text in enumerate(chunks):
        print(f"  处理第 {i+1}/{len(chunks)} 个文本块...")

        prompt = f"""你是一个知识图谱抽取专家。请从以下《红楼梦》文本中提取实体和关系。

文本：
{chunk_text}

请提取：
1. 人物（姓名、称呼）
2. 地点（建筑、房间、地名）
3. 物品（重要物件）
4. 概念（情感、事件主题）

以及它们之间的关系。

请以JSON格式返回，格式如下：
{{
  "entities": [
    {{"name": "实体名", "type": "人物|地点|物品|概念"}},
    ...
  ],
  "relationships": [
    {{"source": "实体1", "target": "实体2", "type": "关系类型"}},
    ...
  ]
}}

只返回JSON，不要其他内容。"""

        try:
            response = client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            data = json.loads(result_text)

            # Collect entities and relationships
            all_entities.extend(data.get('entities', []))
            all_relationships.extend(data.get('relationships', []))

        except Exception as e:
            print(f"    ⚠ 处理失败: {e}")
            continue

    print(f"✓ 提取到 {len(all_entities)} 个实体和 {len(all_relationships)} 个关系")

    # Create embedder
    embedder = ExternalEmbedder(dimension=1536)

    print("正在将数据写入 Neo4j...")

    with driver.session() as session:
        # Create document node
        session.run("""
            CREATE (d:Document {
                name: '红楼梦',
                id: 'hongloumeng'
            })
        """)

        # Create chunk nodes with embeddings
        for i, chunk_text in enumerate(chunks):
            embedding = embedder.embed_query(chunk_text)

            session.run("""
                MATCH (d:Document {id: 'hongloumeng'})
                CREATE (c:Chunk {
                    text: $text,
                    embedding: $embedding,
                    index: $index
                })
                CREATE (c)-[:PART_OF]->(d)
            """, text=chunk_text, embedding=embedding, index=i)

        # Create entity nodes
        entity_map = {}
        for entity in all_entities:
            name = entity.get('name', '').strip()
            entity_type = entity.get('type', '概念')

            if not name or name in entity_map:
                continue

            entity_map[name] = entity_type

            session.run(f"""
                MERGE (e:`{entity_type}` {{name: $name}})
            """, name=name)

        # Create relationships between entities
        for rel in all_relationships:
            source = rel.get('source', '').strip()
            target = rel.get('target', '').strip()
            rel_type = rel.get('type', 'RELATED_TO').strip().replace(' ', '_')

            if not source or not target or source not in entity_map or target not in entity_map:
                continue

            try:
                session.run(f"""
                    MATCH (a {{name: $source}})
                    MATCH (b {{name: $target}})
                    MERGE (a)-[r:`{rel_type}`]->(b)
                """, source=source, target=target)
            except:
                pass

        # Link entities to chunks
        for entity in all_entities:
            name = entity.get('name', '').strip()
            if not name:
                continue

            # Find chunks that mention this entity
            for i, chunk_text in enumerate(chunks):
                if name in chunk_text:
                    try:
                        session.run("""
                            MATCH (e {name: $name})
                            MATCH (c:Chunk {index: $index})
                            MERGE (e)-[:FROM_CHUNK]->(c)
                        """, name=name, index=i)
                    except:
                        pass

    print("\n正在验证数据...")
    with driver.session() as session:
        node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
        rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]

        print(f"✓ 总节点数: {node_count}")
        print(f"✓ 总关系数: {rel_count}")

    print("\n✓ 知识图谱构建完成!")
    print("可以在 Neo4j Browser 中运行以下查询查看结果:")
    print("  MATCH (n) RETURN n LIMIT 100;")

    driver.close()


if __name__ == "__main__":
    build_knowledge_graph()
