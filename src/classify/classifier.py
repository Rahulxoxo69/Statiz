"""UNSPSC classification: local embedding retrieval + LLM pick with confidence.

Fallback chain (demo always works):
  1. LLM (free-tier provider) picks among top-k embedding candidates -> confidence from LLM
  2. No API key / failure -> top embedding candidate with similarity as confidence
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from ..llm import chat_json

_MODEL = None
_ST_OK = True  # sentence-transformers availability (set False if import fails)


def _model():
    """Lazy-load the embedding model; tolerate environments without it."""
    global _MODEL, _ST_OK
    if not _ST_OK:
        return None
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[classify] sentence-transformers unavailable: {e}")
            _ST_OK = False
    return _MODEL


@lru_cache(maxsize=1)
def load_taxonomy(path: str) -> tuple[list[dict], "torch.Tensor"]:
    with open(path, newline="", encoding="utf-8") as f:
        classes = list(csv.DictReader(f))
    texts = [f"{c['title']} ({c['family']})" for c in classes]
    emb = _model().encode(texts, convert_to_tensor=True, normalize_embeddings=True)
    return classes, emb


def classify(product: dict, taxonomy_path: Path, top_k: int = 5) -> dict | None:
    model = _model()
    if model is None:
        return None  # embedding backend unavailable; pipeline handles None
    classes, tax_emb = load_taxonomy(str(taxonomy_path))
    text = _product_text(product)
    if not text.strip():
        return None
    from sentence_transformers import util
    q = model.encode(text, convert_to_tensor=True, normalize_embeddings=True)
    scores = util.cos_sim(q, tax_emb)[0]
    top = scores.argsort(descending=True)[:top_k]
    candidates = []
    for idx in top.tolist():
        c = classes[idx]
        candidates.append({
            "unspsc_code": c["unspsc_code"],
            "title": c["title"],
            "family": c["family"],
            "similarity": round(float(scores[idx]), 3),
        })

    llm = chat_json(
        system="You classify industrial products into UNSPSC classes. "
               "Reply as JSON: {\"unspsc_code\": str, \"confidence\": 0-1, \"reason\": str}. "
               "Choose only from the candidates provided.",
        user=f"Product: {text}\n\nCandidates:\n"
             + "\n".join(f"- {c['unspsc_code']} {c['title']} (sim {c['similarity']})"
                         for c in candidates),
        max_tokens=300,
    )
    if llm and llm.get("unspsc_code") in {c["unspsc_code"] for c in candidates}:
        pick = next(c for c in candidates if c["unspsc_code"] == llm["unspsc_code"])
        return {
            "unspsc_code": pick["unspsc_code"],
            "title": pick["title"],
            "family": pick["family"],
            "confidence": round(min(max(float(llm.get("confidence", 0.8)), 0), 1), 2),
            "method": "embedding+LLM",
            "reason": llm.get("reason", ""),
            "candidates": candidates,
        }
    # heuristic fallback: best embedding candidate
    best = candidates[0]
    return {
        "unspsc_code": best["unspsc_code"],
        "title": best["title"],
        "family": best["family"],
        "confidence": round(min(best["similarity"] + 0.15, 0.95), 2),
        "method": "embedding",
        "reason": f"Best embedding match (sim={best['similarity']})",
        "candidates": candidates,
    }


def _product_text(p: dict) -> str:
    attrs = " ".join(f"{k}={v['value']}" for k, v in p.get("attributes", {}).items())
    return f"{p.get('description', '')} {attrs}".strip()
