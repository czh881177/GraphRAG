# tests/conftest.py
"""
Pytest configuration and fixtures for GraphRAG tests
"""
import pytest
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


@pytest.fixture(scope="session")
def neo4j_driver():
    """Provide Neo4j driver for tests"""
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URL"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )
    yield driver
    driver.close()


@pytest.fixture(scope="session")
def neo4j_connection_test(neo4j_driver):
    """Verify Neo4j connection before running tests"""
    try:
        neo4j_driver.verify_connectivity()
        return True
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")


@pytest.fixture
def clean_database(neo4j_driver):
    """Clean database before each test"""
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield
    # Cleanup after test
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


@pytest.fixture(scope="session")
def sample_text():
    """Provide sample text for testing"""
    return """
阿司匹林是一种非甾体抗炎药，由拜耳公司于1897年首次合成。
它常用于治疗头痛、发烧和炎症，也被用于预防心血管疾病。
"""
