#!/usr/bin/env python3
"""
Refresh _data/papers.yml from a NASA ADS library.

Pipeline per paper:
  1. Pull recent bibcodes from the ADS library, biased toward recent ones.
  2. Fetch metadata (title, authors, year, venue, DOI, arXiv id).
  3. Try to download the arXiv PDF; render its pages.
  4. Ask a small vision-capable model on GitHub Models to pick the
     single page with the most representative figure.
  5. Crop that page (top/bottom whitespace) and save as a PNG.
  6. Ask the same model for a short plain-English summary.
  7. Write the result to _data/papers.yml so Jekyll can render cards.

Required environment:
  ADS_API_TOKEN     Personal NASA ADS token (https://ui.adsabs.harvard.edu/user/settings/token)
  GITHUB_TOKEN      Token with `models:read` (workflows: github.token works)

Optional:
  ADS_LIBRARY_ID    Overrides _config.yml's ads_library_id.
  PAPERS_LIMIT      How many papers to keep (default 6).
  MODEL_NAME        GitHub Models model name (default openai/gpt-4o-mini).
"""

from __future__ import annotations

import base64
import io
import json
import os
import pathlib
import random
import re
import sys
import time
import urllib.parse
from typing import Any

import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "_data" / "papers.yml"
FIGURE_DIR = ROOT / "assets" / "img" / "papers"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

ADS_BASE = "https://api.adsabs.harvard.edu/v1"
GH_MODELS_BASE = "https://models.github.ai/inference"

PAPERS_LIMIT = int(os.environ.get("PAPERS_LIMIT", "6"))
MODEL_NAME = os.environ.get("MODEL_NAME", "openai/gpt-4o-mini")

# Recent-bias: how many of the most recent papers to pull from the library.
ADS_FETCH_ROWS = 30

# Rate-limit handling for GitHub Models.
# The free tier enforces requests-per-minute, tokens-per-minute, and a
# daily quota. Cap any Retry-After we honour at MAX_RATELIMIT_WAIT so a
# day-long backoff doesn't hang the workflow — we'll just resume next run
# (the per-paper cache means already-finished work is skipped).
MAX_RATELIMIT_WAIT = int(os.environ.get("MAX_RATELIMIT_WAIT", "600"))
REQUEST_SPACING = float(os.environ.get("REQUEST_SPACING", "60"))

# Vision payload knobs. With detail="low" each image costs ~85 tokens
# regardless of resolution, which keeps the figure-pick call well inside
# the per-minute token ceiling.
FIGURE_MAX_PAGES = int(os.environ.get("FIGURE_MAX_PAGES", "8"))
FIGURE_RENDER_DPI = int(os.environ.get("FIGURE_RENDER_DPI", "100"))


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------
# ADS
# --------------------------------------------------------------------------


def _ads_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def fetch_library_bibcodes(session: requests.Session, library_id: str) -> list[str]:
    """Return all bibcodes in the ADS library, ordered by ADS's default."""
    url = f"{ADS_BASE}/biblib/libraries/{library_id}"
    bibcodes: list[str] = []
    start = 0
    rows = 200
    while True:
        r = session.get(url, params={"start": start, "rows": rows}, timeout=30)
        r.raise_for_status()
        data = r.json()
        chunk = data.get("documents") or data.get("solr", {}).get("response", {}).get("docs") or []
        if isinstance(chunk, list) and chunk and isinstance(chunk[0], dict):
            chunk = [d.get("bibcode") for d in chunk]
        bibcodes.extend(c for c in chunk if c)
        meta = data.get("metadata", {})
        total = meta.get("num_documents") or len(bibcodes)
        start += rows
        if start >= total:
            break
    return bibcodes


def fetch_paper_metadata(session: requests.Session, bibcodes: list[str]) -> list[dict[str, Any]]:
    """Look up canonical metadata for a list of bibcodes via ADS search."""
    if not bibcodes:
        return []
    fl = ",".join([
        "bibcode",
        "title",
        "author",
        "year",
        "pub",
        "pubdate",
        "doi",
        "identifier",
        "abstract",
        "page",
    ])
    q = " OR ".join(f"bibcode:{b}" for b in bibcodes)
    r = session.get(
        f"{ADS_BASE}/search/query",
        params={"q": q, "fl": fl, "rows": len(bibcodes), "sort": "date desc"},
        timeout=30,
    )
    r.raise_for_status()
    docs = r.json()["response"]["docs"]
    by_bib = {d["bibcode"]: d for d in docs}
    return [by_bib[b] for b in bibcodes if b in by_bib]


def arxiv_id(doc: dict[str, Any]) -> str | None:
    for ident in doc.get("identifier", []) or []:
        m = re.match(r"^(?:arXiv:)?(\d{4}\.\d{4,5})", ident)
        if m:
            return m.group(1)
    return None


def short_authors(authors: list[str], focal: str = "Benson, A.") -> str:
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    head = authors[0]
    if any(a.startswith("Benson") for a in authors):
        if authors[0].startswith("Benson"):
            return f"{head} et al." if len(authors) > 1 else head
        return f"{head}, A. Benson, et al."
    return f"{head} et al."


def venue(doc: dict[str, Any]) -> str:
    pub = doc.get("pub") or ""
    return pub.replace("\\", "").strip()


# --------------------------------------------------------------------------
# Paper PDF + figures
# --------------------------------------------------------------------------


def download_arxiv_pdf(arxiv: str, dest: pathlib.Path) -> bool:
    url = f"https://arxiv.org/pdf/{arxiv}.pdf"
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "abensonca-site/1.0"})
        r.raise_for_status()
    except requests.RequestException as e:
        log(f"  arXiv download failed for {arxiv}: {e}")
        return False
    dest.write_bytes(r.content)
    return True


def render_pdf_pages(pdf_path: pathlib.Path,
                     max_pages: int = FIGURE_MAX_PAGES,
                     dpi: int = FIGURE_RENDER_DPI) -> list[bytes]:
    """Render the first `max_pages` pages of a PDF to PNG bytes.

    We render at modest DPI because the model uses `detail: low` for the
    figure-pick call (where it only needs to recognise figure-vs-text
    layout), and we re-render the chosen page at high DPI separately for
    the saved card image.
    """
    import fitz  # PyMuPDF

    out: list[bytes] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pm = page.get_pixmap(dpi=dpi, alpha=False)
            out.append(pm.tobytes("png"))
    return out


def render_pdf_page_hires(pdf_path: pathlib.Path, index: int, dpi: int = 160,
                          clip: tuple[float, float, float, float] | None = None) -> bytes | None:
    """Re-render a specific page (or sub-rectangle of one) at high DPI."""
    import fitz

    with fitz.open(pdf_path) as doc:
        if not (0 <= index < len(doc)):
            return None
        page = doc[index]
        kwargs: dict[str, Any] = {"dpi": dpi, "alpha": False}
        if clip is not None:
            kwargs["clip"] = fitz.Rect(*clip)
        pm = page.get_pixmap(**kwargs)
        return pm.tobytes("png")


def figure_bbox_in_page(pdf_path: pathlib.Path, page_idx: int) -> tuple[float, float, float, float] | None:
    """
    Compute a tight PDF-coord bounding box around the dominant figure on a
    page using PyMuPDF's image+drawing primitives, with no model calls.

    Most astrophysics figures are either embedded raster images or large
    clusters of vector drawing operations (axes, ticks, lines, scatter
    points). Page furniture — citation underlines, table rules, headers —
    is filtered out by area and by overlap with text blocks. Returns None
    if the page doesn't have a clearly dominant graphical region; the
    caller should then fall back to the full-page render.
    """
    import fitz

    with fitz.open(pdf_path) as doc:
        if not (0 <= page_idx < len(doc)):
            return None
        page = doc[page_idx]
        pw, ph = page.rect.width, page.rect.height
        page_area = pw * ph
        if page_area <= 0:
            return None

        rects: list[fitz.Rect] = []

        # Embedded raster images.
        for info in page.get_images(full=True):
            try:
                bbox = page.get_image_bbox(info)
            except Exception:
                continue
            r = fitz.Rect(bbox)
            if r.width > 0 and r.height > 0:
                rects.append(r)

        # Vector drawings (paths, fills, strokes — i.e. the bones of a plot).
        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []
        for d in drawings:
            r = d.get("rect")
            if r is None:
                continue
            r = fitz.Rect(r)
            if r.width > 0 and r.height > 0:
                rects.append(r)

        if not rects:
            return None

        # Drop hair-line page furniture and ultra-tiny marks (rules, separator
        # lines, single tick marks would each be filtered, but their union
        # would survive — we only filter rects that are tiny in BOTH axes).
        min_area = page_area * 0.001
        rects = [r for r in rects if (r.width * r.height) >= min_area or (r.width > 5 and r.height > 5)]
        if not rects:
            return None

        # Drop rects that lie almost entirely inside a text block (citation
        # underlines, equation horizontal rules, in-line decorations).
        text_blocks: list[fitz.Rect] = []
        try:
            for b in page.get_text("blocks"):
                # blocks tuple: (x0, y0, x1, y1, text, block_no, block_type).
                # block_type 0 == text, 1 == image. Treat both as text-like
                # for "is this just decoration in a paragraph" purposes.
                text_blocks.append(fitz.Rect(b[0], b[1], b[2], b[3]))
        except Exception:
            pass

        def heavily_in_text(r: fitz.Rect) -> bool:
            for tb in text_blocks:
                inter = fitz.Rect(r) & tb
                if inter.is_empty:
                    continue
                if (inter.width * inter.height) > 0.7 * (r.width * r.height):
                    return True
            return False

        graphical = [r for r in rects if not heavily_in_text(r)]
        if not graphical:
            graphical = rects  # don't strand pages whose figure overlapped a label block

        # Cluster spatially: rects within `gap` points of each other belong
        # to the same figure. Then pick the cluster covering the most area.
        gap = 18.0  # ~quarter-inch at 72 DPI

        def expanded(r: fitz.Rect) -> fitz.Rect:
            return fitz.Rect(r.x0 - gap, r.y0 - gap, r.x1 + gap, r.y1 + gap)

        clusters: list[list[fitz.Rect]] = []
        for r in graphical:
            placed = False
            for c in clusters:
                if any(expanded(cr).intersects(r) for cr in c):
                    c.append(r)
                    placed = True
                    break
            if not placed:
                clusters.append([r])

        # Greedy second pass: clusters that grew until they touch each other.
        merged = True
        while merged:
            merged = False
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    ui = fitz.Rect(clusters[i][0])
                    for r in clusters[i][1:]:
                        ui |= r
                    uj = fitz.Rect(clusters[j][0])
                    for r in clusters[j][1:]:
                        uj |= r
                    if expanded(ui).intersects(uj):
                        clusters[i].extend(clusters[j])
                        clusters.pop(j)
                        merged = True
                        break
                if merged:
                    break

        def cluster_bbox(c: list[fitz.Rect]) -> fitz.Rect:
            u = fitz.Rect(c[0])
            for r in c[1:]:
                u |= r
            return u

        best = max(clusters, key=lambda c: cluster_bbox(c).width * cluster_bbox(c).height)
        bbox = cluster_bbox(best)

        # Guard against runaway unions covering the whole page (e.g. when
        # the figure spans full-width and we accidentally sucked in headers).
        if (bbox.width * bbox.height) > 0.85 * page_area:
            biggest = max(graphical, key=lambda r: r.width * r.height)
            bbox = fitz.Rect(biggest)

        # Reject results that are too small to be a real figure.
        if (bbox.width * bbox.height) < 0.05 * page_area:
            return None
        if bbox.width < 0.20 * pw and bbox.height < 0.20 * ph:
            return None

        # Pad slightly so axis tick labels at the rim aren't clipped.
        pad = 4.0
        x0 = max(0.0, bbox.x0 - pad)
        y0 = max(0.0, bbox.y0 - pad)
        x1 = min(pw, bbox.x1 + pad)
        y1 = min(ph, bbox.y1 + pad)
        return (x0, y0, x1, y1)


def crop_whitespace(png_bytes: bytes) -> bytes:
    """Trim large white margins from a page image so figure cards look clean."""
    from PIL import Image, ImageChops

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    bg = Image.new(img.mode, img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        # Add a small padding.
        pad = 12
        left, upper, right, lower = bbox
        left = max(0, left - pad)
        upper = max(0, upper - pad)
        right = min(img.width, right + pad)
        lower = min(img.height, lower + pad)
        img = img.crop((left, upper, right, lower))
    # Cap the long edge so the asset stays small.
    max_edge = 1000
    if max(img.size) > max_edge:
        scale = max_edge / max(img.size)
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


# --------------------------------------------------------------------------
# GitHub Models
# --------------------------------------------------------------------------


def _gh_models_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return s


def gh_models_chat(session: requests.Session, messages: list[dict[str, Any]],
                   max_tokens: int = 600, retries: int = 6) -> str:
    """Call GitHub Models chat completions, honouring Retry-After on 429s."""
    body = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    for attempt in range(retries):
        try:
            r = session.post(
                f"{GH_MODELS_BASE}/chat/completions",
                json=body,
                timeout=120,
            )
        except requests.RequestException as e:
            wait = min(60, 2 ** attempt)
            log(f"  request error ({e}); sleeping {wait}s")
            time.sleep(wait)
            continue

        if r.status_code == 429:
            # Free-tier limits are per-minute (TPM/RPM) and per-day. Honour
            # whichever Retry-After-style header GitHub sends; cap the wait
            # so a daily-quota response doesn't hang the workflow for hours.
            ra = (
                r.headers.get("Retry-After")
                or r.headers.get("retry-after")
                or r.headers.get("x-ratelimit-timeremaining")
            )
            try:
                wait = int(float(ra)) if ra is not None else 0
            except ValueError:
                wait = 0
            if wait <= 0:
                wait = 20 * (attempt + 1)
            wait = min(wait, MAX_RATELIMIT_WAIT)
            try:
                msg = r.json().get("error", {}).get("message", "")
            except Exception:
                msg = (r.text or "")[:200]
            log(f"  rate-limited (attempt {attempt + 1}/{retries}); sleeping {wait}s — {msg}")
            time.sleep(wait)
            continue

        if 500 <= r.status_code < 600:
            wait = min(60, 5 * (attempt + 1))
            log(f"  server error {r.status_code}; sleeping {wait}s")
            time.sleep(wait)
            continue

        if not r.ok:
            try:
                msg = r.json().get("error", {}).get("message", "")
            except Exception:
                msg = (r.text or "")[:200]
            raise RuntimeError(f"GitHub Models {r.status_code}: {msg}")

        # Be polite between successful calls so we don't immediately re-trip
        # the per-minute TPM ceiling on the next request.
        time.sleep(REQUEST_SPACING)
        return r.json()["choices"][0]["message"]["content"].strip()

    raise RuntimeError(f"GitHub Models still rate-limited after {retries} attempts")


def pick_figure_page(session: requests.Session, page_pngs: list[bytes],
                     title: str) -> int:
    """Ask the vision model which page best represents the paper's lead figure."""
    if not page_pngs:
        return -1

    # Build a multi-image content payload. Skip page 0 (typically text) but
    # include it as a fallback option.
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": (
            f"Paper title: {title}\n"
            "Below are thumbnails of pages from this paper, in order. "
            "Pick the SINGLE page that contains the most visually compelling, "
            "representative figure for use as a thumbnail on a research website. "
            "Strongly prefer pages dominated by a plot, diagram, or image rather "
            "than text. Reply with only an integer index (0-based)."
        ),
    }]
    for png in page_pngs:
        b64 = base64.b64encode(png).decode("ascii")
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                # detail=low fixes the per-image cost at ~85 input tokens,
                # which is essential for staying under the free-tier TPM.
                "detail": "low",
            },
        })

    try:
        reply = gh_models_chat(session, [{"role": "user", "content": content}], max_tokens=8)
    except Exception as e:
        log(f"  figure pick failed: {e}; falling back to page 1")
        return 1 if len(page_pngs) > 1 else 0

    m = re.search(r"\d+", reply)
    if not m:
        return 1 if len(page_pngs) > 1 else 0
    idx = int(m.group(0))
    if 0 <= idx < len(page_pngs):
        return idx
    return 1 if len(page_pngs) > 1 else 0


def summarize_paper(session: requests.Session, title: str, abstract: str) -> str:
    if not abstract:
        return ""
    prompt = (
        "Summarize the following astrophysics paper abstract for a research-website "
        "card. Two sentences max, plain English, focus on the result's significance. "
        "No hype, no first person, no quotation marks.\n\n"
        f"Title: {title}\n\nAbstract: {abstract}"
    )
    try:
        return gh_models_chat(
            session,
            [{"role": "user", "content": prompt}],
            max_tokens=200,
        )
    except Exception as e:
        log(f"  summary failed: {e}")
        return ""


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def site_config() -> dict[str, Any]:
    cfg_path = ROOT / "_config.yml"
    return yaml.safe_load(cfg_path.read_text()) or {}


def load_existing() -> list[dict[str, Any]]:
    if not DATA_FILE.exists():
        return []
    try:
        data = yaml.safe_load(DATA_FILE.read_text()) or []
        return data if isinstance(data, list) else []
    except yaml.YAMLError:
        return []


def main() -> int:
    ads_token = os.environ.get("ADS_API_TOKEN")
    gh_token = os.environ.get("GITHUB_TOKEN")
    if not ads_token:
        log("ADS_API_TOKEN is not set; skipping paper update.")
        return 0
    if not gh_token:
        log("GITHUB_TOKEN is not set; will fetch metadata but skip summaries/figures.")

    cfg = site_config()
    library_id = os.environ.get("ADS_LIBRARY_ID") or cfg.get("ads_library_id")
    if not library_id:
        log("No ADS library id configured (`ads_library_id` in _config.yml).")
        return 1

    ads = _ads_session(ads_token)
    gh = _gh_models_session(gh_token) if gh_token else None

    log(f"Fetching library {library_id}…")
    bibcodes = fetch_library_bibcodes(ads, library_id)
    if not bibcodes:
        log("Library returned no bibcodes; aborting.")
        return 1
    log(f"  → {len(bibcodes)} bibcodes total")

    # Pull fresh metadata for the most recent N entries (ADS sorts library by
    # add-date by default; we re-sort by date desc on the metadata side).
    head = bibcodes[: ADS_FETCH_ROWS]
    docs = fetch_paper_metadata(ads, head)

    # Recent-bias: weight by year so newer papers are likelier to land in
    # the front-page sample, but allow a few older highlights through.
    def weight(d: dict[str, Any]) -> float:
        try:
            y = int(d.get("year") or 0)
        except (TypeError, ValueError):
            y = 0
        return max(1.0, y - 2010) ** 1.4

    docs_sorted = sorted(docs, key=lambda d: int(d.get("year") or 0), reverse=True)
    pool = docs_sorted[: max(PAPERS_LIMIT * 2, PAPERS_LIMIT)]
    weights = [weight(d) for d in pool]
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    rng = random.Random(42)
    for cand in pool[:PAPERS_LIMIT]:
        chosen.append(cand)
        seen.add(cand["bibcode"])
    if len(chosen) < PAPERS_LIMIT:
        # Sample additional unique entries weighted by recency.
        for _ in range(PAPERS_LIMIT * 5):
            if len(chosen) >= PAPERS_LIMIT:
                break
            cand = rng.choices(pool, weights=weights, k=1)[0]
            if cand["bibcode"] in seen:
                continue
            chosen.append(cand)
            seen.add(cand["bibcode"])

    existing = {p.get("bibcode"): p for p in load_existing()}
    out: list[dict[str, Any]] = []

    for doc in chosen:
        bib = doc["bibcode"]
        title = (doc.get("title") or [""])[0]
        log(f"\nProcessing {bib}: {title[:80]}")

        prev = existing.get(bib, {})
        figure_path = prev.get("figure")
        summary = prev.get("summary", "")

        ax = arxiv_id(doc)
        url = f"https://ui.adsabs.harvard.edu/abs/{urllib.parse.quote(bib)}"

        # Figure: only re-run if we don't already have one.
        if gh and not (figure_path and (ROOT / figure_path.lstrip("/")).exists()) and ax:
            pdf_path = FIGURE_DIR / f"{bib.replace('/', '_')}.pdf"
            if download_arxiv_pdf(ax, pdf_path):
                try:
                    pages = render_pdf_pages(pdf_path)
                except Exception as e:
                    log(f"  PDF render failed: {e}")
                    pages = []
                if pages:
                    idx = pick_figure_page(gh, pages, title)
                    # Try to crop to just the figure region using PyMuPDF's
                    # geometry; fall back to the full page if we can't tell.
                    clip = None
                    try:
                        clip = figure_bbox_in_page(pdf_path, idx)
                    except Exception as e:
                        log(f"  figure bbox detection failed: {e}")
                    log(f"  picked page {idx}" + (" (cropped to figure)" if clip else " (full page)"))
                    hi = render_pdf_page_hires(pdf_path, idx, clip=clip) or pages[idx]
                    try:
                        cropped = crop_whitespace(hi)
                    except Exception:
                        cropped = hi
                    img_path = FIGURE_DIR / f"{bib.replace('/', '_')}.png"
                    img_path.write_bytes(cropped)
                    figure_path = "/" + img_path.relative_to(ROOT).as_posix()
                pdf_path.unlink(missing_ok=True)

        # Summary: only re-run if we don't already have one.
        abstract = doc.get("abstract") or ""
        if gh and not summary and abstract:
            summary = summarize_paper(gh, title, abstract)

        out.append({
            "bibcode": bib,
            "title": title,
            "authors_short": short_authors(doc.get("author") or []),
            "year": int(doc.get("year") or 0) or None,
            "venue": venue(doc),
            "url": url,
            "arxiv": f"https://arxiv.org/abs/{ax}" if ax else None,
            "doi": (doc.get("doi") or [None])[0],
            "summary": summary,
            "figure": figure_path,
        })

    # Stable order: most recent first.
    out.sort(key=lambda p: p.get("year") or 0, reverse=True)

    DATA_FILE.write_text(
        "# Auto-generated by scripts/fetch_papers.py — do not edit by hand.\n"
        + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=100)
    )
    log(f"\nWrote {DATA_FILE.relative_to(ROOT)} with {len(out)} entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
