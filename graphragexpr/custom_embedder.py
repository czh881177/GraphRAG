# custom_embedder.py
"""
自定义 Embedder 封装，支持外部 Embedding + 哈希降级

包含：
- SimpleHashEmbedder：确定性哈希向量（原版，1536 维 L2 归一化），供 ExternalEmbedder 降级使用
- CustomEmbedder：外部优先 + 哈希兜底（C 的检索器使用），哈希算法与 SimpleHashEmbedder 保持一致
"""
from typing import List
import hashlib
import numpy as np


class SimpleHashEmbedder:
    """
    Simple embedder that creates deterministic embeddings from text hashing.
    This is for demonstration purposes when OpenAI embeddings are not available.
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def embed_query(self, text: str) -> list[float]:
        """Generate a simple embedding from text using hashing"""
        # Create a deterministic hash-based embedding
        # Use multiple hash functions to fill the embedding vector
        embedding = []

        for i in range(self.dimension // 16):
            # Create hash with different seeds
            hash_input = f"{text}_{i}".encode('utf-8')
            hash_obj = hashlib.sha256(hash_input)
            hash_bytes = hash_obj.digest()

            # Convert bytes to float values between -1 and 1
            for j in range(min(16, self.dimension - len(embedding))):
                if j < len(hash_bytes):
                    # Normalize to [-1, 1] range
                    val = (hash_bytes[j] / 255.0) * 2 - 1
                    embedding.append(val)

        # Fill remaining dimensions if needed
        while len(embedding) < self.dimension:
            embedding.append(0.0)

        # Normalize the vector
        embedding = np.array(embedding)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding.tolist()


class CustomEmbedder:
    """自定义 Embedder，优先使用外部 API，失败时降级为哈希"""

    def __init__(self, external, dimension: int = 1536):
        self.external = external
        self.dimension = dimension
        self._hash = SimpleHashEmbedder(dimension=dimension)

    def embed_query(self, text: str) -> List[float]:
        """对单个文本进行 embedding；external 为 None 时直接哈希（无噪音）"""
        if self.external is None:
            return self._hash.embed_query(text)
        try:
            # 尝试调用外部 API
            result = self.external.embed_query(text)
            if len(result) != self.dimension:
                # 如果维度不匹配，截断或填充
                result = self._fix_dimension(result)
            return result
        except Exception as e:
            print(f"⚠️ 外部 Embedding 失败，降级为哈希: {e}")
            return self._hash.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量 embedding"""
        return [self.embed_query(t) for t in texts]

    def _fix_dimension(self, vec: List[float]) -> List[float]:
        """修正维度不匹配"""
        if len(vec) > self.dimension:
            return vec[:self.dimension]
        else:
            # 填充 0
            return vec + [0.0] * (self.dimension - len(vec))
