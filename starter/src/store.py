"""Persistent vector store: ChromaDB (local, on disk), cosine distance.

One collection per strategy: lab_A and lab_B. Strategy C searches lab_B with a metadata filter.
Chroma uses an approximate HNSW index (not exact search) - noted in the report.
"""
import sys
import types
from pathlib import Path
from typing import Any

try:
    import grpc  # noqa: F401
except ImportError:
    # This machine's Application Control policy blocks grpc's native DLL, which chromadb only
    # needs for its optional OpenTelemetry exporter. Stub that one module; storage/search are
    # unaffected. Without the stub, chromadb cannot be imported at all.
    _stub = types.ModuleType("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")
    _stub.OTLPSpanExporter = object
    sys.modules[_stub.__name__] = _stub

import chromadb

from .models import Chunk

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "results" / "chroma"


def _clean(meta: dict[str, Any]) -> dict[str, Any]:
    """Chroma metadata accepts str/int/float/bool only; drop None values."""
    return {k: v for k, v in meta.items() if v is not None}


class ChromaStore:
    def __init__(self, path: Path = DEFAULT_PATH, dimensions: int | None = None) -> None:
        self.path = Path(path)
        self.dimensions = dimensions
        self.client = chromadb.PersistentClient(
            path=str(self.path), settings=chromadb.Settings(anonymized_telemetry=False))

    def _col(self, strategy: str):
        return self.client.get_or_create_collection(
            f"lab_{strategy}", configuration={"hnsw": {"space": "cosine"}})

    def create_schema(self, strategies=("A", "B")) -> None:
        for s in strategies:
            self._col(s)

    def count(self, strategy: str) -> int:
        return self._col(strategy).count()

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> dict:
        """Write stable IDs (re-running never duplicates) and delete chunks that no longer exist."""
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        if self.dimensions and any(len(v) != self.dimensions for v in vectors):
            raise ValueError(f"vector dimension != {self.dimensions}")
        col = self._col(strategy)
        new_ids = [c.chunk_id for c in chunks]
        if len(set(new_ids)) != len(new_ids):
            raise ValueError("duplicate chunk ids in input")
        stale = sorted(set(col.get(include=[])["ids"]) - set(new_ids))
        if stale:
            col.delete(ids=stale)
        base = [{"document_id": c.document_id, "source": c.source, "page": c.page} for c in chunks]
        col.upsert(
            ids=new_ids, embeddings=vectors, documents=[c.text for c in chunks],
            metadatas=[_clean({**b, **c.metadata}) for b, c in zip(base, chunks)])
        return {"upserted": len(new_ids), "deleted_stale": len(stale), "count": col.count()}

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        where = None
        if filters:
            items = [{k: v} for k, v in filters.items()]
            where = items[0] if len(items) == 1 else {"$and": items}
        res = self._col(strategy).query(
            query_embeddings=[query_vector], n_results=top_k, where=where,
            include=["documents", "metadatas", "distances"])
        return [
            {"chunk_id": cid, "text": doc, "score": 1.0 - dist, "metadata": meta}
            for cid, doc, meta, dist in zip(
                res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])
        ]
