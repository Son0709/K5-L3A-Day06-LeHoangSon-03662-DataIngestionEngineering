"""Local multilingual embedding model (no API key, cost 0).

Model: intfloat/multilingual-e5-small, mean pooling + L2 normalisation (cosine == dot).
E5 convention: documents are prefixed with "passage: " and queries with "query: ".
The same model and prefixes are used for every strategy (A/B/C).

transformers is used directly because sentence-transformers imports scikit-learn, whose native
DLL is blocked by this machine's Application Control policy.
"""
from typing import Protocol

import torch
from transformers import AutoModel, AutoTokenizer

MODEL_NAME = "intfloat/multilingual-e5-small"
MAX_TOKENS = 512  # model limit; longer inputs are truncated and counted (see truncated_count)


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    def __init__(self, model_name: str = MODEL_NAME, batch_size: int = 16) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.truncated_count = 0
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name).eval()
        except Exception as exc:  # fail loudly; never fall back to mock vectors
            raise RuntimeError(f"Cannot load embedding model {model_name!r}: {exc}") from exc
        self.dimensions = int(self.model.config.hidden_size)

    @torch.inference_mode()
    def _embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            enc = self.tokenizer(batch, padding=True, truncation=True, max_length=MAX_TOKENS,
                                 return_tensors="pt")
            full = self.tokenizer(batch, truncation=False)["input_ids"]
            self.truncated_count += sum(len(ids) > MAX_TOKENS for ids in full)
            hidden = self.model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(1) / mask.sum(1)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            out.extend(pooled.tolist())
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([f"passage: {t}" for t in texts])

    def embed_query(self, question: str) -> list[float]:
        return self._embed([f"query: {question}"])[0]
