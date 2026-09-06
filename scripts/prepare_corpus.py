# scripts/prepare_corpus.py
"""
医药 GraphRAG · 语料清洗与分块（B 数据/图谱 负责）

用途：读取 data/raw/*.txt（每篇一个文件），清洗后按句子边界分块，
输出 data/processed/chunks.json，供 build_kg_dyn.py 消费。

输出格式（与 docs/DATA_PLAN.md §3 一致）：
[
  { "index": 0, "source": "aspirin.txt", "text": "……" },
  ...
]
其中 index 为全局唯一、跨文档单调递增。

用法：
  .venv\\Scripts\\python.exe scripts\\prepare_corpus.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"
OUT_FILE = OUT_DIR / "chunks.json"

CHUNK_SIZE = 600          # 目标每块字数（DATA_PLAN §2：500–800）
CHUNK_OVERLAP = 80        # 相邻块重叠字数（DATA_PLAN §2：50–100）


def clean_text(text: str) -> str:
    """清洗：去首尾空白、压缩多余空行、去掉控制字符，保留中文标点。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)          # 连续空白合并为一个空格
    text = text.strip()
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """按句子边界将文本切为重叠分块。

    优先在句末标点（。！？；…）处断句；若一句超过 chunk_size，则硬切。
    返回不含空串的文本块列表。
    """
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end]

        # 若还没到文末，尝试在句号处向后收尾，避免把句子拦腰截断
        if end < n:
            last_punct = max(
                chunk.rfind("。"),
                chunk.rfind("！"),
                chunk.rfind("？"),
                chunk.rfind("；"),
            )
            if last_punct >= max(chunk_size * 0.5, 40) and last_punct < len(chunk) - 1:
                end = start + last_punct + 1
                chunk = text[start:end]

        chunk = clean_text(chunk)
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks


def process_source_files():
    if not RAW_DIR.exists():
        sys.exit(f"未找到语料目录：{RAW_DIR}")

    raw_files = sorted(RAW_DIR.glob("*.txt"))
    if not raw_files:
        sys.exit(f"data/raw 下没有 .txt 语料文件")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    idx = 0
    for fp in raw_files:
        try:
            raw = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = fp.read_text(encoding="gb18030")

        text = clean_text(raw)
        if not text:
            print(f"  ⚠ 跳过空文件 {fp.name}")
            continue

        chunks = chunk_text(text)
        for ci, ctxt in enumerate(chunks):
            records.append({"index": idx, "source": fp.name, "text": ctxt})
            idx += 1

        print(f"  ✓ {fp.name}: {len(chunks)} 块")

    OUT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    total_chars = sum(len(r["text"]) for r in records)
    print(f"\n总计：{len(records)} 个分块，{total_chars} 字")
    print(f"已写出：{OUT_FILE}")


if __name__ == "__main__":
    process_source_files()
