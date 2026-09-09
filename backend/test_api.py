"""
Automated tests for backend/api.py

Run:

    pytest backend/test_api.py -v

or:

    pytest -v
"""

import pytest

import backend.api as api


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def client():
    """
    Flask test client.

    Neo4j is not required for validation tests.
    """
    api.app.config["TESTING"] = True

    with api.app.test_client() as client:
        yield client


# ============================================================
# Basic API Tests
# ============================================================

def test_health_route_exists(client):
    """
    /api/health should exist.
    """

    response = client.get(
        "/api/health"
    )

    assert response.status_code in {
        200,
        500,
    }


def test_graph_route_exists(client):

    response = client.get(
        "/api/graph"
    )

    assert response.status_code in {
        200,
        500,
    }


def test_entities_route_exists(client):

    response = client.get(
        "/api/entities"
    )

    assert response.status_code in {
        200,
        500,
    }


def test_stats_route_exists(client):

    response = client.get(
        "/api/stats"
    )

    assert response.status_code in {
        200,
        500,
    }


# ============================================================
# Entity API Validation
# ============================================================

def test_entities_invalid_type(client):

    response = client.get(
        "/api/entities?type=INVALID_TYPE"
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "error" in data


def test_entities_valid_type(client):

    response = client.get(
        "/api/entities?type=药物"
    )

    assert response.status_code in {
        200,
        500,
    }


# ============================================================
# Search API Validation
# ============================================================

def test_search_without_query(client):

    response = client.get(
        "/api/search"
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "error" in data


def test_search_empty_query(client):

    response = client.get(
        "/api/search?q="
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "error" in data


def test_search_valid_query(client):

    response = client.get(
        "/api/search?q=阿司匹林"
    )

    assert response.status_code in {
        200,
        500,
    }


# ============================================================
# Entity Detail API
# ============================================================

def test_entity_not_found_format(client):

    response = client.get(
        "/api/entity/non-existent-id"
    )

    assert response.status_code in {
        404,
        500,
    }

    if response.status_code == 404:

        data = response.get_json()

        assert "error" in data


# ============================================================
# GraphRAG Validation
# ============================================================

def test_graphrag_empty_body(client):

    response = client.post(
        "/api/graphrag",
        json={},
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "error" in data


def test_graphrag_empty_question(client):

    response = client.post(
        "/api/graphrag",
        json={
            "question": "",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "error" in data


def test_graphrag_whitespace_question(client):

    response = client.post(
        "/api/graphrag",
        json={
            "question": "   ",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "error" in data


def test_graphrag_invalid_method(client):

    response = client.post(
        "/api/graphrag",
        json={
            "question": "阿司匹林有什么作用？",
            "method": "invalid_method",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "error" in data


@pytest.mark.parametrize(
    "method",
    [
        "vector",
        "vector_cypher",
        "hybrid",
        "hybrid_cypher",
    ],
)
def test_graphrag_supported_methods(client, method):

    response = client.post(
        "/api/graphrag",
        json={
            "question": "阿司匹林有什么作用？",
            "method": method,
        },
    )

    # If LLM_TOKEN is not configured, the endpoint
    # should return a controlled 500 rather than crash.
    assert response.status_code in {
        200,
        500,
    }

    data = response.get_json()

    assert isinstance(data, dict)


# ============================================================
# Response JSON Tests
# ============================================================

def test_search_response_is_json(client):

    response = client.get(
        "/api/search"
    )

    assert response.is_json


def test_graphrag_invalid_request_is_json(client):

    response = client.post(
        "/api/graphrag",
        json={
            "question": "",
        },
    )

    assert response.is_json

    data = response.get_json()

    assert isinstance(data, dict)
