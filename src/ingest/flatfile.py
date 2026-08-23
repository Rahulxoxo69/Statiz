"""Messy flat-file ingestion: fuzzy header mapping to a canonical schema.

Canonical product record:
  {
    "source_file": str,
    "row_index": int,
    "part_number": str,
    "description": str,
    "attributes": {canonical_name: {"value": str, "unit": str|None, "source_header": str}},
    "price": {"value": float, "currency": str} | None,
  }
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import openpyxl
from rapidfuzz import fuzz, process

# canonical attribute name -> (synonyms, unit_hint)
FIELD_SYNONYMS = {
    "part_number": ["partno", "part no", "part number", "item", "item code", "stockcode",
                    "stock code", "part_id", "part id", "sku", "ref"],
    "description": ["description", "long_description", "descr", "name", "title",
                    "product name", "long description"],
    "bore_mm": ["bore (mm)", "bore mm", "bore", "inner_dia_in", "inner dia", "id mm",
                "inner diameter"],
    "od_mm": ["od mm", "od (mm)", "outer_dia_in", "outer dia", "outer diameter", "od"],
    "dynamic_load_kn": ["c", "dyn_load", "dynamic load", "c kn", "dynamic load kn"],
    "max_rpm": ["speed", "max_speed_rpm", "max rpm", "speed rpm", "rpm"],
    "seal_type": ["sealtype", "seal type", "seal", "sealing"],
    "thread_size": ["thread", "diameter", "dia", "size"],
    "length_mm": ["len (mm)", "length mm", "length", "len"],
    "grade": ["material/grade", "grade", "material grade", "material"],
    "sensing_range_mm": ["sensing_mm", "sensing range", "sensing distance"],
    "pressure_range_bar": ["range_bar", "pressure range"],
    "supply_voltage": ["voltage", "supply", "supply voltage"],
    "output_signal": ["output", "output signal"],
    "accuracy": ["accuracy"],
    "price": ["price eur", "€ price", "unit_price_eur", "unit price", "list price",
              "price", "price euro"],
}
UNIT_BY_HEADER = {"inner_dia_in": "in", "outer_dia_in": "in"}

HEADER_ALIASES = {syn: canon for canon, syns in FIELD_SYNONYMS.items() for syn in syns}

IN_TO_MM = 25.4
COMMA_DECIMAL = re.compile(r"^\d+,\d+$")


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", str(h).strip().lower())


def _read_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".xlsx":
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        headers = [_norm_header(h) for h in next(it)]
        return [dict(zip(headers, r)) for r in it]
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _map_headers(headers: list[str]) -> dict[str, str]:
    """header -> canonical name via exact alias then fuzzy match."""
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for h in headers:
        nh = _norm_header(h)
        if nh in HEADER_ALIASES and HEADER_ALIASES[nh] not in used:
            mapping[h] = HEADER_ALIASES[nh]
            used.add(HEADER_ALIASES[nh])
    for h in headers:
        if h in mapping:
            continue
        nh = _norm_header(h)
        choices = [a for a, c in HEADER_ALIASES.items() if c not in used]
        if not choices:
            break
        m = process.extractOne(nh, choices, scorer=fuzz.token_sort_ratio,
                               score_cutoff=80)
        if m:
            mapping[h] = HEADER_ALIASES[m[0]]
            used.add(HEADER_ALIASES[m[0]])
    return mapping


def _clean_value(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "n/a", "N/A"):
        return None
    if COMMA_DECIMAL.match(s):  # European decimal comma
        s = s.replace(",", ".")
    return s


def _to_float(s: str | None) -> float | None:
    if s is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def load_flat_file(path: Path) -> list[dict]:
    rows = _read_rows(path)
    if not rows:
        return []
    mapping = _map_headers(list(rows[0].keys()))
    products = []
    for i, row in enumerate(rows):
        attrs: dict[str, dict] = {}
        part_number = description = None
        price = None
        for header, canon in mapping.items():
            raw = _clean_value(row.get(header))
            if raw is None:
                continue
            if canon == "part_number":
                part_number = raw
            elif canon == "description":
                description = raw
            elif canon == "price":
                price = {"value": _to_float(raw), "currency": "EUR"}
            else:
                unit = UNIT_BY_HEADER.get(_norm_header(header))
                val = raw
                if unit == "in" and canon.endswith("_mm"):
                    v = _to_float(raw)
                    if v is not None:
                        val, unit = str(round(v * IN_TO_MM, 1)), "mm"
                attrs[canon] = {"value": val, "unit": unit, "source_header": header}
        if part_number or description:
            products.append({
                "source_file": path.name,
                "row_index": i,
                "part_number": part_number,
                "description": description or "",
                "attributes": attrs,
                "price": price,
                "classification": None,
                "enrichment": [],
                "crossrefs": [],
            })
    return products
