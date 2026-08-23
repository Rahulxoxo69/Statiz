"""Unihack solver CLI: input CSV -> delivery-format CSV/XLSX.

Usage:
  python -m src.solve input.csv [-o output.csv|.xlsx]

Input columns are auto-detected by fuzzy name (works with any field
combination the evaluation set uses). Recognised inputs:
  MFR URL / Manufacturer URL / URL          (required-ish)
  Ref URL 1..5 / Reference URL / Doc URL    (optional)
  PART_NUMBER / SKU / Mfg_Part_Num / Mfg Part Number / UPC ... (passthrough)
Everything else in the delivery schema is enriched from the web evidence.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from rapidfuzz import fuzz, process

from .enrich.delivery_mapper import map_evidence
from .enrich.desc_parser import parse_product
from .ingest.scraper import gather_evidence
from .output.delivery import write_output, write_output_xlsx

INPUT_SYNONYMS = {
    "mfr_url": ["mfr url", "mfrurl", "manufacturer url", "manufacturerurl", "url",
                "product url", "source url", "link"],
    "ref_urls": ["ref url 1", "ref url 2", "ref url 3", "ref url 4", "ref url 5",
                 "reference url 1", "reference url", "doc url", "resource url"],
    "part_number": ["part_number", "part number", "partnumber"],
    "sku": ["sku - my_part_number", "sku", "my_part_number", "sku - my part number"],
    "mfg_part_num": ["mfg_part_num", "mfg part num", "mfg_part_number",
                     "manufacturer part number", "mpn"],
    "part_desc": ["part_desc", "part desc", "description", "short description",
                  "short_desc"],
    "part_manuf": ["part_manuf", "part manufacturer", "manufacturer"],
    "e1_brand": ["e1_brand", "e1 brand"],
    "unilog_brand": ["unilog_brand", "unilog brand"],
    "dib_brand": ["dib_brand", "dib brand"],
    "dept": ["dept", "department"], "klass": ["class"], "fine": ["fine"],
}


def _detect(headers: list[str]) -> dict[str, list[str]]:
    """Map input-file columns to canonical inputs via exact then fuzzy match."""
    found: dict[str, list[str]] = {}
    used: set[str] = set()
    for h in headers:
        nh = h.strip().lower()
        for canon, syns in INPUT_SYNONYMS.items():
            if nh in syns:
                found.setdefault(canon, []).append(h)
                used.add(h)
    for h in headers:
        if h in used:
            continue
        nh = h.strip().lower()
        flat = [(s, c) for c, syns in INPUT_SYNONYMS.items() for s in syns]
        for s, canon in flat:
            if fuzz.token_sort_ratio(nh, s) >= 85:
                found.setdefault(canon, []).append(h)
                used.add(h)
                break
    # generic URL columns not matched above -> treat as ref urls
    for h in headers:
        if h not in used and "url" in h.strip().lower():
            found.setdefault("ref_urls", []).append(h)
            used.add(h)
    return found


def solve(input_csv: Path, output: Path) -> None:
    with open(input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames or []
    mapped = _detect(headers)
    print(f"[input ] {len(rows)} rows; detected columns: "
          f"{ {k: v for k, v in mapped.items()} }")

    records = []
    for i, row in enumerate(rows, 1):
        def first(canon):
            cols = mapped.get(canon, [])
            for c in cols:
                v = (row.get(c) or "").strip()
                if v:
                    return v
            return ""
        mfr_url = first("mfr_url")
        ref_urls = [v for c in mapped.get("ref_urls", [])
                    if (v := (row.get(c) or "").strip())]
        known = {"part_number": first("part_number"), "sku": first("sku"),
                 "mfg_part_num": first("mfg_part_num"),
                 "dept": first("dept"), "klass": first("klass"), "fine": first("fine")}
        if not mfr_url:
            # description-driven enrichment (no URL available)
            rec = parse_product(first("mfg_part_num"), first("part_desc"),
                                first("part_manuf"))
            rec.update({k: v for k, v in known.items() if v and not rec.get(k)})
            e1 = first("e1_brand")
            rec["e1_brand"] = e1 if e1 and not e1.startswith("--") else None
            records.append(rec)
            n_attrs = len(rec.get("attributes", []))
            if i <= 3 or n_attrs:
                print(f"[row {i}] desc-enriched: brand={rec.get('brand_name')} "
                      f"type={rec.get('product_name')} attrs={n_attrs}")
            continue
        print(f"[row {i}] gathering evidence: {mfr_url[:70]} "
              f"(+{len(ref_urls)} refs)")
        ev = gather_evidence(mfr_url, ref_urls)
        rec = map_evidence(ev, known)
        records.append(rec)
        filled = sum(1 for v in rec.values() if v)
        print(f"[row {i}] enriched record with ~{filled} populated fields "
              f"(LLM: {rec.get('llm_used')})")

    if output.suffix.lower() == ".xlsx":
        write_output_xlsx(records, output)
    else:
        write_output(records, output)
    print(f"[output] wrote {len(records)} records -> {output} "
          f"(all 252 static headers preserved)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("output.csv"))
    args = ap.parse_args()
    solve(args.input, args.output)
