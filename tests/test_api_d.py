# tests/test_api_d.py
"""
Task D: Flask API endpoint tests.

The tests use fake Neo4j sessions so the API behavior can be verified
offline; real Neo4j/LLM integration is not required for these tests.
"""

import os
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
for entry in (ROOT / "backend", ROOT / "graphragexpr", ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

# api.py builds the driver at import time; a reachable-looking fake URI is enough.
os.environ.setdefault("NEO4J_URL", "bolt://127.0.0.1:1")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test-password")
os.environ.setdefault("LLM_TOKEN", "sk-test")

from api import app  # noqa: E402


class _Record(dict):
    """Minimal dict-like stand-in for a Neo4j Record."""


class _Result:
    def __init__(self, records=None):
        self.records = list(records or [])

    def single(self):
        return self.records[0] if self.records else None

    def __iter__(self):
        return iter(self.records)


class _Session:
    def __init__(self, handler, queries):
        self._handler = handler
        self.queries = queries

    def run(self, query, **params):
        self.queries.append((query, params))
        return self._handler(query, params)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeDriver:
    def __init__(self, handler=None):
        self.handler = handler or (lambda query, params: _Result())
        self.queries = []

    def session(self):
        return _Session(self.handler, self.queries)


class _OkHealthDriver:
    def verify_connectivity(self):
        return None


class _ErrorHealthDriver:
    def verify_connectivity(self):
        raise RuntimeError("Neo4j unreachable")


class _FakeEmbedder:
    def __init__(self, **kwargs):
        pass

    def embed_query(self, text):
        return [0.0] * 1536


class _RagResponse:
    def __init__(self, answer="测试答案"):
        self.answer = answer


class _FakeGraphRAG:
    def __init__(self, *args, **kwargs):
        pass

    def search(self, **kwargs):
        return _RagResponse()


def _patch_driver(monkeypatch, handler=None):
    driver = _FakeDriver(handler)
    monkeypatch.setattr(api_module, "driver", driver)
    return driver


# api is imported above as a module-level symbol only when the module is loaded;
# pytest imports this test module directly, so keep a stable reference here.
import api as api_module  # noqa: E402


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_health_ok(monkeypatch, client):
    monkeypatch.setattr(api_module, "driver", _OkHealthDriver())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_health_failure(monkeypatch, client):
    monkeypatch.setattr(api_module, "driver", _ErrorHealthDriver())
    response = client.get("/api/health")
    assert response.status_code == 500
    assert response.get_json()["status"] == "error"


def test_get_graph_builds_nodes_and_edges(monkeypatch, client):
    records = [
        _Record(
            source_id="4:d1", source_label="药物", source_name="阿司匹林",
            rel_type="作用于", target_id="4:m1", target_label="作用机制",
            target_name="环氧合酶",
        ),
        _Record(
            source_id="4:d2", source_label="药物", source_name="布洛芬",
            rel_type="作用于", target_id="4:m1", target_label="作用机制",
            target_name="环氧合酶",
        ),
    ]
    driver = _patch_driver(monkeypatch, lambda query, params: _Result(records))

    response = client.get("/api/graph")

    assert response.status_code == 200
    body = response.get_json()
    assert {node["id"] for node in body["nodes"]} == {"4:d1", "4:d2", "4:m1"}
    assert len(body["edges"]) == 2
    assert len(driver.queries) == 1


def test_get_graph_db_error_returns_500(monkeypatch, client):
    def fail(query, params):
        raise RuntimeError("connection failed")

    _patch_driver(monkeypatch, fail)
    response = client.get("/api/graph")
    assert response.status_code == 500
    assert "error" in response.get_json()


def test_get_entities_without_filter(monkeypatch, client):
    records = [
        _Record(id="4:d1", type="药物", name="阿司匹林"),
        _Record(id="4:d2", type="疾病", name="头痛"),
    ]
    _patch_driver(monkeypatch, lambda query, params: _Result(records))

    response = client.get("/api/entities")

    assert response.status_code == 200
    assert response.get_json()["entities"] == records


def test_get_entities_with_allowed_type(monkeypatch, client):
    records = [_Record(id="4:d1", type="药物", name="阿司匹林")]
    driver = _patch_driver(monkeypatch, lambda query, params: _Result(records))

    response = client.get("/api/entities?type=药物")

    assert response.status_code == 200
    assert response.get_json()["entities"] == records
    assert "MATCH (n:`药物`)" in driver.queries[0][0]


def test_get_entities_with_invalid_type_returns_400(client):
    response = client.get("/api/entities?type=无效类型")
    assert response.status_code == 400
    assert response.get_json()["error"].startswith("Invalid type:")


def test_get_entity_not_found_returns_404(monkeypatch, client):
    _patch_driver(monkeypatch, lambda query, params: _Result())
    response = client.get("/api/entity/4:missing")
    assert response.status_code == 404
    assert response.get_json()["error"] == "Entity not found"


def test_get_entity_details(monkeypatch, client):
    record = _Record(
        n={"name": "阿司匹林"},
        type="药物",
        connections=[{"node": "环氧合酶", "relationship": "作用于", "direction": "outgoing"}],
    )
    driver = _patch_driver(monkeypatch, lambda query, params: _Result([record]))

    response = client.get("/api/entity/4:aspirin")

    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == "4:aspirin"
    assert body["type"] == "药物"
    assert body["properties"]["name"] == "阿司匹林"
    assert len(body["connections"]) == 1
    assert "AND NOT n:Chunk AND NOT n:Document" in driver.queries[0][0]


def test_get_stats_counts_entity_graph_only(monkeypatch, client):
    def handler(query, params):
        if "labels(n)[0] as type, count(n) as count" in query:
            return _Result([_Record(type="药物", count=2), _Record(type="疾病", count=1)])
        if "type(r) as type, count(r) as count" in query:
            return _Result([_Record(type="作用于", count=1)])
        if "RETURN count(n) as count" in query:
            return _Result([_Record(count=3)])
        if "RETURN count(r) as count" in query:
            return _Result([_Record(count=1)])
        return _Result()

    driver = _patch_driver(monkeypatch, handler)
    response = client.get("/api/stats")

    assert response.status_code == 200
    body = response.get_json()
    assert body["total_nodes"] == 3
    assert body["total_relationships"] == 1
    assert body["nodes_by_type"] == {"药物": 2, "疾病": 1}
    assert body["relationships_by_type"] == {"作用于": 1}
    rel_queries = [query for query, _ in driver.queries if "count(r)" in query]
    assert rel_queries and all("NOT startNode(r):Chunk" in query for query in rel_queries)


def test_search_requires_query(client):
    assert client.get("/api/search").status_code == 400
    assert client.get("/api/search?q=%20").status_code == 400


def test_search_returns_results(monkeypatch, client):
    records = [_Record(id="4:d1", type="药物", name="阿司匹林")]
    driver = _patch_driver(monkeypatch, lambda query, params: _Result(records))

    response = client.get("/api/search?q=阿司匹林")

    assert response.status_code == 200
    assert response.get_json()["results"] == records
    assert driver.queries[0][1]["parameters"]["query"] == "阿司匹林"


def test_graphrag_rejects_invalid_json(client):
    response = client.post("/api/graphrag", data="not-json", content_type="application/json")
    assert response.status_code == 400
    assert "JSON object" in response.get_json()["error"]


def test_graphrag_requires_question(client):
    response = client.post("/api/graphrag", json={"question": "", "method": "vector"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Question is required"


def test_graphrag_rejects_unknown_method(client):
    response = client.post("/api/graphrag", json={"question": "测试问题", "method": "unknown"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Unknown method: unknown"


def test_graphrag_vector_returns_answer_without_subgraph(monkeypatch, client):
    driver = _patch_driver(monkeypatch, lambda query, params: _Result())

    with ExitStack() as stack:
        for target in (
            "neo4j_graphrag.llm.OpenAILLM",
            "neo4j_graphrag.retrievers.VectorRetriever",
            "neo4j_graphrag.retrievers.VectorCypherRetriever",
            "neo4j_graphrag.retrievers.HybridRetriever",
            "neo4j_graphrag.retrievers.HybridCypherRetriever",
            "neo4j_graphrag.generation.RagTemplate",
        ):
            stack.enter_context(patch(target, MagicMock()))
        stack.enter_context(patch("external_embedder.ExternalEmbedder", _FakeEmbedder))
        stack.enter_context(patch("neo4j_graphrag.generation.GraphRAG", _FakeGraphRAG))
        response = client.post("/api/graphrag", json={"question": "测试问题", "method": "vector"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["answer"] == "测试答案"
    assert body["method"] == "vector"
    assert body["subgraph"] == {"nodes": [], "edges": []}
    assert driver.queries == []


def test_graphrag_vector_cypher_returns_answer_and_subgraph(monkeypatch, client):
    def handler(query, params):
        if "queryNodes" in query:
            return _Result([_Record(chunk_id="4:c1")])
        if "UNWIND $chunk_ids" in query:
            return _Result([
                _Record(
                    source_id="4:d1", source_label="药物", source_name="阿司匹林",
                    target_id="4:m1", target_label="作用机制", target_name="环氧合酶",
                    rel_type="作用于",
                )
            ])
        return _Result()

    driver = _patch_driver(monkeypatch, handler)

    with ExitStack() as stack:
        for target in (
            "neo4j_graphrag.llm.OpenAILLM",
            "neo4j_graphrag.retrievers.VectorRetriever",
            "neo4j_graphrag.retrievers.VectorCypherRetriever",
            "neo4j_graphrag.retrievers.HybridRetriever",
            "neo4j_graphrag.retrievers.HybridCypherRetriever",
            "neo4j_graphrag.generation.RagTemplate",
        ):
            stack.enter_context(patch(target, MagicMock()))
        stack.enter_context(patch("external_embedder.ExternalEmbedder", _FakeEmbedder))
        stack.enter_context(patch("neo4j_graphrag.generation.GraphRAG", _FakeGraphRAG))
        response = client.post(
            "/api/graphrag",
            json={"question": "哪些药物通过抑制环氧合酶发挥作用？", "method": "vector_cypher"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["method"] == "vector_cypher"
    assert body["subgraph"]["nodes"] == [
        {"id": "4:d1", "label": "阿司匹林", "type": "药物"},
        {"id": "4:m1", "label": "环氧合酶", "type": "作用机制"},
    ]
    assert body["subgraph"]["edges"] == [{"source": "4:d1", "target": "4:m1", "type": "作用于"}]
    assert "UNWIND $chunk_ids" in driver.queries[1][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
