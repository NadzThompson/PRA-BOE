# BoE Scraper - Quick Start Guide

## Installation

```bash
pip install requests beautifulsoup4 html2text
```

## Basic Usage

### Option 1: Scrape from Seed File (Bulk)

Create `boe_publication_urls.json`:
```json
[
  "https://www.bankofengland.co.uk/prudential-regulation/publication/2024/12/ps2-24",
  "https://www.bankofengland.co.uk/prudential-regulation/publication/2024/11/ss1-24"
]
```

Run:
```bash
python3 boe_scraper.py
```

### Option 2: Scrape Single URL

```bash
python3 boe_scraper.py --url "https://www.bankofengland.co.uk/prudential-regulation/publication/2024/12/ps2-24"
```

### Option 3: Custom Output Directory

```bash
python3 boe_scraper.py --output-dir /path/to/output
```

## Output Structure

```
BoE Publications/
├── json/          # NOVA metadata + content
├── html/          # Standalone HTML files
├── md/            # Markdown versions
└── scrape_report.json
```

## NOVA Metadata Example

```json
{
  "doc_id": "boe.ps.2-24.2024",
  "title": "Policy Statement 2/24: ...",
  "document_class": "policy_statement",
  "regulator": "BoE",
  "jurisdiction": "United Kingdom",
  "authority_class": "primary_normative",
  "nova_tier": 1,
  "effective_date_start": "2024-12-01",
  "guideline_number": "PS2/24",
  "sector": ["Banking"]
}
```

## Key Features

- **Automatic doc_id generation**: `boe.ps.2-24.2024`, `boe.ss.1-14.2024`
- **Smart document classification**: Detects PS/SS/CP/Letter automatically
- **Metadata enrichment**: Authority class, tier, sector, content features
- **Robust error handling**: 3 retries with exponential backoff
- **Rate limiting**: 1.5-second delays between requests

## Document Types & NOVA Tiers

| Type | Pattern | NOVA Tier | Authority |
|------|---------|-----------|-----------|
| Policy Statement | `PS2/24` | 1 | primary_normative |
| Supervisory Statement | `SS1/14` | 2 | interpretive |
| Consultation Paper | `CP5/24` | 3 | context |
| Letter | Letter | 3 | context |

## Troubleshooting

**Issue**: "No URLs discovered"
- **Cause**: BoE pages use JavaScript pagination
- **Fix**: Use seed file mode instead

**Issue**: Missing dependencies
- **Fix**: `pip install requests beautifulsoup4 html2text`

**Issue**: Permission denied
- **Fix**: `chmod 755 /path/to/output` or use writable directory

## Help

```bash
python3 boe_scraper.py --help
```

## See Also

- `BOE_SCRAPER_README.md` - Full documentation
- `boe_publication_urls.json` - Example seed file
- `pra_nova_enrichment.py` - NOVA enrichment pipeline
