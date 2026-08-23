# Solution Overview — Statiz

**Problem.** Industrial/e-commerce distributors receive product data as messy supplier flat files (inconsistent headers, mixed units, comma decimals) and unstructured spec-sheet PDFs — and need it as a governed, classified, enriched catalog. No mainstream tool auto-classifies to industrial taxonomies (UNSPSC/eCl@ss/ETIM), almost none extract datasheet content, and everything serious costs $45–100K/yr with 6–12-month implementations. Rexel — on Akeneo's own customer page — admits suppliers "can't do ETIM."

**Solution.** A five-stage dynamic pipeline that turns messy inputs into a governed catalog, with every AI decision carrying evidence:

1. **Ingest** — fuzzy header mapping (RapidFuzz) maps any supplier's column names onto a canonical schema; handles inches→mm, decimal commas, CSV/XLSX and manufacturer URLs.
2. **Extract** — PyMuPDF + pdfplumber parse spec-sheet PDFs into part numbers and key/value spec tables.
3. **Classify** — local sentence-transformer embeddings retrieve top-k UNSPSC candidates; a free-tier LLM (Cerebras/Groq/Gemini wrapper) picks with a confidence score. With no API key it degrades gracefully to the embedding match — the system never fails for lack of a key.
4. **Enrich** — missing attributes are filled from matched datasheets, and every enriched value stores its source (PDF filename / header) — anti-hallucination by construction.
5. **Cross-reference & deliver** — dimension-equivalent parts are matched across suppliers (substitute search API); a FastAPI review console lets a human approve/correct each row; export writes the required delivery format with all 252 static headers populated, never renamed. The solver CLI (`python -m src.solve input.csv -o output.csv|xlsx`) is fully dynamic — column detection is fuzzy, so it handles evaluation data with unseen field combinations, no hardcoding.

**Results on the demo dataset:** 145 products from 4 suppliers in 3 formats → 100% family classification accuracy, 116 products cross-referenced across suppliers, source-grounded PDF enrichment, 8-second runtime on CPU, $0 API cost.

**Why it wins:** it occupies the exact intersection no incumbent covers (taxonomy + datasheets + cross-referencing + governance + self-serve), and every judging criterion — live end-to-end demo, real messy data grounding, technical depth, deployment realism — is demonstrable on stage.
