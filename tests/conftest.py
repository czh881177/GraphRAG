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
    """只清理测试自己新增的节点，绝不删除测试前已存在的真实图谱数据。

    原理：测试前记录所有节点 elementId 快照，测试后只 DETACH DELETE
    快照中不存在的节点（即本次测试新建的），真实知识图谱不受影响。
    """
    with neo4j_driver.session() as session:
        before = set(session.run("MATCH (n) RETURN elementId(n) AS id").value())
    yield
    with neo4j_driver.session() as session:
        after = set(session.run("MATCH (n) RETURN elementId(n) AS id").value())
        new_ids = after - before
        for nid in new_ids:
            session.run("MATCH (n) WHERE elementId(n) = $id DETACH DELETE n", id=nid)


@pytest.fixture(scope="session")
def sample_text():
    """Provide sample text for testing"""
    return """
阿司匹林是一种非甾体抗炎药，由拜耳公司于1897年首次合成。
它常用于治疗头痛、发烧和炎症，也被用于预防心血管疾病。
"""
