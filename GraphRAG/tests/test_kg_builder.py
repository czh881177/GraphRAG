# tests/test_kg_builder.py
"""
Tests for knowledge graph builder
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import json

sys.path.insert(0, str(Path(__file__).parent.parent / "graphragexpr" / "extract"))


class TestKGBuilder:
    """Test suite for knowledge graph building"""

    @patch('build_kg_simple.OpenAI')
    def test_extract_entities_and_relations(self, mock_openai_class):
        """Test entity and relation extraction"""
        from build_kg_simple import extract_entities_and_relations

        # Mock OpenAI response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "entities": [
                {"name": "阿司匹林", "type": "药物"},
                {"name": "拜耳公司", "type": "公司"}
            ],
            "relationships": [
                {"source": "拜耳公司", "target": "阿司匹林", "type": "研发"}
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response

        text = "阿司匹林由拜耳公司研发"
        result = extract_entities_and_relations(text, mock_client)

        assert len(result["entities"]) == 2
        assert len(result["relationships"]) == 1
        assert result["entities"][0]["name"] == "阿司匹林"
        assert result["relationships"][0]["type"] == "研发"

    @patch('build_kg_simple.OpenAI')
    def test_extract_handles_markdown_json(self, mock_openai_class):
        """Test extraction handles JSON wrapped in markdown code blocks"""
        from build_kg_simple import extract_entities_and_relations

        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        # Response with markdown code block
        mock_response.choices[0].message.content = """```json
{
  "entities": [{"name": "test", "type": "药物"}],
  "relationships": []
}
```"""
        mock_client.chat.completions.create.return_value = mock_response

        result = extract_entities_and_relations("test", mock_client)

        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "test"

    def test_entity_creation(self, neo4j_driver, clean_database):
        """Test creating entities in Neo4j"""
        with neo4j_driver.session() as session:
            # Create entities like the builder does
            entities = [
                {"name": "阿司匹林", "type": "药物"},
                {"name": "拜耳公司", "type": "公司"}
            ]

            for entity in entities:
                session.run(f"""
                    MERGE (e:`{entity['type']}` {{name: $name}})
                """, name=entity['name'])

            # Verify they were created
            result = session.run("MATCH (n) RETURN count(n) as count")
            assert result.single()["count"] == 2

    def test_relationship_creation(self, neo4j_driver, clean_database):
        """Test creating relationships between entities"""
        with neo4j_driver.session() as session:
            # Create entities
            session.run("""
                CREATE (a:药物 {name: '阿司匹林'})
                CREATE (b:公司 {name: '拜耳公司'})
            """)

            # Get their IDs
            result = session.run("""
                MATCH (a:药物 {name: '阿司匹林'})
                RETURN elementId(a) as id
            """)
            drug_id = result.single()["id"]

            result = session.run("""
                MATCH (b:公司 {name: '拜耳公司'})
                RETURN elementId(b) as id
            """)
            company_id = result.single()["id"]

            # Create relationship
            session.run("""
                MATCH (s) WHERE elementId(s) = $source_id
                MATCH (t) WHERE elementId(t) = $target_id
                MERGE (s)-[:研发]->(t)
            """, source_id=company_id, target_id=drug_id)

            # Verify relationship
            result = session.run("""
                MATCH (c:公司)-[r:研发]->(d:药物)
                RETURN type(r) as rel_type
            """)
            assert result.single()["rel_type"] == "研发"
