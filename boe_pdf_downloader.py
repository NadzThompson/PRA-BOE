#!/usr/bin/env python3
"""
BoE PDF Downloader
===================
Downloads PDF files referenced in the PRA corpus from bankofengland.co.uk,
extracts their text content, and merges the extracted text back into the
corresponding PRA JSON files.

This handles the case where the PRA Rulebook page only shows a summary
but the actual full content (SS, SoP chapters) lives in PDFs hosted on
the Bank of England website.

Usage:
    python boe_pdf_downloader.py                    # Download all referenced PDFs
    python boe_pdf_downloader.py --extract-only     # Only extract text from already-downloaded PDFs
    python boe_pdf_downloader.py --merge-only       # Only merge extracted text into JSONs
    python boe_pdf_downloader.py --dry-run          # Preview without downloading

Prerequisites:
    pip install requests PyPDF2 --break-system-packages
"""

import os
import sys
import json
import time
import re
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

try:
    from PyPDF2 import PdfReader
except ImportError:
    print("Install PyPDF2: pip install PyPDF2 --break-system-packages")
    sys.exit(1)

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
PDF_DOWNLOAD_DIR = BASE_DIR / "BoE PDFs"
REQUEST_DELAY = 1.0  # seconds between downloads
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/pdf,*/*",
})


# ─── DOWNLOAD ─────────────────────────────────────────────────────────────────

def download_pdf(url: str, output_dir: Path) -> Optional[Path]:
    """Download a single PDF from BoE. Returns the local file path or None."""
    # Derive filename from URL
    fname = url.split("/")[-1]
    if not fname.endswith(".pdf"):
        fname += ".pdf"
    # Clean up common URL artefacts
    fname = fname.split("?")[0].split("#")[0]
    fname = re.sub(r'[^\w\-.]', '_', fname)

    out_path = output_dir / fname
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path  # Already downloaded

    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = SESSION.get(url, timeout=30, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 100:
                out_path.write_bytes(resp.content)
                return out_path
            elif resp.status_code == 404:
                print(f"    404 Not Found: {url}")
                return None
            else:
                print(f"    HTTP {resp.status_code} (attempt {attempt+1})")
        except requests.RequestException as e:
            print(f"    Error (attempt {attempt+1}): {e}")

        if attempt < RETRY_ATTEMPTS - 1:
            time.sleep(REQUEST_DELAY * RETRY_BACKOFF ** attempt)

    return None


# ─── TEXT EXTRACTION ──────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file using PyPDF2."""
    try:
        reader = PdfReader(str(pdf_path))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
        return "\n\n".join(pages)
    except Exception as e:
        print(f"    Extract error for {pdf_path.name}: {e}")
        return ""


# ─── COLLECT REFERENCED PDFs ─────────────────────────────────────────────────

def collect_pdf_references() -> dict:
    """Scan all enriched PRA JSONs for boe_pdf_urls field.

    Returns: {json_file_path: [pdf_url, ...]}
    """
    refs = {}
    for cat in ["PRA Rules", "PRA Guidance"]:
        jdir = BASE_DIR / cat / "json"
        if not jdir.exists():
            continue
        for fp in sorted(jdir.glob("*.json")):
            if fp.name.startswith("_"):
                continue
            try:
                with open(fp) as f:
                    data = json.load(f)
                boe_pdfs = data.get("boe_pdf_urls", [])
                if boe_pdfs:
                    refs[str(fp)] = boe_pdfs
            except (json.JSONDecodeError, KeyError):
                pass
    return refs


# ─── MERGE EXTRACTED TEXT INTO JSON ───────────────────────────────────────────

def merge_extracted_content(json_path: str, extracted_texts: dict, dry_run: bool = False):
    """Merge extracted PDF text into the JSON file's content.

    Adds a 'boe_pdf_content' field with the extracted text from each PDF,
    and appends the combined text to content_markdown.
    """
    with open(json_path) as f:
        data = json.load(f)

    boe_pdfs = data.get("boe_pdf_urls", [])
    if not boe_pdfs:
        return

    pdf_content = {}
    for url in boe_pdfs:
        fname = url.split("/")[-1].split("?")[0].split("#")[0]
        fname = re.sub(r'[^\w\-.]', '_', fname)
        text = extracted_texts.get(fname, "")
        if text:
            pdf_content[url] = {
                "filename": fname,
                "text_length": len(text),
                "text": text,
            }

    if not pdf_content:
        return

    # Store extracted PDF content
    data["boe_pdf_content"] = pdf_content

    # Append the most recent PDF's text to content_markdown
    # (use the last URL which is typically the latest version)
    latest_url = boe_pdfs[-1]
    if latest_url in pdf_content:
        latest_text = pdf_content[latest_url]["text"]
        existing_md = data.get("content_markdown", "")

        # Only append if the PDF text adds substantial new content
        if len(latest_text) > len(existing_md) * 0.5:
            separator = "\n\n---\n\n## Full Document Content (from BoE PDF)\n\n"
            data["content_markdown"] = existing_md + separator + latest_text

            # Recompute SHA256
            data["sha256"] = hashlib.sha256(
                data["content_markdown"].encode("utf-8")
            ).hexdigest()

    if not dry_run:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    return len(pdf_content)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BoE PDF Downloader & Content Extractor")
    parser.add_argument("--dry-run", action="store_true", help="Preview without downloading or writing")
    parser.add_argument("--extract-only", action="store_true", help="Only extract text from downloaded PDFs")
    parser.add_argument("--merge-only", action="store_true", help="Only merge extracted text into JSONs")
    parser.add_argument("--output-dir", type=Path, default=PDF_DOWNLOAD_DIR,
                       help="Directory for downloaded PDFs")
    args = parser.parse_args()

    pdf_dir = args.output_dir
    pdf_dir.mkdir(parents=True, exist_ok=True)

    # Collect all BoE PDF references from the corpus
    print("Scanning PRA corpus for BoE PDF references...")
    refs = collect_pdf_references()
    all_urls = set()
    for urls in refs.values():
        all_urls.update(urls)
    print(f"Found {len(all_urls)} unique BoE PDFs across {len(refs)} files")

    # --- Phase 1: Download ---
    if not args.extract_only and not args.merge_only:
        print(f"\n{'='*60}")
        print("PHASE 1: DOWNLOADING BoE PDFs")
        print(f"{'='*60}")

        downloaded = 0
        skipped = 0
        failed = 0

        for i, url in enumerate(sorted(all_urls), 1):
            fname = url.split("/")[-1].split("?")[0]
            print(f"  [{i}/{len(all_urls)}] {fname}...", end=" ", flush=True)

            if args.dry_run:
                print("(dry run)")
                continue

            result = download_pdf(url, pdf_dir)
            if result:
                if result.stat().st_size > 0:
                    downloaded += 1
                    print(f"OK ({result.stat().st_size:,} bytes)")
                else:
                    skipped += 1
                    print("(already exists)")
            else:
                failed += 1
                print("FAILED")

            time.sleep(REQUEST_DELAY)

        print(f"\nDownloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}")

    # --- Phase 2: Extract text ---
    if not args.merge_only:
        print(f"\n{'='*60}")
        print("PHASE 2: EXTRACTING TEXT FROM PDFs")
        print(f"{'='*60}")

    extracted_texts = {}
    for pdf_file in sorted(pdf_dir.glob("*.pdf")):
        text = extract_text_from_pdf(pdf_file)
        if text:
            extracted_texts[pdf_file.name] = text
            print(f"  ✓ {pdf_file.name}: {len(text):,} chars")
        else:
            print(f"  ✗ {pdf_file.name}: no text extracted")

    print(f"\nExtracted text from {len(extracted_texts)} PDFs")

    # --- Phase 3: Merge into JSONs ---
    print(f"\n{'='*60}")
    print("PHASE 3: MERGING EXTRACTED TEXT INTO PRA JSONs")
    print(f"{'='*60}")

    merged = 0
    for json_path, urls in sorted(refs.items()):
        fname = Path(json_path).name
        count = merge_extracted_content(json_path, extracted_texts, dry_run=args.dry_run)
        if count:
            merged += 1
            print(f"  ✓ {fname}: merged {count} PDF(s)")

    print(f"\nMerged content into {merged} JSON files")

    # --- Report ---
    report = {
        "run_date": datetime.now().isoformat(),
        "total_pdf_urls": len(all_urls),
        "files_with_references": len(refs),
        "pdfs_downloaded": len(list(pdf_dir.glob("*.pdf"))),
        "pdfs_with_text": len(extracted_texts),
        "jsons_updated": merged,
    }
    report_path = BASE_DIR / "boe_pdf_download_report.json"
    if not args.dry_run:
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to {report_path}")

    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
