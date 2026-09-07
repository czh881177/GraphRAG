"""
测试问题集 - 用于评估 4 种检索器的效果
覆盖：单跳、多跳、跨实体、反向关系、比较类
"""

test_questions = [
    # ===== 单跳问题（1跳） =====
    {
        "id": "Q1",
        "category": "单跳-机制",
        "question": "阿司匹林的作用机制是什么？",
        "expected_hint": "抑制环氧合酶 / COX",
    },
    {
        "id": "Q2",
        "category": "单跳-药物列表",
        "question": "哪些药物通过抑制环氧合酶发挥作用？",
        "expected_hint": "阿司匹林、布洛芬、对乙酰氨基酚等",
    },
    {
        "id": "Q3",
        "category": "单跳-副作用",
        "question": "布洛芬有哪些副作用？",
        "expected_hint": "胃肠道不适、头痛、恶心等",
    },
    {
        "id": "Q4",
        "category": "单跳-公司",
        "question": "拜耳公司研发了哪些药物？",
        "expected_hint": "阿司匹林等",
    },
    
    # ===== 多跳问题（2跳及以上） =====
    {
        "id": "Q5",
        "category": "多跳-药物到症状",
        "question": "服用阿司匹林会引发什么症状？",
        "expected_hint": "胃肠道出血、过敏反应等",
    },
    {
        "id": "Q6",
        "category": "多跳-公司到副作用",
        "question": "拜耳公司研发的药物有哪些副作用？",
        "expected_hint": "需要联查公司→药物→副作用",
    },
    
    # ===== 反向关系问题 =====
    {
        "id": "Q7",
        "category": "反向关系",
        "question": "环氧合酶与哪些药物有关？",
        "expected_hint": "环氧合酶是作用机制节点，反向关联到药物",
    },
    
    # ===== 比较类问题 =====
    {
        "id": "Q8",
        "category": "比较类",
        "question": "对乙酰氨基酚的作用机制与布洛芬有什么不同？",
        "expected_hint": "两者作用机制不同，需要对比",
    },
    
    # ===== 跨实体复杂查询 =====
    {
        "id": "Q9",
        "category": "跨实体",
        "question": "哪些药物可以治疗头痛？",
        "expected_hint": "疾病→治疗→药物",
    },
    {
        "id": "Q10",
        "category": "跨实体",
        "question": "长期服用布洛芬有什么风险？",
        "expected_hint": "副作用或长期风险",
    },
]


def get_all_questions():
    """返回所有测试问题列表"""
    return test_questions


def get_questions_by_category(category: str):
    """按类别筛选测试问题"""
    return [q for q in test_questions if q["category"] == category]


def print_all_questions():
    """打印所有测试问题（用于人工检查）"""
    print("=" * 60)
    print("📋 测试问题清单（共 {} 个）".format(len(test_questions)))
    print("=" * 60)
    for q in test_questions:
        print(f"\n【{q['id']}】{q['category']}")
        print(f"  问题：{q['question']}")
        print(f"  预期提示：{q['expected_hint']}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_all_questions()