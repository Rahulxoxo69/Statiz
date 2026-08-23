"""Delivery-format schema: loads the 252 static headers and writes populated
CSV/XLSX outputs. Headers are never modified, removed or renamed.

Internal enrichment records use a small canonical dict; `flatten()` maps it
onto the delivery headers.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEADERS_FILE = ROOT / "data" / "delivery" / "delivery_headers.csv"

# canonical record -> delivery header (1:1 targets)
SIMPLE_MAP = {
    "mfr_url": "MFR URL",
    "part_number": "PART_NUMBER",
    "dept": "Dept",
    "klass": "Class",
    "fine": "Fine",
    "sku": "SKU - MY_PART_NUMBER",
    "mfg_part_num": "Mfg_Part_Num",
    "part_desc": "Part_Desc",
    "e1_brand": "E1_Brand",
    "unilog_brand": "Unilog_Brand",
    "dib_brand": "DIB_Brand",
    "part_manuf": "Part_Manuf",
    "manufacturer_name": "MANUFACTURER_NAME",
    "brand_name": "BRAND_NAME",
    "trade_name": "TRADE_NAME",
    "manufacturer_part_number": "MANUFACTURER_PART_NUMBER",
    "alternate_part_number": "ALTERNATE_PART_NUMBER",
    "classpath": "Classpath",
    "mobile_desc": "MOBILE_DESC",
    "invoice_desc": "INVOICE_DESC",
    "short_desc": "SHORT_DESC",
    "long_desc": "LONG_DESC1",
    "retail_desc": "RETAIL_DESC",
    "marketing_description": "MARKETING_DESCRIPTION",
    "with": "With",
    "standard_approvals": "Standard/Approvals",
    "prop65": "Prop 65",
    "application": "Application",
    "includes": "Includes",
    "product_name": "Product Name",
    "upc": "UPC",
    "ean": "EAN",
    "gtin": "GTIN",
    "unspsc": "UNSPSC",
    "warranty": "Warranty",
    "list_price": "List Price",
    "selling_qty": "Selling Qty",
    "selling_uom": "Selling UOM",
    "standard_packaging": "Standard Packaging Information",
    "length": "LENGTH",
    "length_uom": "LENGTH_UOM",
    "height": "HEIGHT",
    "height_uom": "HEIGHT_UOM",
    "width": "WIDTH",
    "width_uom": "WIDTH_UOM",
    "weight": "WEIGHT",
    "weight_uom": "WEIGHT_UOM",
    "volume": "VOLUME",
    "volume_uom": "VOLUME_UOM",
    "product_image": "Product Image",
    "country_of_origin": "Country Of Origin",
    "discontinued": "Discontinued",
    "actual_image": "Actual Image (Yes/No)",
}


def load_headers() -> list[str]:
    with open(HEADERS_FILE, newline="", encoding="utf-8") as f:
        return next(csv.reader(f))


def flatten(rec: dict) -> dict[str, str]:
    """Map canonical enrichment record -> {delivery_header: value}."""
    out: dict[str, str] = {}
    for key, header in SIMPLE_MAP.items():
        v = rec.get(key)
        if v is not None and str(v).strip() != "":
            out[header] = str(v)
    # reference URLs
    for i, url in enumerate(rec.get("ref_urls", [])[:5], 1):
        out[f"Ref URL {i}"] = url
    # item features 1..20
    for i, feat in enumerate(rec.get("features", [])[:20], 1):
        out[f"ITEM_FEATURES_{i}"] = feat
    # attribute triplets 1..50
    for i, attr in enumerate(rec.get("attributes", [])[:50], 1):
        label, value, uom = (attr + ["", "", ""])[:3] if isinstance(attr, list) else (
            attr.get("label", ""), attr.get("value", ""), attr.get("uom", ""))
        out[f"ATTRIBUTE_LABEL {i}"] = label
        out[f"ATTRIBUTE_VALUE {i}"] = value
        out[f"ATTRIBUTE_UOM {i}"] = uom
    # alternate images 1..4 + videos
    for i, url in enumerate(rec.get("alt_images", [])[:4], 1):
        out[f"Alternate Image {i}"] = url
    for i, url in enumerate(rec.get("videos", [])[:2], 1):
        out["Video Link" if i == 1 else f"Video Link {i}"] = url
    # document links by canonical doc type
    DOC_MAP = {
        "sds": "SDS", "sds1": "SDS_1", "catalog": "Catalog",
        "spec_sheet": "Specification Sheet",
        "installation_manual": "Instruction/Installation Manual",
        "service_manual": "Service Manual", "user_manual": "Owners/User Manual",
        "line_drawing": "Line Drawing", "mtr": "MTR", "rohs": "RoHS",
        "engineering_drawing": "Full Engineering Drawing",
        "energy_guide": "Energy Star Guide", "tech_bulletin": "Technical Bulletin",
        "submittal": "Submittal", "compatibility_chart": "Compatibility Chart",
        "size_chart": "Size Chart", "label_insert": "Product Label/Insert",
        "warranty_info": "Warranty Information",
    }
    for key, header in DOC_MAP.items():
        v = rec.get(key)
        if v:
            out[header] = v
    return out


def write_output(records: list[dict], out_path: Path) -> Path:
    headers = load_headers()
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for rec in records:
            flat = flatten(rec)
            w.writerow([flat.get(h, "") for h in headers])
    return out_path


def write_output_xlsx(records: list[dict], out_path: Path) -> Path:
    import openpyxl
    headers = load_headers()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Output"
    ws.append(headers)
    for rec in records:
        flat = flatten(rec)
        ws.append([flat.get(h, "") for h in headers])
    wb.save(out_path)
    return out_path
