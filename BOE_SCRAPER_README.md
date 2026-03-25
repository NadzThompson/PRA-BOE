# BoE Prudential Regulation Publications Scraper

A comprehensive Python scraper for Bank of England (BoE) prudential regulation publications, designed to extract, process, and output content in NOVA-compatible formats.

## Overview

This scraper is specifically designed to scrape and enrich Bank of England prudential regulation publications including:
- **Policy Statements (PS)** - Primary normative documents (NOVA Tier 1)
- **Supervisory Statements (SS)** - Interpretive guidance (NOVA Tier 2)
- **Consultation Papers (CP)** - Consultation documents (NOVA Tier 3)
- **Letters** - Regulatory letters and communications (NOVA Tier 3)

All publications are processed into NOVA-compatible JSON metadata files along with HTML and Markdown versions.

## Features

### Core Capabilities

1. **Flexible Input Modes**
   - **Seed file mode**: Bulk scraping from a JSON array of URLs
   - **Single URL mode**: One-off scraping with `--url` flag
   - **Discovery mode**: Auto-discover publication URLs from listing pages (first page only due to JavaScript limitations)

2. **NOVA Metadata Enrichment**
   - Full NOVA-compatible metadata generation
   - Automatic document type classification
   - Document number extraction (PS3/26, SS1/14, etc.)
   - Authority level and tier assignment
   - Sector derivation from content
   - Content feature detection (definitions, formulas, requirements)

3. **Multi-Format Output**
   - **JSON**: Full NOVA metadata + content text + HTML
   - **HTML**: Standalone HTML with embedded metadata and styling
   - **Markdown**: Clean markdown version with metadata header

4. **Robust Error Handling**
   - Retry logic with exponential backoff (3 attempts)
   - Graceful handling of 404, 429 (rate limit), and network errors
   - Request rate limiting (1.5-second delays between requests)
   - Comprehensive error logging

5. **Content Processing**
   - Automatic HTML cleaning (removes noise elements)
   - Smart text extraction from article body
   - Metadata extraction from multiple HTML patterns
   - PDF link discovery
   - Related links extraction

## Installation

### Requirements

```bash
pip install requests beautifulsoup4 html2text
```

Or install all at once:

```bash
pip install -r requirements.txt
```

### Files Included

- `boe_scraper.py` - Main scraper script
- `boe_publication_urls.json` - Seed file template (JSON array of publication URLs)
- `BOE_SCRAPER_README.md` - This documentation

## Usage

### 1. Seed File Mode (Default - Bulk Scraping)

Create a `boe_publication_urls.json` file with an array of publication URLs:

```json
[
  "https://www.bankofengland.co.uk/prudential-regulation/publication/2024/12/ps2-24",
  "https://www.bankofengland.co.uk/prudential-regulation/publication/2024/11/ss1-24",
  "https://www.bankofengland.co.uk/prudential-regulation/publication/2024/10/cp5-24"
]
```

Then run:

```bash
python3 boe_scraper.py
```

Or specify a custom seed file:

```bash
python3 boe_scraper.py --seed-file /path/to/urls.json
```

### 2. Single URL Mode

Scrape a single publication:

```bash
python3 boe_scraper.py --url "https://www.bankofengland.co.uk/prudential-regulation/publication/2024/12/ps2-24"
```

### 3. Discovery Mode

Discover publication URLs from a listing page and scrape them (first page only):

```bash
python3 boe_scraper.py --discover "https://www.bankofengland.co.uk/news/prudential-regulation"
```

**Note**: The BoE listing pages use JavaScript for pagination, so the discovery mode can only access URLs visible in the initial HTML. For comprehensive scraping of all publications, use the seed file mode with a pre-compiled list of URLs.

### 4. Custom Output Directory

Specify where to save scraped content:

```bash
python3 boe_scraper.py --output-dir "/path/to/output"
```

Default: `/sessions/festive-dreamy-sagan/mnt/PRA/BoE Publications`

### 5. Combined Options

```bash
python3 boe_scraper.py \
  --seed-file /path/to/urls.json \
  --output-dir /path/to/output
```

## Output Structure

The scraper creates the following directory structure:

```
BoE Publications/
├── json/
│   ├── boe_ps_2-24_2024.json
│   ├── boe_ss_1-24_2024.json
│   ├── boe_cp_5-24_2024.json
│   └── ...
├── html/
│   ├── boe_ps_2-24_2024.html
│   ├── boe_ss_1-24_2024.html
│   ├── boe_cp_5-24_2024.html
│   └── ...
├── md/
│   ├── boe_ps_2-24_2024.md
│   ├── boe_ss_1-24_2024.md
│   ├── boe_cp_5-24_2024.md
│   └── ...
└── scrape_report.json
```

## Output Formats

### JSON Format

Each JSON file contains:
- Full NOVA-compatible metadata
- Extracted content text
- Original HTML content
- Document classification and authority information

```json
{
  "nova_metadata": {
    "doc_id": "boe.ps.2-24.2024",
    "doc_family_id": "boe.ps.2-24",
    "title": "Policy Statement 2/24: Title",
    "short_title": "PS2/24",
    "document_class": "policy_statement",
    "source_type": "external_regulatory",
    "regulator": "BoE",
    "regulator_acronym": "BoE",
    "jurisdiction": "United Kingdom",
    "authority_class": "primary_normative",
    "authority_level": 1,
    "nova_tier": 1,
    "status": "active",
    "effective_date_start": "2024-12-01",
    "guideline_number": "PS2/24",
    "sector": ["Banking"],
    "contains_definition": true,
    "contains_formula": false,
    "contains_requirement": true,
    "parser_version": "boe-scraper-v1.0.0",
    "metadata": {
      "source_url": "...",
      "title": "...",
      "document_number": "PS2/24",
      "document_type": "policy_statement",
      "published_date": "2024-12-01",
      "scrape_date": "2024-03-24T...",
      "pdf_links": [...],
      "related_links": [...]
    }
  },
  "content_text": "...",
  "content_html": "..."
}
```

### HTML Format

Standalone HTML files with:
- Embedded metadata section
- Professional styling
- Full content with formatting preserved
- Links to source URLs and PDFs

### Markdown Format

Clean markdown with:
- Metadata header
- Source attribution
- Hierarchical heading structure
- Preserved formatting

## NOVA Metadata Schema

The scraper generates NOVA-compatible metadata with these key fields:

| Field | Description | Example |
|-------|-------------|---------|
| `doc_id` | Unique document identifier | `boe.ps.2-24.2024` |
| `doc_family_id` | Version-independent family ID | `boe.ps.2-24` |
| `title` | Full publication title | "Policy Statement 2/24: Implementation of..." |
| `short_title` | Abbreviated title | "PS2/24" |
| `document_class` | Document type | "policy_statement", "supervisory_statement", "consultation_paper", "letter" |
| `source_type` | Source classification | "external_regulatory" |
| `regulator` | Issuing regulator | "BoE" |
| `jurisdiction` | Legal jurisdiction | "United Kingdom" |
| `authority_class` | Authority type | "primary_normative", "interpretive", "context" |
| `authority_level` | Authority level (1-3) | 1 (highest) to 3 (lowest) |
| `nova_tier` | NOVA classification tier | 1-3 |
| `status` | Document status | "active", "superseded", "withdrawn" |
| `effective_date_start` | Effective date in ISO format | "2024-12-01" |
| `guideline_number` | Official guideline number | "PS2/24", "SS1/14" |
| `sector` | Applicable sectors | ["Banking"], ["Insurance"], ["All"] |
| `contains_definition` | Whether document defines terms | true/false |
| `contains_formula` | Whether document includes formulas | true/false |
| `contains_requirement` | Whether document imposes requirements | true/false |

## Document Type Classification

The scraper automatically classifies documents based on patterns in title, URL, and content:

| Type | NOVA Tier | Authority Class | Pattern |
|------|-----------|-----------------|---------|
| Policy Statement | 1 | primary_normative | "PS", "Policy Statement" |
| Supervisory Statement | 2 | interpretive | "SS", "Supervisory Statement" |
| Consultation Paper | 3 | context | "CP", "Consultation Paper" |
| Letter | 3 | context | "Letter" |

## Document Number Extraction

Automatically extracts official document numbers from titles:
- **PS3/26** - Policy Statement 3/26
- **SS1/14** - Supervisory Statement 1/14
- **CP5/24** - Consultation Paper 5/24

If a document number is not found, the metadata field will contain `null`.

## Content Feature Detection

The scraper automatically detects these features in document content:

- **contains_definition**: Looks for "defined as", "means", "definition", etc.
- **contains_formula**: Detects mathematical formulas and calculation expressions
- **contains_requirement**: Searches for mandatory language ("must", "shall", "required", etc.)

## Sector Derivation

Automatically classifies documents by sector:
- **Banking**: Documents mentioning "bank", "banking", "CRR", etc.
- **Insurance**: Documents mentioning "insur", "SII", "Solvency", etc.
- **All**: Default if no sector-specific terms detected

## Error Handling & Retry Logic

### Retry Strategy

- **Maximum retries**: 3 attempts per URL
- **Backoff strategy**: Exponential backoff (2x multiplier)
- **Rate limiting**: 1.5-second delay between requests

### Handled Errors

- **404 Not Found**: Logged as warning, skipped
- **429 Rate Limited**: Automatic exponential backoff wait
- **Network errors**: Connection timeouts, DNS failures
- **Content errors**: Invalid HTML, encoding issues

### Logging

All operations are logged with timestamps and severity levels:
```
[2024-03-24 10:15:23] [INFO] BoE Publications Scraper Started
[2024-03-24 10:15:24] [INFO] Scraping: https://www.bankofengland.co.uk/...
[2024-03-24 10:15:25] [INFO] Title: Policy Statement 2/24: Implementation...
[2024-03-24 10:15:25] [INFO] Type: policy_statement
[2024-03-24 10:15:25] [INFO] Saved as: boe.ps.2-24.2024
```

## Scraping Report

After each run, a `scrape_report.json` is generated with:

```json
{
  "timestamp": "2024-03-24T10:15:30.123456",
  "output_directory": "/sessions/festive-dreamy-sagan/mnt/PRA/BoE Publications",
  "total_urls": 5,
  "successful": 4,
  "failed": 1,
  "success_rate": "80.0%",
  "details": [
    {
      "url": "https://...",
      "success": true
    },
    {
      "url": "https://...",
      "success": false
    }
  ]
}
```

## Rate Limiting & Politeness

The scraper includes several features to be respectful to the BoE servers:

- **1.5-second delay** between requests
- **Proper User-Agent** header
- **Connection pooling** via `requests.Session()`
- **Timeout handling** (30-second timeout per request)
- **Graceful degradation** on rate limits (429 responses)

## Troubleshooting

### Issue: "No URLs discovered"

**Cause**: The listing page uses JavaScript for pagination.

**Solution**: Create a seed file with explicit URLs using `--seed-file` mode instead.

### Issue: "Request timeout"

**Cause**: The BoE server is slow or unresponsive.

**Solution**: The scraper retries 3 times automatically. If it still fails, try again later.

### Issue: Module not found errors

**Cause**: Missing dependencies.

**Solution**:
```bash
pip install requests beautifulsoup4 html2text
```

### Issue: Permission denied when saving files

**Cause**: Output directory is not writable.

**Solution**:
```bash
python3 boe_scraper.py --output-dir /tmp/boe_output
# Or check permissions on the output directory
chmod 755 /sessions/festive-dreamy-sagan/mnt/PRA/BoE\ Publications
```

## Seed File Format

The `boe_publication_urls.json` file must be a valid JSON array:

```json
[
  "URL1",
  "URL2",
  "URL3"
]
```

Key points:
- Must be valid JSON syntax
- Must be an array (not an object)
- URLs should be complete and valid
- URLs should point to BoE prudential regulation publications
- Example URL pattern: `https://www.bankofengland.co.uk/prudential-regulation/publication/{year}/{month}/{slug}`

## Integration with PRA Enrichment Pipeline

The output of this scraper is designed to integrate with the PRA NOVA enrichment pipeline. The NOVA metadata can be used directly with:

```python
from pra_nova_enrichment import enrich_metadata
enriched = enrich_metadata(nova_metadata)
```

## Performance Characteristics

- **Typical scraping rate**: ~2-4 publications per minute (accounting for rate limiting)
- **Memory usage**: ~50-100MB for typical documents
- **Disk space**: ~200KB per publication (JSON, HTML, Markdown combined)

### Batch Scraping Times (Approximate)

- 10 publications: 2-5 minutes
- 50 publications: 10-25 minutes
- 100 publications: 20-50 minutes

## License & Attribution

This scraper is designed to work with publicly available BoE content. Please ensure your use complies with:
- Bank of England's terms of service
- UK copyright and data protection laws
- The scraper's rate limiting and respectful behavior toward BoE servers

## Support & Feedback

For issues, improvements, or feature requests, refer to the main project documentation.

## Version History

### v1.0.0 (2024-03-24)
- Initial release
- Full NOVA metadata generation
- Multi-format output (JSON, HTML, MD)
- Robust error handling and retry logic
- Comprehensive documentation
