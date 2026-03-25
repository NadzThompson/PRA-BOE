#!/usr/bin/env python3
"""
Bank of England Prudential Regulation Publications Scraper
===========================================================
Scrapes Bank of England prudential regulation publications (Policy Statements,
Supervisory Statements, Consultation Papers, Letters) from the BoE website and
outputs NOVA-compatible JSON files along with HTML and Markdown versions.

Supports:
- Seed URL lists (JSON array of URLs)
- Single URL scraping via --url flag
- Discovery mode (with limitations due to JavaScript pagination)
- NOVA metadata enrichment
- Robust error handling with retry logic

Usage:
    python boe_scraper.py
    python boe_scraper.py --url https://www.bankofengland.co.uk/prudential-regulation/publication/2024/12/ps2-24
    python boe_scraper.py --output-dir /path/to/output
    python boe_scraper.py --discover https://www.bankofengland.co.uk/news/prudential-regulation
"""

import os
import sys
import json
import time
import re
import html as html_module
import argparse
import traceback
import warnings
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Optional, Dict, List, Any

warnings.filterwarnings("ignore", category=DeprecationWarning)

import requests
from bs4 import BeautifulSoup, Comment
import html2text

# ─── Configuration ───────────────────────────────────────────────────────────

BOE_BASE_URL = "https://www.bankofengland.co.uk"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "BoE Publications"
REQUEST_DELAY = 1.5  # seconds between requests (be respectful)
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2  # multiplier for exponential backoff

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
})

# Document type mappings
DOCUMENT_TYPES = {
    "policy statement": {"doc_class": "policy_statement", "nova_tier": 1, "authority_class": "primary_normative"},
    "supervisory statement": {"doc_class": "supervisory_statement", "nova_tier": 2, "authority_class": "interpretive"},
    "consultation paper": {"doc_class": "consultation_paper", "nova_tier": 3, "authority_class": "context"},
    "letter": {"doc_class": "letter", "nova_tier": 3, "authority_class": "context"},
}

# Noise patterns to remove from content
NOISE_PATTERNS = [
    r'(?i)subscribe to updates',
    r'(?i)email this page',
    r'(?i)print this page',
    r'(?i)share this page',
    r'(?i)cookie policy',
    r'(?i)sign up for',
    r'(?i)newsletter',
    r'(?i)feedback',
    r'(?i)back to top',
]

# ─── Logging Setup ────────────────────────────────────────────────────────────

def log_msg(msg: str, level: str = "INFO"):
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


# ─── Helper Functions ────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Remove noise patterns and clean whitespace from text."""
    if not text:
        return ""
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, '', text)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove leading/trailing whitespace from lines
    lines = [line.rstrip() for line in text.split('\n')]
    return '\n'.join(lines).strip()


def clean_html_content(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove noise elements from BeautifulSoup parsed HTML."""
    # Remove script and style elements
    for tag in soup.find_all(['script', 'style', 'noscript', 'iframe']):
        tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove navigation, footer, header, cookie banners
    for selector in [
        'nav', 'footer', 'header',
        '.cookie-banner', '.cookie-consent', '#cookie-banner',
        '.share-buttons', '.social-share', '.email-share',
        '.print-button', '.pdf-button', '.export-buttons',
        '.breadcrumb', '.breadcrumbs',
        '.sidebar-nav', '.side-navigation',
        '#navigation', '.navigation',
        '.back-to-top',
        '[class*="cookie"]', '[class*="Cookie"]',
        '[class*="share"]', '[class*="Share"]',
        '[class*="print"]', '[class*="Print"]',
        '[class*="email"]', '[class*="Email"]',
        '[class*="pdf-export"]', '[class*="convert"]',
        '[class*="toolbar"]', '[class*="Toolbar"]',
        '.document-actions', '.page-actions',
        '.subscribe', '.newsletter',
        '[class*="history"]', '[class*="History"]',
        '[class*="export"]', '[class*="Export"]',
        '[class*="date-picker"]', '[class*="datepicker"]',
    ]:
        for el in soup.select(selector):
            el.decompose()

    # Remove buttons
    for btn in soup.find_all('button'):
        btn.decompose()

    # Remove empty list items and empty lists
    for li in soup.find_all('li'):
        if not li.get_text(strip=True):
            li.decompose()
    for ul in soup.find_all(['ul', 'ol']):
        if not ul.get_text(strip=True):
            ul.decompose()

    return soup


def fetch_page(url: str, retries: int = RETRY_ATTEMPTS) -> Optional[requests.Response]:
    """Fetch a page with retries and exponential backoff."""
    for attempt in range(retries):
        try:
            time.sleep(REQUEST_DELAY)
            resp = SESSION.get(url, timeout=30)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 404:
                log_msg(f"Page not found (404): {url}", "WARN")
                return None
            elif resp.status_code == 429:
                wait = (attempt + 1) * RETRY_BACKOFF * 5
                log_msg(f"Rate limited (429), waiting {wait}s...", "WARN")
                time.sleep(wait)
            else:
                log_msg(f"HTTP {resp.status_code} for {url}", "WARN")
                if attempt < retries - 1:
                    time.sleep(RETRY_BACKOFF ** attempt)
        except requests.RequestException as e:
            log_msg(f"Request error: {e}", "ERROR")
            if attempt < retries - 1:
                time.sleep(RETRY_BACKOFF ** attempt)
    return None


def extract_document_number(title: str) -> Optional[str]:
    """Extract document number (PS3/26, SS1/14, etc.) from title."""
    # Pattern: PS/SS/CP/Letter followed by number/year
    patterns = [
        r'\b(PS|SS|CP)\s*(\d+/\d+)\b',  # PS3/26, SS1/14, CP5/24
        r'\b(PS|SS|CP)(\d+/\d+)\b',
        r'(?:Policy Statement|Supervisory Statement|Consultation Paper)\s+(\d+/\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            if len(match.groups()) >= 2:
                return f"{match.group(1).upper()}{match.group(2)}"
            else:
                return match.group(1).upper()
    return None


def extract_document_type(title: str, url: str, content: str = "") -> str:
    """Determine document type from title, URL, and content."""
    combined = f"{title} {url} {content}".lower()

    if "policy statement" in combined or "ps" in combined.split():
        return "policy_statement"
    elif "supervisory statement" in combined or "ss" in combined.split():
        return "supervisory_statement"
    elif "consultation paper" in combined or "cp" in combined.split():
        return "consultation_paper"
    elif "letter" in combined:
        return "letter"

    return "regulatory_guidance"


def parse_boe_date(date_str: str) -> Optional[str]:
    """Parse BoE date formats to ISO YYYY-MM-DD."""
    if not date_str:
        return None

    date_str = date_str.strip()

    # Try various date formats
    formats = [
        "%d %B %Y",      # 15 March 2024
        "%B %d, %Y",     # March 15, 2024
        "%d/%m/%Y",      # 15/03/2024
        "%Y-%m-%d",      # 2024-03-15
        "%B %Y",         # March 2024
        "%d %b %Y",      # 15 Mar 2024
        "%Y/%m/%d",      # 2024/03/15
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def extract_metadata_from_page(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """Extract metadata from BoE publication page."""
    metadata = {
        "source_url": url,
        "title": "",
        "document_number": None,
        "document_type": "",
        "published_date": None,
        "scrape_date": datetime.now().isoformat(),
        "content_length": 0,
        "pdf_links": [],
        "related_links": [],
    }

    # Extract title
    title_el = soup.find('h1') or soup.find('title')
    if title_el:
        title_text = title_el.get_text(strip=True)
        # Remove "Bank of England" prefix if present
        title_text = re.sub(r'^Bank of England\s*[-–]\s*', '', title_text)
        metadata["title"] = clean_text(title_text)

    # Extract document number
    metadata["document_number"] = extract_document_number(metadata["title"])

    # Extract published date - look in common metadata locations
    date_candidates = []

    # Try finding date in meta tags
    date_meta = soup.find('meta', attrs={'property': 'article:published_time'})
    if date_meta and date_meta.get('content'):
        date_candidates.append(date_meta['content'])

    # Try finding in time elements
    time_el = soup.find('time')
    if time_el and time_el.get('datetime'):
        date_candidates.append(time_el['datetime'])

    # Try finding in common text patterns
    for el in soup.find_all(['span', 'p', 'div']):
        text = el.get_text(strip=True)
        if 'Published' in text or 'published' in text:
            # Extract date after "Published"
            match = re.search(r'Published[:\s]+(.+?)(?:\n|$)', text)
            if match:
                date_candidates.append(match.group(1).strip())

    # Parse first valid date found
    for date_str in date_candidates:
        parsed = parse_boe_date(date_str)
        if parsed:
            metadata["published_date"] = parsed
            break

    # Extract PDF links
    for a in soup.find_all('a', href=True):
        href = a['href']
        link_text = a.get_text(strip=True).lower()
        if 'pdf' in link_text or href.lower().endswith('.pdf'):
            full_url = urljoin(BOE_BASE_URL, href)
            metadata["pdf_links"].append({
                "text": a.get_text(strip=True),
                "url": full_url
            })

    # Extract related links (excluding PDFs)
    for a in soup.find_all('a', href=True):
        href = a['href']
        link_text = a.get_text(strip=True)
        if (link_text and
            not link_text.lower().endswith('pdf') and
            'news' not in link_text.lower() and
            len(link_text) > 3 and
            '/prudential-regulation/' in href):
            metadata["related_links"].append({
                "text": link_text,
                "url": urljoin(BOE_BASE_URL, href)
            })

    return metadata


def extract_content_from_page(soup: BeautifulSoup) -> str:
    """Extract main content text from BoE publication page."""
    # Clone soup for processing
    content_soup = BeautifulSoup(str(soup), 'html.parser')
    content_soup = clean_html_content(content_soup)

    # Find main content container (typical BoE patterns)
    main_content = None
    for selector in ['main', 'article', '[role="main"]', '.content', '.article-body']:
        main_content = content_soup.select_one(selector)
        if main_content:
            break

    if not main_content:
        main_content = content_soup

    # Extract text
    content_text = main_content.get_text(separator='\n', strip=True)
    return clean_text(content_text)


def generate_doc_id(document_number: str, doc_type: str, year: str) -> str:
    """Generate NOVA-compatible doc_id."""
    if document_number:
        # Format: boe.ps.3-26.2024 or boe.ss.1-14.2024
        type_prefix = doc_type.replace('_', '').lower()[:2]
        doc_num = document_number.lower().replace('/', '-')
        return f"boe.{type_prefix}.{doc_num}.{year}"
    else:
        # Fallback
        doc_slug = re.sub(r'[^\w\-]', '', doc_type.lower())[:10]
        return f"boe.{doc_slug}.{year}"


def build_nova_metadata(metadata: Dict, content_text: str, doc_type: str) -> Dict[str, Any]:
    """Build full NOVA metadata structure."""
    doc_type_lower = doc_type.lower()
    doc_type_info = DOCUMENT_TYPES.get(doc_type_lower, {})

    # Determine year from published_date or current year
    if metadata.get("published_date"):
        year = metadata["published_date"][:4]
    else:
        year = datetime.now().strftime("%Y")

    # Generate IDs
    doc_id = generate_doc_id(metadata.get("document_number"), doc_type_lower, year)

    # Detect content flags
    content_lower = content_text.lower()
    contains_definition = bool(re.search(r'\b(means|shall mean|defined as|definition)\b', content_lower))
    contains_formula = bool(re.search(r'[=\+\-\*/()]+|formula|calculation', content_lower))
    contains_requirement = bool(re.search(r'\b(must|should|shall|required|requirement)\b', content_lower))

    # Derive sector from content if possible
    sector = "All"
    if any(term in content_lower for term in ["bank", "banking", "crr"]):
        sector = "Banking"
    elif any(term in content_lower for term in ["insur", "sii"]):
        sector = "Insurance"

    nova_metadata = {
        "doc_id": doc_id,
        "doc_family_id": doc_id.rsplit('.', 1)[0],  # Remove year
        "title": metadata.get("title", ""),
        "short_title": metadata.get("document_number") or metadata.get("title", "")[:60],
        "document_class": doc_type_info.get("doc_class", "regulatory_guidance"),
        "source_type": "external_regulatory",
        "regulator": "BoE",
        "regulator_acronym": "BoE",
        "jurisdiction": "United Kingdom",
        "authority_class": doc_type_info.get("authority_class", "context"),
        "authority_level": {
            "policy_statement": 1,
            "supervisory_statement": 2,
            "consultation_paper": 3,
            "letter": 3,
        }.get(doc_type_lower, 3),
        "nova_tier": doc_type_info.get("nova_tier", 3),
        "status": "active",
        "effective_date_start": metadata.get("published_date"),
        "guideline_number": metadata.get("document_number"),
        "sector": [sector],
        "contains_definition": contains_definition,
        "contains_formula": contains_formula,
        "contains_requirement": contains_requirement,
        "parser_version": "boe-scraper-v1.0.0",
        "metadata": metadata,
    }

    return nova_metadata


def html_to_markdown(html_text: str) -> str:
    """Convert HTML to Markdown using html2text."""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0
    h.unicode_snob = True
    markdown = h.handle(html_text)
    # Clean up extra blank lines
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    return markdown.strip()


def save_outputs(output_dir: Path, doc_id: str, title: str,
                 nova_metadata: Dict, content_text: str, content_html: str) -> bool:
    """Save outputs in JSON, HTML, and Markdown formats."""
    try:
        # Create subdirectories
        json_dir = output_dir / "json"
        html_dir = output_dir / "html"
        md_dir = output_dir / "md"

        for d in [json_dir, html_dir, md_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_doc_id = re.sub(r'[^\w\-]', '_', doc_id)

        # 1. Save JSON with NOVA metadata
        json_data = {
            "nova_metadata": nova_metadata,
            "content_text": content_text,
            "content_html": content_html,
        }
        json_path = json_dir / f"{safe_doc_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # 2. Save HTML
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_module.escape(title)} - BoE</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }}
        h1 {{ color: #003399; border-bottom: 3px solid #003399; padding-bottom: 10px; }}
        h2 {{ color: #1a5490; margin-top: 30px; }}
        h3 {{ color: #4a7ab7; }}
        .metadata {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 30px; border-left: 4px solid #003399; font-size: 0.95em; }}
        .metadata p {{ margin: 5px 0; }}
        .meta-label {{ font-weight: bold; }}
        a {{ color: #0066cc; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
        th {{ background: #e6e6e6; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>{html_module.escape(title)}</h1>
    <div class="metadata">
        <p><span class="meta-label">Source:</span> <a href="{html_module.escape(nova_metadata['metadata']['source_url'])}">{html_module.escape(nova_metadata['metadata']['source_url'])}</a></p>
        <p><span class="meta-label">Document Type:</span> {html_module.escape(nova_metadata.get('document_class', 'N/A'))}</p>
        <p><span class="meta-label">Published:</span> {html_module.escape(nova_metadata.get('effective_date_start', 'N/A'))}</p>
        <p><span class="meta-label">Document Number:</span> {html_module.escape(nova_metadata.get('guideline_number', 'N/A'))}</p>
        <p><span class="meta-label">Regulator:</span> {html_module.escape(nova_metadata.get('regulator', 'N/A'))}</p>
        <p><span class="meta-label">Jurisdiction:</span> {html_module.escape(nova_metadata.get('jurisdiction', 'N/A'))}</p>
        <p><span class="meta-label">NOVA Tier:</span> {html_module.escape(str(nova_metadata.get('nova_tier', 'N/A')))}</p>
        <p><span class="meta-label">Scraped:</span> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    <div class="content">
        {content_html}
    </div>
</body>
</html>"""
        html_path = html_dir / f"{safe_doc_id}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # 3. Save Markdown
        markdown_content = f"""# {title}

**Source:** [{nova_metadata['metadata']['source_url']}]({nova_metadata['metadata']['source_url']})

**Document Type:** {nova_metadata.get('document_class', 'N/A')}
**Published:** {nova_metadata.get('effective_date_start', 'N/A')}
**Document Number:** {nova_metadata.get('guideline_number', 'N/A')}
**Regulator:** {nova_metadata.get('regulator', 'N/A')}
**Jurisdiction:** {nova_metadata.get('jurisdiction', 'N/A')}
**NOVA Tier:** {nova_metadata.get('nova_tier', 'N/A')}
**Scraped:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{html_to_markdown(content_html)}
"""
        md_path = md_dir / f"{safe_doc_id}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return True
    except Exception as e:
        log_msg(f"Error saving outputs: {e}", "ERROR")
        return False


def scrape_publication(url: str, output_dir: Path) -> bool:
    """Scrape a single BoE publication page."""
    log_msg(f"Scraping: {url}", "INFO")

    resp = fetch_page(url)
    if not resp:
        log_msg(f"Failed to fetch: {url}", "ERROR")
        return False

    try:
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extract metadata
        metadata = extract_metadata_from_page(soup, url)
        log_msg(f"  Title: {metadata['title'][:60]}...", "INFO")

        # Extract content
        content_text = extract_content_from_page(soup)
        content_html = extract_content_from_page(BeautifulSoup(resp.text, 'html.parser'))

        # Determine document type
        doc_type = extract_document_type(metadata['title'], url, content_text)
        log_msg(f"  Type: {doc_type}", "INFO")

        # Build NOVA metadata
        nova_metadata = build_nova_metadata(metadata, content_text, doc_type)
        doc_id = nova_metadata['doc_id']

        # Save outputs
        success = save_outputs(output_dir, doc_id, metadata['title'],
                              nova_metadata, content_text, resp.text)

        if success:
            log_msg(f"  Saved as: {doc_id}", "INFO")

        return success

    except Exception as e:
        log_msg(f"Error processing {url}: {e}", "ERROR")
        traceback.print_exc()
        return False


def scrape_from_seed_file(seed_file: Path, output_dir: Path) -> Dict[str, Any]:
    """Scrape publications from a seed URL list file."""
    log_msg(f"Reading seed file: {seed_file}", "INFO")

    try:
        with open(seed_file, 'r', encoding='utf-8') as f:
            urls = json.load(f)
    except Exception as e:
        log_msg(f"Error reading seed file: {e}", "ERROR")
        return {"success": 0, "failed": 0, "total": 0}

    if not isinstance(urls, list):
        log_msg("Seed file must contain a JSON array of URLs", "ERROR")
        return {"success": 0, "failed": 0, "total": 0}

    log_msg(f"Found {len(urls)} URLs to scrape", "INFO")

    results = {"success": 0, "failed": 0, "total": len(urls), "urls": []}

    for i, url in enumerate(urls, 1):
        log_msg(f"Processing {i}/{len(urls)}...", "INFO")
        success = scrape_publication(url, output_dir)
        results["urls"].append({"url": url, "success": success})
        if success:
            results["success"] += 1
        else:
            results["failed"] += 1

    return results


def discover_publications(listing_url: str) -> List[str]:
    """
    Attempt to discover publication URLs from a BoE listing page.

    NOTE: The BoE listing pages use JavaScript for pagination, so this
    method has limitations and can only scrape the first page visible
    in the HTML. For comprehensive scraping, use a seed file instead.
    """
    log_msg(f"Attempting discovery from: {listing_url}", "INFO")
    log_msg("WARNING: BoE listing pages use JavaScript pagination. Only first page will be scraped.", "WARN")
    log_msg("Recommendation: Use a seed URL list file for comprehensive scraping.", "WARN")

    resp = fetch_page(listing_url)
    if not resp:
        log_msg("Failed to fetch listing page", "ERROR")
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    urls = []

    # Find all publication links (pattern: /prudential-regulation/publication/...)
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/prudential-regulation/publication/' in href:
            full_url = urljoin(BOE_BASE_URL, href)
            urls.append(full_url)

    # Remove duplicates while preserving order
    urls = list(dict.fromkeys(urls))

    log_msg(f"Discovered {len(urls)} publication URLs (first page only)", "INFO")
    return urls


def generate_report(results: Dict[str, Any], output_dir: Path):
    """Generate a summary report of the scraping session."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "output_directory": str(output_dir),
        "total_urls": results.get("total", 0),
        "successful": results.get("success", 0),
        "failed": results.get("failed", 0),
        "success_rate": f"{(results.get('success', 0) / results.get('total', 1) * 100):.1f}%",
        "details": results.get("urls", []),
    }

    # Save report
    report_path = output_dir / "scrape_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    log_msg(f"Report saved to: {report_path}", "INFO")

    # Print summary
    print("\n" + "="*70)
    print("SCRAPING SUMMARY")
    print("="*70)
    print(f"Total URLs processed: {report['total_urls']}")
    print(f"Successful: {report['successful']}")
    print(f"Failed: {report['failed']}")
    print(f"Success rate: {report['success_rate']}")
    print(f"Output directory: {report['output_directory']}")
    print("="*70 + "\n")

    return report


# ─── Main Entry Point ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Bank of England Prudential Regulation Publications Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape from seed file
  python boe_scraper.py

  # Scrape single URL
  python boe_scraper.py --url https://www.bankofengland.co.uk/prudential-regulation/publication/2024/12/ps2-24

  # Custom output directory
  python boe_scraper.py --output-dir /path/to/output

  # Discover from listing (first page only - use seed file for complete)
  python boe_scraper.py --discover https://www.bankofengland.co.uk/news/prudential-regulation
        """
    )

    parser.add_argument(
        '--url',
        help='Single publication URL to scrape'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '--discover',
        metavar='LISTING_URL',
        help='Discover publication URLs from a listing page (first page only, use seed file for comprehensive)'
    )
    parser.add_argument(
        '--seed-file',
        type=Path,
        default=Path(__file__).parent / "boe_publication_urls.json",
        help='Seed file with publication URLs (default: boe_publication_urls.json in script directory)'
    )

    args = parser.parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    log_msg("BoE Publications Scraper Started", "INFO")

    results = None

    if args.url:
        # Single URL mode
        log_msg("Single URL mode", "INFO")
        results = {"total": 1, "success": 0, "failed": 0, "urls": []}
        success = scrape_publication(args.url, output_dir)
        results["success"] = 1 if success else 0
        results["failed"] = 0 if success else 1
        results["urls"] = [{"url": args.url, "success": success}]

    elif args.discover:
        # Discovery mode
        log_msg("Discovery mode", "INFO")
        urls = discover_publications(args.discover)
        if urls:
            results = {"total": len(urls), "success": 0, "failed": 0, "urls": []}
            for i, url in enumerate(urls, 1):
                log_msg(f"Processing {i}/{len(urls)}...", "INFO")
                success = scrape_publication(url, output_dir)
                results["urls"].append({"url": url, "success": success})
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
        else:
            log_msg("No URLs discovered", "WARN")
            results = {"total": 0, "success": 0, "failed": 0, "urls": []}

    else:
        # Seed file mode (default)
        if args.seed_file.exists():
            log_msg("Seed file mode", "INFO")
            results = scrape_from_seed_file(args.seed_file, output_dir)
        else:
            log_msg(f"Seed file not found: {args.seed_file}", "ERROR")
            log_msg("Please provide: --url, --discover, or create boe_publication_urls.json", "ERROR")
            sys.exit(1)

    if results:
        generate_report(results, output_dir)

    log_msg("Scraper Completed", "INFO")


if __name__ == "__main__":
    main()
