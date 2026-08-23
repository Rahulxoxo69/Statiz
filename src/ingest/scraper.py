"""Manufacturer-page scraper: static fetch first, Playwright for JS pages.

Returns structured "evidence" per product:
  {html_text, jsonld: [...], meta: {...}, title, pdf_texts: [(url, text)]}
The enrichment mapper turns evidence into delivery fields.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(url: str) -> Path:
    h = str(abs(hash(url)))
    return CACHE_DIR / (urlparse(url).netloc.replace(".", "_") + h + ".txt")


def fetch_text(url: str, force: bool = False) -> str:
    """Fetch URL text with disk cache. Tries httpx, falls back to Playwright."""
    cp = _cache_path(url)
    if cp.exists() and not force:
        return cp.read_text(encoding="utf-8")
    content = ""
    try:
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", "html"):
            content = r.text
    except Exception:
        pass
    if not content:
        content = _playwright_text(url)
    cp.write_text(content or "", encoding="utf-8")
    return content or ""


def _playwright_text(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(user_agent=UA)
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            html = page.content()
            b.close()
            return html
    except Exception as e:
        print(f"  [warn] playwright failed for {url}: {e}")
        return ""


def fetch_pdf_text(url: str, max_chars: int = 12000) -> str:
    """Download a PDF and extract its text (cached)."""
    cp = _cache_path(url + "#pdf")
    if cp.exists():
        return cp.read_text(encoding="utf-8")[:max_chars]
    text = ""
    tmp = CACHE_DIR / "tmp_download.pdf"
    try:
        with httpx.Client(headers={"User-Agent": UA}, timeout=60,
                          follow_redirects=True) as c:
            r = c.get(url)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                tmp.write_bytes(r.content)
                import pymupdf
                with pymupdf.open(tmp) as doc:
                    text = "\n".join(pg.get_text() for pg in doc)
    except Exception as e:
        print(f"  [warn] pdf fetch failed {url}: {e}")
    cp.write_text(text or "", encoding="utf-8")
    return (text or "")[:max_chars]


META_RE = re.compile(
    r'<meta[^>]+(?:name|property)=["\'](description|og:title|og:description|og:image|'
    r'og:site_name|product:price:amount|keyword)["\'][^>]+content=["\']([^"\']*)["\']',
    re.I)
JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']', re.I)


def parse_html(html: str, base_url: str) -> dict:
    """Extract title/meta/JSON-LD/images from HTML without a DOM library."""
    metas = {}
    for name, content in META_RE.findall(html or ""):
        metas[name] = content
    jsonld = []
    for m in JSONLD_RE.findall(html or ""):
        try:
            jsonld.append(json.loads(m))
        except json.JSONDecodeError:
            continue
    images = [urljoin(base_url, s) for s in IMG_RE.findall(html or "")]
    title = ""
    tm = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    if tm:
        title = re.sub(r"\s+", " ", tm.group(1)).strip()
    return {"title": title, "meta": metas, "jsonld": jsonld, "images": images}


def gather_evidence(mfr_url: str, ref_urls: list[str]) -> dict:
    html = fetch_text(mfr_url) if mfr_url else ""
    parsed = parse_html(html, mfr_url)
    pdfs = []
    for u in ref_urls:
        if not u:
            continue
        if u.lower().endswith(".pdf") or "pdf" in urlparse(u).path.lower():
            t = fetch_pdf_text(u)
            if t:
                pdfs.append({"url": u, "text": t})
        else:
            t = fetch_text(u)
            if t:
                pp = parse_html(t, u)
                pdfs.append({"url": u, "text": pp["title"] + " " +
                             " ".join(pp["meta"].values())})
    return {"mfr_url": mfr_url, "html_parsed": parsed,
            "raw_text": _strip_html(html)[:8000], "docs": pdfs}


def _strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.I | re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()
