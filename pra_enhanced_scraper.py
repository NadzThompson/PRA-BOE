#!/usr/bin/env python3
"""
PRA Enhanced Scraper
====================
Scrapes additional PRA Rulebook data:
1. Sector index pages (CRR, Non-CRR, SII, Non-SII, Non-authorised)
2. Rule change timelines and version history
3. Forms (759 items)
4. Legal Instruments (1,394 items)

Outputs in PDF, JSON, MD, and HTML.
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

# Import from main scraper
sys.path.insert(0, str(Path(__file__).parent))
from pra_scraper import (
    BASE_URL, DATE_PARAM, OUTPUT_DIR, SESSION, REQUEST_DELAY,
    clean_text, clean_html_content, fetch_page, PdfWriter, sanitize_for_pdf,
    save_outputs, html_to_clean_markdown, build_clean_html
)


# ─── 1. SECTOR INDEX PAGES ──────────────────────────────────────────────────

SECTORS = {
    "crr-firms": {
        "url": f"{BASE_URL}/pra-rules/crr-firms",
        "title": "CRR Firms (Capital Requirements Regulation)",
        "description": "UK banks, building societies, or UK designated investment firms subject to the CRR",
    },
    "non-crr-firms": {
        "url": f"{BASE_URL}/pra-rules/non-crr-firms",
        "title": "Non-CRR Firms",
        "description": "Firms not subject to the Capital Requirements Regulation",
    },
    "sii-firms": {
        "url": f"{BASE_URL}/pra-rules/sii-firms",
        "title": "SII Firms (Solvency II Insurance)",
        "description": "Insurance firms subject to Solvency II",
    },
    "non-sii-firms": {
        "url": f"{BASE_URL}/pra-rules/non-sii-firms",
        "title": "Non-SII Firms",
        "description": "Insurance firms not subject to Solvency II",
    },
    "non-authorised-persons": {
        "url": f"{BASE_URL}/pra-rules/non-authorised-persons",
        "title": "Non-authorised Persons",
        "description": "Persons or firms not authorised by the PRA but subject to PRA rules",
    },
}


def scrape_sector_pages():
    """Scrape the 5 sector navigation/index pages."""
    print(f"\n{'='*60}")
    print("SCRAPING SECTOR INDEX PAGES")
    print(f"{'='*60}")

    all_sectors_data = {}

    for sector_slug, sector_info in SECTORS.items():
        url = sector_info["url"]
        print(f"  Scraping {sector_slug}...")

        resp = fetch_page(url)
        if not resp:
            print(f"    FAILED")
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extract rule listings from card-block elements
        rules = []
        cards = soup.find_all('div', class_='card-block')
        for card in cards:
            # Rule title is in the main link
            title_link = card.find('a', href=lambda h: h and '/pra-rules/' in h)
            if not title_link:
                continue

            rule_title = title_link.get_text(strip=True)
            rule_href = title_link.get('href', '')

            # Extract the rule slug from href
            rule_slug = ""
            match = re.search(r'/pra-rules/([^/]+)', rule_href)
            if match:
                rule_slug = match.group(1)

            # Find which other sectors this applies to
            other_sectors = []
            bottom = card.find('div', class_='card-block__inner')
            if bottom:
                for a in bottom.find_all('a'):
                    sector_text = a.get_text(strip=True)
                    if sector_text and sector_text != rule_title:
                        other_sectors.append(sector_text)

            # Check if deleted
            is_deleted = '(deleted)' in rule_title.lower()

            rules.append({
                "title": rule_title,
                "slug": rule_slug,
                "url": f"{BASE_URL}{rule_href}" if rule_href.startswith('/') else rule_href,
                "also_applies_to": other_sectors,
                "deleted": is_deleted,
            })

        sector_data = {
            "sector": sector_info["title"],
            "description": sector_info["description"],
            "slug": sector_slug,
            "url": url,
            "as_at_date": DATE_PARAM,
            "total_rules": len(rules),
            "rules": rules,
            "scrape_date": datetime.now().isoformat(),
        }

        all_sectors_data[sector_slug] = sector_data
        print(f"    -> {len(rules)} rules found")

        # Save individual sector file
        metadata = {
            "source_url": url,
            "content_type": "Sector Index",
            "scrape_date": datetime.now().isoformat(),
            "as_at_date": DATE_PARAM,
            "title": sector_info["title"],
        }

        # Build markdown
        md_lines = [
            f"# {sector_info['title']}",
            f"",
            f"**Description:** {sector_info['description']}",
            f"**Total Rules:** {len(rules)}",
            f"**Effective Date:** {DATE_PARAM}",
            f"",
            "## Rules",
            "",
        ]
        html_lines = [
            f"<h1>{html_module.escape(sector_info['title'])}</h1>",
            f"<p><strong>Description:</strong> {html_module.escape(sector_info['description'])}</p>",
            f"<p><strong>Total Rules:</strong> {len(rules)}</p>",
            "<table><thead><tr><th>#</th><th>Rule</th><th>Also Applies To</th><th>Status</th></tr></thead><tbody>",
        ]

        for i, rule in enumerate(rules, 1):
            status = "Deleted" if rule["deleted"] else "Active"
            sectors_str = ", ".join(rule["also_applies_to"]) if rule["also_applies_to"] else "-"
            md_lines.append(f"{i}. **{rule['title']}**")
            if rule["also_applies_to"]:
                md_lines.append(f"   - Also applies to: {sectors_str}")
            if rule["deleted"]:
                md_lines.append(f"   - Status: Deleted")
            md_lines.append("")

            html_lines.append(f"<tr><td>{i}</td><td>{html_module.escape(rule['title'])}</td>")
            html_lines.append(f"<td>{html_module.escape(sectors_str)}</td><td>{status}</td></tr>")

        html_lines.append("</tbody></table>")

        save_outputs(sector_slug, sector_info["title"],
                     "\n".join(html_lines), "\n".join(md_lines), metadata, "sectors")

    # Save combined sectors mapping
    combined_path = OUTPUT_DIR / "json" / "sectors" / "all-sectors-mapping.json"
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "title": "PRA Rulebook - Complete Sector-to-Rule Mapping",
                "scrape_date": datetime.now().isoformat(),
                "as_at_date": DATE_PARAM,
            },
            "sectors": all_sectors_data
        }, f, indent=2, ensure_ascii=False)

    print(f"  Sector pages complete. Combined mapping saved.")
    return len(all_sectors_data)


# ─── 2. RULE CHANGE TIMELINES ───────────────────────────────────────────────

def scrape_rule_timelines():
    """Re-scrape each rule page to capture amendment timeline dates."""
    print(f"\n{'='*60}")
    print("SCRAPING RULE CHANGE TIMELINES")
    print(f"{'='*60}")

    # Get list of existing rule JSONs
    rules_dir = OUTPUT_DIR / "json" / "rules"
    rule_files = sorted(rules_dir.glob("*.json"))
    total = len(rule_files)
    print(f"  Processing {total} existing rules...")

    all_timelines = {}

    for i, jf in enumerate(rule_files, 1):
        with open(jf, 'r', encoding='utf-8') as f:
            data = json.load(f)

        source_url = data.get("metadata", {}).get("source_url", "")
        title = data.get("title", jf.stem)

        if not source_url:
            continue

        # Extract slug from URL
        slug = jf.stem

        # Fetch the page to get timeline data
        print(f"  [{i}/{total}] {slug}...")
        resp = fetch_page(source_url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extract timeline dates from "View Rulebook as at" links
        timeline_dates = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if f'/pra-rules/{slug}/' in href and 'View Rulebook as at' in text:
                date_match = re.search(r'(\d{2}-\d{2}-\d{4})', href)
                if date_match:
                    date_str = date_match.group(1)
                    timeline_dates.append(date_str)

        # Also extract per-rule effective dates from the content
        rule_dates = []
        # Find all date elements within rule content (dates like "19/06/2014")
        content_div = None
        chapters_container = soup.find('div', class_='chapters')
        if chapters_container:
            content_div = chapters_container.find('div', class_='col9')

        if content_div:
            for li in content_div.find_all('li', class_='list-links__item'):
                text = li.get_text(strip=True)
                date_match = re.match(r'^(\d{2}/\d{2}/\d{4})$', text)
                if date_match:
                    rule_dates.append(date_match.group(1))

        # Extract "Past version" references
        past_versions = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            if 'past' in text.lower() and 'version' in text.lower():
                version_match = re.search(r'version of (.+?) before (\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
                if version_match:
                    past_versions.append({
                        "rule_ref": version_match.group(1),
                        "changed_before": version_match.group(2),
                        "previous_url": a['href'],
                    })

        # Deduplicate
        timeline_dates = sorted(set(timeline_dates))
        rule_dates = sorted(set(rule_dates))

        timeline_data = {
            "title": title,
            "slug": slug,
            "source_url": source_url,
            "version_dates": timeline_dates,
            "rule_as_at_dates": rule_dates,
            "past_versions": past_versions,
            "total_amendments": len(timeline_dates),
        }

        all_timelines[slug] = timeline_data

        # Update the existing JSON with timeline data
        data["metadata"]["timeline"] = timeline_data
        with open(jf, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"    -> {len(timeline_dates)} version dates, {len(past_versions)} past versions")

    # Also do the same for guidance
    guidance_dir = OUTPUT_DIR / "json" / "guidance"
    guidance_files = sorted(guidance_dir.glob("*.json"))
    total_g = len(guidance_files)
    print(f"\n  Processing {total_g} existing guidance docs...")

    for i, jf in enumerate(guidance_files, 1):
        with open(jf, 'r', encoding='utf-8') as f:
            data = json.load(f)

        source_url = data.get("metadata", {}).get("source_url", "")
        title = data.get("title", jf.stem)
        slug = jf.stem

        if not source_url:
            continue

        print(f"  [{i}/{total_g}] {slug[:60]}...")
        resp = fetch_page(source_url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extract timeline for guidance
        timeline_dates = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if '/guidance/' in href and 'View' in text:
                date_match = re.search(r'(\d{2}-\d{2}-\d{4})', href)
                if date_match:
                    timeline_dates.append(date_match.group(1))

        # Bank of England links to previous versions
        boe_versions = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if 'bankofengland.co.uk' in href and text:
                boe_versions.append({"title": text, "url": href})

        timeline_dates = sorted(set(timeline_dates))

        timeline_data = {
            "title": title,
            "slug": slug,
            "version_dates": timeline_dates,
            "boe_references": boe_versions,
            "total_amendments": len(timeline_dates),
        }

        data["metadata"]["timeline"] = timeline_data
        with open(jf, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        if timeline_dates:
            print(f"    -> {len(timeline_dates)} versions")

    # Save complete timeline index
    timeline_path = OUTPUT_DIR / "json" / "rules" / "_rule_change_timelines.json"
    with open(timeline_path, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "title": "PRA Rulebook - Rule Change Timeline Index",
                "scrape_date": datetime.now().isoformat(),
                "as_at_date": DATE_PARAM,
                "total_rules": len(all_timelines),
            },
            "timelines": all_timelines
        }, f, indent=2, ensure_ascii=False)

    # Generate timeline summary outputs
    md_lines = [
        "# PRA Rulebook - Rule Change Timeline Index",
        f"",
        f"**Effective Date:** {DATE_PARAM}",
        f"**Total Rules Tracked:** {len(all_timelines)}",
        "",
        "## Timeline Summary",
        "",
        "| Rule | Amendments | Version Dates |",
        "|------|-----------|---------------|",
    ]
    for slug, tl in sorted(all_timelines.items()):
        dates_str = ", ".join(tl["version_dates"][:5])
        if len(tl["version_dates"]) > 5:
            dates_str += f" (+{len(tl['version_dates'])-5} more)"
        md_lines.append(f"| {tl['title']} | {tl['total_amendments']} | {dates_str} |")

    html_content = "<h1>PRA Rule Change Timeline Index</h1>\n"
    html_content += f"<p>Total rules: {len(all_timelines)}</p>\n"
    html_content += "<table><thead><tr><th>Rule</th><th>Amendments</th><th>Version Dates</th></tr></thead><tbody>\n"
    for slug, tl in sorted(all_timelines.items()):
        dates_str = ", ".join(tl["version_dates"])
        html_content += f"<tr><td>{html_module.escape(tl['title'])}</td><td>{tl['total_amendments']}</td><td>{dates_str}</td></tr>\n"
    html_content += "</tbody></table>"

    timeline_meta = {
        "source_url": f"{BASE_URL}/pra-rules",
        "content_type": "Timeline Index",
        "scrape_date": datetime.now().isoformat(),
        "as_at_date": DATE_PARAM,
        "title": "PRA Rule Change Timeline Index",
    }
    save_outputs("_rule-change-timelines", "PRA Rule Change Timeline Index",
                 html_content, "\n".join(md_lines), timeline_meta, "rules")

    print(f"\n  Timeline scraping complete. {len(all_timelines)} rules tracked.")
    return len(all_timelines)


# ─── 3. FORMS ───────────────────────────────────────────────────────────────

def scrape_forms():
    """Scrape all forms from the PRA Rulebook."""
    print(f"\n{'='*60}")
    print("SCRAPING PRA FORMS")
    print(f"{'='*60}")

    all_forms = []
    page = 1
    max_pages = 120  # Safety limit (759 / ~7 per page ≈ 109 pages)

    while page <= max_pages:
        if page == 1:
            url = f"{BASE_URL}/pra-rules/forms"
        else:
            url = f"{BASE_URL}/pra-rules/forms?p={page}"

        print(f"  Page {page}...")
        resp = fetch_page(url)
        if not resp:
            break

        soup = BeautifulSoup(resp.text, 'html.parser')

        cards = soup.find_all('div', class_='card-block')
        if not cards:
            print(f"    No cards found, stopping.")
            break

        page_forms = []
        for card in cards:
            form_data = extract_form_data(card)
            if form_data:
                page_forms.append(form_data)

        if not page_forms:
            break

        # Check for duplicates
        existing_titles = {f['title'] for f in all_forms}
        new_forms = [f for f in page_forms if f['title'] not in existing_titles]

        if not new_forms and page > 1:
            print(f"    All duplicates, stopping.")
            break

        all_forms.extend(new_forms)
        print(f"    -> {len(new_forms)} new forms (total: {len(all_forms)})")

        # Check for next page
        next_link = soup.find('a', string=re.compile(r'(?i)next\s*page'))
        if not next_link:
            # Also check for numbered page links
            page_links = soup.find_all('a', href=re.compile(r'p=\d+'))
            has_next = any(f'p={page+1}' in a.get('href', '') for a in page_links)
            if not has_next:
                break

        page += 1

    print(f"\n  Total forms collected: {len(all_forms)}")

    if all_forms:
        # Save forms data
        metadata = {
            "source_url": f"{BASE_URL}/pra-rules/forms",
            "content_type": "Forms",
            "scrape_date": datetime.now().isoformat(),
            "as_at_date": DATE_PARAM,
            "title": "PRA Rulebook Forms",
            "total_forms": len(all_forms),
        }

        # Build outputs
        md_lines = [
            "# PRA Rulebook Forms",
            "",
            f"**Total Forms:** {len(all_forms)}",
            f"**Effective Date:** {DATE_PARAM}",
            "",
        ]
        html_lines = [
            "<h1>PRA Rulebook Forms</h1>",
            f"<p><strong>Total Forms:</strong> {len(all_forms)}</p>",
            "<table><thead><tr><th>#</th><th>Title</th><th>Part</th><th>Rule Ref</th><th>Effective</th><th>Link</th></tr></thead><tbody>",
        ]

        for i, form in enumerate(all_forms, 1):
            md_lines.append(f"### {i}. {form['title']}")
            md_lines.append(f"- **Part:** {form.get('part', 'N/A')}")
            md_lines.append(f"- **Rule:** {form.get('rule_ref', 'N/A')}")
            md_lines.append(f"- **Effective:** {form.get('as_at_date', 'N/A')}")
            if form.get('download_url'):
                md_lines.append(f"- **Link:** [{form['title']}]({form['download_url']})")
            md_lines.append("")

            html_lines.append(f"<tr><td>{i}</td><td>{html_module.escape(form['title'])}</td>")
            html_lines.append(f"<td>{html_module.escape(form.get('part', 'N/A'))}</td>")
            html_lines.append(f"<td>{html_module.escape(form.get('rule_ref', 'N/A'))}</td>")
            html_lines.append(f"<td>{form.get('as_at_date', 'N/A')}</td>")
            link = form.get('download_url', '')
            html_lines.append(f"<td><a href='{link}'>Download</a></td></tr>")

        html_lines.append("</tbody></table>")

        save_outputs("pra-forms-complete", "PRA Rulebook Forms",
                     "\n".join(html_lines), "\n".join(md_lines), metadata, "forms")

        # Save structured JSON
        forms_json_path = OUTPUT_DIR / "json" / "forms" / "pra-forms-structured.json"
        with open(forms_json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": metadata,
                "forms": all_forms
            }, f, indent=2, ensure_ascii=False)

    return len(all_forms)


def extract_form_data(card):
    """Extract form data from a card-block element."""
    form = {}

    # Get full text for parsing
    text = card.get_text(strip=True)
    if not text or len(text) < 10:
        return None

    # Title - the main link text
    main_link = card.find('a', href=lambda h: h and ('bankofengland.co.uk' in h or '/-/media/' in h))
    if main_link:
        # The title is the text of the main link, but we need to strip "Effective: DD/MM/YYYY" prefix
        full_text = main_link.get_text(strip=True)
        # Remove "Effective:..." prefix
        title_match = re.sub(r'^Effective:\s*\d{2}/\d{2}/\d{4}', '', full_text).strip()
        form['title'] = title_match if title_match else full_text
        form['download_url'] = main_link.get('href', '')
    else:
        # Fallback: get title from card text
        form['title'] = text[:200]
        form['download_url'] = ''

    # Effective date
    date_match = re.search(r'Effective:\s*(\d{2}/\d{2}/\d{4})', text)
    if date_match:
        form['as_at_date'] = date_match.group(1)

    # Part
    bottom = card.find('div', class_='card-block__inner')
    if bottom:
        part_links = bottom.find_all('a', href=lambda h: h and '/pra-rules/' in h)
        if part_links:
            form['part'] = part_links[0].get_text(strip=True)
            if len(part_links) > 1:
                form['rule_ref'] = part_links[1].get_text(strip=True)
            else:
                form['rule_ref'] = ''
        else:
            form['part'] = ''
            form['rule_ref'] = ''
    else:
        form['part'] = ''
        form['rule_ref'] = ''

    return form if form.get('title') else None


# ─── 4. LEGAL INSTRUMENTS ───────────────────────────────────────────────────

def scrape_legal_instruments():
    """Scrape all legal instruments."""
    print(f"\n{'='*60}")
    print("SCRAPING LEGAL INSTRUMENTS")
    print(f"{'='*60}")

    all_instruments = []
    page = 1
    max_pages = 240  # Safety limit (1394 / ~6 per page ≈ 233 pages)

    while page <= max_pages:
        if page == 1:
            url = f"{BASE_URL}/legal-instruments"
        else:
            url = f"{BASE_URL}/legal-instruments?p={page}"

        print(f"  Page {page}...", end=" ", flush=True)
        resp = fetch_page(url)
        if not resp:
            print("FAILED")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')

        cards = soup.find_all('div', class_='card-block')
        if not cards:
            print("No cards, stopping.")
            break

        page_instruments = []
        for card in cards:
            inst = extract_legal_instrument(card)
            if inst:
                page_instruments.append(inst)

        if not page_instruments:
            print("No instruments parsed, stopping.")
            break

        # Check for duplicates by reference
        existing_refs = {i.get('reference', '') for i in all_instruments}
        new_instruments = [i for i in page_instruments if i.get('reference', '') not in existing_refs]

        if not new_instruments and page > 1:
            print("All duplicates, stopping.")
            break

        all_instruments.extend(new_instruments)
        print(f"{len(new_instruments)} new (total: {len(all_instruments)})")

        # Check for next page
        next_link = soup.find('a', string=re.compile(r'(?i)next\s*page'))
        if not next_link:
            page_links = soup.find_all('a', href=re.compile(r'p=\d+'))
            has_next = any(f'p={page+1}' in a.get('href', '') for a in page_links)
            if not has_next:
                break

        page += 1

    print(f"\n  Total legal instruments collected: {len(all_instruments)}")

    if all_instruments:
        metadata = {
            "source_url": f"{BASE_URL}/legal-instruments",
            "content_type": "Legal Instruments",
            "scrape_date": datetime.now().isoformat(),
            "as_at_date": DATE_PARAM,
            "title": "PRA Legal Instruments",
            "total_instruments": len(all_instruments),
        }

        # Build outputs
        md_lines = [
            "# PRA Legal Instruments",
            "",
            f"**Total Instruments:** {len(all_instruments)}",
            "",
        ]
        html_lines = [
            "<h1>PRA Legal Instruments</h1>",
            f"<p><strong>Total:</strong> {len(all_instruments)}</p>",
            "<table><thead><tr><th>#</th><th>Reference</th><th>Title</th><th>Published</th><th>Effective</th><th>Affected Parts</th><th>PDF</th></tr></thead><tbody>",
        ]

        for i, inst in enumerate(all_instruments, 1):
            parts_str = ", ".join(inst.get('affected_parts', [])) if inst.get('affected_parts') else "N/A"
            md_lines.append(f"### {i}. {inst.get('reference', 'N/A')} - {inst.get('title', 'N/A')}")
            md_lines.append(f"- **Published:** {inst.get('published_date', 'N/A')}")
            md_lines.append(f"- **Effective:** {inst.get('as_at_date', 'N/A')}")
            md_lines.append(f"- **Affected Parts:** {parts_str}")
            if inst.get('pdf_url'):
                md_lines.append(f"- **PDF:** [{inst['reference']}]({inst['pdf_url']})")
            if inst.get('policy_statement'):
                md_lines.append(f"- **Policy Statement:** [{inst['policy_statement']['title']}]({inst['policy_statement']['url']})")
            md_lines.append("")

            html_lines.append(f"<tr><td>{i}</td><td>{html_module.escape(inst.get('reference', ''))}</td>")
            html_lines.append(f"<td>{html_module.escape(inst.get('title', ''))}</td>")
            html_lines.append(f"<td>{inst.get('published_date', '')}</td>")
            html_lines.append(f"<td>{inst.get('as_at_date', '')}</td>")
            html_lines.append(f"<td>{html_module.escape(parts_str[:100])}</td>")
            pdf = inst.get('pdf_url', '')
            html_lines.append(f"<td><a href='{pdf}'>PDF</a></td></tr>")

        html_lines.append("</tbody></table>")

        save_outputs("pra-legal-instruments-complete", "PRA Legal Instruments",
                     "\n".join(html_lines), "\n".join(md_lines), metadata, "legal-instruments")

        # Structured JSON
        li_json_path = OUTPUT_DIR / "json" / "legal-instruments" / "pra-legal-instruments-structured.json"
        with open(li_json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": metadata,
                "instruments": all_instruments
            }, f, indent=2, ensure_ascii=False)

        # Also save by year
        by_year = {}
        for inst in all_instruments:
            year_match = re.search(r'(\d{4})', inst.get('published_date', ''))
            if year_match:
                year = year_match.group(1)
                by_year.setdefault(year, []).append(inst)

        for year, instruments in sorted(by_year.items()):
            year_meta = {**metadata, "title": f"PRA Legal Instruments - {year}", "total_instruments": len(instruments)}
            year_md = [f"# PRA Legal Instruments - {year}\n\n**Total:** {len(instruments)}\n"]
            for inst in instruments:
                year_md.append(f"### {inst.get('reference', 'N/A')} - {inst.get('title', 'N/A')}")
                year_md.append(f"- Published: {inst.get('published_date', '')}, Effective: {inst.get('as_at_date', '')}")
                year_md.append("")

            save_outputs(f"legal-instruments-{year}", f"PRA Legal Instruments - {year}",
                         f"<h1>Legal Instruments {year}</h1><p>{len(instruments)} instruments</p>",
                         "\n".join(year_md), year_meta, "legal-instruments")

    return len(all_instruments)


def extract_legal_instrument(card):
    """Extract legal instrument data from a card-block element."""
    inst = {}
    text = card.get_text(strip=True)
    if not text or len(text) < 10:
        return None

    # PDF link - the main document link
    pdf_link = card.find('a', href=lambda h: h and ('/-/media/' in h or '.pdf' in str(h).lower()))
    if pdf_link:
        link_text = pdf_link.get_text(strip=True)
        inst['pdf_url'] = pdf_link['href']
        if inst['pdf_url'].startswith('/'):
            inst['pdf_url'] = f"{BASE_URL}{inst['pdf_url']}"

        # Parse reference and title from link text
        # Format: "Published: DD/MM/YYYYPRA20XX/N - Title"
        ref_match = re.search(r'(PRA\d{4}/\d+)\s*-\s*(.+)', link_text)
        if ref_match:
            inst['reference'] = ref_match.group(1)
            inst['title'] = ref_match.group(2).strip()
        else:
            inst['title'] = link_text
            inst['reference'] = ''

        # Published date
        pub_match = re.search(r'Published:\s*(\d{2}/\d{2}/\d{4})', link_text)
        if pub_match:
            inst['published_date'] = pub_match.group(1)
    else:
        return None

    # Effective date(s)
    eff_match = re.search(r'Effective:\s*(\d{2}/\d{2}/\d{4})', text)
    if eff_match:
        inst['as_at_date'] = eff_match.group(1)
    else:
        inst['as_at_date'] = ''

    # All effective dates (some instruments have multiple)
    all_eff = re.findall(r'Effective:\s*(\d{2}/\d{2}/\d{4})', text)
    if len(all_eff) > 1:
        inst['as_at_dates'] = all_eff

    # Affected parts
    affected_parts = []
    for a in card.find_all('a', href=lambda h: h and '/pra-rules/' in h):
        part_name = a.get_text(strip=True)
        if part_name and part_name not in affected_parts:
            affected_parts.append(part_name)
    inst['affected_parts'] = affected_parts

    # Policy statement
    ps_link = card.find('a', href=lambda h: h and 'bankofengland.co.uk' in h)
    if ps_link:
        inst['policy_statement'] = {
            "title": ps_link.get_text(strip=True),
            "url": ps_link['href'],
        }

    # Glossary link
    glossary_link = card.find('a', href=lambda h: h and '/glossary' in h)
    if glossary_link:
        inst['glossary_url'] = glossary_link['href']

    return inst


# ─── 5. MAIN RULES/GUIDANCE PAGE INDEXES ────────────────────────────────────

def scrape_main_index_pages():
    """Scrape the main PRA rules and guidance index pages."""
    print(f"\n{'='*60}")
    print("SCRAPING MAIN INDEX PAGES")
    print(f"{'='*60}")

    index_pages = {
        "pra-rules-index": f"{BASE_URL}/pra-rules",
        "guidance-index": f"{BASE_URL}/guidance",
    }

    for slug, url in index_pages.items():
        print(f"  Scraping {slug}...")
        resp = fetch_page(url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')
        soup_clean = BeautifulSoup(resp.text, 'html.parser')
        soup_clean = clean_html_content(soup_clean)

        # Extract all rule/guidance links
        items = []
        for card in soup.find_all('div', class_='card-block'):
            title_el = card.find('a')
            if title_el:
                items.append({
                    "title": title_el.get_text(strip=True),
                    "url": title_el.get('href', ''),
                })

        metadata = {
            "source_url": url,
            "content_type": "Index Page",
            "scrape_date": datetime.now().isoformat(),
            "as_at_date": DATE_PARAM,
            "title": f"PRA Rulebook - {'Rules' if 'rules' in slug else 'Guidance'} Index",
            "total_items": len(items),
        }

        # Build clean content
        md_lines = [f"# {metadata['title']}\n\n**Total Items:** {len(items)}\n"]
        for i, item in enumerate(items, 1):
            md_lines.append(f"{i}. [{item['title']}]({item['url']})")

        content_html = f"<h1>{metadata['title']}</h1><p>Total: {len(items)}</p><ol>"
        for item in items:
            content_html += f"<li><a href='{item['url']}'>{html_module.escape(item['title'])}</a></li>"
        content_html += "</ol>"

        save_outputs(slug, metadata["title"], content_html, "\n".join(md_lines), metadata, "rules" if "rules" in slug else "guidance")

        print(f"    -> {len(items)} items")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    print("=" * 60)
    print("PRA ENHANCED SCRAPER")
    print(f"Date: {DATE_PARAM}")
    print("=" * 60)

    # Phase 1: Sector pages
    sectors = scrape_sector_pages()

    # Phase 2: Main index pages
    scrape_main_index_pages()

    # Phase 3: Rule change timelines
    timelines = scrape_rule_timelines()

    # Phase 4: Forms
    forms = scrape_forms()

    # Phase 5: Legal instruments
    instruments = scrape_legal_instruments()

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print("ENHANCED SCRAPE COMPLETE")
    print(f"{'='*60}")
    print(f"Sectors:          {sectors}")
    print(f"Timelines:        {timelines} rules enhanced")
    print(f"Forms:            {forms}")
    print(f"Legal Instruments: {instruments}")
    print(f"Time:             {elapsed:.1f}s ({elapsed/60:.1f}min)")

    # Final counts
    print(f"\nOutput directories:")
    for fmt in ['pdf', 'json', 'md', 'html']:
        for cat in ['rules', 'guidance', 'glossary', 'sectors', 'forms', 'legal-instruments']:
            p = OUTPUT_DIR / fmt / cat
            count = len(list(p.glob('*'))) if p.exists() else 0
            if count > 0:
                print(f"  {fmt}/{cat}: {count} files")


if __name__ == "__main__":
    main()
