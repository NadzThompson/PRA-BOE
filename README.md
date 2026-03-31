# NOVA PRA/BoE Regulatory Corpus

Comprehensive regulatory corpus from the UK Prudential Regulation Authority (PRA) and Bank of England (BoE), structured for the NOVA RAG pipeline. Every document has a raw source file and an enriched JSON metadata sidecar conforming to the NOVA 3-layer metadata architecture.

**Last updated:** March 2026
**Total:** 677 documents across 7 categories

---

## Corpus Summary

| Category | Documents | Raw Format | Description | Ingestion Priority |
|----------|-----------|------------|-------------|-------------------|
| **PRA Rules** | 169 | HTML | Binding rulebook provisions from prarulebook.co.uk | **P0 — ingest first** |
| **PRA Guidance** | 168 | HTML | Supervisory statements and statements of policy | **P0 — ingest first** |
| **BoE Guidance** | 293 | PDF | Bank of England prudential guidance documents | P1 |
| **PRA Glossary** | 25 | HTML | Defined terms and regulatory definitions | P1 |
| **PRA Legal Instruments** | 16 | HTML | Statutory instruments and legal orders | P1 |
| **PRA Sectors** | 5 | HTML | Sector-specific scope and application | P2 |
| **PRA Forms** | 1 | HTML | Regulatory reporting form templates | P2 |

---

## What to Ingest into the NOVA RAG Model

For each document, the pipeline ingests exactly **two files**:

1. **Raw content file** (HTML or PDF) — the original source as scraped from the regulator's website
2. **Enriched metadata sidecar** (JSON) — the NOVA 3-layer metadata to attach to each chunk

| Category | Raw File | Raw Path | JSON Metadata Path |
|----------|----------|----------|-------------------|
| **PRA Rules** | **HTML** | `PRA Rules/html/{name}.html` | `PRA Rules/json/{name}.json` |
| **PRA Guidance** | **HTML** | `PRA Guidance/html/{name}.html` | `PRA Guidance/json/{name}.json` |
| **BoE Guidance** | **PDF** | `BoE Guidance/pdf/{name}.pdf` | `BoE Guidance/json/{name}.json` |
| **PRA Glossary** | **HTML** | `PRA Glossary/html/{name}.html` | `PRA Glossary/json/{name}.json` |
| **PRA Legal Instruments** | **HTML** | `PRA Legal Instruments/html/{name}.html` | `PRA Legal Instruments/json/{name}.json` |
| **PRA Sectors** | **HTML** | `PRA Sectors/html/{name}.html` | `PRA Sectors/json/{name}.json` |
| **PRA Forms** | **HTML** | `PRA Forms/html/{name}.html` | `PRA Forms/json/{name}.json` |

The `md/` and `pdf/` subfolders contain **derived** content (pre-parsed markdown and rendered PDFs). These are for human reference only — the pipeline should ingest the raw HTML/PDF files paired with their JSON metadata.

### PRA Rules (169 documents) — Primary Corpus

**Ingest these first.** These are the binding PRA Rulebook provisions — the equivalent of the Basel Framework chapters but for the UK jurisdiction.

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `PRA Rules/html/*.html` | **HTML** | Original HTML scraped from prarulebook.co.uk. This is the raw source file for the NOVA pipeline. |
| **Enriched metadata** | `PRA Rules/json/*.json` | JSON | Full NOVA 3-layer metadata sidecar. Pair with the raw HTML file at ingestion time. |

The `md/` and `pdf/` subfolders contain derived content (pre-parsed markdown and rendered PDFs) for reference. **The pipeline should ingest the raw HTML + JSON pairs.**

### PRA Guidance (168 documents) — Primary Corpus

**Ingest alongside PRA Rules.** Supervisory statements (SS) and statements of policy (SoP) that explain how the PRA interprets and applies the rules.

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `PRA Guidance/html/*.html` | **HTML** | Original HTML from prarulebook.co.uk |
| **Enriched metadata** | `PRA Guidance/json/*.json` | JSON | Full NOVA metadata sidecar |

### BoE Guidance (293 documents) — Secondary Corpus

**Ingest after PRA Rules and Guidance.** Bank of England prudential guidance sourced from PDF publications. Includes consultation papers, policy statements, and supervisory approach documents.

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `BoE Guidance/pdf/*.pdf` | **PDF** | Original PDFs from bankofengland.co.uk. This is the raw source — no HTML exists for these documents. |
| **Enriched metadata** | `BoE Guidance/json/*.json` | JSON | Full NOVA metadata sidecar |

**Note:** No HTML subfolder — these were sourced directly from BoE-published PDFs, not web pages. The `md/` subfolder contains pre-extracted text for reference.

### PRA Glossary (25 documents)

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `PRA Glossary/html/*.html` | **HTML** | Regulatory definitions from prarulebook.co.uk |
| **Enriched metadata** | `PRA Glossary/json/*.json` | JSON | `normative_weight = mandatory` — definitions are binding |

### PRA Legal Instruments (16 documents)

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `PRA Legal Instruments/html/*.html` | **HTML** | Statutory instruments and legal orders |
| **Enriched metadata** | `PRA Legal Instruments/json/*.json` | JSON | `authority_level = 1` — primary legal authority |

### PRA Sectors (5 documents) and PRA Forms (1 document)

Lower priority reference content.

| What to ingest | Path | Raw Format |
|---------------|------|------------|
| **Raw content** + **Enriched metadata** | `PRA Sectors/html/*.html` + `PRA Sectors/json/*.json` | **HTML** + JSON |
| **Raw content** + **Enriched metadata** | `PRA Forms/html/*.html` + `PRA Forms/json/*.json` | **HTML** + JSON |

### Ingestion Pattern (All Groups)

For every document, the NOVA pipeline ingests exactly **two files**:

1. **Raw content file** — the original HTML or PDF as scraped from the source website
2. **Enriched metadata sidecar** — the JSON file with all NOVA 3-layer fields

The `md/` and `pdf/` subfolders (where they exist alongside HTML) are **derived** content for human reference. They are not the raw source and should not be used as the primary ingestion target.

---

## Folder Structure

```
PRA/
  PRA Rules/
    html/     <- Raw HTML from prarulebook.co.uk (169 files)
    md/       <- Pre-parsed markdown (169 files)
    json/     <- Enriched NOVA metadata (169 files)
    pdf/      <- Rendered PDFs (169 files)
  PRA Guidance/
    html/     <- Raw HTML (168 files)
    md/       <- Pre-parsed markdown (168 files)
    json/     <- Enriched NOVA metadata (168 files)
    pdf/      <- Rendered PDFs (168 files)
  BoE Guidance/
    pdf/      <- Raw PDFs from bankofengland.co.uk (293 files)
    md/       <- Pre-extracted text (293 files)
    json/     <- Enriched NOVA metadata (293 files)
  PRA Glossary/
    html/     <- Raw HTML (25 files)
    md/       <- Markdown (25 files)
    json/     <- Metadata (25 files)
    pdf/      <- PDFs (24 files)
  PRA Legal Instruments/
    html/     <- Raw HTML (16 files)
    md/       <- Markdown (16 files)
    json/     <- Metadata (16 files)
    pdf/      <- PDFs (8 files)
  PRA Sectors/
    html/ + md/ + json/ + pdf/    (5 files each)
  PRA Forms/
    html/ + md/ + json/ + pdf/    (1 file each)
  docs/       <- Reference documentation
  scripts/    <- Scraping and enrichment scripts
```

**Raw content formats by category:**

| Category | Raw Format | Source | Parser Required |
|----------|-----------|--------|-----------------|
| PRA Rules | **HTML** | prarulebook.co.uk | BeautifulSoup or use pre-parsed MD |
| PRA Guidance | **HTML** | prarulebook.co.uk | BeautifulSoup or use pre-parsed MD |
| BoE Guidance | **PDF** | bankofengland.co.uk | Azure Doc Intelligence / pymupdf, or use pre-parsed MD |
| PRA Glossary | **HTML** | prarulebook.co.uk | BeautifulSoup or use pre-parsed MD |
| PRA Legal Instruments | **HTML** | prarulebook.co.uk | BeautifulSoup or use pre-parsed MD |
| PRA Sectors | **HTML** | prarulebook.co.uk | BeautifulSoup or use pre-parsed MD |
| PRA Forms | **HTML** | prarulebook.co.uk | BeautifulSoup or use pre-parsed MD |

Every raw file has exactly one corresponding JSON metadata sidecar with the same filename stem.

---

## JSON Metadata Schema

Every JSON sidecar conforms to the NOVA 3-layer metadata architecture. Fields serve three distinct pipeline purposes:

### Layer 1 — Embedding Layer

| Field | Description | Coverage |
|-------|-------------|---------|
| `doc_id` | Unique identifier (e.g., `PRA-_capital-buffers`) | 100% |
| `short_title` | Abbreviated title | 100% |
| `document_class` | `rulebook_rule`, `supervisory_statement`, `statement_of_policy`, etc. | 100% |
| `heading_path` | Hierarchical breadcrumb | 100% |
| `section_path` | Flattened section path | 100% |
| `regulator` | `PRA` or `BoE` | 100% |
| `structural_level` | `chapter`, `document`, `definition` | 100% |
| `section_number` | Guideline reference number | varies |
| `normative_weight` | `mandatory` / `advisory` / `informational` | 100% |

### Layer 2 — Index/Filter Layer

| Field | Description | Coverage |
|-------|-------------|---------|
| `status` | `active`, `superseded`, `deleted` | 100% |
| `original_effective_date` | Date the rule/guidance **first came into force** (e.g., `2013-04-01` for SS12/13) | 50% |
| `effective_date_start` | Date of the **most recent amendment** to the current version | 92% (null for index pages) |
| `effective_dates_all` | Full array of all amendment dates in chronological order | 50% |
| `effective_date_end` | Date the document was superseded or deleted | deleted/superseded only |
| `scrape_date` | Date the document was scraped from the source website (NOT an effective date) | 100% |
| `current_version_flag` | `true` for active documents | 100% |
| `authority_class` | `primary_normative`, `guidance_interpretive`, etc. | 100% |
| `authority_level` | 1 (binding rules) to 7 (contextual) | 100% |
| `nova_tier` | 1 (core binding) to 5 (administrative) | 100% |
| `jurisdiction` | `United Kingdom (UK)` | 100% |
| `sector` | Array: `["Banking"]`, `["Insurance"]`, etc. | 100% |
| `paragraph_role` | `requirement`, `guidance`, `definition`, etc. | 100% |
| `is_appendix` | Boolean | 100% |
| `contains_definition` / `contains_formula` / `contains_requirement` | Content flags | 100% |
| `contains_deadline` / `contains_assignment` / `contains_parameter` | Content flags (from text analysis) | varies |
| `cross_references` | Array of PRA/CRR cross-references | varies |
| `approval_status` | `approved`, `superseded` | 100% |
| `audience` | Target readership | 100% |
| `confidentiality` | `public` | 100% |
| `superseded_by_doc_id` / `supersedes_doc_id` | Version chain links | where applicable |

### Layer 3 — Prompt Injection Layer

| Field | Description |
|-------|-------------|
| `title` | Full document title |
| `citation_anchor` | Precise citation reference |
| `version_id` / `version_label` | Temporal context |
| `status` | Active/superseded/deleted |
| `authority_class` | Normative vs interpretive |
| `normative_weight` | mandatory/advisory/informational |
| `paragraph_role` | requirement/guidance/definition |

### Layer 4 — Operational

| Field | Description | Coverage |
|-------|-------------|---------|
| `raw_path` | Path to raw source file | 50% |
| `sha256` | Content hash | 93% |
| `parser_version` | `pra-scraper-v1.0.0` or `pra-nova-enrichment-v1.0.0` or `boe-scraper-v1.0.0` | 100% |
| `quality_score` | 1.0 | 100% |

---

## Status Model

| Status | Count | Description |
|--------|-------|-------------|
| `active` | 654 | Current and in force |
| `deleted` | 16 | Withdrawn by the PRA |
| `superseded` | 7 | Replaced by a newer version |

---

## Normative Weight Distribution

| Weight | PRA Rules | PRA Guidance | BoE Guidance | Other | Total |
|--------|-----------|-------------|-------------|-------|-------|
| `mandatory` | 167 | 0 | 0 | 42 | 209 |
| `advisory` | 0 | 168 | 293 | 0 | 461 |
| `informational` | 2 | 0 | 0 | 5 | 7 |

---

## Sources

- PRA Rulebook: https://www.prarulebook.co.uk
- Bank of England Prudential Regulation: https://www.bankofengland.co.uk/prudential-regulation

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/enrich_pra_metadata.py` | NOVA 3-layer metadata enrichment for all 677 files |

## Related Documentation

| Document | Description |
|----------|-------------|
| `docs/PRA_Corpus_Audit_Report.docx` | Audit findings and remediation |
| `docs/PRA_Source_Verification_Report.docx` | Source verification against live PRA Rulebook |
| `docs/NOVA_Corpus_Guide.docx` | RAG pipeline guide |
| `docs/NOVA_Metadata_Build_Specification.docx` | Metadata field definitions |
| `docs/NOVA_RAG_Pipeline_Implementation_Guide.docx` | Pipeline implementation |
