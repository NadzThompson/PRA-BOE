# BoE Scraper - Technical Implementation Guide

This document provides detailed technical information about the BoE Publications Scraper implementation.

## Architecture Overview

The scraper follows a modular architecture with clear separation of concerns:

```
Input Layer (URL sources)
    ↓
Fetch & Parse Layer (HTTP requests, BeautifulSoup)
    ↓
Extraction Layer (metadata, content, document type)
    ↓
Enrichment Layer (NOVA metadata generation)
    ↓
Output Layer (JSON, HTML, Markdown)
    ↓
Reporting Layer (summary report)
```

## Core Functions

### Network Layer

#### `fetch_page(url, retries=RETRY_ATTEMPTS) → Optional[requests.Response]`

Fetches a page with automatic retry logic and exponential backoff.

**Parameters:**
- `url` (str): URL to fetch
- `retries` (int): Number of retry attempts (default: 3)

**Returns:**
- `requests.Response` if successful
- `None` if all retries failed

**Behavior:**
- Adds 1.5-second delay between requests (rate limiting)
- Implements exponential backoff: wait time = 2^attempt * 5 seconds
- Handles HTTP status codes:
  - 200: Success, return response
  - 404: Not found, log warning and return None
  - 429: Rate limited, exponential backoff
  - Other: Retry with backoff
- Catches `requests.RequestException` and retries

**Example:**
```python
resp = fetch_page("https://example.com/pub/2024/12/ps2-24")
if resp:
    soup = BeautifulSoup(resp.text, 'html.parser')
```

### Content Processing Layer

#### `clean_html_content(soup: BeautifulSoup) → BeautifulSoup`

Removes noise elements from parsed HTML (scripts, styles, navigation, etc.).

**Parameters:**
- `soup` (BeautifulSoup): Parsed HTML document

**Returns:**
- Modified BeautifulSoup object with noise removed

**Removes:**
- Script and style tags
- HTML comments
- Navigation, header, footer elements
- Cookie banners and consent notices
- Share buttons and action buttons
- Sidebar navigation
- Empty lists and list items

**Example:**
```python
soup = BeautifulSoup(html_text, 'html.parser')
clean_soup = clean_html_content(soup)
content = clean_soup.get_text()
```

#### `clean_text(text: str) → str`

Removes noise patterns and normalizes whitespace.

**Parameters:**
- `text` (str): Raw text to clean

**Returns:**
- Cleaned text with normalized whitespace

**Cleaning operations:**
- Removes noise patterns (newsletters, cookies, etc.)
- Collapses multiple blank lines to max 2
- Strips whitespace from line endings
- Preserves paragraph structure

#### `extract_content_from_page(soup: BeautifulSoup) → str`

Extracts main content text from a BoE publication page.

**Parameters:**
- `soup` (BeautifulSoup): Parsed HTML document

**Returns:**
- Extracted and cleaned text content

**Process:**
1. Clones soup for safe processing
2. Removes noise elements via `clean_html_content()`
3. Searches for main content containers (main, article, .content, etc.)
4. Extracts text with `\n` separator
5. Final cleanup with `clean_text()`

### Metadata Extraction Layer

#### `extract_metadata_from_page(soup: BeautifulSoup, url: str) → Dict[str, Any]`

Extracts metadata from BoE publication page.

**Parameters:**
- `soup` (BeautifulSoup): Parsed HTML document
- `url` (str): Source URL

**Returns:**
- Dictionary with extracted metadata fields:
  - `source_url`: Original URL
  - `title`: Document title
  - `document_number`: PS/SS/CP designation
  - `document_type`: Inferred type
  - `published_date`: ISO date string
  - `scrape_date`: Timestamp
  - `pdf_links`: List of PDF links
  - `related_links`: List of related publication links

**Extraction logic:**

1. **Title**: From `<h1>` or `<title>` tag, removes "Bank of England" prefix
2. **Document Number**: Via `extract_document_number()`
3. **Published Date**: From multiple sources (in order of priority):
   - `<meta property="article:published_time">`
   - `<time datetime="...">` element
   - Text pattern matching "Published: {date}"
4. **PDF Links**: All `<a>` tags with 'pdf' in text or href
5. **Related Links**: Non-PDF links containing '/prudential-regulation/'

#### `extract_document_number(title: str) → Optional[str]`

Extracts official document number from title.

**Parameters:**
- `title` (str): Document title

**Returns:**
- Document number string (e.g., "PS2/24", "SS1/14") or `None`

**Patterns matched:**
- `PS 2/24`, `PS2/24`, `PS2/24`
- `SS 1/14`, `SS1/14`, `SS1/14`
- `CP 5/24`, `CP5/24`, `CP5/24`
- Full text patterns: "Policy Statement 2/24", etc.

**Example:**
```python
num = extract_document_number("Policy Statement 2/24: Implementation of...")
# Returns: "PS2/24"
```

#### `extract_document_type(title: str, url: str, content: str = "") → str`

Determines document type from title, URL, and content.

**Parameters:**
- `title` (str): Document title
- `url` (str): Source URL
- `content` (str): Document content (optional)

**Returns:**
- Document type string from: "policy_statement", "supervisory_statement", "consultation_paper", "letter", "regulatory_guidance"

**Detection logic:**
1. Combines title, URL, and content into single searchable string (lowercased)
2. Searches for type-specific keywords:
   - "policy statement" or "ps" → policy_statement
   - "supervisory statement" or "ss" → supervisory_statement
   - "consultation paper" or "cp" → consultation_paper
   - "letter" → letter
3. Defaults to "regulatory_guidance" if no match

**Example:**
```python
dtype = extract_document_type("Policy Statement 2/24", "https://.../ps2-24", "...")
# Returns: "policy_statement"
```

#### `parse_boe_date(date_str: str) → Optional[str]`

Parses BoE date formats to ISO YYYY-MM-DD.

**Parameters:**
- `date_str` (str): Date string in various formats

**Returns:**
- ISO date string (YYYY-MM-DD) or `None` if parsing fails

**Supported formats:**
- `15 March 2024` (d B Y)
- `March 15, 2024` (B d, Y)
- `15/03/2024` (d/m/Y)
- `2024-03-15` (Y-m-d)
- `March 2024` (B Y)
- `15 Mar 2024` (d b Y)
- `2024/03/15` (Y/m/d)

**Example:**
```python
iso_date = parse_boe_date("15 March 2024")
# Returns: "2024-03-15"
```

### NOVA Enrichment Layer

#### `build_nova_metadata(metadata: Dict, content_text: str, doc_type: str) → Dict[str, Any]`

Builds complete NOVA-compatible metadata structure.

**Parameters:**
- `metadata` (Dict): Extracted metadata from `extract_metadata_from_page()`
- `content_text` (str): Extracted document content
- `doc_type` (str): Document type from `extract_document_type()`

**Returns:**
- Complete NOVA metadata dictionary with all required fields

**NOVA fields generated:**
- `doc_id`: Unique identifier (e.g., "boe.ps.2-24.2024")
- `doc_family_id`: Version-independent ID (e.g., "boe.ps.2-24")
- `title`: Full document title
- `short_title`: Abbreviated title (document number or truncated title)
- `document_class`: Classification from DOCUMENT_TYPES mapping
- `source_type`: Always "external_regulatory" for BoE
- `regulator`: Always "BoE"
- `regulator_acronym`: Always "BoE"
- `jurisdiction`: Always "United Kingdom"
- `authority_class`: primary_normative, interpretive, or context
- `authority_level`: 1-3 (1=highest)
- `nova_tier`: 1-3 (1=highest)
- `status`: "active" (for current documents)
- `effective_date_start`: Published date in ISO format
- `guideline_number`: Official document number
- `sector`: Derived from content (Banking, Insurance, or All)
- `contains_definition`: Boolean, detected from content
- `contains_formula`: Boolean, detected from content
- `contains_requirement`: Boolean, detected from content

**Content feature detection:**
- `contains_definition`: Searches for "defined as", "means", "definition of"
- `contains_formula`: Searches for math operators, "formula", "calculation"
- `contains_requirement`: Searches for "must", "shall", "should", "required"

**Example:**
```python
nova_md = build_nova_metadata(metadata, content_text, "policy_statement")
# Returns complete NOVA metadata structure
```

#### `generate_doc_id(document_number: str, doc_type: str, year: str) → str`

Generates NOVA-compatible doc_id.

**Parameters:**
- `document_number` (str): Document number like "PS2/24"
- `doc_type` (str): Document type like "policy_statement"
- `year` (str): Year in YYYY format

**Returns:**
- doc_id string

**Format:**
- If document_number exists: `boe.{type_prefix}.{doc_num}.{year}`
  - Example: `boe.ps.2-24.2024` (from PS2/24)
- Fallback: `boe.{doc_slug}.{year}`

**Example:**
```python
doc_id = generate_doc_id("PS2/24", "policy_statement", "2024")
# Returns: "boe.ps.2-24.2024"
```

### Conversion Layer

#### `html_to_markdown(html_text: str) → str`

Converts HTML to Markdown using html2text library.

**Parameters:**
- `html_text` (str): HTML content

**Returns:**
- Markdown-formatted text

**Processing:**
- Uses html2text.HTML2Text
- Ignores links structure but preserves link text
- Ignores images
- Preserves Unicode characters
- Collapses excessive blank lines

**Example:**
```python
md = html_to_markdown("<h1>Title</h1><p>Content</p>")
# Returns: "# Title\n\nContent"
```

### Output Layer

#### `save_outputs(output_dir: Path, doc_id: str, title: str, nova_metadata: Dict, content_text: str, content_html: str) → bool`

Saves scraped content in three formats: JSON, HTML, Markdown.

**Parameters:**
- `output_dir` (Path): Base output directory
- `doc_id` (str): Document identifier
- `title` (str): Document title
- `nova_metadata` (Dict): NOVA metadata structure
- `content_text` (str): Extracted text content
- `content_html` (str): Original HTML content

**Returns:**
- `True` if all outputs saved successfully, `False` otherwise

**Outputs created:**
1. **JSON**: `{output_dir}/json/{doc_id}.json`
   - Contains nova_metadata, content_text, content_html

2. **HTML**: `{output_dir}/html/{doc_id}.html`
   - Standalone HTML with embedded metadata and styling

3. **Markdown**: `{output_dir}/md/{doc_id}.md`
   - Markdown with metadata header

**Directory creation:**
- Automatically creates json/, html/, md/ subdirectories if needed

### Scraping Orchestration

#### `scrape_publication(url: str, output_dir: Path) → bool`

Main scraping function for a single URL.

**Parameters:**
- `url` (str): Publication URL
- `output_dir` (Path): Output directory

**Returns:**
- `True` if successfully scraped and saved, `False` otherwise

**Process:**
1. Fetch page via `fetch_page()`
2. Parse HTML with BeautifulSoup
3. Extract metadata via `extract_metadata_from_page()`
4. Extract content via `extract_content_from_page()`
5. Determine type via `extract_document_type()`
6. Build NOVA metadata via `build_nova_metadata()`
7. Save outputs via `save_outputs()`
8. Log results

**Error handling:**
- Catches and logs all exceptions
- Returns False on any error
- Continues processing other URLs

#### `scrape_from_seed_file(seed_file: Path, output_dir: Path) → Dict[str, Any]`

Bulk scraping from seed URL file.

**Parameters:**
- `seed_file` (Path): JSON file containing URL array
- `output_dir` (Path): Output directory

**Returns:**
- Summary dictionary with:
  - `success`: Count of successful scrapes
  - `failed`: Count of failed scrapes
  - `total`: Total URLs processed
  - `urls`: List of {url, success} objects

**File format requirement:**
```json
[
  "url1",
  "url2",
  "url3"
]
```

#### `discover_publications(listing_url: str) → List[str]`

Discovers publication URLs from a listing page.

**Parameters:**
- `listing_url` (str): BoE listing page URL

**Returns:**
- List of discovered publication URLs

**Limitations:**
- BoE pages use JavaScript for pagination
- Can only access URLs in initial HTML
- Does not handle dynamically loaded content
- Recommendation: Use seed file for comprehensive scraping

**Detection:**
- Searches for all `<a>` tags with '/prudential-regulation/publication/' in href
- Removes duplicates while preserving order
- Returns absolute URLs

### Reporting Layer

#### `generate_report(results: Dict[str, Any], output_dir: Path)`

Generates scraping session report.

**Parameters:**
- `results` (Dict): Results from scraping session
- `output_dir` (Path): Output directory

**Output:**
1. **JSON file**: `{output_dir}/scrape_report.json` containing:
   - Timestamp
   - Output directory path
   - Total URLs processed
   - Successful/failed counts
   - Success rate percentage
   - Detailed list of all URLs and their status

2. **Console output**: Summary table

**Example output:**
```json
{
  "timestamp": "2024-03-24T10:15:30.123456",
  "output_directory": "/sessions/festive-dreamy-sagan/mnt/PRA/BoE Publications",
  "total_urls": 5,
  "successful": 4,
  "failed": 1,
  "success_rate": "80.0%",
  "details": [...]
}
```

## Constants and Configuration

### Network Configuration

```python
BOE_BASE_URL = "https://www.bankofengland.co.uk"
REQUEST_DELAY = 1.5  # seconds between requests
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2  # multiplier for exponential backoff
```

### Document Type Mapping

```python
DOCUMENT_TYPES = {
    "policy statement": {
        "doc_class": "policy_statement",
        "nova_tier": 1,
        "authority_class": "primary_normative"
    },
    "supervisory statement": {
        "doc_class": "supervisory_statement",
        "nova_tier": 2,
        "authority_class": "interpretive"
    },
    # ... etc
}
```

### HTTP Headers

```python
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Accept": "text/html,application/xhtml+xml...",
    "Accept-Language": "en-GB,en;q=0.9",
})
```

## Data Flow Diagram

```
Publication URL
    ↓
fetch_page() ← [retry logic, rate limiting]
    ↓
BeautifulSoup parsing
    ↓
┌─────────────────────────────────────┐
│ extract_metadata_from_page()        │
│ ├─ title extraction                 │
│ ├─ document_number extraction       │
│ ├─ published_date parsing           │
│ ├─ pdf_links discovery              │
│ └─ related_links discovery          │
└─────────────────────────────────────┘
    ↓
extract_content_from_page()
├─ clean_html_content()
└─ clean_text()
    ↓
extract_document_type()
    ↓
┌─────────────────────────────────────┐
│ build_nova_metadata()               │
│ ├─ generate_doc_id()                │
│ ├─ map document_class               │
│ ├─ detect content features          │
│ ├─ derive sector                    │
│ └─ assign authority levels          │
└─────────────────────────────────────┘
    ↓
save_outputs()
├─ JSON (nova_metadata + content)
├─ HTML (styled standalone page)
└─ Markdown (formatted text)
    ↓
Report generation
```

## Performance Considerations

### Memory Usage

- **Per-document**: ~50-100MB (including full HTML + processed content)
- **Session overhead**: ~10-20MB (Session object, regex patterns, etc.)
- **Peak usage**: Proportional to document size, typical max ~200MB for large docs

### Processing Time

- **Fetch + Parse**: 0.5-2 seconds per document
- **Extraction**: 0.1-0.5 seconds per document
- **NOVA enrichment**: <0.1 seconds per document
- **Output writing**: 0.1-0.2 seconds per document
- **Total with delays**: ~2-4 documents per minute (accounting for 1.5s rate limit delay)

### Network Considerations

- **Bandwidth**: ~50-200KB per document request
- **Connection pooling**: Implemented via requests.Session()
- **Timeout**: 30 seconds per request (generous for BoE)
- **Rate limit compliance**: 1.5-second delays between requests

## Error Recovery

The scraper implements multiple levels of error recovery:

1. **HTTP-level**: Retry logic with exponential backoff
2. **Parsing-level**: BeautifulSoup error tolerance
3. **Function-level**: Try-except with logging
4. **Session-level**: Continue processing on per-document failures

All errors are logged with timestamps and can be reviewed in the final report.

## Testing & Validation

Key aspects to test:

1. **Date parsing**: Multiple BoE date formats
2. **Document number extraction**: Various PS/SS/CP formats
3. **HTML cleaning**: Verify noise elements removed
4. **Metadata extraction**: Verify all fields populated correctly
5. **NOVA generation**: Check doc_id format and tier assignments
6. **File writing**: Verify JSON validity and encoding
7. **Error handling**: Test network failures, invalid URLs, etc.

## Integration Points

The scraper outputs are designed to integrate with:

1. **pra_nova_enrichment.py**: Further enrichment of NOVA metadata
2. **PRA Rules JSON**: Combined with PRA Rulebook publications
3. **Downstream systems**: Any system expecting NOVA-compatible JSON

## Future Enhancements

Potential improvements:

1. **JavaScript rendering**: Use Selenium/Playwright for dynamic pagination discovery
2. **PDF extraction**: Download and extract text from PDF links
3. **Appendix handling**: Extract and link appendices separately
4. **Version tracking**: Detect and track document versions/supersessions
5. **Link resolution**: Resolve relative links to full publication references
6. **Batch optimization**: Async requests for faster bulk scraping
7. **Database output**: Direct database insertion instead of file-based output
