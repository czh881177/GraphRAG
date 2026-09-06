# external_embedder.py
"""
External embedding model support using OpenAI-compatible API
"""
import os
from openai import OpenAI
from neo4j_graphrag.embeddings.base import Embedder
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ExternalEmbedder(Embedder):
    """
    Embedder that uses external embedding API (OpenAI-compatible)
    Falls back to hash-based embedder if not configured
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self.endpoint = os.getenv("EMBED_ENDPOINT")
        self.model = os.getenv("EMBED_MODEL")
        self.token = os.getenv("EMBED_TOKEN")

        # Check if external embedding is configured
        self.use_external = bool(self.endpoint and self.model and self.token)

        if self.use_external:
            self.client = OpenAI(
                api_key=self.token,
                base_url=self.endpoint
            )
            print(f"✓ Using external embedding model: {self.model}")
        else:
            print("⚠ External embedding not configured, using hash-based embedder")
            # Import hash embedder as fallback
            from custom_embedder import SimpleHashEmbedder
            self.fallback = SimpleHashEmbedder(dimension=dimension)

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding using external API or fallback"""
        if self.use_external:
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=text
                )
                embedding = response.data[0].embedding

                # Verify dimension
                if len(embedding) != self.dimension:
                    print(f"⚠ Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}")
                    # Pad or truncate if needed
                    if len(embedding) < self.dimension:
                        embedding.extend([0.0] * (self.dimension - len(embedding)))
                    else:
                        embedding = embedding[:self.dimension]

                return embedding
            except Exception as e:
                print(f"⚠ External embedding failed: {e}, falling back to hash embedder")
                if hasattr(self, 'fallback'):
                    return self.fallback.embed_query(text)
                else:
                    from custom_embedder import SimpleHashEmbedder
                    self.fallback = SimpleHashEmbedder(dimension=self.dimension)
                    return self.fallback.embed_query(text)
        else:
            return self.fallback.embed_query(text)
