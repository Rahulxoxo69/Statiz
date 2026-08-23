"""FastAPI review application.

Run:  uvicorn src.app:app --reload   ->  http://127.0.0.1:8000

Endpoints
  GET  /                     review UI (single page)
  POST /api/run              re-run the full pipeline
  GET  /api/catalog          processed products (+ stats)
  GET  /api/products/{id}    single product
  POST /api/products/{id}/review   approve / correct classification
  GET  /api/substitutes/{part_number}
  GET  /api/export?format=json|csv   clean catalog export
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .crossref.matcher import find_substitutes
from .pipeline import OUT, run

app = FastAPI(title="SpecSheet → Smart Catalog", version="0.1.0")

STATIC = Path(__file__).parent / "review-ui" / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _load() -> dict:
    if not OUT.exists():
        run(verbose=False)
    return json.loads(OUT.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.post("/api/run")
def rerun():
    return run(verbose=True)["stats"]


@app.get("/api/catalog")
def catalog():
    return _load()


@app.get("/api/products/{pid}")
def product(pid: int):
    data = _load()
    if not 0 <= pid < len(data["products"]):
        raise HTTPException(404, "product not found")
    return data["products"][pid]


class ReviewDecision(BaseModel):
    decision: str  # "approve" | "reject"
    unspsc_code: str | None = None

@app.post("/api/products/{pid}/review")
def review(pid: int, body: ReviewDecision):
    data = _load()
    if not 0 <= pid < len(data["products"]):
        raise HTTPException(404, "product not found")
    p = data["products"][pid]
    p["review"] = {"decision": body.decision}
    if body.decision == "approve":
        p["review"]["confidence"] = 1.0
    if body.unspsc_code:
        p["classification"]["unspsc_code"] = body.unspsc_code
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "pid": pid, "decision": body.decision}


@app.get("/api/substitutes/{part_number}")
def substitutes(part_number: str):
    data = _load()
    subs = find_substitutes(data["products"], part_number)
    return {"query": part_number,
            "substitutes": [{"part_number": s["part_number"],
                             "source": s["source_file"],
                             "title": (s.get("classification") or {}).get("title"),
                             "price": s.get("price")} for s in subs]}


@app.get("/api/export")
def export(format: str = "json"):
    data = _load()
    approved = [p for p in data["products"] if (p.get("review") or {}).get("decision") == "approve"]
    rows = approved or data["products"]
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["part_number", "description", "unspsc_code", "unspsc_title",
                    "confidence", "attributes", "price_eur", "crossrefs", "source_file"])
        for p in rows:
            w.writerow([
                p.get("part_number"), p.get("description"),
                (p.get("classification") or {}).get("unspsc_code"),
                (p.get("classification") or {}).get("title"),
                (p.get("classification") or {}).get("confidence"),
                json.dumps({k: v["value"] for k, v in p.get("attributes", {}).items()}),
                (p.get("price") or {}).get("value"),
                ";".join(p.get("crossrefs", [])), p.get("source_file"),
            ])
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]), media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=catalog_export.csv"})
    return JSONResponse({"count": len(rows), "products": rows})
