"""End-to-end pipeline orchestrator.

Run:  python -m src.pipeline            (processes data/raw -> data/processed/catalog.json)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .classify.classifier import classify
from .crossref.matcher import build_crossrefs
from .enrich.extractor import enrich_from_pdfs, match_pdfs
from .extract.pdf import extract_pdf_dir
from .ingest.flatfile import load_flat_file
from .llm import available_providers

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TAXONOMY = ROOT / "data" / "taxonomy" / "unspsc_slice.csv"
OUT = ROOT / "data" / "processed" / "catalog.json"


def run(verbose: bool = True) -> dict:
    t0 = time.time()
    log = print if verbose else (lambda *a, **k: None)

    # 1. ingest flat files
    products: list[dict] = []
    for f in sorted(RAW.iterdir()):
        if f.suffix.lower() in (".csv", ".xlsx"):
            rows = load_flat_file(f)
            log(f"[ingest ] {f.name}: {len(rows)} products")
            products.extend(rows)

    # 2. extract spec PDFs
    pdfs = extract_pdf_dir(RAW / "spec_pdfs")
    log(f"[extract] {len(pdfs)} spec PDFs parsed")

    # 3. classify against UNSPSC slice
    providers = available_providers()
    log(f"[classify] LLM providers available: {providers or 'none — using local embeddings only'}")
    for p in products:
        p["classification"] = classify(p, TAXONOMY)
    for rec in pdfs:
        rec["classification"] = classify(rec, TAXONOMY)
    fam_count: dict[str, int] = {}
    for p in products:
        fam = (p["classification"] or {}).get("family", "?")
        fam_count[fam] = fam_count.get(fam, 0) + 1
    log(f"[classify] families: {fam_count}")

    # 4. enrich from matched PDFs
    products = match_pdfs(products, pdfs)
    # classification for enrichment must run before enrich (family needed) — done above
    products = enrich_from_pdfs(products)
    n_enriched = sum(len(p["enrichment"]) for p in products)
    log(f"[enrich ] {n_enriched} attributes filled from datasheets (source-grounded)")

    # 5. cross-reference
    products = build_crossrefs(products)
    n_ref = sum(1 for p in products if p["crossrefs"])
    log(f"[crossref] {n_ref} products have cross-supplier references")

    # 6. persist
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stats": {
            "products": len(products),
            "pdfs": len(pdfs),
            "enriched_attributes": n_enriched,
            "cross_referenced": n_ref,
            "llm_providers": providers,
            "elapsed_sec": round(time.time() - t0, 1),
        },
        "products": products,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"[done   ] {len(products)} products -> {OUT} ({payload['stats']['elapsed_sec']}s)")
    return payload


if __name__ == "__main__":
    run()
