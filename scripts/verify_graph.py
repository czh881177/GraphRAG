# scripts/verify_graph.py
# 医药 GraphRAG · 图谱质检脚本（B 数据/图谱）
# 用途：入库后核对 业务关系/Chunk 向量/检索耦合 是否符合契约与目标阈值。
# 用法：.venv\\Scripts\\python.exe scripts\\verify_graph.py
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def main():
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URL"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )
    with driver.session() as s:
        biz_rows = [
            (r["t"], r["c"])
            for r in s.run(
                "MATCH ()-[r]->() WHERE NOT type(r) IN ['PART_OF','FROM_CHUNK'] "
                "RETURN type(r) AS t, count(r) AS c"
            )
        ]
        biz_total = sum(c for _, c in biz_rows)
        print("=== 业务关系（按类型）===")
        for t, c in sorted(biz_rows, key=lambda x: -x[1]):
            print(f"  {t}: {c}")
        print(f"  业务关系合计: {biz_total}  (目标>=500) -> {'OK' if biz_total >= 500 else 'FAIL'}")

        chunk_count = s.run("MATCH (c:Chunk) RETURN count(c) AS c").single()["c"]
        vecs = s.run(
            "MATCH (c:Chunk) WHERE size(c.embedding)=1536 RETURN count(c) AS c"
        ).single()["c"]
        print(f"Chunk 节点: {chunk_count}, 带 1536 维向量: {vecs} -> {'OK' if vecs == chunk_count else 'FAIL'}")

        fc = s.run("MATCH ()-[r:FROM_CHUNK]->() RETURN count(r) AS c").single()["c"]
        doc = s.run("MATCH (d:Document) RETURN count(d) AS c").single()["c"]
        iso = s.run(
            "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document AND NOT (n)--() "
            "RETURN count(n) AS c"
        ).single()["c"]
        total_ent = s.run(
            "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document RETURN count(n) AS c"
        ).single()["c"]
        iso_ratio = (iso / total_ent * 100) if total_ent else 0.0
        print(f"FROM_CHUNK: {fc}, Document: {doc}")
        print(f"孤立实体: {iso} ({iso_ratio:.1f}%) -> {'OK' if iso_ratio <= 5 else 'FAIL'}")

        sample = s.run("MATCH (c:Chunk) RETURN elementId(c) AS id LIMIT 1").single()
        if sample:
            row = s.run(
                """
                MATCH (chunk) WHERE elementId(chunk)=$eid
                MATCH (chunk)<-[:FROM_CHUNK]-(entity)-[rel*0..2]-(neighbor)
                WHERE NOT neighbor:Chunk AND NOT neighbor:Document
                RETURN count(DISTINCT entity) AS entities, count(DISTINCT neighbor) AS neighbors
                """,
                eid=sample["id"],
            ).single()
            ok = "OK" if row["neighbors"] > 0 else "FAIL"
            print(
                f"检索耦合测试(入口 chunk): 命中实体={row['entities']}, "
                f"邻居={row['neighbors']} -> {ok}"
            )
    driver.close()


if __name__ == "__main__":
    main()
