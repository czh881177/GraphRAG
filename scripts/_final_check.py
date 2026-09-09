# -*- coding: utf-8 -*-
checks = {
    "模块级 Retriever 导入": "from neo4j_graphrag.retrievers.base import Retriever",
    "TOP_K 默认5": 'RAG_TOP_K", "5"',
    "2跳检索": "r*1..2",
    "核心关系优先": '治疗", "缓解", "副作用", "研发',
    "实体锚定类": "class EntityAnchoredRetriever",
    "实体提取": "def extract_entities_for_question",
    "图谱锚定上下文": "def build_entity_anchored_context",
    "主流程接入": "EntityAnchoredRetriever(retriever, llm, driver)",
    "兼容回退": "兼容离线测试环境",
}
c = open(r"D:\project\GraphRAG\backend\api.py", encoding="utf-8").read()
for k, v in checks.items():
    print(("OK " if v in c else "MISS "), k)
