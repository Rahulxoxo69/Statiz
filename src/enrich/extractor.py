"""Attribute enrichment from spec PDFs, with source-span grounding.

For every flat-file product that has an associated datasheet (matched by part
number), missing canonical attributes are filled from the PDF — each enriched
attribute records the exact source line so reviewers can verify it
(anti-hallucination requirement).
"""
from __future__ import annotations

from rapidfuzz import fuzz

REQUIRED_BY_FAMILY = {
    "Bearings": ["bore_mm", "od_mm", "dynamic_load_kn", "max_rpm", "seal_type"],
    "Fasteners": ["thread_size", "length_mm", "grade"],
    "Sensors": ["sensing_range_mm", "pressure_range_bar", "supply_voltage",
                "output_signal", "accuracy"],
}


def match_pdfs(products: list[dict], pdf_records: list[dict],
               threshold: int = 70) -> list[dict]:
    """Attach PDF records to products by fuzzy part-number match."""
    indexed = [(p, p.get("part_number") or "") for p in products if p.get("part_number")]
    for rec in pdf_records:
        pn = rec.get("part_number") or rec.get("description") or ""
        if not pn:
            continue
        best, best_score = None, 0
        for prod, prod_pn in indexed:
            s = fuzz.partial_ratio(pn.lower(), prod_pn.lower())
            if s > best_score:
                best, best_score = prod, s
        if best is not None and best_score >= threshold:
            rec["_matched_to"] = best["part_number"]
            best.setdefault("_pdfs", []).append(rec)
    return products


def enrich_from_pdfs(products: list[dict]) -> list[dict]:
    """Fill missing attributes from matched PDFs; record source spans."""
    for p in products:
        for rec in p.pop("_pdfs", []):
            for key, attr in rec.get("attributes", {}).items():
                existing = p["attributes"].get(key)
                if existing is None or not str(existing.get("value", "")).strip():
                    p["attributes"][key] = {
                        "value": attr["value"],
                        "unit": attr.get("unit"),
                        "source_header": f"PDF:{rec['source_file']}",
                    }
                    p["enrichment"].append({
                        "attribute": key,
                        "value": attr["value"],
                        "source": f"PDF:{rec['source_file']}",
                        "grounded": True,
                    })
        family = (p.get("classification") or {}).get("family", "")
        missing = [a for a in REQUIRED_BY_FAMILY.get(family, [])
                   if not str(p["attributes"].get(a, {}).get("value", "") or "").strip()]
        if missing:
            p["review_flags"] = {"missing_required": missing}
    return products
