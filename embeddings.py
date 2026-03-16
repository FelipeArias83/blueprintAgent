"""Local deterministic embedding function (no external service required)."""

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings


class SimpleEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic character-frequency embeddings for local ChromaDB indexing."""

    def __call__(self, input: Documents) -> Embeddings:
        vectors: Embeddings = []
        for text in input:
            bins = [0.0] * 64
            for ch in text.lower():
                bins[ord(ch) % 64] += 1.0
            norm = sum(v * v for v in bins) ** 0.5 or 1.0
            vectors.append([v / norm for v in bins])
        return vectors
