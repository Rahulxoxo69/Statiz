"""Cross-supplier part cross-referencing.

Matches parts across supplier files that are technically equivalent:
same family + compatible key attributes (within tolerance), regardless of
part numbering. Output feeds the "find substitutes" API.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

TOLERANCE = {  # fractional tolerance for numeric equivalence
    "bore_mm": 0.0, "od_mm": 0.0, "dynamic_load_kn": 0.10, "max_rpm": 0.0,
    "length_mm": 0.0, "sensing_range_mm": 0.0, "pressure_range_bar": 0.0,
}
KEY_ATTRS = ["bore_mm", "od_mm", "thread_size", "length_mm", "sensing_range_mm",
             "pressure_range_bar"]


def _num(attr: dict | None):
    if not attr:
        return None
    m = NUM_RE.search(str(attr.get("value", "")))
    return float(m.group()) if m else None


def _same_part(a: dict, b: dict) -> bool:
    fa, fb = a.get("classification") or {}, b.get("classification") or {}
    if fa.get("unspsc_code") != fb.get("unspsc_code"):
        return False
    comparable = 0
    for key in KEY_ATTRS:
        va, vb = _num(a["attributes"].get(key)), _num(b["attributes"].get(key))
        if va is None or vb is None:
            continue
        comparable += 1
        tol = TOLERANCE.get(key, 0.0)
        if tol == 0 and va != vb:
            return False
        if tol and abs(va - vb) / max(va, vb) > tol:
            return False
    if comparable == 0:  # fall back to description similarity
        return fuzz.token_sort_ratio(a.get("description", "").lower(),
                                     b.get("description", "").lower()) >= 85
    return True


def build_crossrefs(products: list[dict]) -> list[dict]:
    groups: list[list[dict]] = []
    for p in products:
        placed = False
        for g in groups:
            if _same_part(p, g[0]):
                g.append(p)
                placed = True
                break
        if not placed:
            groups.append([p])
    for g in groups:
        if len(g) > 1:
            ids = [x["part_number"] or f"{x['source_file']}#{x['row_index']}" for x in g]
            for x in g:
                x["crossrefs"] = [i for i in ids if i != (x["part_number"] or "")]
    return products


def find_substitutes(products: list[dict], part_number: str) -> list[dict]:
    me = next((p for p in products
               if p.get("part_number") and fuzz.partial_ratio(
                   part_number.lower(), p["part_number"].lower()) >= 90), None)
    if me is None:
        return []
    return [p for p in products if p is not me and _same_part(me, p)]
