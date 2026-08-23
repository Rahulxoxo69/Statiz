# SpecSheet → Smart Catalog

**AI-powered product intelligence for industrial commerce** — a hackathon prototype that turns messy supplier data into a governed, classified, cross-referenced product catalog.

Drop in messy supplier flat files (CSV/XLSX with inconsistent headers, mixed units, comma decimals) and spec-sheet PDFs. Get back a UNSPSC-classified, attribute-enriched, cross-referenced catalog — with every AI decision carrying a confidence score and every enriched attribute carrying its source, reviewed by a human before export.

## Why this exists (the gap)

Deep-dive research on ~25 incumbents (Aug 2026) found **no product combines these**:

1. **Industrial taxonomy auto-classification** — no mainstream PIM/search vendor natively classifies to UNSPSC/eCl@ss/ETIM (outsourced to niche services; Rexel on Akeneo's own page: suppliers "can't do ETIM")
2. **Datasheet-grounded enrichment** — only inRiver partially extracts from spec PDFs
3. **Cross-supplier part cross-referencing** — Partly proved it's worth $500M, but automotive-only
4. **Human-reviewable output** — Constructor/Coveo enrich their own search index, not an exportable governed catalog
5. **Self-serve deployment** — everything serious is ~$45–100K/yr with 6–12-month implementations

This prototype hits all five on a $0 budget in 8 seconds.

## Architecture

```
data/raw/                    messy inputs
  supplierA_bearings.csv       — clean-ish headers
  supplierB_bearings.csv       — inches, comma decimals, different headers
  supplierC_fasteners.xlsx     — yet another header style
  supplierD_sensors.csv        — Title-case chaos
  spec_pdfs/*.pdf              — technical datasheets
data/taxonomy/unspsc_slice.csv  — UNSPSC taxonomy slice (22 classes)
        │
        ▼
┌─────────────┐   fuzzy header mapping (rapidfuzz), unit conversion (in→mm)
│  ingest     │
└──────┬──────┘
       ▼
┌─────────────┐   PyMuPDF text + pdfplumber tables; part no + key/value specs
│  extract    │
└──────┬──────┘
       ▼
┌─────────────┐   local embeddings (MiniLM) retrieve top-k UNSPSC candidates
│  classify   │   → LLM picks w/ confidence (heuristic fallback, no API needed)
└──────┬──────┘
       ▼
┌─────────────┐   fill missing attributes from matched datasheets,
│  enrich     │   every value tagged with source (anti-hallucination)
└──────┬──────┘
       ▼
┌─────────────┐   same-family + dimension-equivalent parts matched across
│  crossref   │   suppliers (rapidfuzz + numeric tolerance)
└──────┬──────┘
       ▼
data/processed/catalog.json
       ▼
┌─────────────────────────────────────┐
│ FastAPI review console (browser)    │  approve / correct / export CSV-JSON
│ + /api/substitutes/{part_number}    │  "what can I buy instead?"
└─────────────────────────────────────┘
```

## Quickstart

```bash
cd D:\projects1\hackathon-industrial
pip install pymupdf pdfplumber rapidfuzz pandas openpyxl fastapi "uvicorn[standard]" \
            sentence-transformers python-multipart reportlab httpx

# generate the demo dataset (or replace with your own files in data/raw/)
python scripts/make_sample_data.py

# run the pipeline
python -m src.pipeline

# launch the review console
python -m uvicorn src.app:app --port 8000     # → http://127.0.0.1:8000
```

**No API key required** — classification falls back to local embeddings automatically.

### Optional: free LLM providers (better classification reasoning)

The wrapper tries providers in order; set any one (or several) as env vars:

| Provider  | Env var           | Free tier                     |
|-----------|-------------------|-------------------------------|
| Cerebras  | `CEREBRAS_API_KEY` | ~30K TPM (gpt-oss-120b)       |
| Groq      | `GROQ_API_KEY`     | fast, ~6K TPM (Llama 3.3 70B) |
| Gemini    | `GEMINI_API_KEY`   | tertiary only (tiny quota)    |

```bash
set CEREBRAS_API_KEY=...   # then re-run: python -m src.pipeline
```

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/run` | re-run full pipeline |
| `GET /api/catalog` | processed products + stats |
| `POST /api/products/{id}/review` | approve / correct classification |
| `GET /api/substitutes/{part_number}` | technically-equivalent parts across suppliers |
| `GET /api/export?format=csv\|json` | clean catalog export (approved rows first) |

## Demo script (2 minutes)

1. **Show the mess** — open `data/raw/`: four suppliers, four header styles, inches vs mm, `14,3` comma decimals, PDFs.
2. **Run live** — click "Re-run pipeline" in the console (or `python -m src.pipeline`): 145 products → classified, enriched, cross-referenced in ~8s.
3. **Show grounding** — in the table, yellow attribute chips came from datasheet PDFs; each shows its source header/file. Hover the confidence badge: method = embedding or embedding+LLM, plus the top-5 candidate classes.
4. **The payoff** — `GET /api/substitutes/BRG-BEA0000`: 7 equivalent parts across 2 suppliers with prices — buy the cheaper one.
5. **Governance** — approve a row, hit Export CSV: clean, governed, UNSPSC-coded catalog file.

## Results on the demo dataset

| Metric | Value |
|---|---|
| Products ingested (4 suppliers, 3 formats) | 145 |
| Family classification accuracy | 100% (80 Bearings / 35 Fasteners / 30 Sensors) |
| Spec PDFs parsed | 10 |
| Attributes enriched from PDFs (source-grounded) | 5 |
| Products with cross-supplier references | 116 |
| Pipeline runtime (CPU, no API key) | ~8 s |

## Limitations (honest view for judges)

- Taxonomy is a 22-class UNSPSC slice; full eCl@ss (~41K classes) needs a licensed or scraped tree — architecture is unchanged, only data.
- Cross-referencing uses attribute equivalence, not engineering-constraint validation (fit/load margins) — that's the roadmap.
- PDF OCR fallback (scanned sheets) is wired for Windows OCR but untested in the demo set.

## Project layout

```
scripts/make_sample_data.py   generates the messy demo dataset + spec PDFs
src/ingest/flatfile.py        fuzzy header mapping, unit normalisation
src/extract/pdf.py            PDF text/table extraction
src/classify/classifier.py    embedding retrieval + LLM/heuristic pick
src/enrich/extractor.py       datasheet enrichment w/ source spans
src/crossref/matcher.py       cross-supplier equivalence + substitute search
src/llm/provider.py           multi-provider free-tier LLM wrapper
src/pipeline.py               orchestrator
src/app.py                    FastAPI review console
```
