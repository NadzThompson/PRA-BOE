# NOVA Regulatory Corpus: Web Scraping & Metadata Enrichment Documentation

This document provides a comprehensive reference for how each NOVA regulatory corpus is scraped, parsed, enriched, and what metadata fields are produced. It covers all four repositories:

1. **US_Fed_Regulations** -- US Federal Reserve (eCFR, Federal Register, SR Letters)
2. **Basel Framework** -- Basel Committee on Banking Supervision (BCBS/BIS)
3. **OSFI_Guidance** -- Office of the Superintendent of Financial Institutions (Canada)
4. **PRA** -- Prudential Regulation Authority / Bank of England (UK)

---

## Table of Contents

- [1. Corpus Summary](#1-corpus-summary)
- [2. US Federal Regulations](#2-us-federal-regulations)
  - [2.1 eCFR Scraper](#21-ecfr-scraper)
  - [2.2 Federal Register Scraper](#22-federal-register-scraper)
  - [2.3 SR Letters Scraper](#23-sr-letters-scraper)
  - [2.4 US Fed Metadata Enrichment](#24-us-fed-metadata-enrichment)
- [3. Basel Framework](#3-basel-framework)
  - [3.1 Group A: Framework Chapters (API)](#31-group-a-framework-chapters-api)
  - [3.2 Groups B-J: PDFs and HTML](#32-groups-b-j-pdfs-and-html)
  - [3.3 Basel Metadata Enrichment](#33-basel-metadata-enrichment)
- [4. OSFI Guidance](#4-osfi-guidance)
- [5. PRA / Bank of England](#5-pra--bank-of-england)
  - [5.1 PRA Rulebook Scraping](#51-pra-rulebook-scraping)
  - [5.2 BoE Guidance (PDFs)](#52-boe-guidance-pdfs)
  - [5.3 PRA Metadata Enrichment](#53-pra-metadata-enrichment)
- [6. Standardized Metadata Fields](#6-standardized-metadata-fields)
  - [6.1 authority_level](#61-authority_level)
  - [6.2 version_id](#62-version_id)
  - [6.3 version_label](#63-version_label)
  - [6.4 Full Field Comparison](#64-full-field-comparison)
- [7. NOVA 3-Layer Metadata Architecture](#7-nova-3-layer-metadata-architecture)
- [8. Pipeline Execution Reference](#8-pipeline-execution-reference)

---

## 1. Corpus Summary

| Repo | Regulator | Jurisdiction | Documents | Sources | Scraping Method |
|------|-----------|-------------|-----------|---------|-----------------|
| **US_Fed_Regulations** | Federal Reserve System | United States | 3,434 | eCFR API, Federal Register API, Fed website | Live API scraping |
| **Basel Framework** | BCBS / BIS | International | 288 | BIS JSON API, BIS PDF downloads | API + direct download |
| **OSFI_Guidance** | OSFI | Canada | 278 | OSFI website (osfi-bsif.gc.ca) | Pre-scraped HTML |
| **PRA** | PRA / BoE | United Kingdom | 677 | prarulebook.co.uk, bankofengland.co.uk | Pre-scraped HTML + PDF |

### Output File Structure (All Repos)

Each repo produces four file types per document:

```
{corpus}/
  json/   -- NOVA metadata sidecar (no embedded content)
  md/     -- Normalized markdown text (authoritative content for RAG)
  html/   -- Formatted or raw HTML
  pdf/    -- Rendered or source PDFs
```

For RAG ingestion, the pipeline consumes **exactly two files per document**: the JSON metadata sidecar paired with the raw content file (HTML or PDF).

---

## 2. US Federal Regulations

**Repository:** `US_Fed_Regulations/`
**GitHub:** https://github.com/NadzThompson/US_Fed_Regulations

### Directory Layout

```
US_Fed_Regulations/
  scrapers/
    config.py                         -- Shared configuration, tier mappings, API endpoints
    scrape_ecfr.py                    -- eCFR regulation scraper
    scrape_federal_register.py        -- Federal Register API scraper
    scrape_sr_letters.py              -- SR Letters web scraper
    enrich_metadata.py                -- Post-processing enrichment for all sources
    run_all.py                        -- Orchestrates all scrapers
  ecfr/           {json, md, html, pdf, raw_html}    -- 59 regulation parts
  federal_register/ {json, md, html, raw_html}       -- 3,037 documents
  SR_Letters/     {json, md, raw_html, pdf}           -- 338 letters
```

---

### 2.1 eCFR Scraper

**Script:** `scrapers/scrape_ecfr.py` (33.5 KB)
**Source:** Electronic Code of Federal Regulations API (https://www.ecfr.gov/developer/documentation/api/v1)
**Scope:** All active parts under 12 CFR Chapter II (Federal Reserve System) -- 59 parts

#### What It Scrapes

| API Endpoint | Purpose |
|---|---|
| `GET /api/versioner/v1/structure/{date}/title-12.json` | Table-of-contents structure |
| `GET /api/renderer/v1/content/enhanced/{date}/title-12?part={N}` | Full rendered HTML of a regulation part |
| `GET /api/versioner/v1/versions/title-12?part={N}` | Amendment history (effective dates) |

#### Pipeline Steps

1. **Fetch structure** -- Gets the TOC for 12 CFR to identify all parts in Chapter II
2. **Fetch part HTML** -- Downloads the full rendered HTML for each part (e.g., Part 252 = Reg YY)
3. **Parse HTML** -- Extracts with BeautifulSoup:
   - Part name and title
   - Section headings (for TOC)
   - Content flags (definitions, formulas, requirements, deadlines, parameters)
   - Word count
4. **Generate outputs**:
   - `raw_html/` -- Original API response
   - `html/` -- Styled HTML with metadata header
   - `md/` -- Markdown conversion (headings, tables, lists preserved)
   - `json/` -- NOVA metadata (51+ fields, no content)
   - `pdf/` -- Rendered via xhtml2pdf
5. **Enrich effective dates** -- Calls the versions API to get the true latest amendment date, overwriting the initial scrape-date placeholder

#### Key Metadata Produced

| Field | Value | Source |
|---|---|---|
| `authority_level` | `100` (integer) | Hardcoded -- all eCFR regs are binding law |
| `authority_class` | `"primary_normative"` or `"reference_interpretive"` | Based on part type |
| `version_id` | ISO date (e.g., `"2025-12-01"`) | Latest amendment date from versions API |
| `version_label` | Year string (e.g., `"2025"`) | First 4 chars of `version_id` |
| `nova_tier` | 1-4 | From `config.nova_tier_for_part()` lookup table |
| `normative_weight` | `"mandatory"`, `"advisory"`, or `"informational"` | Derived from `authority_class` |

#### Rate Limiting

- 1.0 second delay between requests (`ECFR_DELAY_SECONDS`)
- 60-second request timeout
- User-Agent: `NOVA-eCFR-Scraper/1.0`

---

### 2.2 Federal Register Scraper

**Script:** `scrapers/scrape_federal_register.py` (23.5 KB)
**Source:** Federal Register API (https://www.federalregister.gov/developers/documentation/api/v1)
**Scope:** All Federal Reserve System documents -- Final Rules, Proposed Rules, and Notices

#### What It Scrapes

| API Endpoint | Purpose |
|---|---|
| `GET /api/v1/documents.json?agencies=federal-reserve-system&type={TYPE}` | Paginated document search |

The API returns structured metadata (title, abstract, action, dates, CFR references, body HTML) for each document. The scraper pages through all results for three document types:
- `RULE` -- Final rules (binding)
- `PRORULE` -- Proposed rules (consultative)
- `NOTICE` -- Notices and announcements

#### Pipeline Steps

1. **Query API** -- Paginate through all Federal Reserve documents by type
2. **Extract metadata** -- Parse API response fields (title, abstract, action, dates, CFR refs)
3. **Extract body text** -- Strip HTML tags from full body for word count and content flags
4. **Generate outputs**:
   - `raw_html/` -- Original body HTML from API
   - `html/` -- Styled HTML with metadata header + body
   - `md/` -- Markdown with abstract, action, and full body text
   - `json/` -- NOVA metadata

#### Key Metadata Produced

| Field | Condition | Value |
|---|---|---|
| `authority_level` | Final Rule | `100` |
| `authority_level` | Proposed Rule | `40` |
| `authority_level` | Notice | `30` |
| `authority_class` | Final Rule | `"primary_normative"` |
| `authority_class` | Proposed Rule / Notice | `"guidance_interpretive"` |
| `version_id` | All | Publication date (ISO) |
| `version_label` | All | Publication year |
| `nova_tier` | Rules / Proposed | `2` |
| `nova_tier` | Notices | `3` |

#### Rate Limiting

- 0.5 second delay between requests (`FR_DELAY_SECONDS`)
- User-Agent: `NOVA-FedRegister-Scraper/1.0`

---

### 2.3 SR Letters Scraper

**Script:** `scrapers/scrape_sr_letters.py` (33.9 KB)
**Source:** Federal Reserve Board website (https://www.federalreserve.gov/supervisionreg/srletters.htm)
**Scope:** All SR (Supervision and Regulation) Letters from 1990 to present -- 338 letters

#### Crawl Strategy

Unlike the API-based scrapers, this one crawls HTML pages:

1. **Fetch all-years index** -- `sr-letters-all-years.htm` lists links to each year page
2. **Fetch year pages** -- Each year page (e.g., `srletters2024.htm`) lists individual letters
3. **Fetch letter pages** -- Extract title, date, applicability, body text, and PDF links
4. **Download PDF attachments** -- Each letter may have 1+ attached PDFs
5. **Generate outputs** -- JSON metadata, markdown summary, raw HTML

#### Key Metadata Produced

| Field | Value | Source |
|---|---|---|
| `authority_level` | `70` (integer) | Hardcoded -- supervisory guidance |
| `authority_class` | `"primary_normative"` | Issued by Division of S&R |
| `version_id` | ISO date (e.g., `"2000-08-15"`) | Document issuance date |
| `version_label` | Year string (e.g., `"2000"`) | Parsed from SR number (SR 00-13 = 2000) |
| `normative_weight` | `"mandatory"`, `"advisory"`, or `"informational"` | Detected from body text (shall/must/should) |
| `nova_tier` | `2` | All SR Letters |

#### Rate Limiting

- 1.5 second delay between requests (`SR_DELAY_SECONDS`)
- User-Agent: `NOVA-SR-Scraper/2.0`

---

### 2.4 US Fed Metadata Enrichment

**Script:** `scrapers/enrich_metadata.py` (566 lines)
**Runs after** all three scrapers complete.

The enricher validates and fills in missing NOVA 3-layer fields across all 3,434 JSON files:

| Enrichment | What It Does |
|---|---|
| **authority_level normalization** | Converts any legacy string values (e.g., `"binding_regulation"`) to integers on the OSFI 0-100 scale |
| **version_id / version_label sync** | Ensures `version_label` always matches `version_id[:4]` |
| **eCFR effective dates** | Calls eCFR versions API to replace scrape-date placeholders with true amendment dates |
| **Content flags** | Scans markdown for definitions, requirements, formulas, deadlines, parameters |
| **BM25 / vector text** | Computes search-optimized text fields |
| **SHA256 hash** | Recomputes content hash from markdown file |
| **NOVA tier validation** | Cross-checks tier against `config.nova_tier_for_part()` |

**Execution:**
```bash
cd US_Fed_Regulations
python -m scrapers.enrich_metadata              # Enrich all sources
python -m scrapers.enrich_metadata --source ecfr  # Just eCFR
python -m scrapers.enrich_metadata --validate-only  # Dry run
```

---

## 3. Basel Framework

**Repository:** `Basel Framework/`
**GitHub:** https://github.com/NadzThompson/Basel-Framework-Library

### Directory Layout

```
Basel Framework/
  scripts/
    scrape_basel_framework.py        -- Main scraper (1,031 lines)
    enrich_metadata.py               -- PDF group enrichment
    enrich_nova_fields.py            -- NOVA 3-layer field addition
    redownload_fixes.py              -- Error recovery for failed downloads
  json/                              -- Group A: 127 framework chapters
  json/foundational_accords/         -- Group B: 28 historical accords
  json/guidelines/                   -- Group C: 20 current guidelines
  json/policy_papers/                -- Group A2: 65 policy papers
  json/fsi_summaries/                -- Group I: 12 FSI summaries
  json/newsletters/                  -- Group J: 36 BCBS newsletters
  html/, md/, pdf/                   -- Corresponding content files
  logs/                              -- Timestamped scraper logs
```

### 3.1 Group A: Framework Chapters (API)

**Script:** `scripts/scrape_basel_framework.py`
**Source:** BIS JSON API
**Documents:** 127 chapters across 14 standards

#### What It Scrapes

| API Endpoint | Purpose |
|---|---|
| `GET https://www.bis.org/api/bcbs_standards.json` | Full standards index with chapter lists |
| `GET https://www.bis.org/api/bcbs_chapters/{id}.json` | Individual chapter content (paragraphs, footnotes, FAQs) |

#### Pipeline Steps

1. **Fetch standards index** -- Returns all 14 standards with their chapter metadata
2. **Resolve current chapters** -- For each chapter number, determine which version is active as of the timeline date (`--tldate`). Handles active, future_effective, and removed statuses.
3. **Fetch chapter content** -- API returns structured data: paragraphs (with display_position), footnotes, and FAQs
4. **Parse to HTML** -- Sort paragraphs, extract sections, build HTML with template and CSS
5. **Convert to Markdown** -- HTML-to-markdown with headings, tables, footnotes as blockquotes
6. **Generate metadata** -- 51-field NOVA JSON using `STANDARD_META` mapping for authority/tier
7. **Render PDF** -- Optional, via pdfkit/wkhtmltopdf

#### Standards and Their Tiers

| Standard | Title | Nova Tier | Authority |
|---|---|---|---|
| CAP | Capital | 1 | primary_normative |
| RBC | Risk-based capital | 1 | primary_normative |
| CRE | Credit risk | 1 | primary_normative |
| MAR | Market risk | 1 | primary_normative |
| OPE | Operational risk | 1 | primary_normative |
| LEV | Leverage | 1 | primary_normative |
| LCR | Liquidity coverage | 1 | primary_normative |
| NSF | Net stable funding | 1 | primary_normative |
| SCO | Scope | 2 | primary_normative |
| LEX | Large exposures | 2 | primary_normative |
| MGN | Margin | 2 | primary_normative |
| DIS | Disclosure | 2 | primary_normative |
| SRP | Supervisory review | 2 | guidance_interpretive |
| BCP | Core principles | 3 | guidance_interpretive |

#### Key Metadata Produced

| Field | Logic | Example |
|---|---|---|
| `authority_level` | 1 (primary), 2 (guidance), 3 (reference); from `STANDARD_META` + document_class adjustments | `1` for CRE20 |
| `version_id` | `in_force_at` date from API | `"2028-01-01"` |
| `version_label` | Year from `version_id` | `"2028"` |
| `prior_version_count` | `version_count - 1` from API | `5` |
| `superseded_by_doc_id` | Lookup in `SUPERSESSION_MAP` | `"basel.ope.25.*.chapter"` |

#### Rate Limiting

- 1.5 seconds between requests (`REQUEST_DELAY`)
- 60-second timeout per request
- 3 retries with exponential backoff (5s, 10s, 15s)

---

### 3.2 Groups B-J: PDFs and HTML

These groups are downloaded directly (no API parsing):

| Group | Name | Documents | Source | Format |
|---|---|---|---|---|
| **B** | Foundational Accords | 28 | BIS PDFs | PDF |
| **C** | Current Guidelines | 20 | BIS PDFs | PDF |
| **A2** | Policy Papers | 65 + 1 XLSX | BIS PDFs | PDF |
| **I** | FSI Summaries | 12 | BIS PDFs | PDF |
| **J** | BCBS Newsletters | 36 | BIS website | HTML |

Each PDF is downloaded with streaming (8KB chunks), and a minimal JSON metadata file is generated with: `doc_id`, `bis_ref`, `title`, `source_url`, `doc_type`, `doc_status`, `priority`, `sha256`.

These are then upgraded to full NOVA schema by the enrichment scripts.

---

### 3.3 Basel Metadata Enrichment

Two enrichment scripts run after scraping:

#### `enrich_metadata.py` -- Schema Upgrade for PDF Groups

Upgrades minimal JSON to full 51-field NOVA schema using hard-coded mappings:

- **`DOC_TYPE_MAP`**: Maps `doc_type` to (`document_class`, `authority_class`, `authority_level`, `content_type`)
- **`STATUS_MAP`**: Maps `doc_status` to (`status`, `current_version_flag`)
- **`EFFECTIVE_DATES`**: Hard-coded effective dates for 100+ known documents
- **`TOPIC_MAP`**: Maps `bis_ref` to topic labels (e.g., `bcbs144` -> `"Liquidity Risk"`)

#### `enrich_nova_fields.py` -- Content Analysis

Adds Layer 1-3 fields by analyzing markdown content:

| Detection | Patterns | Output Field |
|---|---|---|
| Normative weight | "shall", "must", "is required to" -> mandatory; "should", "is expected to" -> advisory | `normative_weight` |
| Cross-references | `[CRE20]`, `[MAR50.3]` patterns | `cross_references` |
| Deadlines | "by {date}", "no later than", "transition", "phase-in" | `contains_deadline` |
| Assignments | "banks shall", "supervisors must", "board shall" | `contains_assignment` |
| Parameters | Percentages, risk weights, CCF, LGD, thresholds | `contains_parameter` |

---

## 4. OSFI Guidance

**Repository:** `OSFI_Guidance/`
**GitHub:** https://github.com/NadzThompson/OSFI-Guidance-Library

### Overview

The OSFI corpus contains 278 documents scraped from the OSFI guidance library (osfi-bsif.gc.ca/en/guidance). Unlike the other repos, there are **no scraper scripts** in this repository -- the content was pre-scraped and the JSON metadata was generated externally.

### Directory Layout

```
OSFI_Guidance/
  json/    -- 278 NOVA metadata files (121 fields each)
  md/      -- 278 normalized markdown content files
  html/    -- 278 source HTML files
  pdf/     -- 278 rendered PDFs
  docs/    -- Reference documentation and audit reports
```

### Metadata Schema (121 Fields)

OSFI has the most comprehensive metadata schema of all four repos. Key field groups:

**Authority and hierarchy:**
- `authority_level`: Integer on 0-100 scale (100=binding, 90=operational, 70=interpretive, 60=support, 40/30=contextual, 0=excluded)
- `authority_class`: 6 values (primary_normative, official_support, official_interpretive, contextual_summary, historical_reference, excluded)
- `nova_tier`: 1-3 (1=core binding, 2=supporting, 3=ancillary)
- `prudential_weight`: Float 0.0-1.0 for retrieval weighting

**Version control:**
- `version_id`: ISO date from `effective_date_start` (e.g., `"2025-04-01"`)
- `version_label`: 4-digit year (e.g., `"2025"`)
- `version_sort_key`: `YYYY-MM` for sorting

**Supersession chain:**
- `superseded_by_doc_id` / `supersedes_doc_id`: Bidirectional version links
- `current_version_flag`: Boolean
- `document_order_within_family`: Position in version sequence

**Package/chapter structure** (for multi-part guidelines like LAR, MCT):
- `is_package_page` / `is_chapter_page`: Boolean
- `parent_doc_id` / `child_doc_ids`: Hierarchy links
- `chapter_number` / `chapter_title`

**Sector applicability:**
- `sector`: Array (Banks, Trust and Loan Companies, Life Insurance, P&C Insurance, etc.)
- 8 boolean flags: `applies_to_banks`, `applies_to_life_insurance`, etc.

**Document classes** (16 types):
transmittal_letter (108), package_guideline (44), chapter_guideline (36), advisory (32), standalone_guideline (27), implementation_note (9), bulletin (4), guidance_note (4), instructions (3), regulatory_notice (3), assessment_tool (2), interpretive_faq (2), backgrounder (1), consultation_document (1), consultation_response (1), discussion_paper (1)

### Status Distribution

| Status | Count | Meaning |
|---|---|---|
| `final_current` | 244 | Published and in force |
| `superseded` | 20 | Replaced by newer version |
| `final_future_effective` | 9 | Published but not yet in force |
| `draft_or_consultation` | 5 | Still in development |

---

## 5. PRA / Bank of England

**Repository:** `PRA/`
**GitHub:** https://github.com/NadzThompson/PRA-BOE-Regulatory-Library

### Overview

The PRA corpus contains 677 documents from two UK regulatory sources: the PRA Rulebook (HTML) and Bank of England publications (PDF). Like OSFI, the original scrapers are not in the repo -- content was pre-scraped. A post-scrape enrichment script adds NOVA 3-layer fields.

### Directory Layout

```
PRA/
  scripts/
    enrich_pra_metadata.py           -- NOVA metadata enrichment (438 lines)
  PRA Rules/      {html, json, md, pdf}    -- 169 binding rulebook provisions
  PRA Guidance/   {html, json, md, pdf}    -- 168 supervisory statements
  BoE Guidance/   {pdf, json, md}          -- 293 Bank of England guidance PDFs
  PRA Glossary/   {html, json, md, pdf}    -- 25 defined terms
  PRA Legal Instruments/ {html, json, md, pdf} -- 16 statutory instruments
  PRA Sectors/    {html, json, md, pdf}    -- 5 sector scope documents
  PRA Forms/      {html, json, md, pdf}    -- 1 reporting template
  docs/           -- 5 Word documents (corpus guide, audit report, etc.)
```

### 5.1 PRA Rulebook Scraping

**Source:** prarulebook.co.uk
**Documents:** 169 rules + 168 guidance + 25 glossary + 16 instruments + 5 sectors + 1 form = 384 HTML documents

The HTML contains structured rule text with:
- Rule numbers and per-rule effective dates
- Chapter/section hierarchy
- Glossary term links
- Cross-references to other PRA/CRR provisions
- Amendment timeline

### 5.2 BoE Guidance (PDFs)

**Source:** bankofengland.co.uk
**Documents:** 293 PDFs (supervisory statements, policy statements, consultation papers)

PDFs are downloaded directly. Text is extracted to markdown for content analysis. No HTML intermediate for these documents.

### 5.3 PRA Metadata Enrichment

**Script:** `scripts/enrich_pra_metadata.py`

Key enrichment operations:

| Fix | Description |
|---|---|
| Sector reconstruction | Rebuilds character-exploded sector arrays (e.g., `["B","a","n","k","i","n","g"]` -> `["Banking"]`) |
| Jurisdiction normalization | `"UK"` -> `"United Kingdom (UK)"` |
| SHA256 backfill | Copies `raw_sha256` to `sha256` where missing |
| Effective date end | Sets end date for deleted/superseded documents |
| 15 NOVA fields | Adds structural_level, normative_weight, paragraph_role, cross_references, content flags, approval_status, audience, confidentiality |

**Content detection:**

| Detection | Method | Output |
|---|---|---|
| Normative weight | From document_class first, then text scan for "must/shall" vs "should" | `normative_weight` |
| Cross-references | Regex for PRA refs (`SS\d+/\d+`, `CP\d+/\d+`) and CRR articles | `cross_references` |
| Deadlines | Date patterns, transition periods | `contains_deadline` |
| Assignments | Firm/board requirement patterns | `contains_assignment` |
| Parameters | Thresholds, ratios, percentages | `contains_parameter` |

### Authority Level Distribution (PRA)

| Level | Count | Classification |
|---|---|---|
| 1 | 183 | Primary normative (PRA Rules + Legal Instruments) |
| 2 | 166 | Guidance/interpretive (Supervisory Statements) |
| 5 | 293 | Supportive guidance (BoE publications) |
| 7 | 35 | Contextual (Glossary, Sectors, Forms) |

---

## 6. Standardized Metadata Fields

### 6.1 authority_level

**Type:** Integer
**Purpose:** Numeric authority rank indicating how binding/authoritative a document is. Used at retrieval time for score boosting.

| Repo | Scale | Values |
|---|---|---|
| **US Fed** | OSFI 0-100 scale | 100 (eCFR, Final Rules), 70 (SR Letters), 40 (Proposed Rules), 30 (Notices) |
| **Basel** | 1-3 scale | 1 (primary normative), 2 (guidance), 3 (reference) |
| **OSFI** | 0-100 scale | 100/90 (primary normative), 70 (interpretive), 60 (support), 40/30 (contextual), 0 (excluded) |
| **PRA** | 1-7 scale | 1 (binding rules), 2 (guidance), 5 (BoE guidance), 7 (contextual) |

> **Note:** The scales are not yet fully harmonized across all repos. US Fed and OSFI use the same 0-100 scale. Basel uses 1-3 and PRA uses 1-7. For cross-corpus retrieval, a normalization layer is needed.

### 6.2 version_id

**Type:** String (ISO date, YYYY-MM-DD)
**Purpose:** Machine-comparable version identifier. Used for deduplication, version chain navigation, and as-of-date filtering.

| Repo | Source of version_id | Example |
|---|---|---|
| **US Fed (eCFR)** | Latest amendment date from eCFR versions API | `"2025-12-01"` |
| **US Fed (FR)** | Publication date from API | `"2000-06-01"` |
| **US Fed (SR)** | Document issuance date | `"2000-08-15"` |
| **Basel (chapters)** | `in_force_at` from BIS API | `"2028-01-01"` |
| **Basel (PDFs)** | Hard-coded `EFFECTIVE_DATES` map | `"2006-06-01"` |
| **OSFI** | `effective_date_start` | `"2025-04-01"` |
| **PRA** | `effective_date_start` or `original_effective_date` | `"2020-12-31"` |

### 6.3 version_label

**Type:** String (4-digit year)
**Purpose:** Human-readable version identifier for display and LLM prompt injection.

All repos now derive `version_label` as the first 4 characters of `version_id` (the year). Examples: `"2025"`, `"2028"`, `"2000"`.

### 6.4 Full Field Comparison

Fields present across all four repos (NOVA common schema):

| Field | US Fed | Basel | OSFI | PRA | Type |
|---|---|---|---|---|---|
| `doc_id` | Y | Y | Y | Y | string |
| `doc_family_id` | Y | Y | Y | - | string |
| `title` | Y | Y | Y | Y | string |
| `short_title` | Y | Y | Y | Y | string |
| `regulator` | Y | Y | Y | Y | string |
| `jurisdiction` | Y | Y | Y | Y | string |
| `document_class` | Y | Y | Y | Y | string enum |
| `authority_class` | Y | Y | Y | Y | string enum |
| `authority_level` | Y | Y | Y | Y | integer |
| `nova_tier` | Y | Y | Y | Y | integer |
| `status` | Y | Y | Y | Y | string enum |
| `current_version_flag` | Y | Y | Y | Y | boolean |
| `effective_date_start` | Y | Y | Y | Y | ISO date |
| `effective_date_end` | Y | Y | Y | Y | ISO date / null |
| `version_id` | Y | Y | Y | Y | ISO date |
| `version_label` | Y | Y | Y | Y | year string |
| `normative_weight` | Y | Y | Y | Y | string enum |
| `heading_path` | Y | Y | Y | Y | array[string] |
| `section_path` | Y | Y | Y | Y | string |
| `structural_level` | Y | Y | Y | Y | string enum |
| `paragraph_role` | Y | Y | - | Y | string enum |
| `citation_anchor` | Y | Y | Y | Y | string |
| `contains_definition` | Y | Y | - | Y | boolean |
| `contains_requirement` | Y | Y | - | Y | boolean |
| `contains_formula` | Y | Y | - | Y | boolean |
| `contains_deadline` | Y | Y | - | Y | boolean |
| `contains_parameter` | Y | Y | - | Y | boolean |
| `cross_references` | - | Y | Y | Y | array[string] |
| `superseded_by_doc_id` | - | Y | Y | Y | string / null |
| `supersedes_doc_id` | - | Y | Y | Y | string / null |
| `bm25_text` | Y | Y | Y | - | string |
| `vector_text_prefix` | Y | Y | Y | - | string |
| `sha256` / `normalized_text_sha256` | Y | Y | Y | Y | hex string |
| `parser_version` | Y | Y | Y | Y | string |
| `quality_score` | Y | Y | Y | Y | float |

---

## 7. NOVA 3-Layer Metadata Architecture

All repos follow the NOVA 3-layer architecture for metadata:

### Layer 1: Embedding (Baked into Vector Space)

Fields that shape semantic search behavior. Included in the text that gets embedded.

- `doc_id`, `short_title`, `document_class`, `heading_path`, `section_path`
- `regulator`, `structural_level`, `normative_weight`

### Layer 2: Index/Filter (Elasticsearch Facets, Gates, Boosts)

Fields used to filter, gate, and boost results at retrieval time. Stored as indexed keywords/integers.

- **Authority:** `status`, `authority_class`, `authority_level`, `nova_tier`, `normative_weight`
- **Version:** `version_id`, `version_label`, `current_version_flag`, `supersedes_doc_id`, `superseded_by_doc_id`
- **Temporal:** `effective_date_start`, `effective_date_end`
- **Content flags:** `contains_definition`, `contains_requirement`, `contains_formula`, `contains_deadline`, `contains_parameter`
- **Search text:** `bm25_text`, `vector_text_prefix`

### Layer 3: Prompt Injection (LLM Reasoning Context)

Fields injected into the LLM prompt alongside retrieved chunks, so the model can reason about source authority and currency.

```
TITLE: Regulation YY: Enhanced Prudential Standards
CITATION: #12cfr252
VERSION_ID: 2025-12-01
VERSION_LABEL: 2025
CURRENT_VERSION_FLAG: true
EFFECTIVE_DATE_START: 2025-12-01
STATUS: active
AUTHORITY_CLASS: primary_normative
AUTHORITY_LEVEL: 100
NOVA_TIER: 1
NORMATIVE_WEIGHT: mandatory
```

### Layer 4: Operational (Audit Trail)

Fields for pipeline tracking and reproducibility.

- `canonical_json_path`, `normalized_md_path`, `raw_path`
- `parser_version`, `normalizer_version`
- `quality_score`, `quality_flags`
- `scraped_on`, `enriched_timestamp`
- `normalized_text_sha256`

---

## 8. Pipeline Execution Reference

### US Federal Regulations

```bash
cd US_Fed_Regulations

# Full pipeline
python -m scrapers.run_all

# Individual scrapers
python -m scrapers.scrape_ecfr                     # All 59 eCFR parts
python -m scrapers.scrape_ecfr --parts 217 252     # Specific parts
python -m scrapers.scrape_federal_register          # All FR document types
python -m scrapers.scrape_federal_register --types final_rules
python -m scrapers.scrape_sr_letters                # All SR letters
python -m scrapers.scrape_sr_letters --years 2024 2025

# Post-processing enrichment
python -m scrapers.enrich_metadata                  # All sources
python -m scrapers.enrich_metadata --source ecfr    # Just eCFR
python -m scrapers.enrich_metadata --validate-only  # Dry run
```

### Basel Framework

```bash
cd "Basel Framework"

# Full scrape (all groups)
python scripts/scrape_basel_framework.py

# Specific groups
python scripts/scrape_basel_framework.py --group A B C
python scripts/scrape_basel_framework.py --group A --chapter CRE20

# Enrichment (PDF groups)
python scripts/enrich_metadata.py
python scripts/enrich_nova_fields.py

# Error recovery
python scripts/redownload_fixes.py
```

### PRA / Bank of England

```bash
cd PRA

# Post-scrape enrichment
python scripts/enrich_pra_metadata.py --output-dir .
```

### Rate Limiting Summary

| Repo | Delay | Timeout | Retries | Backoff |
|---|---|---|---|---|
| US Fed (eCFR) | 1.0s | 60s | None | None |
| US Fed (FR) | 0.5s | Default | None | None |
| US Fed (SR) | 1.5s | Default | None | None |
| Basel | 1.5s | 60s | 3 | 5s x attempt |

---

*Document generated: 2026-04-09*
*Covers repositories as of their latest commits.*
