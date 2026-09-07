# scripts/init_schema.py
"""
初始化 Neo4j Schema 与索引（医药 GraphRAG）— 幂等，可重复执行
组长 A 制定，B/C/D 统一使用本脚本初始化数据库。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def run(session, cypher, desc):
    try:
        session.run(cypher)
        print(f"  ✓ {desc}")
    except Exception as e:
        print(f"  ✗ {desc}: {e}")


def init_schema():
    print("正在连接到 Neo4j 数据库...")
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URL"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )
    try:
        driver.verify_connectivity()
        print("✓ Neo4j 连接成功\n")
    except Exception as e:
        print(f"✗ 无法连接 Neo4j，请先启动数据库并配置 .env：{e}")
        return

    with driver.session() as session:
        print("—— 约束（Constraints）——")
        run(session,
            "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE",
            "Document.id 唯一")
        run(session,
            "CREATE CONSTRAINT chunk_index IF NOT EXISTS FOR (n:Chunk) REQUIRE n.index IS UNIQUE",
            "Chunk.index 唯一")

        print("\n—— 向量索引（Vector，1536 维 cosine）——")
        run(session, """
            CREATE VECTOR INDEX text_embeddings IF NOT EXISTS
            FOR (n:Chunk) ON (n.embedding)
            OPTIONS { indexConfig: {
              `vector.dimensions`: 1536,
              `vector.similarity_function`: 'cosine'
            }}
        """, "text_embeddings 向量索引")

        print("\n—— 全文索引（Fulltext）——")
        run(session, """
            CREATE FULLTEXT INDEX text_fulltext IF NOT EXISTS
            FOR (n:Chunk) ON EACH [n.text]
        """, "text_fulltext 全文索引")

        print("\n—— 实体 name 索引（加速 MERGE/检索）——")
        for label in ["药物", "疾病", "症状", "公司", "作用机制", "副作用"]:
            run(session,
                f"CREATE INDEX entity_{label} IF NOT EXISTS FOR (n:`{label}`) ON (n.name)",
                f"{label}.name 索引")

    driver.close()
    print("\n✓ Schema 初始化完成（幂等，可重复执行）")
    print("  验证：Neo4j Browser 执行  SHOW CONSTRAINTS; SHOW INDEXES;")


if __name__ == "__main__":
    init_schema()
