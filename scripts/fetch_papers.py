#!/usr/bin/env python3
"""
Refresh _data/papers.yml from a NASA ADS library.

Pipeline per paper:
  1. Pull recent bibcodes from the ADS library, biased toward recent ones.
  2. Fetch metadata (title, authors, year, venue, DOI, arXiv id, abstract).
  3. Try to download the arXiv PDF; render its pages.
  4. Score each page's dominant graphical region and pick the best figure page.
  5. Crop to that figure and save as a PNG.
  6. Write the result to _data/papers.yml so Jekyll can render cards.

No model is called here. Summaries are written by scripts/summaries.py, run
from Claude Code, into _data/papers_cache.yml — a durable per-bibcode store of
summaries, abstracts, and figure paths that is never pruned. papers.yml holds
only the papers currently on the front page, so without that cache a paper
that rotated out and later returned would need its summary regenerated.

Required environment:
  ADS_API_TOKEN     Personal NASA ADS token (https://ui.adsabs.harvard.edu/user/settings/token)

Optional:
  ADS_LIBRARY_ID    Overrides _config.yml's ads_library_id.
  PAPERS_LIMIT      How many papers to keep (default 6).
"""

from __future__ import annotations

import html
import io
import os
import pathlib
import random
import re
import sys
import urllib.parse
from typing import Any

import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "_data" / "papers.yml"
CACHE_FILE = ROOT / "_data" / "papers_cache.yml"
FIGURE_DIR = ROOT / "assets" / "img" / "papers"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

ADS_BASE = "https://api.adsabs.harvard.edu/v1"

PAPERS_LIMIT = int(os.environ.get("PAPERS_LIMIT", "6"))

# Recent-bias: how many of the most recent papers to pull from the library.
ADS_FETCH_ROWS = 30

# How many leading pages to consider when hunting for the figure, and at what
# resolution to render them. The chosen page is re-rendered at high DPI.
FIGURE_MAX_PAGES = int(os.environ.get("FIGURE_MAX_PAGES", "8"))
FIGURE_RENDER_DPI = int(os.environ.get("FIGURE_RENDER_DPI", "100"))

# Figure/table captions, so they can be kept out of the cropped card image —
# at card size the caption text is unreadable and just crowds the figure.
CAPTION_RE = re.compile(r"\s*(?:Figure|Fig\.?|Table|TAB\.?|FIG\.?)\s*\d", re.IGNORECASE)


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------
# ADS
# --------------------------------------------------------------------------


def ads_token() -> str | None:
    """ADS token from the environment, falling back to the standard dotfile."""
    token = os.environ.get("ADS_API_TOKEN")
    if token:
        return token.strip()
    dotfile = pathlib.Path.home() / ".ads" / "dev_key"
    if dotfile.exists():
        return dotfile.read_text().strip() or None
    return None


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
        "alternate_bibcode",
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


def strip_markup(text: str) -> str:
    """Flatten the HTML/MathML that ADS embeds in titles and abstracts.

    ADS returns things like `with <inline-formula><mml:math><mml:mi>N</mml:mi>
    </mml:math></inline-formula>-body simulations` and `r<SUP>-1.5</SUP>`.
    Dropping the tags and keeping their text gives "with N-body simulations"
    and "r-1.5" — readable in a card title, and clean input for summarizing.
    """
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return " ".join(text.split())


def arxiv_id(doc: dict[str, Any]) -> str | None:
    for ident in doc.get("identifier", []) or []:
        m = re.match(r"^(?:arXiv:)?(\d{4}\.\d{4,5})", ident)
        if m:
            return m.group(1)

    # ADS intermittently returns a truncated `identifier` list for published
    # records — just the bibcode and DOI, with the eprint id missing. The
    # preprint's own bibcode (2026arXiv260515371N) encodes the same id, so
    # recover it from there rather than losing the arXiv link for a week.
    for alt in list(doc.get("alternate_bibcode") or []) + [doc.get("bibcode") or ""]:
        m = re.match(r"^\d{4}arXiv(\d{4})(\d{4,5})", str(alt))
        if m:
            return f"{m.group(1)}.{m.group(2)}"
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

    Modest DPI is fine here: these renders are only used as a fallback if the
    high-DPI re-render of the chosen page fails. Page *selection* works off
    PDF geometry, not these images.
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

        def clipped(r: Any) -> fitz.Rect | None:
            """Confine a rect to the visible page; drop it if nothing is left.

            Figures routinely carry clipping or background paths that extend
            well past the page edge (one seen in the wild: a 509x659 path on a
            612pt-wide page, running out to x=808). Left unclamped, a single
            one of those defines the whole bounding box.
            """
            r = fitz.Rect(r) & page.rect
            if r.is_empty or r.width <= 0 or r.height <= 0:
                return None
            return r

        # Embedded raster images.
        for info in page.get_images(full=True):
            try:
                bbox = page.get_image_bbox(info)
            except Exception:
                continue
            r = clipped(bbox)
            if r is not None:
                rects.append(r)

        # Vector drawings (paths, fills, strokes — i.e. the bones of a plot).
        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []
        for d in drawings:
            if d.get("rect") is None:
                continue
            r = clipped(d["rect"])
            if r is None:
                continue
            # A single vector path covering most of the page is a background
            # or clip region, not a figure. A real figure is reconstructed
            # from its many component paths, so dropping these loses nothing.
            if (r.width * r.height) > 0.55 * page_area:
                continue
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
        caption_blocks: list[fitz.Rect] = []
        try:
            for b in page.get_text("blocks"):
                # blocks tuple: (x0, y0, x1, y1, text, block_no, block_type).
                # block_type 0 == text, 1 == image. Treat both as text-like
                # for "is this just decoration in a paragraph" purposes.
                r = fitz.Rect(b[0], b[1], b[2], b[3])
                text_blocks.append(r)
                if CAPTION_RE.match(str(b[4] or "")):
                    caption_blocks.append(r)
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

        # Locate the figure by drawing *density* rather than by clustering
        # rects into connected groups. A plot is hundreds of overlapping
        # paths — axes, ticks, grid lines, data — stacked in one band of the
        # page, whereas the stray clip and background paths that survive the
        # filters above are lone rects that can span a whole column. Counting
        # how many rects cover each row separates the two cleanly; a union of
        # touching rects cannot, because one stray rect bridges everything.
        gap = 18.0  # bridge whitespace between panels of one figure, in points

        def dense_span(lo_attr: str, hi_attr: str, extent: float,
                       source: list[fitz.Rect]) -> tuple[float, float] | None:
            """Find the densest contiguous band along one axis."""
            n = int(extent) + 1
            counts = [0] * n
            for r in source:
                lo = max(0, int(getattr(r, lo_attr)))
                hi = min(n - 1, int(getattr(r, hi_attr)))
                for i in range(lo, hi + 1):
                    counts[i] += 1

            peak = max(counts)
            if peak <= 0:
                return None
            # With a single covering rect (a lone raster figure) any coverage
            # counts; with many, require a real pile-up to exclude strays.
            threshold = 1 if peak <= 1 else max(2, int(0.10 * peak))

            best_run: tuple[float, float] | None = None
            best_mass = 0
            start = None
            last = 0
            mass = 0
            gap_run = 0
            for i, c in enumerate(counts):
                if c >= threshold:
                    if start is None:
                        start = i
                    last = i
                    mass += c
                    gap_run = 0
                elif start is not None:
                    gap_run += 1
                    if gap_run > gap:
                        if mass > best_mass:
                            best_mass, best_run = mass, (float(start), float(last))
                        start, mass, gap_run = None, 0, 0
            # A run still open at the end closes on the last qualifying index,
            # not on the page edge.
            if start is not None and mass > best_mass:
                best_run = (float(start), float(last))
            return best_run

        rows = dense_span("y0", "y1", ph, graphical)
        if rows is None:
            return None
        y_lo, y_hi = rows

        # Columns are measured only across the rows the figure actually
        # occupies, so text elsewhere on the page can't widen the box.
        in_band = [r for r in graphical if r.y1 >= y_lo and r.y0 <= y_hi]
        cols = dense_span("x0", "x1", pw, in_band)
        if cols is None:
            return None
        x_lo, x_hi = cols

        bbox = fitz.Rect(x_lo, y_lo, x_hi, y_hi)
        if bbox.is_empty or bbox.width <= 0 or bbox.height <= 0:
            return None

        # The dense band is the figure's *body*; its frame, tick marks and
        # tick labels sit in the sparse margin just outside and would be
        # sliced off. Grow the box back over anything that plainly belongs to
        # it — graphical rects mostly inside it, then small text blocks
        # (tick labels, axis titles) mostly inside a slightly padded version.
        # Captions and body paragraphs sit wholly outside, so they stay out.
        def fraction_inside(r: fitz.Rect, box: fitz.Rect) -> float:
            area = r.width * r.height
            if area <= 0:
                return 0.0
            inter = fitz.Rect(r) & box
            if inter.is_empty:
                return 0.0
            return (inter.width * inter.height) / area

        for _ in range(2):
            for r in graphical:
                if fraction_inside(r, bbox) >= 0.5:
                    bbox |= r

        label_zone = fitz.Rect(bbox.x0 - 14, bbox.y0 - 14, bbox.x1 + 14, bbox.y1 + 14)
        margin = 0.08 * ph  # running heads and page numbers live in here
        for tb in text_blocks:
            if tb.height > 0.25 * ph or tb.height <= 0:
                continue  # a paragraph, not a label
            centre_y = 0.5 * (tb.y0 + tb.y1)
            if centre_y < margin or centre_y > ph - margin:
                continue  # running head / folio, not part of the figure
            if tb in caption_blocks:
                continue  # handled below
            if fraction_inside(tb, label_zone) >= 0.6:
                bbox |= tb

        # Captions get cut mid-line by whatever edge the box happens to land
        # on, which looks worse than either including or excluding them
        # cleanly. Pull the box back to the caption's edge so it's excluded
        # outright — at card size the caption text is unreadable anyway.
        centre_y = 0.5 * (bbox.y0 + bbox.y1)
        for cb in caption_blocks:
            if cb.y0 >= bbox.y1 or cb.y1 <= bbox.y0:
                continue  # already outside
            if cb.y0 > centre_y:            # caption below the figure
                bbox.y1 = min(bbox.y1, cb.y0 - 6)
            elif cb.y1 < centre_y:          # caption above (tables, mostly)
                bbox.y0 = max(bbox.y0, cb.y1 + 6)

        bbox &= page.rect

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


def pick_figure_page(pdf_path: pathlib.Path,
                     n_pages: int) -> tuple[int, tuple[float, float, float, float] | None]:
    """Choose the page whose dominant figure covers the most of the page.

    `figure_bbox_in_page` already isolates the dominant graphical region on a
    page and returns None when there isn't one, so scoring every candidate
    page by its bbox area fraction picks the figure page without a model in
    the loop. Falls back to page 1 (page 0 is nearly always the title page)
    when no page has a detectable figure.
    """
    best_idx = -1
    best_score = 0.0
    best_clip: tuple[float, float, float, float] | None = None

    import fitz

    with fitz.open(pdf_path) as doc:
        page_areas = [
            doc[i].rect.width * doc[i].rect.height
            for i in range(min(n_pages, len(doc)))
        ]

    for idx, page_area in enumerate(page_areas):
        if page_area <= 0:
            continue
        try:
            clip = figure_bbox_in_page(pdf_path, idx)
        except Exception as e:
            log(f"  figure bbox detection failed on page {idx}: {e}")
            continue
        if clip is None:
            continue
        x0, y0, x1, y1 = clip
        score = ((x1 - x0) * (y1 - y0)) / page_area
        # Slightly discount the title page: a big logo or masthead graphic
        # there is rarely the paper's representative figure.
        if idx == 0:
            score *= 0.5
        if score > best_score:
            best_idx, best_score, best_clip = idx, score, clip

    if best_idx < 0:
        return (1 if len(page_areas) > 1 else 0), None
    return best_idx, best_clip


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


def load_cache() -> dict[str, dict[str, Any]]:
    """Durable per-bibcode store of summaries and figure paths.

    papers.yml only holds the papers currently on the front page, so a paper
    that rotates out and later returns would otherwise need a fresh model
    call (and got a blank card whenever that call failed). This file is
    keyed by bibcode and never pruned.
    """
    if not CACHE_FILE.exists():
        return {}
    try:
        data = yaml.safe_load(CACHE_FILE.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def save_cache(cache: dict[str, dict[str, Any]]) -> None:
    CACHE_FILE.write_text(
        "# Auto-generated by scripts/fetch_papers.py — do not edit by hand.\n"
        "# Durable cache of model-generated summaries and figure paths, keyed\n"
        "# by bibcode. Never pruned: entries outlive rotation out of papers.yml.\n"
        + yaml.safe_dump(cache, sort_keys=True, allow_unicode=True, width=100)
    )


def main() -> int:
    token = ads_token()
    if not token:
        log("No ADS token (set ADS_API_TOKEN or ~/.ads/dev_key); skipping paper update.")
        return 0

    cfg = site_config()
    library_id = os.environ.get("ADS_LIBRARY_ID") or cfg.get("ads_library_id")
    if not library_id:
        log("No ADS library id configured (`ads_library_id` in _config.yml).")
        return 1

    ads = _ads_session(token)

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
    cache = load_cache()
    # Seed the cache from papers.yml so the first run after this change keeps
    # the summaries already on the page.
    for bib, prev in existing.items():
        if not bib:
            continue
        entry = cache.setdefault(bib, {})
        for key in ("summary", "figure"):
            if prev.get(key) and not entry.get(key):
                entry[key] = prev[key]

    out: list[dict[str, Any]] = []

    for doc in chosen:
        bib = doc["bibcode"]
        title = strip_markup((doc.get("title") or [""])[0])
        log(f"\nProcessing {bib}: {title[:80]}")

        cached = cache.get(bib, {})
        figure_path = existing.get(bib, {}).get("figure") or cached.get("figure")
        summary = existing.get(bib, {}).get("summary") or cached.get("summary") or ""

        # Fall back to the cached id if ADS omits it this time round.
        ax = arxiv_id(doc) or cached.get("arxiv")
        url = f"https://ui.adsabs.harvard.edu/abs/{urllib.parse.quote(bib)}"

        # Figure: only re-run if we don't already have one on disk.
        if not (figure_path and (ROOT / figure_path.lstrip("/")).exists()) and ax:
            pdf_path = FIGURE_DIR / f"{bib.replace('/', '_')}.pdf"
            if download_arxiv_pdf(ax, pdf_path):
                try:
                    pages = render_pdf_pages(pdf_path)
                except Exception as e:
                    log(f"  PDF render failed: {e}")
                    pages = []
                if pages:
                    idx, clip = pick_figure_page(pdf_path, len(pages))
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

        # Summaries are written separately by scripts/summaries.py, run from
        # Claude Code — this pipeline never calls a model. Stash the abstract
        # so that step doesn't need an ADS token of its own.
        abstract = strip_markup(doc.get("abstract") or "")

        # Record whatever we have so it survives rotating off the front page.
        entry = cache.setdefault(bib, {})
        entry["title"] = title
        if ax:
            entry["arxiv"] = ax
        if abstract:
            entry["abstract"] = abstract
        if summary:
            entry["summary"] = summary
        if figure_path:
            entry["figure"] = figure_path

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
    save_cache(cache)
    missing = [p["bibcode"] for p in out if not p.get("summary")]
    log(f"\nWrote {DATA_FILE.relative_to(ROOT)} with {len(out)} entries.")
    log(f"Wrote {CACHE_FILE.relative_to(ROOT)} with {len(cache)} cached entries.")
    if missing:
        log(f"Awaiting summaries ({len(missing)}): {', '.join(missing)}")
        log("Run `scripts/summaries.py pending` from Claude Code to fill them in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
