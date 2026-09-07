"""
评估记录模板 - 用于对比 4 种检索器的效果
使用方法：跑完每种检索器后，将答案粘贴到对应位置
"""

evaluation_results = {
    "vector": {
        "Q1": {"answer": "", "score": 0, "note": ""},
        "Q2": {"answer": "", "score": 0, "note": ""},
        # ... 其他问题
    },
    "vector_cypher": {
        "Q1": {"answer": "", "score": 0, "note": ""},
        # ...
    },
    "hybrid": {
        "Q1": {"answer": "", "score": 0, "note": ""},
        # ...
    },
    "hybrid_cypher": {
        "Q1": {"answer": "", "score": 0, "note": ""},
        # ...
    },
}

def record_answer(method: str, q_id: str, answer: str, score: int = 0, note: str = ""):
    """记录某个检索器对某个问题的回答"""
    if method in evaluation_results and q_id in evaluation_results[method]:
        evaluation_results[method][q_id]["answer"] = answer
        evaluation_results[method][q_id]["score"] = score
        evaluation_results[method][q_id]["note"] = note
        print(f"✅ 已记录 {method} - {q_id}")
    else:
        print(f"❌ 无效的方法名或问题ID：{method} - {q_id}")

# 使用示例（等数据导入后，跑完检索器再填入）
# record_answer("hybrid", "Q1", "阿司匹林通过抑制COX-1和COX-2发挥作用", 4, "答案完整")