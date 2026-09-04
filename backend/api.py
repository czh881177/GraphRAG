# backend/api.py
"""
Flask backend API for serving knowledge graph data to visualization
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Neo4j connection
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URL"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        driver.verify_connectivity()
        return jsonify({"status": "ok", "message": "Connected to Neo4j"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/graph', methods=['GET'])
def get_graph():
    """Get the complete knowledge graph (entities only, no chunks)"""
    query = """
    MATCH (n)-[r]->(m)
    WHERE NOT n:Chunk AND NOT n:Document
      AND NOT m:Chunk AND NOT m:Document
    RETURN elementId(n) AS source_id, labels(n)[0] AS source_label,
           coalesce(n.name, 'unknown') AS source_name,
           type(r) AS rel_type,
           elementId(m) AS target_id, labels(m)[0] AS target_label,
           coalesce(m.name, 'unknown') AS target_name
    """

    try:
        with driver.session() as session:
            result = session.run(query)

            nodes = {}
            edges = []

            for record in result:
                # Add source node
                source_id = record["source_id"]
                if source_id not in nodes:
                    nodes[source_id] = {
                        "id": source_id,
                        "label": record["source_name"],
                        "type": record["source_label"]
                    }

                # Add target node
                target_id = record["target_id"]
                if target_id not in nodes:
                    nodes[target_id] = {
                        "id": target_id,
                        "label": record["target_name"],
                        "type": record["target_label"]
                    }

                # Add edge
                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "type": record["rel_type"]
                })

            return jsonify({
                "nodes": list(nodes.values()),
                "edges": edges
            }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/entities', methods=['GET'])
def get_entities():
    """Get all entities with their types"""
    entity_type = request.args.get('type', None)

    if entity_type:
        query = f"""
        MATCH (n:`{entity_type}`)
        WHERE NOT n:Chunk AND NOT n:Document
        RETURN elementId(n) as id, labels(n)[0] as type,
               coalesce(n.name, 'unknown') as name
        """
    else:
        query = """
        MATCH (n)
        WHERE NOT n:Chunk AND NOT n:Document
        RETURN elementId(n) as id, labels(n)[0] as type,
               coalesce(n.name, 'unknown') as name
        """

    try:
        with driver.session() as session:
            result = session.run(query)
            entities = [dict(record) for record in result]
            return jsonify({"entities": entities}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/entity/<entity_id>', methods=['GET'])
def get_entity_details(entity_id):
    """Get detailed information about a specific entity"""
    query = """
    MATCH (n)
    WHERE elementId(n) = $entity_id
    OPTIONAL MATCH (n)-[r]-(related)
    WHERE NOT related:Chunk AND NOT related:Document
    RETURN n,
           labels(n)[0] as type,
           collect(DISTINCT {
               node: related.name,
               relationship: type(r),
               direction: CASE
                   WHEN startNode(r) = n THEN 'outgoing'
                   ELSE 'incoming'
               END
           }) as connections
    """

    try:
        with driver.session() as session:
            result = session.run(query, entity_id=entity_id)
            record = result.single()

            if not record:
                return jsonify({"error": "Entity not found"}), 404

            node = record["n"]
            return jsonify({
                "id": entity_id,
                "type": record["type"],
                "properties": dict(node),
                "connections": record["connections"]
            }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics about the knowledge graph"""
    try:
        with driver.session() as session:
            # Count nodes by type
            node_counts = session.run("""
                MATCH (n)
                WHERE NOT n:Chunk AND NOT n:Document
                RETURN labels(n)[0] as type, count(n) as count
            """)

            nodes_by_type = {record["type"]: record["count"] for record in node_counts}

            # Count relationships by type
            rel_counts = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
            """)

            rels_by_type = {record["type"]: record["count"] for record in rel_counts}

            # Total counts
            total_nodes = session.run("""
                MATCH (n)
                WHERE NOT n:Chunk AND NOT n:Document
                RETURN count(n) as count
            """).single()["count"]

            total_rels = session.run("""
                MATCH ()-[r]->()
                RETURN count(r) as count
            """).single()["count"]

            return jsonify({
                "total_nodes": total_nodes,
                "total_relationships": total_rels,
                "nodes_by_type": nodes_by_type,
                "relationships_by_type": rels_by_type
            }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/search', methods=['GET'])
def search_entities():
    """Search entities by name"""
    query_text = request.args.get('q', '')

    if not query_text:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    query = """
    MATCH (n)
    WHERE NOT n:Chunk AND NOT n:Document
      AND toLower(coalesce(n.name, '')) CONTAINS toLower($query)
    RETURN elementId(n) as id, labels(n)[0] as type, n.name as name
    LIMIT 20
    """

    try:
        with driver.session() as session:
            result = session.run(query, query=query_text)
            entities = [dict(record) for record in result]
            return jsonify({"results": entities}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/graphrag', methods=['POST'])
def graphrag_query():
    """Perform GraphRAG query and return answer with subgraph used"""
    data = request.get_json()
    question = data.get('question', '')
    method = data.get('method', 'hybrid')  # vector, hybrid, vector_cypher, hybrid_cypher

    if not question:
        return jsonify({"error": "Question is required"}), 400

    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "graphragexpr"))

        from external_embedder import ExternalEmbedder
        from neo4j_graphrag.llm import OpenAILLM
        from neo4j_graphrag.retrievers import (
            VectorRetriever,
            VectorCypherRetriever,
            HybridRetriever,
            HybridCypherRetriever
        )
        from neo4j_graphrag.generation import GraphRAG, RagTemplate

        # Initialize components
        embedder = ExternalEmbedder(dimension=1536)

        api_key = os.getenv("LLM_TOKEN")
        base_url = os.getenv("LLM_ENDPOINT", "https://api.deepseek.com")

        llm = OpenAILLM(
            model_name=os.getenv("LLM_MODEL", "deepseek-chat"),
            api_key=api_key,
            base_url=base_url,
            model_params={"temperature": 0}
        )

        # Select retriever based on method
        if method == 'vector':
            # Pure vector search
            retriever = VectorRetriever(
                driver=driver,
                index_name="text_embeddings",
                embedder=embedder,
                return_properties=["text"]
            )
        elif method == 'vector_cypher':
            # Vector search + graph traversal
            retrieval_query = """
            WITH node AS chunk
            MATCH (chunk)<-[:FROM_CHUNK]-(entity)-[rel*0..2]-(neighbor)
            WHERE NOT neighbor:Chunk AND NOT neighbor:Document
            WITH DISTINCT chunk, entity, neighbor, rel
            WITH chunk,
                 collect(DISTINCT chunk.text) AS texts,
                 collect(DISTINCT {
                   source_id: elementId(entity),
                   source_name: coalesce(entity.name, ''),
                   source_type: labels(entity)[0],
                   target_id: elementId(neighbor),
                   target_name: coalesce(neighbor.name, ''),
                   target_type: labels(neighbor)[0],
                   relationships: [r IN rel | type(r)]
                 }) as graph_data
            WITH reduce(s = '', text IN texts |
                    s + CASE WHEN s = '' THEN text ELSE '\n---\n' + text END
                 ) AS context_text,
                 graph_data
            RETURN context_text as info, graph_data
            """
            retriever = VectorCypherRetriever(
                driver=driver,
                index_name="text_embeddings",
                embedder=embedder,
                retrieval_query=retrieval_query
            )
        elif method == 'hybrid':
            # Hybrid: vector + fulltext (requires fulltext index)
            retriever = HybridRetriever(
                driver=driver,
                vector_index_name="text_embeddings",
                fulltext_index_name="text_fulltext",  # Need to create this
                embedder=embedder,
                return_properties=["text"]
            )
        elif method == 'hybrid_cypher':
            # Hybrid + graph traversal
            retrieval_query = """
            WITH node AS chunk
            MATCH (chunk)<-[:FROM_CHUNK]-(entity)-[rel*0..2]-(neighbor)
            WHERE NOT neighbor:Chunk AND NOT neighbor:Document
            WITH DISTINCT chunk, entity, neighbor, rel
            WITH chunk,
                 collect(DISTINCT chunk.text) AS texts,
                 collect(DISTINCT {
                   source_id: elementId(entity),
                   source_name: coalesce(entity.name, ''),
                   source_type: labels(entity)[0],
                   target_id: elementId(neighbor),
                   target_name: coalesce(neighbor.name, ''),
                   target_type: labels(neighbor)[0],
                   relationships: [r IN rel | type(r)]
                 }) as graph_data
            WITH reduce(s = '', text IN texts |
                    s + CASE WHEN s = '' THEN text ELSE '\n---\n' + text END
                 ) AS context_text,
                 graph_data
            RETURN context_text as info, graph_data
            """
            retriever = HybridCypherRetriever(
                driver=driver,
                vector_index_name="text_embeddings",
                fulltext_index_name="text_fulltext",
                embedder=embedder,
                retrieval_query=retrieval_query
            )
        else:
            return jsonify({"error": f"Unknown method: {method}"}), 400

        # Create RAG template
        rag_template = RagTemplate(
            template="""你是一个专业的问答助手。请仅根据以下上下文回答问题，
上下文包括相关文本片段和知识图谱三元组。如果上下文不足以回答，请如实说明。

# 问题：
{query_text}

# 上下文：
{context}

# 回答：
""",
            expected_inputs=["query_text", "context"],
        )

        # Create GraphRAG instance
        graph_rag = GraphRAG(retriever=retriever, llm=llm, prompt_template=rag_template)

        # Perform search
        response = graph_rag.search(
            query_text=question,
            retriever_config={"top_k": 3},
        )

        # Extract subgraph for *Cypher methods by querying Neo4j directly
        subgraph = {"nodes": [], "edges": []}

        if method in ['vector_cypher', 'hybrid_cypher']:
            try:
                # Get query embedding to find which chunks were retrieved
                query_embedding = embedder.embed_query(question)

                # Find relevant chunks that were used in retrieval
                chunk_query = """
                CALL db.index.vector.queryNodes('text_embeddings', $top_k, $query_embedding)
                YIELD node, score
                RETURN elementId(node) as chunk_id
                """

                with driver.session() as session:
                    result = session.run(chunk_query, query_embedding=query_embedding, top_k=3)
                    chunk_ids = [record['chunk_id'] for record in result]

                    if chunk_ids:
                        # Get subgraph around those chunks (same as retrieval_query pattern)
                        subgraph_query = """
                        UNWIND $chunk_ids AS chunk_id
                        MATCH (chunk) WHERE elementId(chunk) = chunk_id
                        MATCH (chunk)<-[:FROM_CHUNK]-(entity)-[rel*0..2]-(neighbor)
                        WHERE NOT neighbor:Chunk AND NOT neighbor:Document
                        WITH DISTINCT entity, neighbor, rel
                        UNWIND CASE WHEN rel = [] THEN [null] ELSE rel END AS r
                        WITH DISTINCT
                            CASE WHEN r IS NULL THEN entity ELSE startNode(r) END as source,
                            CASE WHEN r IS NULL THEN null ELSE endNode(r) END as target,
                            CASE WHEN r IS NULL THEN null ELSE type(r) END as rel_type
                        WHERE source IS NOT NULL
                        RETURN DISTINCT
                            elementId(source) as source_id,
                            labels(source)[0] as source_label,
                            coalesce(source.name, 'unknown') as source_name,
                            CASE WHEN target IS NOT NULL THEN elementId(target) END as target_id,
                            CASE WHEN target IS NOT NULL THEN labels(target)[0] END as target_label,
                            CASE WHEN target IS NOT NULL THEN coalesce(target.name, 'unknown') END as target_name,
                            rel_type
                        """

                        result = session.run(subgraph_query, chunk_ids=chunk_ids)

                        nodes_map = {}
                        edges = []

                        for record in result:
                            source_id = record['source_id']
                            if source_id and source_id not in nodes_map:
                                nodes_map[source_id] = {
                                    'id': source_id,
                                    'label': record['source_name'],
                                    'type': record['source_label']
                                }

                            target_id = record['target_id']
                            if target_id:
                                if target_id not in nodes_map:
                                    nodes_map[target_id] = {
                                        'id': target_id,
                                        'label': record['target_name'],
                                        'type': record['target_label']
                                    }

                                if record['rel_type']:
                                    edges.append({
                                        'source': source_id,
                                        'target': target_id,
                                        'type': record['rel_type']
                                    })

                        subgraph['nodes'] = list(nodes_map.values())
                        subgraph['edges'] = edges
            except Exception as e:
                print(f"Error extracting subgraph for cypher method: {e}")
                import traceback
                traceback.print_exc()

        return jsonify({
            "answer": response.answer,
            "method": method,
            "subgraph": subgraph
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.teardown_appcontext
def close_db(error):
    """Close database connection on app teardown"""
    pass


if __name__ == '__main__':
    print("Starting GraphRAG Backend API...")
    print(f"Neo4j URI: {os.getenv('NEO4J_URI')}")
    print("API will be available at http://localhost:5000")
    print("\nAvailable endpoints:")
    print("  GET  /api/health          - Health check")
    print("  GET  /api/graph           - Get complete knowledge graph")
    print("  GET  /api/entities        - Get all entities")
    print("  GET  /api/entity/<id>     - Get entity details")
    print("  GET  /api/stats           - Get graph statistics")
    print("  GET  /api/search?q=...    - Search entities")

    app.run(debug=True, host='0.0.0.0', port=5000)
