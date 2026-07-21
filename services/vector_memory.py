"""
Persistent Vector Memory Store.
Provides semantic vector search, document indexing, and persistent historical memory storage.
"""
import os
import json
import math
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

VECTOR_STORE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vector_store.json")


class MemoryDocument(BaseModel):
    doc_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    vector: Optional[List[float]] = None


class SearchResult(BaseModel):
    doc_id: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any]


from adk.logging import Redactor


class PersistentVectorMemoryBank:
    """Vector database storing semantic embeddings for meal history, preferences, and reports."""

    def __init__(self, storage_path: str = VECTOR_STORE_FILE):
        self.storage_path = storage_path
        self.documents: Dict[str, MemoryDocument] = {}
        self._load_memory()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def _load_memory(self):
        self._ensure_dir()
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self.documents[k] = MemoryDocument(**v)
            except Exception:
                self.documents = {}

    def save_memory(self):
        self._ensure_dir()
        serialized = {k: doc.model_dump() for k, doc in self.documents.items()}
        scrubbed = Redactor.scrub_dict(serialized)
        with open(self.storage_path, "w") as f:
            json.dump(scrubbed, f, indent=2)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def _compute_vector(self, text: str) -> Dict[str, float]:
        """Computes normalized term frequency vector for text."""
        tokens = self._tokenize(text)
        if not tokens:
            return {}
        counts: Dict[str, float] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0.0) + 1.0
        
        # L2 norm
        norm = math.sqrt(sum(v * v for v in counts.values()))
        if norm > 0:
            for k in counts:
                counts[k] /= norm
        return counts

    @staticmethod
    def _cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculates cosine similarity between two sparse term vectors."""
        score = 0.0
        for term, val in vec1.items():
            if term in vec2:
                score += val * vec2[term]
        return score

    def add_document(self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Indexes a document into vector memory bank after scrubbing PII."""
        scrubbed_content = Redactor.scrub_text(content)
        scrubbed_metadata = Redactor.scrub_dict(metadata or {})
        
        doc = MemoryDocument(
            doc_id=doc_id,
            content=scrubbed_content,
            metadata=scrubbed_metadata,
        )
        self.documents[doc_id] = doc
        self.save_memory()

    def search_similar(self, query: str, top_k: int = 3, filter_category: Optional[str] = None) -> List[SearchResult]:
        """Performs semantic similarity search over vector store."""
        query_vec = self._compute_vector(query)
        if not query_vec:
            return []

        results: List[SearchResult] = []
        for doc_id, doc in self.documents.items():
            if filter_category and doc.metadata.get("category") != filter_category:
                continue

            doc_vec = self._compute_vector(doc.content)
            sim = self._cosine_similarity(query_vec, doc_vec)
            
            if sim > 0.05:
                results.append(SearchResult(
                    doc_id=doc_id,
                    content=doc.content,
                    similarity_score=round(sim, 4),
                    metadata=doc.metadata,
                ))

        # Sort descending by similarity
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:top_k]
