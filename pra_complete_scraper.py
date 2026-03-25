#!/usr/bin/env python3
"""
PRA Complete Scraper - Phase 3
===============================
1. Fix forms pagination (759 items, page= param)
2. Fix legal instruments pagination (1394 items, page= param)
3. Identify and scrape BoE-hosted guidance documents (not yet in PRA Rulebook)
4. Re-scrape empty guidance pages to find BoE links
"""

import os
import sys
import json
import time
import re
import html as html_module
import traceback
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

import requests
from bs4 import BeautifulSoup, Comment
import html2text

sys.path.insert(0, str(Path(__file__).parent))
from pra_scraper import (
    BASE_URL, DATE_PARAM, OUTPUT_DIR, SESSION, REQUEST_DELAY,
    clean_text, fetch_page, PdfWriter, sanitize_for_pdf,
    save_outputs, html_to_clean_markdown, build_clean_html
)


# ─── 1. FORMS (with correct pagination) ─────────────────────────────────────

def scrape_all_forms():
    """Scrape all 759 forms using page= pagination."""
    print(f"\n{'='*60}")
    print("SCRAPING ALL PRA FORMS (759 expected)")
    print(f"{'='*60}")

    all_forms = []
    page = 1
    max_pages = 115

    while page <= max_pages:
        url = f"{BASE_URL}/pra-rules/forms?page={page}"
        print(f"  Page {page}...", end=" ", flush=True)

        resp = fetch_page(url)
        if not resp:
            print("FAILED")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.find_all('div', class_='card-block')

        if not cards:
            print("No cards, done.")
            break

        page_forms = []
        for card in cards:
            form = extract_form(card)
            if form:
                page_forms.append(form)

        if not page_forms:
            print("No forms parsed, done.")
            break

        all_forms.extend(page_forms)
        print(f"{len(page_forms)} forms (total: {len(all_forms)})")

        # Stop if we got fewer than expected per page (last page)
        if len(cards) < 7:
            break

        page += 1

    print(f"\n  Total forms collected: {len(all_forms)}")

    # Save outputs
    if all_forms:
        metadata = {
            "source_url": f"{BASE_URL}/pra-rules/forms",
            "content_type": "Forms",
            "scrape_date": datetime.now().isoformat(),
            "as_at_date": DATE_PARAM,
            "title": "PRA Rulebook Forms",
            "total_forms": len(all_forms),
        }

        # Structured JSON
        with open(OUTPUT_DIR / "json" / "forms" / "pra-forms-structured.json", 'w', encoding='utf-8') as f:
            json.dump({"metadata": metadata, "forms": all_forms}, f, indent=2, ensure_ascii=False)

        # MD
        md_lines = [
            "# PRA Rulebook Forms",
            f"\n**Total Forms:** {len(all_forms)}\n",
        ]
        html_lines = [
            "<h1>PRA Rulebook Forms</h1>",
            f"<p><strong>Total:</strong> {len(all_forms)}</p>",
            "<table><thead><tr><th>#</th><th>Title</th><th>Part</th><th>Rule</th><th>Effective</th></tr></thead><tbody>",
        ]

        for i, form in enumerate(all_forms, 1):
            md_lines.append(f"{i}. **{form['title']}**")
            md_lines.append(f"   - Part: {form.get('part', 'N/A')}")
            md_lines.append(f"   - Rule: {form.get('rule_ref', 'N/A')}")
            md_lines.append(f"   - Effective: {form.get('as_at_date', 'N/A')}")
            if form.get('download_url'):
                md_lines.append(f"   - [Download]({form['download_url']})")
            md_lines.append("")

            html_lines.append(f"<tr><td>{i}</td><td>{html_module.escape(form['title'])}</td>")
            html_lines.append(f"<td>{html_module.escape(form.get('part', ''))}</td>")
            html_lines.append(f"<td>{html_module.escape(form.get('rule_ref', ''))}</td>")
            html_lines.append(f"<td>{form.get('as_at_date', '')}</td></tr>")

        html_lines.append("</tbody></table>")

        save_outputs("pra-forms-complete", "PRA Rulebook Forms",
                     "\n".join(html_lines), "\n".join(md_lines), metadata, "forms")

    return len(all_forms)


def extract_form(card):
    """Extract form data from a card-block."""
    text = card.get_text(strip=True)
    if not text or len(text) < 10:
        return None

    form = {}

    # Main link (usually to BoE PDF)
    main_link = card.find('a', href=lambda h: h and ('bankofengland.co.uk' in h or '/-/media/' in h))
    if main_link:
        link_text = main_link.get_text(strip=True)
        form['download_url'] = main_link.get('href', '')
        # Remove "Effective:..." prefix from title
        title = re.sub(r'^Effective:\s*\d{2}/\d{2}/\d{4}\s*', '', link_text).strip()
        form['title'] = title if title else link_text
    else:
        form['title'] = re.sub(r'^Effective:\s*\d{2}/\d{2}/\d{4}\s*', '', text[:200]).strip()
        form['download_url'] = ''

    # Effective date
    date_match = re.search(r'Effective:\s*(\d{2}/\d{2}/\d{4})', text)
    form['as_at_date'] = date_match.group(1) if date_match else ''

    # Part and Rule
    bottom = card.find('div', class_='card-block__inner')
    if bottom:
        part_links = bottom.find_all('a', href=lambda h: h and '/pra-rules/' in h)
        form['part'] = part_links[0].get_text(strip=True) if len(part_links) > 0 else ''
        form['rule_ref'] = part_links[1].get_text(strip=True) if len(part_links) > 1 else ''
    else:
        # Try to parse from text
        part_match = re.search(r'Part:(.+?)(?:Rule:|$)', text)
        form['part'] = part_match.group(1).strip() if part_match else ''
        rule_match = re.search(r'Rule:(.+?)$', text)
        form['rule_ref'] = rule_match.group(1).strip() if rule_match else ''

    return form if form.get('title') else None


# ─── 2. LEGAL INSTRUMENTS (with correct pagination) ─────────────────────────

def scrape_all_legal_instruments():
    """Scrape all 1394 legal instruments using page= pagination."""
    print(f"\n{'='*60}")
    print("SCRAPING ALL LEGAL INSTRUMENTS (1394 expected)")
    print(f"{'='*60}")

    all_instruments = []
    page = 1
    max_pages = 240

    while page <= max_pages:
        url = f"{BASE_URL}/legal-instruments?page={page}"
        print(f"  Page {page}...", end=" ", flush=True)

        resp = fetch_page(url)
        if not resp:
            print("FAILED")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.find_all('div', class_='card-block')

        if not cards:
            print("No cards, done.")
            break

        page_instruments = []
        for card in cards:
            inst = extract_instrument(card)
            if inst:
                page_instruments.append(inst)

        if not page_instruments:
            print("No instruments parsed, done.")
            break

        all_instruments.extend(page_instruments)
        print(f"{len(page_instruments)} instruments (total: {len(all_instruments)})")

        if len(cards) < 6:
            break

        page += 1

    print(f"\n  Total legal instruments collected: {len(all_instruments)}")

    # Save outputs
    if all_instruments:
        metadata = {
            "source_url": f"{BASE_URL}/legal-instruments",
            "content_type": "Legal Instruments",
            "scrape_date": datetime.now().isoformat(),
            "as_at_date": DATE_PARAM,
            "title": "PRA Legal Instruments",
            "total_instruments": len(all_instruments),
        }

        # Structured JSON
        with open(OUTPUT_DIR / "json" / "legal-instruments" / "pra-legal-instruments-structured.json", 'w', encoding='utf-8') as f:
            json.dump({"metadata": metadata, "instruments": all_instruments}, f, indent=2, ensure_ascii=False)

        # MD
        md_lines = [
            "# PRA Legal Instruments",
            f"\n**Total:** {len(all_instruments)}\n",
        ]
        html_lines = [
            "<h1>PRA Legal Instruments</h1>",
            f"<p><strong>Total:</strong> {len(all_instruments)}</p>",
            "<table><thead><tr><th>#</th><th>Reference</th><th>Title</th><th>Published</th><th>Effective</th><th>Affected Parts</th></tr></thead><tbody>",
        ]

        for i, inst in enumerate(all_instruments, 1):
            parts = ", ".join(inst.get('affected_parts', [])[:5])
            if len(inst.get('affected_parts', [])) > 5:
                parts += f" (+{len(inst['affected_parts'])-5} more)"

            md_lines.append(f"### {inst.get('reference', 'N/A')}")
            md_lines.append(f"**{inst.get('title', 'N/A')}**")
            md_lines.append(f"- Published: {inst.get('published_date', 'N/A')}")
            md_lines.append(f"- Effective: {', '.join(inst.get('as_at_dates', [inst.get('as_at_date', 'N/A')]))}")
            md_lines.append(f"- Affected Parts: {parts}")
            if inst.get('pdf_url'):
                md_lines.append(f"- [PDF]({inst['pdf_url']})")
            if inst.get('policy_statement'):
                md_lines.append(f"- Policy Statement: [{inst['policy_statement']['title']}]({inst['policy_statement']['url']})")
            md_lines.append("")

            html_lines.append(f"<tr><td>{i}</td><td>{html_module.escape(inst.get('reference', ''))}</td>")
            html_lines.append(f"<td>{html_module.escape(inst.get('title', ''))}</td>")
            html_lines.append(f"<td>{inst.get('published_date', '')}</td>")
            html_lines.append(f"<td>{', '.join(inst.get('as_at_dates', [inst.get('as_at_date', '')]))}</td>")
            html_lines.append(f"<td>{html_module.escape(parts)}</td></tr>")

        html_lines.append("</tbody></table>")

        save_outputs("pra-legal-instruments-complete", "PRA Legal Instruments",
                     "\n".join(html_lines), "\n".join(md_lines), metadata, "legal-instruments")

        # Save by year
        by_year = {}
        for inst in all_instruments:
            year_match = re.search(r'(\d{4})', inst.get('published_date', ''))
            year = year_match.group(1) if year_match else 'Unknown'
            by_year.setdefault(year, []).append(inst)

        for year, instruments in sorted(by_year.items()):
            year_meta = {**metadata, "title": f"PRA Legal Instruments - {year}", "total_instruments": len(instruments)}
            year_md = [f"# PRA Legal Instruments - {year}\n\n**Total:** {len(instruments)}\n"]
            for inst in instruments:
                year_md.append(f"- **{inst.get('reference', '')}**: {inst.get('title', '')} (Published: {inst.get('published_date', '')})")

            save_outputs(f"legal-instruments-{year}", f"PRA Legal Instruments - {year}",
                         f"<h1>Legal Instruments {year}</h1><p>{len(instruments)} instruments</p>",
                         "\n".join(year_md), year_meta, "legal-instruments")

    return len(all_instruments)


def extract_instrument(card):
    """Extract legal instrument data from card-block."""
    text = card.get_text(strip=True)
    if not text or len(text) < 10:
        return None

    inst = {}

    # PDF link
    pdf_link = card.find('a', href=lambda h: h and ('/-/media/' in h or '.pdf' in str(h).lower()))
    if pdf_link:
        inst['pdf_url'] = pdf_link['href']
        if inst['pdf_url'].startswith('/'):
            inst['pdf_url'] = f"{BASE_URL}{inst['pdf_url']}"

        link_text = pdf_link.get_text(strip=True)
        ref_match = re.search(r'(PRA\d{4}/\d+)\s*-\s*(.+)', link_text)
        if ref_match:
            inst['reference'] = ref_match.group(1)
            inst['title'] = ref_match.group(2).strip()
        else:
            inst['reference'] = ''
            inst['title'] = link_text

        pub_match = re.search(r'Published:\s*(\d{2}/\d{2}/\d{4})', link_text)
        inst['published_date'] = pub_match.group(1) if pub_match else ''
    else:
        return None

    # All effective dates
    inst['as_at_dates'] = re.findall(r'Effective:\s*(\d{2}/\d{2}/\d{4})', text)
    inst['as_at_date'] = inst['as_at_dates'][0] if inst['as_at_dates'] else ''

    # Affected parts
    inst['affected_parts'] = []
    for a in card.find_all('a', href=lambda h: h and '/pra-rules/' in h):
        part = a.get_text(strip=True)
        if part and part not in inst['affected_parts']:
            inst['affected_parts'].append(part)

    # Policy statement
    ps_link = card.find('a', href=lambda h: h and 'bankofengland.co.uk' in h and '/prudential-regulation/' in h)
    if ps_link:
        inst['policy_statement'] = {
            "title": ps_link.get_text(strip=True),
            "url": ps_link['href'],
        }

    return inst


# ─── 3. BOE-HOSTED GUIDANCE DOCUMENTS ───────────────────────────────────────

def scrape_boe_guidance():
    """Find and scrape guidance documents not yet added to PRA Rulebook."""
    print(f"\n{'='*60}")
    print("SCRAPING BOE-HOSTED GUIDANCE (not yet in PRA Rulebook)")
    print(f"{'='*60}")

    # Scan existing guidance JSONs for empty content
    guidance_dir = OUTPUT_DIR / "json" / "guidance"
    empty_docs = []

    for jf in sorted(guidance_dir.glob("*.json")):
        if jf.name.startswith('_'):
            continue
        with open(jf, 'r', encoding='utf-8') as f:
            data = json.load(f)

        md_content = data.get("content_markdown", "")
        if len(md_content.strip()) < 50:
            empty_docs.append((jf, data))

    print(f"  Found {len(empty_docs)} empty/minimal guidance documents")

    boe_scraped = 0
    boe_links_found = []

    for jf, data in empty_docs:
        title = data.get("title", jf.stem)
        source_url = data.get("metadata", {}).get("source_url", "")

        if not source_url:
            continue

        print(f"  Re-fetching: {title[:70]}...")

        # Re-fetch the PRA page to find the BoE link
        resp = fetch_page(source_url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Look for "Bank of England website" link
        boe_link = None
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True).lower()
            if 'bankofengland.co.uk' in href:
                if 'prudential-regulation' in href or 'statement-of-policy' in href or 'supervisory-statement' in href:
                    boe_link = href
                    break
                elif any(kw in text for kw in ['here', 'available', 'website']):
                    boe_link = href
                    break

        # Also look for PDF links on BoE
        boe_pdf = None
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'bankofengland.co.uk' in href and '.pdf' in href:
                boe_pdf = href
                break

        # Extract "Used in" sectors
        sectors = []
        col3 = None
        chapters = soup.find('div', class_='chapters')
        if chapters:
            col3 = chapters.find('div', class_='col3')
        if col3:
            used_in = col3.find('h2', string=re.compile(r'(?i)used in'))
            if used_in:
                ul = used_in.find_next('ul')
                if ul:
                    for li in ul.find_all('li'):
                        s = li.get_text(strip=True)
                        if s and 'legal instrument' not in s.lower():
                            sectors.append(s)

        # Extract related guidance/PS links
        related_ps = []
        if col3:
            for a in col3.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True)
                if 'bankofengland.co.uk' in href and text:
                    related_ps.append({"title": text, "url": href})

        # Update metadata
        data["metadata"]["applies_to"] = sectors
        data["metadata"]["boe_page_url"] = boe_link or ""
        data["metadata"]["boe_pdf_url"] = boe_pdf or ""
        data["metadata"]["related_policy_statements"] = related_ps
        data["metadata"]["not_yet_in_rulebook"] = True

        # If we found a BoE page, try to scrape it
        if boe_link:
            print(f"    BoE link: {boe_link[:80]}")
            boe_links_found.append({
                "title": title,
                "pra_url": source_url,
                "boe_url": boe_link,
                "boe_pdf": boe_pdf,
                "sectors": sectors,
            })

            boe_resp = fetch_page(boe_link)
            if boe_resp:
                boe_soup = BeautifulSoup(boe_resp.text, 'html.parser')

                # Extract content from BoE page
                # BoE pages have content in <main> or <article> or <div class="page-content">
                main_el = (
                    boe_soup.find('article') or
                    boe_soup.find('main') or
                    boe_soup.find('div', class_='page-content') or
                    boe_soup.find('div', id='content')
                )

                if main_el:
                    # Clean BoE-specific noise
                    for tag in main_el.find_all(['script', 'style', 'noscript', 'nav', 'footer']):
                        tag.decompose()
                    for tag in main_el.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ['cookie', 'share', 'sidebar', 'navigation', 'breadcrumb'])):
                        tag.decompose()

                    # Convert to markdown
                    h2t = html2text.HTML2Text()
                    h2t.ignore_links = False
                    h2t.ignore_images = True
                    h2t.body_width = 0
                    h2t.unicode_snob = True
                    boe_md = h2t.handle(str(main_el))
                    boe_md = clean_text(boe_md)

                    # Remove BoE noise lines
                    boe_lines = boe_md.split('\n')
                    clean_lines = []
                    for line in boe_lines:
                        stripped = line.strip()
                        if any(kw in stripped.lower() for kw in [
                            'convert this page to pdf', 'share this page',
                            'email this page', 'print this page',
                            'subscribe to', 'follow bank of england',
                            'cookie', 'accessibility',
                        ]):
                            continue
                        clean_lines.append(line)
                    boe_md = '\n'.join(clean_lines)
                    boe_md = re.sub(r'\n{3,}', '\n\n', boe_md).strip()

                    if len(boe_md) > 100:
                        data["content_markdown"] = boe_md
                        data["content_html"] = str(main_el)
                        data["metadata"]["content_source"] = "Bank of England website"
                        boe_scraped += 1
                        print(f"    -> Scraped {len(boe_md)} chars from BoE")

        # Also try the PDF
        if boe_pdf and len(data.get("content_markdown", "").strip()) < 100:
            data["metadata"]["boe_pdf_url"] = boe_pdf
            data["metadata"]["content_source"] = "PDF on Bank of England website (not scraped - requires PDF parser)"

        # Save updated JSON
        with open(jf, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Regenerate other formats if we got content
        if len(data.get("content_markdown", "").strip()) > 100:
            save_outputs(jf.stem, title,
                         data.get("content_html", ""),
                         data.get("content_markdown", ""),
                         data.get("metadata", {}), "guidance")

    # Save BoE links index
    boe_index_path = OUTPUT_DIR / "json" / "guidance" / "_boe-hosted-guidance-index.json"
    with open(boe_index_path, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "title": "PRA Guidance Documents Hosted on Bank of England Website",
                "description": "These guidance documents are referenced in the PRA Rulebook but their full content is hosted on the Bank of England website.",
                "scrape_date": datetime.now().isoformat(),
                "total_documents": len(boe_links_found),
                "scraped_from_boe": boe_scraped,
            },
            "documents": boe_links_found
        }, f, indent=2, ensure_ascii=False)

    # Generate summary MD
    md_lines = [
        "# PRA Guidance - Bank of England Hosted Documents",
        "",
        f"**Total documents not yet in PRA Rulebook:** {len(boe_links_found)}",
        f"**Successfully scraped from BoE:** {boe_scraped}",
        "",
        "## Documents",
        "",
    ]
    for doc in boe_links_found:
        md_lines.append(f"### {doc['title']}")
        md_lines.append(f"- PRA Rulebook: [{doc['pra_url']}]({doc['pra_url']})")
        md_lines.append(f"- Bank of England: [{doc['boe_url']}]({doc['boe_url']})")
        if doc.get('boe_pdf'):
            md_lines.append(f"- PDF: [{doc['boe_pdf']}]({doc['boe_pdf']})")
        if doc.get('sectors'):
            md_lines.append(f"- Applies to: {', '.join(doc['sectors'])}")
        md_lines.append("")

    save_outputs("_boe-hosted-guidance-index", "PRA Guidance - BoE Hosted Documents",
                 "", "\n".join(md_lines),
                 {"source_url": BASE_URL, "content_type": "Index", "scrape_date": datetime.now().isoformat(),
                  "as_at_date": DATE_PARAM, "title": "BoE Hosted Guidance Index"},
                 "guidance")

    print(f"\n  BoE guidance: {len(boe_links_found)} found, {boe_scraped} scraped")
    return boe_scraped


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    print("=" * 60)
    print("PRA COMPLETE SCRAPER - PHASE 3")
    print("=" * 60)

    # 1. Forms
    forms = scrape_all_forms()

    # 2. Legal Instruments
    instruments = scrape_all_legal_instruments()

    # 3. BoE-hosted guidance
    boe = scrape_boe_guidance()

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print("PHASE 3 COMPLETE")
    print(f"{'='*60}")
    print(f"Forms:              {forms}")
    print(f"Legal Instruments:  {instruments}")
    print(f"BoE Guidance:       {boe} scraped")
    print(f"Time:               {elapsed:.1f}s ({elapsed/60:.1f}min)")

    print(f"\nFinal file counts:")
    for fmt in ['pdf', 'json', 'md', 'html']:
        for cat in ['rules', 'guidance', 'glossary', 'sectors', 'forms', 'legal-instruments']:
            p = OUTPUT_DIR / fmt / cat
            count = len(list(p.glob('*'))) if p.exists() else 0
            if count > 0:
                print(f"  {fmt}/{cat}: {count} files")


if __name__ == "__main__":
    main()
