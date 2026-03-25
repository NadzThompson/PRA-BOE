#!/usr/bin/env python3
"""Fix missing PDFs and re-scrape glossary."""
import sys
import warnings
import json
import os
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))

from pra_scraper import *

OUTPUT_DIR_PATH = Path(r"C:\Users\nadin\OneDrive\Documents\NOVA\PRA")

def fix_missing_pdfs():
    """Regenerate PDFs for rules/guidance that have JSON but no PDF."""
    print("=" * 60)
    print("FIXING MISSING PDFs")
    print("=" * 60)

    fixed = 0
    for category in ['rules', 'guidance']:
        json_dir = OUTPUT_DIR_PATH / "json" / category
        pdf_dir = OUTPUT_DIR_PATH / "pdf" / category

        for json_file in sorted(json_dir.glob("*.json")):
            pdf_file = pdf_dir / f"{json_file.stem}.pdf"
            if not pdf_file.exists():
                print(f"  Regenerating PDF: {json_file.stem}")
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    title = data.get("title", json_file.stem)
                    metadata = data.get("metadata", {})
                    md_text = data.get("content_markdown", "")

                    pdf = PdfWriter()
                    pdf.add_page()
                    pdf.add_title(title)
                    pdf.add_metadata(metadata)
                    pdf.add_body_text(md_text)
                    pdf.output(str(pdf_file))
                    fixed += 1
                    print(f"    -> OK")
                except Exception as e:
                    print(f"    -> FAILED: {e}")

    print(f"\nFixed {fixed} PDFs")

def rescrape_glossary():
    """Re-scrape the glossary with improved extraction."""
    print("\n" + "=" * 60)
    print("RE-SCRAPING GLOSSARY")
    print("=" * 60)

    count = scrape_glossary()
    print(f"\nGlossary terms: {count}")

if __name__ == "__main__":
    fix_missing_pdfs()
    rescrape_glossary()

    # Print final stats
    print("\n" + "=" * 60)
    print("FINAL FILE COUNTS")
    print("=" * 60)
    for fmt in ['pdf', 'json', 'md', 'html']:
        for cat in ['rules', 'guidance', 'glossary']:
            p = OUTPUT_DIR_PATH / fmt / cat
            count = len(list(p.glob('*'))) if p.exists() else 0
            print(f"  {fmt}/{cat}: {count} files")
