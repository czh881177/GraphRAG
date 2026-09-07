# tests/test_neo4j_integration.py
"""
Tests for Neo4j integration
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "graphragexpr"))

from custom_embedder import SimpleHashEmbedder


class TestNeo4jIntegration:
    """Test suite for Neo4j database operations"""

    def test_neo4j_connection(self, neo4j_driver, neo4j_connection_test):
        """Test that we can connect to Neo4j"""
        driver = neo4j_driver
        driver.verify_connectivity()

    def test_create_and_query_node(self, neo4j_driver, clean_database):
        """Test creating and querying a node"""
        with neo4j_driver.session() as session:
            # Create a node
            session.run(
                "CREATE (n:TestNode {name: $name, value: $value})",
                name="test", value=42
            )

            # Query it back
            result = session.run(
                "MATCH (n:TestNode {name: $name}) RETURN n.value as value",
                name="test"
            )
            record = result.single()
            assert record["value"] == 42

    def test_create_relationship(self, neo4j_driver, clean_database):
        """Test creating relationships between nodes"""
        with neo4j_driver.session() as session:
            # Create two nodes with a relationship
            session.run("""
                CREATE (a:Drug {name: '阿司匹林'})
                CREATE (b:Company {name: '拜耳公司'})
                CREATE (a)-[:研发]->(b)
            """)

            # Query the relationship
            result = session.run("""
                MATCH (a:Drug)-[r:研发]->(b:Company)
                RETURN a.name as drug, b.name as company
            """)
            record = result.single()
            assert record["drug"] == "阿司匹林"
            assert record["company"] == "拜耳公司"

    def test_vector_storage(self, neo4j_driver, clean_database):
        """Test storing and retrieving vector embeddings"""
        embedder = SimpleHashEmbedder(dimension=1536)
        embedding = embedder.embed_query("test text")

        with neo4j_driver.session() as session:
            # Store embedding
            session.run(
                "CREATE (c:Chunk {text: $text, embedding: $embedding})",
                text="test text", embedding=embedding
            )

            # Retrieve it
            result = session.run(
                "MATCH (c:Chunk {text: $text}) RETURN c.embedding as embedding",
                text="test text"
            )
            record = result.single()
            retrieved_embedding = record["embedding"]

            assert len(retrieved_embedding) == 1536
            assert retrieved_embedding == embedding

    def test_graph_traversal(self, neo4j_driver, clean_database):
        """Test graph traversal queries"""
        with neo4j_driver.session() as session:
            # Create a small knowledge graph
            session.run("""
                CREATE (drug:药物 {name: '阿司匹林'})
                CREATE (mechanism:作用机制 {name: '环氧合酶'})
                CREATE (company:公司 {name: '拜耳公司'})
                CREATE (drug)-[:作用于]->(mechanism)
                CREATE (company)-[:研发]->(drug)
            """)

            # Test 2-hop traversal
            result = session.run("""
                MATCH (c:公司)-[*1..2]-(other)
                RETURN DISTINCT labels(other)[0] as label, other.name as name
            """)

            entities = {record["name"] for record in result}
            assert "阿司匹林" in entities
            assert "环氧合酶" in entities
