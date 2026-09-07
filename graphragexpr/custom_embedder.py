"""
自定义 Embedder 封装，支持外部 Embedding + 哈希降级
"""
from typing import List
import hashlib
import numpy as np


class CustomEmbedder:
    """自定义 Embedder，优先使用外部 API，失败时降级为哈希"""

    def __init__(self, external, dimension: int = 1536):
        self.external = external
        self.dimension = dimension

    def embed_query(self, text: str) -> List[float]:
        """对单个文本进行 embedding"""
        try:
            # 尝试调用外部 API
            result = self.external.embed_query(text)
            if len(result) != self.dimension:
                # 如果维度不匹配，截断或填充
                result = self._fix_dimension(result)
            return result
        except Exception as e:
            print(f"⚠️ 外部 Embedding 失败，降级为哈希: {e}")
            return self._hash_embed(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量 embedding"""
        return [self.embed_query(t) for t in texts]

    def _hash_embed(self, text: str) -> List[float]:
        """哈希降级方案（固定维度）"""
        h = hashlib.sha256(text.encode()).digest()
        # 将哈希值映射到 [-1, 1] 范围
        arr = np.frombuffer(h, dtype=np.uint8).astype(np.float32) / 127.5 - 1.0
        # 如果长度不够，用重复或填充
        if len(arr) < self.dimension:
            arr = np.pad(arr, (0, self.dimension - len(arr)), mode='wrap')
        else:
            arr = arr[:self.dimension]
        return arr.tolist()

    def _fix_dimension(self, vec: List[float]) -> List[float]:
        """修正维度不匹配"""
        if len(vec) > self.dimension:
            return vec[:self.dimension]
        else:
            # 填充 0
            return vec + [0.0] * (self.dimension - len(vec))