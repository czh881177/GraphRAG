"""
GraphRAG Flask Backend API

D 任务：
1. Neo4j health check
2. Knowledge graph visualization API
3. Entity APIs
4. Statistics API
5. Entity search API
6. GraphRAG API
7. GraphRAG subgraph extraction

运行：
    python -m backend.api

默认：
    http://localhost:5000
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from neo4j import GraphDatabase


# ============================================================
# 1. Environment / Application
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

app = Flask(__name__)
CORS(app)


# ============================================================
# 2. Configuration
# ============================================================

NEO4J_URL = os.getenv("NEO4J_URL")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

LLM_TOKEN = os.getenv("LLM_TOKEN")
LLM_ENDPOINT = os.getenv(
    "LLM_ENDPOINT",
    "https://api.deepseek.com"
)
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "deepseek-chat"
)

VECTOR_INDEX_NAME = os.getenv(
    "VECTOR_INDEX_NAME",
    "text_embeddings"
)

FULLTEXT_INDEX_NAME = os.getenv(
    "FULLTEXT_INDEX_NAME",
    "text_fulltext"
)

TOP_K = int(os.getenv("RAG_TOP_K", "3"))

ALLOWED_ENTITY_TYPES = {
    "药物",
    "疾病",
    "症状",
    "公司",
    "作用机制",
    "副作用",
    "概念",
}

ALLOWED_RAG_METHODS = {
    "vector",
    "vector_cypher",
    "hybrid",
    "hybrid_cypher",
}


# ============================================================
# 3. Neo4j Driver
# ============================================================

if not NEO4J_URL:
    print(
        "WARNING: NEO4J_URL is not configured. "
        "Set it in .env before starting the backend."
    )

driver = GraphDatabase.driver(
    NEO4J_URL or "bolt://localhost:7687",
    auth=(
        NEO4J_USER or "neo4j",
        NEO4J_PASSWORD or "",
    ),
)


# ============================================================
# 4. Helper Functions
# ============================================================

def error_response(message: str, status_code: int):
    """Return a consistent JSON error response."""
    if status_code >= 500:
        print("\n========== API ERROR ==========")
        print(message)
        traceback.print_exc()
        print("================================\n")

    return jsonify({"error": message}), status_code


def node_to_dict(node: Any) -> dict:
    """Convert Neo4j Node into JSON-compatible dict."""
    return {
        "id": node.element_id,
        "label": node.get("name", "unknown"),
        "type": (
            list(node.labels)[0]
            if node.labels
            else "unknown"
        ),
    }


def build_subgraph_from_chunks(
    chunk_ids: list[str],
) -> dict[str, list]:
    """
    Build a 1-2 hop entity subgraph around retrieved chunks.

    Use path + relationships(path) for variable-length paths.
    Chunk and Document nodes/relationships are excluded from the result.
    """

    if not chunk_ids:
        return {
            "nodes": [],
            "edges": [],
        }

    query = """
    UNWIND $chunk_ids AS chunk_id

    MATCH (chunk)
    WHERE elementId(chunk) = chunk_id

    MATCH path =
        (chunk)<-[:FROM_CHUNK]-(entity)
        -[*0..2]-(neighbor)

    WHERE NOT neighbor:Chunk
      AND NOT neighbor:Document

    WITH path, relationships(path) AS rels
    UNWIND rels AS rel

    WITH
        rel,
        startNode(rel) AS source,
        endNode(rel) AS target

    WHERE NOT source:Chunk
      AND NOT source:Document
      AND NOT target:Chunk
      AND NOT target:Document

    RETURN
        elementId(source) AS source_id,
        labels(source)[0] AS source_label,
        coalesce(source.name, 'unknown') AS source_name,

        elementId(target) AS target_id,
        labels(target)[0] AS target_label,
        coalesce(target.name, 'unknown') AS target_name,

        type(rel) AS rel_type
    """

    nodes: dict[str, dict] = {}
    edges: dict[tuple[str, str, str], dict] = {}

    with driver.session() as session:
        result = session.run(
            query,
            chunk_ids=chunk_ids,
        )

        for record in result:
            source_id = record["source_id"]
            source_name = record["source_name"]
            source_label = record["source_label"]

            target_id = record["target_id"]
            target_name = record["target_name"]
            target_label = record["target_label"]

            rel_type = record["rel_type"]

            if source_id not in nodes:
                nodes[source_id] = {
                    "id": source_id,
                    "label": source_name,
                    "type": source_label,
                }

            if target_id not in nodes:
                nodes[target_id] = {
                    "id": target_id,
                    "label": target_name,
                    "type": target_label,
                }

            edge_key = (
                source_id,
                target_id,
                rel_type,
            )

            if edge_key not in edges:
                edges[edge_key] = {
                    "source": source_id,
                    "target": target_id,
                    "type": rel_type,
                }

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
def get_vector_chunk_ids(
    question: str,
    embedder: Any,
    top_k: int,
) -> list[str]:
    """
    Find the top-k vector chunks.

    This is used only for frontend subgraph highlighting.
    """

    query_embedding = embedder.embed_query(question)

    query = """
    CALL db.index.vector.queryNodes(
        $index_name,
        $top_k,
        $query_embedding
    )
    YIELD node, score

    RETURN elementId(node) AS chunk_id
    ORDER BY score DESC
    """

    with driver.session() as session:

        result = session.run(
            query,
            index_name=VECTOR_INDEX_NAME,
            top_k=top_k,
            query_embedding=query_embedding,
        )

        return [
            record["chunk_id"]
            for record in result
        ]


def get_graph_retrieval_query() -> str:
    """
    Retrieval query used by VectorCypherRetriever /
    HybridCypherRetriever.

    The query returns textual context plus graph data.
    """

    return """
    WITH node AS chunk

    MATCH path =
        (chunk)<-[:FROM_CHUNK]-(entity)
        -[*0..2]-(neighbor)

    WHERE NOT neighbor:Chunk
      AND NOT neighbor:Document

    WITH chunk, entity, neighbor, path

    RETURN
        chunk.text AS info,
        collect(
            DISTINCT {
                source_id: elementId(entity),
                source_name: coalesce(entity.name, ''),
                source_type:
                    CASE
                        WHEN size(labels(entity)) > 0
                        THEN labels(entity)[0]
                        ELSE 'unknown'
                    END,

                target_id: elementId(neighbor),
                target_name: coalesce(neighbor.name, ''),
                target_type:
                    CASE
                        WHEN size(labels(neighbor)) > 0
                        THEN labels(neighbor)[0]
                        ELSE 'unknown'
                    END,

                relationships:
                    [
                        r IN relationships(path)
                        | type(r)
                    ]
            }
        ) AS graph_data
    """


# ============================================================
# 5. Health API
# ============================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    """Check backend and Neo4j connectivity."""

    try:
        driver.verify_connectivity()

        return jsonify({
            "status": "ok",
            "message": "Connected to Neo4j",
        }), 200

    except Exception as exc:

        return jsonify({
        "status": "error",
        "message": str(exc),
        }), 500


# ============================================================
# 6. Complete Graph API
# ============================================================

@app.route("/api/graph", methods=["GET"])
def get_graph():
    """
    Get the complete knowledge graph.

    Chunk and Document nodes are excluded.
    """

    query = """
    MATCH (n)-[r]->(m)

    WHERE NOT n:Chunk
      AND NOT n:Document
      AND NOT m:Chunk
      AND NOT m:Document

    RETURN
    elementId(n) AS source_id,
    coalesce(n.name, 'unknown') AS source_name,
    labels(n)[0] AS source_type,

    type(r) AS rel_type,

    elementId(m) AS target_id,
    coalesce(m.name, 'unknown') AS target_name,
    labels(m)[0] AS target_type
    """

    try:

        with driver.session() as session:

            result = session.run(query)

            nodes: dict[str, dict] = {}
            edges: list[dict] = []

            for record in result:

                source_id = record["source_id"]

                if source_id not in nodes:
                    nodes[source_id] = {
                        "id": source_id,
                        "label": record["source_name"],
                        "type": record.get("source_type", "unknown"),
                }

                target_id = record["target_id"]

                if target_id not in nodes:
                    nodes[target_id] = {
                        "id": target_id,
                        "label": record["target_name"],
                        "type": record.get("target_type", "unknown"),
                    }

                edges.append({
                        "source": source_id,
                        "target": target_id,
                        "type": record["rel_type"],
                })

            return jsonify({
                "nodes": list(nodes.values()),
                "edges": edges,
            }), 200

    except Exception as exc:

        return error_response(
            str(exc),
            500,
        )


# ============================================================
# 7. Entity List API
# ============================================================

@app.route("/api/entities", methods=["GET"])
def get_entities():
    """Get entities, optionally filtered by type."""

    entity_type = request.args.get("type")

    if (
        entity_type
        and entity_type not in ALLOWED_ENTITY_TYPES
    ):
        return error_response(
            f"Invalid type: {entity_type}",
            400,
        )

    try:

        with driver.session() as session:

            if entity_type:

                query = f"""
                MATCH (n:`{entity_type}`)
                WHERE NOT n:Chunk
                AND NOT n:Document

                RETURN
             elementId(n) AS id,
            labels(n)[0] AS type,
                (n.name, 'unknown') AS name

ORDER BY name
"""

                result = session.run(
                    query,
                    entity_type=entity_type,
                )

            else:

                query = """
                MATCH (n)

                WHERE NOT n:Chunk
                  AND NOT n:Document

                RETURN
                    elementId(n) AS id,
                    labels(n)[0] AS type,
                    coalesce(n.name, 'unknown') AS name

                ORDER BY name
                """

                result = session.run(query)

            entities = [
                dict(record)
                for record in result
            ]

            return jsonify({
                "entities": entities,
            }), 200

    except Exception as exc:

        return error_response(
            str(exc),
            500,
        )


# ============================================================
# 8. Entity Detail API
# ============================================================

@app.route(
    "/api/entity/<path:entity_id>",
    methods=["GET"],
)
def get_entity_details(entity_id: str):
    """Get detailed information about one entity."""

    query = """
MATCH (n)

WHERE elementId(n) = $entity_id
  AND NOT n:Chunk AND NOT n:Document

OPTIONAL MATCH (n)-[r]-(related)

WHERE NOT related:Chunk
  AND NOT related:Document

RETURN
    n,
    labels(n)[0] AS type,

    collect(
        DISTINCT {
            node_id:
                CASE
                    WHEN related IS NULL
                    THEN NULL
                    ELSE elementId(related)
                END,

            node:
                CASE
                    WHEN related IS NULL
                    THEN NULL
                    ELSE coalesce(
                        related.name,
                        'unknown'
                    )
                END,

            relationship:
                CASE
                    WHEN r IS NULL
                    THEN NULL
                    ELSE type(r)
                END,

            direction:
                CASE
                    WHEN r IS NULL
                    THEN NULL
                    WHEN startNode(r) = n
                    THEN 'outgoing'
                    ELSE 'incoming'
                END
        }
    ) AS connections
"""

    try:

        with driver.session() as session:

            record = session.run(
                query,
                entity_id=entity_id,
            ).single()

            if not record:
                return error_response(
                    "Entity not found",
                    404,
                )

            node = record["n"]

            connections = [
                connection
                for connection in record["connections"]
                if connection.get("node") is not None
            ]

            return jsonify({
                "id": entity_id,
                "type": record["type"],
                "properties": dict(node),
                "connections": connections,
            }), 200

    except Exception as exc:

        return error_response(
            str(exc),
            500,
        )


# ============================================================
# 9. Statistics API
# ============================================================

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get knowledge graph statistics."""

    try:

        with driver.session() as session:

            node_counts = session.run("""
                MATCH (n)

                WHERE NOT n:Chunk
                  AND NOT n:Document

                RETURN
                    labels(n)[0] as type, count(n) as count
            """)

            nodes_by_type = {
                record["type"]: record["count"]
                for record in node_counts
            }

            rel_counts = session.run("""
    MATCH (a)-[r]->(b)
    WHERE NOT startNode(r):Chunk
      AND NOT startNode(r):Document
      AND NOT endNode(r):Chunk
      AND NOT endNode(r):Document
    RETURN type(r) as type, count(r) as count
""")

            relationships_by_type = {
                record["type"]: record["count"]
                for record in rel_counts
            }

            total_nodes = session.run("""
                MATCH (n)

                WHERE NOT n:Chunk
                  AND NOT n:Document

                RETURN count(n) as count
            """).single()["count"]

            total_relationships = session.run("""
    MATCH (a)-[r]->(b)
    WHERE NOT startNode(r):Chunk
      AND NOT startNode(r):Document
      AND NOT endNode(r):Chunk
      AND NOT endNode(r):Document
    RETURN count(r) as count
""").single()["count"]

            return jsonify({
                "total_nodes": total_nodes,
                "total_relationships": total_relationships,
                "nodes_by_type": nodes_by_type,
                "relationships_by_type": relationships_by_type,
            }), 200

    except Exception as exc:

        return error_response(
            str(exc),
            500,
        )


# ============================================================
# 10. Search API
# ============================================================

@app.route("/api/search", methods=["GET"])
def search_entities():
    """Search entities by name."""

    query_text = request.args.get(
        "q",
        "",
    ).strip()

    if not query_text:

        return error_response(
            "Query parameter 'q' is required",
            400,
        )

    query = """
    MATCH (n)

    WHERE NOT n:Chunk
      AND NOT n:Document
      AND toLower(
            coalesce(n.name, '')
          ) CONTAINS toLower($query)

    RETURN
        elementId(n) AS id,
        labels(n)[0] AS type,
        coalesce(n.name, 'unknown') AS name

    ORDER BY name

    LIMIT 20
    """

    try:

        with driver.session() as session:

            result = session.run(
                query,
                parameters={"query": query_text},
            )

            entities = [
                dict(record)
                for record in result
            ]

            return jsonify({
                "results": entities,
            }), 200

    except Exception as exc:

        return error_response(
            str(exc),
            500,
        )


# ============================================================
# 11. GraphRAG API
# ============================================================
@app.route("/api/graphrag", methods=["POST"])
def graphrag_query():
    """
    Perform GraphRAG query.

    Supported methods:
        vector
        vector_cypher
        hybrid
        hybrid_cypher
    """

    if not request.is_json:
        return error_response(
            "JSON object is required",
            400,
        )

    try:
        data = request.get_json()
    except Exception:
        return error_response(
            "JSON object is required",
            400,
        )

    if not isinstance(data, dict):
        return error_response(
            "JSON object is required",
            400,
        )

    question = str(
        data.get("question", "")
    ).strip()

    method = data.get(
        "method",
        "vector_cypher",
    )

    # --------------------------------------------------------
    # Validate request
    # --------------------------------------------------------

    # --------------------------------------------------------
    # Validate request
    # --------------------------------------------------------

    if not question:

        return error_response(
            "Question is required",
            400,
        )

    if method not in ALLOWED_RAG_METHODS:

        return error_response(
            f"Unknown method: {method}",
            400,
        )

    if not LLM_TOKEN:

        return error_response(
            "LLM_TOKEN is not configured",
            500,
        )

    try:

        # ----------------------------------------------------
        # Import C's GraphRAG components
        # ----------------------------------------------------

        graphrag_dir = (
            PROJECT_ROOT / "graphragexpr"
        )

        if str(graphrag_dir) not in sys.path:
            sys.path.insert(
                0,
                str(graphrag_dir),
            )

        from external_embedder import ExternalEmbedder

        from neo4j_graphrag.llm import (
            OpenAILLM,
        )

        from neo4j_graphrag.retrievers import (
            VectorRetriever,
            VectorCypherRetriever,
            HybridRetriever,
            HybridCypherRetriever,
        )

        from neo4j_graphrag.generation import (
            GraphRAG,
            RagTemplate,
        )

        # ----------------------------------------------------
        # Embedder
        # ----------------------------------------------------

        embedder = ExternalEmbedder(
            dimension=1536,
        )

        # ----------------------------------------------------
        # LLM
        # ----------------------------------------------------

        llm = OpenAILLM(
            model_name=LLM_MODEL,
            api_key=LLM_TOKEN,
            base_url=LLM_ENDPOINT,
            model_params={
                "temperature": 0,
            },
        )

        # ----------------------------------------------------
        # Retriever
        # ----------------------------------------------------

        if method == "vector":

            retriever = VectorRetriever(
                driver=driver,
                index_name=VECTOR_INDEX_NAME,
                embedder=embedder,
                return_properties=["text"],
            )

        elif method == "vector_cypher":

            retriever = VectorCypherRetriever(
                driver=driver,
                index_name=VECTOR_INDEX_NAME,
                embedder=embedder,
                retrieval_query=
                    get_graph_retrieval_query(),
            )

        elif method == "hybrid":

            retriever = HybridRetriever(
                driver=driver,
                vector_index_name=VECTOR_INDEX_NAME,
                fulltext_index_name=FULLTEXT_INDEX_NAME,
                embedder=embedder,
                return_properties=["text"],
            )

        elif method == "hybrid_cypher":

            retriever = HybridCypherRetriever(
                driver=driver,
                vector_index_name=VECTOR_INDEX_NAME,
                fulltext_index_name=FULLTEXT_INDEX_NAME,
                embedder=embedder,
                retrieval_query=
                    get_graph_retrieval_query(),
            )

        else:
            # Should never happen because of validation.
            return error_response(
                f"Unknown method: {method}",
                400,
            )

        # ----------------------------------------------------
        # RAG Prompt
        # ----------------------------------------------------

        rag_template = RagTemplate(
            template="""
你是一个专业的医药知识问答助手。

请仅根据提供的上下文回答用户问题。

上下文可能包含：
1. 医药文本片段
2. 知识图谱关系
3. 实体之间的关联信息

如果上下文不足以回答问题，请明确说明信息不足，
不要自行编造医学事实。

# 用户问题

{query_text}

# 上下文

{context}

# 回答
""",
            expected_inputs=[
                "query_text",
                "context",
            ],
        )

        # ----------------------------------------------------
        # GraphRAG
        # ----------------------------------------------------

        graph_rag = GraphRAG(
            retriever=retriever,
            llm=llm,
            prompt_template=rag_template,
        )

        response = graph_rag.search(
            query_text=question,
            retriever_config={
                "top_k": TOP_K,
            },
        )

        # ----------------------------------------------------
        # Extract answer
        # ----------------------------------------------------

        answer = getattr(
            response,
            "answer",
            None,
        )

        if answer is None:

            # Compatibility with different neo4j-graphrag
            # response structures.
            answer = str(response)

        # ----------------------------------------------------
        # Subgraph
        # ----------------------------------------------------

        subgraph = {
            "nodes": [],
            "edges": [],
        }

        if method in {
            "vector_cypher",
            "hybrid_cypher",
        }:

            chunk_ids = get_vector_chunk_ids(
                question,
                embedder,
                TOP_K,
            )

            subgraph = build_subgraph_from_chunks(
                chunk_ids,
            )

        # ----------------------------------------------------
        # API response
        # ----------------------------------------------------

        return jsonify({
            "answer": answer,
            "method": method,
            "subgraph": subgraph,
        }), 200

    except ImportError as exc:

        return error_response(
            f"GraphRAG dependency/import error: {exc}",
            500,
        )

    except Exception as exc:

        return error_response(
            str(exc),
            500,
        )


# ============================================================
# 12. Shutdown
# ============================================================

@app.teardown_appcontext
def close_driver(exception=None):
    """
    Do not close the global Neo4j driver here.

    Flask creates/destroys application contexts frequently,
    while the driver is intended to be reused.
    """
    pass


# ============================================================
# 13. Main
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("GraphRAG Backend API")
    print("=" * 60)

    print(
        "Neo4j:",
        NEO4J_URL or "NOT CONFIGURED",
    )

    print(
        "LLM:",
        LLM_MODEL,
    )

    print(
        "Server: http://localhost:5000",
    )

    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )