"""向量检索模块 - ChromaDB存储与检索"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.exceptions import VectorStoreError
from src.rag_generator.ingestion import DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果"""
    chunk: DocumentChunk
    similarity_score: float


class VectorRetriever:
    """向量检索器 - 使用ChromaDB"""

    def __init__(self, collection_name: str = "bid_documents"):
        try:
            import chromadb
            self.client = chromadb.Client()
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            raise VectorStoreError(f"Failed to initialize ChromaDB: {e}")

    def store(self, chunks: list[DocumentChunk]) -> None:
        """存储文档分块到ChromaDB

        Args:
            chunks: DocumentChunk列表（需含embedding）
        """
        if not chunks:
            return

        ids = [f"chunk_{i}_{hash(c.text) & 0xFFFFFFFF:08x}" for i, c in enumerate(chunks)]
        documents = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        embeddings = [c.embedding for c in chunks if c.embedding is not None]

        try:
            if embeddings and len(embeddings) == len(chunks):
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings,
                )
            else:
                # Let ChromaDB generate embeddings
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
        except Exception as e:
            raise VectorStoreError(f"Failed to store chunks: {e}")

    def retrieve(self, query: str, top_k: int = 5, threshold: float = 0.6) -> list[RetrievalResult]:
        """检索最相关的文档分块

        Args:
            query: 查询文本
            top_k: 返回最多top_k个结果
            threshold: 最低相似度阈值 (cosine similarity)

        Returns:
            相似度>=threshold的结果，按相似度降序排列

        Raises:
            VectorStoreError: ChromaDB不可用
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
            )
        except Exception as e:
            raise VectorStoreError(f"Knowledge base temporarily inaccessible: {e}")

        if not results or not results.get("documents") or not results["documents"][0]:
            return []

        retrieval_results = []
        documents = results["documents"][0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            # ChromaDB returns distance; for cosine, similarity = 1 - distance
            similarity = 1.0 - dist

            if similarity >= threshold:
                chunk = DocumentChunk(text=doc, metadata=meta or {})
                retrieval_results.append(
                    RetrievalResult(chunk=chunk, similarity_score=round(similarity, 4))
                )

        # Sort descending by similarity
        retrieval_results.sort(key=lambda r: r.similarity_score, reverse=True)
        return retrieval_results
