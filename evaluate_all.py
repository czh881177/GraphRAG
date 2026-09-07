import subprocess
import re
import sys
from pathlib import Path

# 10 个评估问题
questions = [
    "阿司匹林的作用机制是什么？",
    "哪些药物通过抑制环氧合酶发挥作用？",
    "布洛芬有哪些副作用？",
    "拜耳公司研发了哪些药物？",
    "服用阿司匹林会引发什么症状？",
    "拜耳公司研发的药物有哪些副作用？",
    "环氧合酶与哪些药物有关？",
    "对乙酰氨基酚的作用机制与布洛芬有什么不同？",
    "哪些药物可以治疗头痛？",
    "长期服用布洛芬有什么风险？"
]

# 4 个检索器
retrievers = ["rag_vector", "rag_graph", "rag_hybrid", "rag_hybrid_cypher"]

# 存储结果
results = {r: [] for r in retrievers}

print("\n" + "="*80)
print("🔬 开始自动评估 4 个检索器 × 10 个问题")
print("="*80)

for retriever in retrievers:
    print(f"\n▶ 正在测试 {retriever}.py ...")
    script_path = Path("graphragexpr/extract") / f"{retriever}.py"
    
    for idx, question in enumerate(questions, 1):
        print(f"  问题 {idx}: {question[:20]}...", end="", flush=True)
        try:
            # 启动子进程，通过管道发送输入
            p = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=Path.cwd()
            )
            # 发送问题，然后发送 exit
            out, err = p.communicate(input=f"{question}\nexit\n", timeout=60)
            
            # 从输出中提取答案（匹配 “答案：content='...'” 或 “答案：...”）
            match = re.search(r"答案：content='([^']*)'", out)
            if not match:
                # 尝试更宽松的匹配
                match = re.search(r"答案：(.*?)(?=\n|$)", out)
            answer = match.group(1).strip() if match else "未解析"
            results[retriever].append(answer)
            print(f" ✅ 完成")
        except Exception as e:
            results[retriever].append(f"错误: {str(e)[:50]}")
            print(f" ❌ 失败")

# 打印汇总表格
print("\n" + "="*80)
print("📊 评估结果汇总表")
print("="*80)
print(f"\n{'问题':<30} | {'vector':<20} | {'graph':<20} | {'hybrid':<20} | {'hybrid_cypher':<20}")
print("-"*120)
for i, q in enumerate(questions):
    row = f"{q[:28]:<30} | "
    for r in retrievers:
        ans = results[r][i] if i < len(results[r]) else "无"
        row += f"{ans[:18]:<20} | "
    print(row)

print("\n" + "="*80)
print("✅ 评估完成！")