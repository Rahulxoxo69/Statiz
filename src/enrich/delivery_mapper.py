"""Evidence -> delivery-record mapper.

Strategy:
  1. Heuristic pass: JSON-LD Product schema + meta tags (always runs, works
     offline, no API key) — brand, name, description, image, price, GTIN/MPN.
  2. LLM pass (free-tier provider if key set): derives descriptions, features,
     attribute triplets, dims, taxonomy (Dept/Class/Fine + UNSPSC) from the
     combined page text + reference-document text, grounded to the evidence.
Both passes merge; LLM values never overwrite a solid JSON-LD fact.
"""
from __future__ import annotations

import re

from ..llm import chat_json

LLM_SYSTEM = """You are an industrial/e-commerce catalog enrichment engine. From the
manufacturer page content and reference documents provided, produce ONE JSON object:
{
 "part_desc": "terse invoice-style description (brand + product + key specs, ALL-CAPS abbreviations ok)",
 "manufacturer_name": "", "brand_name": "", "trade_name": "",
 "dept": "", "class": "", "fine": "",
 "classpath": "Dept>Class>Fine using '>' separators",
 "mobile_desc": "brand + product + series + model, comma separated",
 "short_desc": "one-line product descriptor",
 "retail_desc": "short retail-friendly line",
 "long_desc": "rich paragraph with all key specs and features from the source",
 "marketing_description": "benefit-oriented marketing copy grounded in the source",
 "features": ["up to 20 short feature phrases"],
 "attributes": [{"label":"", "value":"", "uom":""}],
 "standard_approvals": "pipe-separated certifications found",
 "with": "key included capability phrase",
 "includes": "what's in the box",
 "product_name": "category noun, e.g. Dishwasher",
 "warranty": "", "list_price": "", "country_of_origin": "",
 "length":"", "length_uom":"", "height":"", "height_uom":"",
 "width":"", "width_uom":"", "weight":"", "weight_uom":"",
 "unspsc": "UNSPSC commodity code if determinable else empty",
 "documents": {"spec_sheet":"", "user_manual":"", "installation_manual":""}
}
Rules: use ONLY facts present in the provided content; leave unknown fields empty;
never invent certifications, numbers or part numbers. UOM only when the value is numeric
(e.g. {"label":"Voltage Rating","value":"120","uom":"V"})."""


def map_evidence(evidence: dict, known: dict) -> dict:
    """known = passthrough input fields (sku, mfg_part_num, part_number...)."""
    rec = dict(known)
    rec["mfr_url"] = evidence.get("mfr_url", "")
    heur = _heuristic(evidence)
    for k, v in heur.items():
        if v and not rec.get(k):
            rec[k] = v
    rec["ref_urls"] = [d["url"] for d in evidence.get("docs", [])][:5]

    llm = chat_json(LLM_SYSTEM, _evidence_text(evidence, known), max_tokens=3000)
    if llm:
        for k, v in llm.items():
            if k in ("features", "attributes", "documents") or (v and not rec.get(k)):
                rec[k] = v
        rec["llm_used"] = True
    else:
        rec.setdefault("features", _fallback_features(evidence))
        rec["llm_used"] = False
    return rec


def _heuristic(ev: dict) -> dict:
    p = ev.get("html_parsed", {})
    out: dict = {}
    prod = _find_product(p.get("jsonld", []))
    if prod:
        brand = prod.get("brand") or {}
        if isinstance(brand, dict):
            brand = brand.get("name", "")
        if brand:
            out["brand_name"] = out["trade_name"] = str(brand)
        if prod.get("name"):
            out["mobile_desc"] = str(prod["name"])
        if prod.get("description"):
            out["long_desc"] = str(prod["description"])[:900]
        imgs = prod.get("image")
        if isinstance(imgs, list) and imgs:
            out["product_image"] = imgs[0]
        elif isinstance(imgs, str):
            out["product_image"] = imgs
        offers = prod.get("offers") or {}
        if isinstance(offers, dict) and offers.get("price"):
            out["list_price"] = str(offers["price"])
        for gid in ("gtin13", "gtin12", "gtin"):
            if prod.get(gid):
                out["gtin"] = str(prod[gid]); break
        if prod.get("mpn"):
            out["manufacturer_part_number"] = str(prod["mpn"])
        if prod.get("sku") and not out.get("mobile_desc"):
            out["mobile_desc"] = str(prod["sku"])
    meta = p.get("meta", {})
    if meta.get("og:title") and not out.get("mobile_desc"):
        out["mobile_desc"] = meta["og:title"]
    if meta.get("description") and not out.get("long_desc"):
        out["long_desc"] = meta["description"]
    if meta.get("og:image") and not out.get("product_image"):
        out["product_image"] = meta["og:image"]
    if not out.get("product_image") and p.get("images"):
        out["product_image"] = p["images"][0]
    if not out.get("brand_name") and meta.get("og:site_name"):
        out["brand_name"] = meta["og:site_name"]
    return out


def _find_product(nodes: list) -> dict:
    for n in nodes:
        if isinstance(n, dict) and n.get("@type") in ("Product", ["Product"]):
            return n
        if isinstance(n, dict):
            for v in n.values():
                if isinstance(v, list):
                    found = _find_product(v)
                    if found:
                        return found
    return {}


def _evidence_text(ev: dict, known: dict) -> str:
    p = ev.get("html_parsed", {})
    parts = [f"Page title: {p.get('title','')}",
             f"Meta: {p.get('meta',{})}",
             f"Page text: {ev.get('raw_text','')[:5000]}"]
    for d in ev.get("docs", [])[:4]:
        parts.append(f"Document {d['url']}:\n{d['text'][:3000]}")
    if known.get("mfg_part_num"):
        parts.append(f"Known part number: {known['mfg_part_num']}")
    return "\n\n".join(parts)[:16000]


def _fallback_features(ev: dict) -> list[str]:
    text = ev.get("raw_text", "")
    feats = [s.strip(" .•-") for s in re.split(r"[.•\n]", text) if 20 < len(s.strip()) < 90]
    return feats[:12]
