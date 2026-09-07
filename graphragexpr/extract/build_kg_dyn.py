# -*- coding: utf-8 -*-
"""
Build knowledge graph dynamically from source text (医药 GraphRAG) — B 数据/图谱

本文件已按 docs/DATA_PLAN.md 与 docs/SCHEMA.md 改造：
  1. 数据源：读取 data/processed/chunks.json（由 scripts/prepare_corpus.py 生成）
  2. 本体：6 类（药物/疾病/症状/公司/作用机制/副作用）+ 必要时 概念
  3. 关系：研发/作用于/治疗/缓解/副作用/属于（方向见 DATA_PLAN §5）
  4. Document：name/id 使用医药文档文件名（如 aspirin.txt）
  5. Chunk.index 全局唯一，写入时必带 1536 维 embedding（向量索引要求）
  6. 实体↔Chunk 关联：使用抽取结果中的 entities 定位（不再用 name-in-text 误匹配）

抽取：
  - 若 .env 配置了 LLM_TOKEN：DeepSeek 抽取，并把结果缓存到 extracted.json；
  - 否则：读取 data/processed/extracted.json（离线抽取结果，gen 脚本生成）。

用法：
  .venv\\Scripts\\python.exe graphragexpr\\extract\\build_kg_dyn.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

from external_embedder import ExternalEmbedder

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent.parent
CHUNKS_FILE = ROOT / "data" / "processed" / "chunks.json"
EXTRACTED_FILE = ROOT / "data" / "processed" / "extracted.json"

ENTITY_TYPES = {"药物", "疾病", "症状", "公司", "作用机制", "副作用"}
CONCEPT = "概念"
VALID_LABELS = ENTITY_TYPES | {CONCEPT}
VALID_REL = {"研发", "作用于", "治疗", "缓解", "副作用", "属于"}

# 医学抽取 Prompt（真实 DeepSeek 模式使用）
MEDICAL_EXTRACT_PROMPT = """你是一个医药知识图谱抽取专家。请从以下文本中抽取实体和关系。

实体类型只能取以下之一：药物、疾病、症状、公司、作用机制、副作用（必要时可用“概念”）。
关系类型只能取以下之一（注意方向）：
  研发：公司 -> 药物
  作用于：药物 -> 作用机制（靶点/机制）
  治疗：药物 -> 疾病
  缓解：药物 -> 症状
  副作用：药物 -> 副作用（不良反应）
  属于：药物 -> 药物

要求：同名实体使用同一名称（便于合并）；尽可能多地抽取实体和关系，并推断语义中潜在的关系。
只返回 JSON，不要其他说明文字，格式如下：
{{
  "entities": [{{"name": "实体名称", "type": "实体类型"}}],
  "relationships": [{{"source": "源实体", "target": "目标实体", "type": "关系类型"}}]
}}

文本：
{text}
"""


def _safe_json_loads(raw):
    """容错解析 LLM 返回的 JSON：
    1. 剥掉 ```json / ``` 代码块标记（若有）
    2. 只取第一个 '{' 到最后一个 '}' 之间的内容（去掉前后杂散文字）
    3. 去除尾随逗号（JSON 不允许 ,} / ,]）
    """
    if "```" in raw:
        parts = raw.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") and p.endswith("}"):
                raw = p
                break
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM 返回内容中未找到完整 JSON 对象")
    raw = raw[start:end + 1]
    import re
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*\]", "]", raw)
    return json.loads(raw)


def extract_via_llm(text, client, max_retries=2):
    """调用 DeepSeek 抽取实体/关系，返回 (entities, relationships)。
    带容错解析 + 重试：JSON 解析失败或调用异常时自动重试，最多 max_retries 次。
    """
    prompt = MEDICAL_EXTRACT_PROMPT.format(text=text)
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = resp.choices[0].message.content.strip()
            data = _safe_json_loads(raw)
            return data.get("entities", []), data.get("relationships", [])
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                print(f"    \u26a0 \u7b2c {attempt + 1} \u6b21\u5931\u8d25({e})\uff0c\u91cd\u8bd5...")
    raise last_err


def load_or_build_extraction(client=None):
    """双模式：有 client（key）则实时抽取并缓存；否则读离线 extracted.json。"""
    if client is not None:
        chunks = load_chunks()
        records = []
        for chunk in chunks:
            print(f"  抽取 {chunk['source']} (chunk {chunk['index']}) ...")
            try:
                ents, rels = extract_via_llm(chunk["text"], client)
            except Exception as e:
                print(f"    ⚠ 抽取失败: {e}")
                ents, rels = [], []
            ents = [{k: v for k, v in e.items() if k in ("name", "type")} for e in ents]
            rels = [{k: v for k, v in r.items() if k in ("source", "target", "type")} for r in rels]
            records.append({
                "chunk_index": chunk["index"],
                "source": chunk["source"],
                "entities": ents,
                "relationships": rels,
            })
        EXTRACTED_FILE.parent.mkdir(parents=True, exist_ok=True)
        EXTRACTED_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return records
    else:
        if not EXTRACTED_FILE.exists():
            sys.exit(f"未找到离线抽取结果 {EXTRACTED_FILE}，请先运行 scripts/generate_extracted.py")
        return json.loads(EXTRACTED_FILE.read_text(encoding="utf-8"))


def load_chunks():
    if not CHUNKS_FILE.exists():
        sys.exit(f"未找到 {CHUNKS_FILE}，请先运行 scripts/prepare_corpus.py")
    return json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))


def connect_driver():
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URL"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )
    driver.verify_connectivity()
    return driver


def build_entity_registry(records):
    """全局实体名 -> 类型，保证同名合并、不重复建节点。
    关系里出现但未声明的名称按“概念”补建。
    """
    registry = {}
    for rec in records:
        for e in rec["entities"]:
            name = (e.get("name") or "").strip()
            typ = (e.get("type") or CONCEPT).strip()
            if not name:
                continue
            if typ not in VALID_LABELS:
                # 未识别类型归并为“概念”，避免违规 Label
                typ = CONCEPT
            if name not in registry:
                registry[name] = typ
            elif registry[name] != typ and typ != CONCEPT:
                # 同名不同类：以最先出现的非“概念”类型为准
                if registry[name] == CONCEPT:
                    registry[name] = typ
        for r in rec["relationships"]:
            for key in ("source", "target"):
                name = (r.get(key) or "").strip()
                if name and name not in registry:
                    registry[name] = CONCEPT
    return registry


def build_graph(driver, chunks, records):
    embedder = ExternalEmbedder(dimension=1536)
    registry = build_entity_registry(records)

    # 先建立 source -> chunk_index 列表（一个文档可能有多个块）
    source_chunks = {}
    for chunk in chunks:
        source_chunks.setdefault(chunk["source"], []).append(chunk)

    with driver.session() as session:
        print("正在清空旧数据（B 串行）...")
        session.run("MATCH (n) DETACH DELETE n")

        # ---- Document 节点 ----
        for source, clist in source_chunks.items():
            full_text = "\n".join(c["text"] for c in clist)
            session.run(
                "MERGE (d:Document {id: $id}) SET d.name = $name, d.text = $text",
                id=source,
                name=source.split(".")[0],
                text=full_text,
            )

        # ---- Chunk 节点 + PART_OF + embedding ----
        for chunk in chunks:
            emb = embedder.embed_query(chunk["text"])
            session.run(
                """
                MERGE (c:Chunk {index: $index})
                SET c.text = $text, c.embedding = $embedding
                WITH c
                MATCH (d:Document {id: $source})
                MERGE (c)-[:PART_OF]->(d)
                """,
                index=chunk["index"],
                text=chunk["text"],
                embedding=emb,
                source=chunk["source"],
            )

        # ---- 实体节点（全局唯一，按 name MERGE）----
        for name, typ in registry.items():
            session.run(f"MERGE (e:`{typ}` {{name: $name}})", name=name)

        # ---- 实体 <-> 分块（FROM_CHUNK，用抽取结果定位）----
        for rec in records:
            idx = rec["chunk_index"]
            for e in rec["entities"]:
                name = (e.get("name") or "").strip()
                if not name:
                    continue
                typ = registry.get(name, CONCEPT)
                session.run(
                    """
                    MATCH (e:`%s` {name: $name})
                    MATCH (c:Chunk {index: $index})
                    MERGE (e)-[:FROM_CHUNK]->(c)
                    """ % typ,
                    name=name,
                    index=idx,
                )

        # ---- 实体间业务关系 ----
        for rec in records:
            for r in rec["relationships"]:
                src = (r.get("source") or "").strip()
                tgt = (r.get("target") or "").strip()
                rtype = (r.get("type") or "").strip()
                if not src or not tgt or rtype not in VALID_REL:
                    continue
                s_typ = registry.get(src, CONCEPT)
                t_typ = registry.get(tgt, CONCEPT)
                session.run(
                    """
                    MATCH (s:`%s` {name: $src})
                    MATCH (t:`%s` {name: $tgt})
                    MERGE (s)-[:`%s`]->(t)
                    """ % (s_typ, t_typ, rtype),
                    src=src,
                    tgt=tgt,
                )


def report(driver):
    with driver.session() as session:
        total_nodes = session.run(
            "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document RETURN count(n) AS c"
        ).single()["c"]
        total_rel = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        by_type = {
            rec["label"]: rec["c"]
            for rec in session.run(
                "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document "
                "RETURN labels(n)[0] AS label, count(n) AS c"
            )
        }
        iso = session.run(
            """
            MATCH (n)
            WHERE NOT n:Chunk AND NOT n:Document AND NOT (n)--()
            RETURN count(n) AS c
            """
        ).single()["c"]
        total_entities = total_nodes
        iso_ratio = (iso / total_entities * 100) if total_entities else 0.0
        print(f"\n—— 图谱统计 ——")
        print(f"实体节点（不含 Chunk/Document）：{total_entities}")
        print(f"关系总数：{total_rel}")
        print(f"按类型：{by_type}")
        print(f"孤立节点：{iso}（{iso_ratio:.1f}%，要求 ≤5%）")
        ok_entities = total_entities >= 300
        ok_rel = total_rel >= 500
        ok_iso = iso_ratio <= 5.0
        print(f"实体达标(≥300)：{'✓' if ok_entities else '✗'}")
        print(f"关系达标(≥500)：{'✓' if ok_rel else '✗'}")
        print(f"孤立节点达标(≤5%)：{'✓' if ok_iso else '✗'}")


def main():
    print("正在连接 Neo4j ...")
    driver = connect_driver()
    print("✓ Neo4j 连接成功")

    chunks = load_chunks()
    print(f"✓ 读取到 {len(chunks)} 个分块")

    token = os.getenv("LLM_TOKEN")
    use_llm = bool(token) and token.strip() and not token.strip().startswith("sk-xxxx")
    if use_llm:
        print("✓ 使用真实 DeepSeek 抽取")
        client = OpenAI(
            api_key=token,
            base_url=os.getenv("LLM_ENDPOINT", "https://api.deepseek.com"),
        )
        records = load_or_build_extraction(client)
    else:
        print("⚠ 无 LLM key，使用离线抽取结果（extracted.json）")
        records = load_or_build_extraction()

    print(f"✓ 待入库实体/关系来自 {len(records)} 个分块")
    build_graph(driver, chunks, records)
    report(driver)
    driver.close()
    print("\n✓ 知识图谱构建完成！可用 Neo4j Browser 验证：MATCH (n) RETURN n LIMIT 50;")


if __name__ == "__main__":
    main()
