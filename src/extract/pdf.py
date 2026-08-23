"""Spec-sheet PDF extraction: text + key/value table pairs.

Produces records shaped like flat-file products so the same downstream
(classify/enrich) applies:
  {"source_file", "row_index": 0, "part_number", "description", "attributes", "price"}
"""
from __future__ import annotations

import re
from pathlib import Path

import pymupdf
import pdfplumber

DESC_RE = re.compile(r"Part\s*No\s*[:.]?\s*(\S+)", re.I)
KV_RE = re.compile(r"^\s*([A-Za-z_][\w /%()\[\]-]{1,30}?)\s*[:=]\s*(.+?)\s*$")
TITLE_KEYS = {"bore_mm", "od_mm", "dynamic_load_kn", "max_rpm", "seal_type",
              "thread_size", "length_mm", "grade", "sensing_range_mm",
              "pressure_range_bar", "supply_voltage", "output_signal", "accuracy"}
TITLE_RE = re.compile(r"\b(bearing|screw|bolt|nut|washer|sensor|probe|transducer)\b", re.I)


def extract_pdf(path: Path) -> dict | None:
    """Extract part number, title/description and key-value spec pairs."""
    kv: list[tuple[str, str]] = {}
    text = ""
    with pymupdf.open(path) as doc:
        text = "\n".join(page.get_text() for page in doc)
    if len(text.strip()) < 20:  # likely scanned -> table extraction as fallback
        with pdfplumber.open(path) as pdf:
            text = "\n".join(
                (cell or "") + "\n"
                for page in pdf.pages
                for row in (page.extract_table() or [])
                for cell in row
            )

    part_number = None
    desc = None
    for line in text.splitlines():
        if part_number is None:
            m = DESC_RE.search(line)
            if m:
                part_number = m.group(1).strip()
                continue
        m = KV_RE.match(line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            canon = _canon_key(key)
            if canon:
                kv[canon] = val
        elif desc is None and TITLE_RE.search(line) and len(line.strip()) > 8:
            desc = line.strip()
    if part_number is None and desc is None and not kv:
        return None

    # Fallback: pull any table rows via pdfplumber for detail pages
    if not kv:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                for row in (page.extract_table() or []):
                    if row and len(row) >= 2 and row[0] and row[1]:
                        canon = _canon_key(str(row[0]))
                        if canon and canon not in kv:
                            kv[canon] = str(row[1]).strip()

    attributes = {k: {"value": v, "unit": "mm" if k.endswith("_mm") else None,
                      "source_header": f"{path.name}#kv"}
                  for k, v in kv.items()}
    return {
        "source_file": path.name,
        "row_index": 0,
        "part_number": part_number,
        "description": desc or (kv.pop("_title", "") or ""),
        "attributes": attributes,
        "price": None,
        "classification": None,
        "enrichment": [],
        "crossrefs": [],
    }


def _canon_key(key: str) -> str | None:
    k = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
    aliases = {
        "bore_mm": "bore_mm", "inner_dia": "bore_mm", "inner_diameter": "bore_mm",
        "od_mm": "od_mm", "outer_dia": "od_mm", "outer_diameter": "od_mm",
        "dynamic_load_kn": "dynamic_load_kn", "c": "dynamic_load_kn",
        "max_rpm": "max_rpm", "speed": "max_rpm", "max_speed_rpm": "max_rpm",
        "seal": "seal_type", "seal_type": "seal_type",
        "thread": "thread_size", "dia": "thread_size",
        "length_mm": "length_mm", "len": "length_mm",
        "grade": "grade", "material_grade": "grade",
        "sensing_mm": "sensing_range_mm", "sensing_range": "sensing_range_mm",
        "range_bar": "pressure_range_bar",
        "voltage": "supply_voltage", "output": "output_signal",
        "accuracy": "accuracy",
    }
    return aliases.get(k)


def extract_pdf_dir(dirpath: Path) -> list[dict]:
    out = []
    for p in sorted(dirpath.glob("*.pdf")):
        try:
            rec = extract_pdf(p)
            if rec:
                rec["_pdf_text"] = _first_page_text(p)
                out.append(rec)
        except Exception as e:  # tolerate a bad PDF in the batch
            print(f"  [warn] failed to parse {p.name}: {e}")
    return out


def _first_page_text(path: Path) -> str:
    with pymupdf.open(path) as doc:
        return doc[0].get_text()[:2000]
