"""Generate the messy industrial sample dataset for the demo.

Produces (into data/raw/ and data/taxonomy/):
  supplierA_bearings.csv     messy headers, mixed units, inline junk
  supplierB_bearings.csv     same parts, different supplier + part numbers (for crossref)
  supplierC_fasteners.xlsx   different header style again
  supplierD_sensors.csv      inconsistent casing/units
  spec_pdfs/*.pdf            generated spec sheets (one per selected part)
  ../taxonomy/unspsc_slice.csv  small UNSPSC taxonomy for grounding

Run:  python scripts/make_sample_data.py
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

random.seed(42)
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SPECS = RAW / "spec_pdfs"
TAX = ROOT / "data" / "taxonomy"
RAW.mkdir(parents=True, exist_ok=True)
SPECS.mkdir(parents=True, exist_ok=True)
TAX.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- taxonomy
TAXONOMY = [
    ("31161501", "Ball bearings", "Bearings"),
    ("31161502", "Roller bearings", "Bearings"),
    ("31161503", "Bearing units and housings", "Bearings"),
    ("31161504", "Thrust bearings", "Bearings"),
    ("31161600", "Bearing accessories", "Bearings"),
    ("31161700", "Linear motion bearings", "Bearings"),
    ("31161900", "Other bearings", "Bearings"),
    ("31171501", "Threaded fasteners Bolts", "Fasteners"),
    ("31171502", "Threaded fasteners Screws", "Fasteners"),
    ("31171503", "Threaded fasteners Nuts", "Fasteners"),
    ("31171504", "Threaded fasteners Washers", "Fasteners"),
    ("31171505", "Self-locking fasteners", "Fasteners"),
]
# keep tuples clean
TAXONOMY = [t for t in TAXONOMY if t[0]]
TAXONOMY += [
    ("31171600", "Rivets and pins", "Fasteners"),
    ("31171700", "Anchors", "Fasteners"),
    ("41113600", "Sensor multiplexers and accessories", "Sensors"),
    ("41113700", "Sensor switching apparatus", "Sensors"),
    ("41113800", "Position sensors", "Sensors"),
    ("41113900", "Pressure and temperature sensors", "Sensors"),
    ("41134100", "Motion and presence sensors", "Sensors"),
    ("41134117", "Inductive proximity sensors", "Sensors"),
    ("24111900", "Electrical power and load monitoring", "Sensors"),
    ("39121600", "Industrial control and measurement software", "Other"),
]

with open(TAX / "unspsc_slice.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["unspsc_code", "title", "family"])
    w.writerows(TAXONOMY)

# ---------------------------------------------------------------- parts
BRANDS_A = ["SKF", "FAG", "NSK", "Timken"]
BRANDS_B = ["RollTech", "AxisPro", "NordBear", "MechLine"]

def bearing(i):
    b = random.choice(["6205", "6206", "6208", "6305", "6308", "6001", "6002"])
    suffix = random.choice(["-2RS", "-Z", ""])
    d = random.choice([25, 30, 40, 52, 62])
    D = d + random.choice([10, 15, 20])
    return {
        "desc": f"Deep groove ball bearing {b}{suffix}",
        "bore_mm": d, "od_mm": D,
        "dynamic_load_kn": round(random.uniform(6.5, 35), 1),
        "max_rpm": random.choice([9000, 12000, 15000]),
        "seal": "contact seal" if "RS" in suffix else ("shield" if suffix == "-Z" else "open"),
    }

def fastener(i):
    d = random.choice(["M3", "M4", "M5", "M6", "M8", "M10"])
    L = random.choice([10, 16, 20, 25, 30, 40, 50])
    kind = random.choice(["socket head cap screw", "hex bolt", "hex nut", "flat washer"])
    grade = random.choice(["8.8", "10.9", "A2-70"])
    return {"desc": f"{kind} {d}x{L} {grade}", "dia": d, "length_mm": L, "grade": grade}

def sensor(i):
    kind = random.choice(["inductive proximity sensor", "pressure transducer", "Pt100 temperature probe"])
    if "inductive" in kind:
        return {"desc": f"{kind} M{random.choice([8,12,18])} {random.choice(['PNP','NPN'])}",
                "sensing_mm": random.choice([2, 4, 8]), "voltage": "10-30 VDC"}
    if "pressure" in kind:
        rng = random.choice([10, 16, 25])
        return {"desc": f"{kind} 0-{rng}bar",
                "range_bar": rng, "output": "4-20mA"}
    return {"desc": f"{kind} {random.choice([3, 4, 6])}-wire class A",
            "wire": random.choice([3, 4, 6]), "accuracy": "±0.15°C"}

def mkpn(prefix, cat, i):
    return f"{prefix}-{cat[:3].upper()}{i:04d}"

rows_a, rows_b, rows_c, rows_d = [], [], [], []
spec_parts = []

for i in range(40):
    p = bearing(i)
    pn_a = mkpn("BRG", "bearing", i)
    pn_b = mkpn(random.choice(BRANDS_B)[:3].upper(), "bearing", i)
    rows_a.append({"PartNo": pn_a, "Description": p["desc"],
                   "Bore (mm)": p["bore_mm"], "OD mm": p["od_mm"],
                   "C": p["dynamic_load_kn"], "Speed": f"{p['max_rpm']} rpm",
                   "SealType": p["seal"], "Price EUR": round(random.uniform(4, 60), 2)})
    # supplier B: inches for bore, comma decimal, different headers
    rows_b.append({"part_id": pn_b, "long_description": p["desc"] + " industrial grade",
                   "inner_dia_in": round(p["bore_mm"] / 25.4, 3),
                   "outer_dia_in": round(p["od_mm"] / 25.4, 3),
                   "dyn_load": str(p["dynamic_load_kn"]).replace(".", ","),
                   "max_speed_rpm": p["max_rpm"],
                   "unit_price_eur": round(random.uniform(5, 65), 2)})
    if i % 7 == 0:
        spec_parts.append((pn_a, p))

for i in range(35):
    p = fastener(i)
    rows_c.append({"ITEM": mkpn("FST", "fastener", i), "DESCR": p["desc"],
                   "Thread": p["dia"], "Len (mm)": p["length_mm"],
                   "Material/Grade": p["grade"], "Qty per box": random.choice([50, 100, 500]),
                   "€ price": round(random.uniform(0.05, 1.8), 3)})

for i in range(30):
    p = sensor(i)
    rows_d.append({"StockCode": mkpn("SNS", "sensor", i), "Name": p["desc"].title(),
                   "spec1": p.get("sensing_mm") or p.get("range_bar") or p.get("wire"),
                   "spec2": p.get("voltage") or p.get("output") or p.get("accuracy"),
                   "List Price": round(random.uniform(12, 240), 2), "MOQ": random.choice([1, 5, 10])})
    if i % 8 == 0:
        spec_parts.append((mkpn("SNS", "sensor", i), p))

def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

write_csv(RAW / "supplierA_bearings.csv", list(rows_a[0]), rows_a)
write_csv(RAW / "supplierB_bearings.csv", list(rows_b[0]), rows_b)
write_csv(RAW / "supplierD_sensors.csv", list(rows_d[0]), rows_d)

wb = Workbook(); ws = wb.active; ws.title = "Fasteners"
ws.append(list(rows_c[0].keys()))
for r in rows_c: ws.append(list(r.values()))
wb.save(RAW / "supplierC_fasteners.xlsx")

# ---------------------------------------------------------------- spec PDFs
def spec_pdf(path, partno, p):
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, h - 60, "TECHNICAL DATASHEET")
    c.setFont("Helvetica", 10)
    c.drawString(50, h - 80, f"Part No: {partno}")
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, h - 110, p["desc"])
    c.setFont("Helvetica", 10)
    y = h - 150
    c.drawString(50, y, "Product Specification")
    c.setFont("Courier", 9)
    y -= 18
    for k, v in p.items():
        if k == "desc":
            continue
        c.drawString(60, y, f"{k:<22} : {v}")
        y -= 14
    y -= 20
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, y, "All values nominal at 20C. Specifications subject to change without notice.")
    c.save()

for pn, p in spec_parts:
    spec_pdf(SPECS / f"{pn.replace(' ', '_')}_datasheet.pdf", pn, p)

print(f"Dataset written to {RAW}")
print(f"  supplierA_bearings.csv  {len(rows_a)} rows")
print(f"  supplierB_bearings.csv  {len(rows_b)} rows")
print(f"  supplierC_fasteners.xlsx {len(rows_c)} rows")
print(f"  supplierD_sensors.csv   {len(rows_d)} rows")
print(f"  spec_pdfs/              {len(spec_parts)} datasheets")
print(f"  taxonomy slice          {len(TAXONOMY)} UNSPSC classes")
