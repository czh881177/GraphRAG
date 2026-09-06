# scripts/generate_extracted.py
"""
医药 GraphRAG · 生成离线抽取结果 extracted.json（B 数据/图谱）

作用：把人工整理的 6 类本体抽取数据（curated_data_a/b.py）按 chunks.json 的
分块顺序对齐，输出 data/processed/extracted.json，供 build_kg_dyn.py 离线建图。

输出结构（每块一项）：
[
  { "chunk_index": 0, "source": "aspirin.txt",
    "entities": [{"name","type"}],
    "relationships": [{"source","target","type"}] }
]

用法：.venv\\Scripts\\python.exe scripts\\generate_extracted.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "graphragexpr" / "extract"))

from curated_data_a import DATA_A
from curated_data_b import DATA_B
from curated_data_c import DATA_C
from curated_data_x import EXTRA_RELS

CHUNKS_FILE = ROOT / "data" / "processed" / "chunks.json"
OUT_FILE = ROOT / "data" / "processed" / "extracted.json"

ALLOWED_REL = {"研发", "作用于", "治疗", "缓解", "副作用", "属于"}
HUB_SOURCE = "cardiovascular_overview.txt"


def main():
    if not CHUNKS_FILE.exists():
        sys.exit(f"未找到 {CHUNKS_FILE}，请先运行 scripts/prepare_corpus.py")

    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    curated = {}
    curated.update(DATA_A)
    curated.update(DATA_B)
    curated.update(DATA_C)

    records = []
    seen_chunk = set()
    for chunk in chunks:
        src = chunk["source"]
        data = curated.get(src)
        if data is None:
            print(f"  ⚠ {src} 无抽取数据，跳过")
            continue

        # 校验关系类型，剔除不合规项
        rels = []
        for r in data["relationships"]:
            if r["type"] not in ALLOWED_REL:
                print(f"  ⚠ 跳过不合规关系 {src}: {r['source']}-[{r['type']}]->{r['target']}")
                continue
            rels.append(r)

        # 把跨文档补充关系挂到枢纽分块上
        if src == HUB_SOURCE:
            for r in EXTRA_RELS:
                if r["type"] in ALLOWED_REL:
                    rels.append(r)

        records.append({
            "chunk_index": chunk["index"],
            "source": src,
            "entities": data["entities"],
            "relationships": rels,
        })
        seen_chunk.add(chunk["index"])

    # 统计实体/关系（按规范化名称去重合并）
    ent_keys = set()
    rel_keys = set()
    for rec in records:
        for e in rec["entities"]:
            ent_keys.add((e["type"], e["name"]))
        for r in rec["relationships"]:
            rel_keys.add((r["source"], r["target"], r["type"]))

    OUT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    total_entities = len(ent_keys)
    total_rels = len(rel_keys)
    print(f"分块对齐：{len(records)} 块")
    print(f"去重后实体：{total_entities}（目标 ≥300）")
    print(f"去重后关系：{total_rels}（目标 ≥500）")
    print(f"已写出：{OUT_FILE}")


if __name__ == "__main__":
    main()
