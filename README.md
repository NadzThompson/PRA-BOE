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

Each document consists of a **raw content file** (the source to parse and chunk) and a **JSON metadata sidecar** (the enriched metadata to attach to each chunk). Both are required at ingestion time.

### PRA Rules (169 documents) — Primary Corpus

**Ingest these first.** These are the binding PRA Rulebook provisions — the equivalent of the Basel Framework chapters but for the UK jurisdiction.

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `PRA Rules/html/*.html` | HTML | Original HTML scraped from prarulebook.co.uk. Parse with BeautifulSoup. |
| **Parsed content** | `PRA Rules/md/*.md` | Markdown | Pre-parsed text. Use as primary ingestion source for text extraction. |
| **Metadata sidecar** | `PRA Rules/json/*.json` | JSON | Full NOVA 3-layer metadata. Attach to each chunk at ingestion time. |
| **Rendered PDF** | `PRA Rules/pdf/*.pdf` | PDF | For reference/backup only. |

### PRA Guidance (168 documents) — Primary Corpus

**Ingest alongside PRA Rules.** Supervisory statements (SS) and statements of policy (SoP) that explain how the PRA interprets and applies the rules.

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `PRA Guidance/html/*.html` | HTML | Original HTML from prarulebook.co.uk |
| **Parsed content** | `PRA Guidance/md/*.md` | Markdown | Pre-parsed text |
| **Metadata sidecar** | `PRA Guidance/json/*.json` | JSON | Full NOVA metadata |

### BoE Guidance (293 documents) — Secondary Corpus

**Ingest after PRA Rules and Guidance.** Bank of England prudential guidance sourced from PDF publications. Includes consultation papers, policy statements, and supervisory approach documents.

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `BoE Guidance/pdf/*.pdf` | PDF | Original PDFs from bankofengland.co.uk. Requires text extraction (Azure Document Intelligence or pymupdf) before chunking. |
| **Parsed content** | `BoE Guidance/md/*.md` | Markdown | Pre-extracted text from PDFs |
| **Metadata sidecar** | `BoE Guidance/json/*.json` | JSON | Full NOVA metadata |

**Note:** No HTML subfolder — these were sourced from BoE-published PDFs, not web pages.

### PRA Glossary (25 documents)

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `PRA Glossary/html/*.html` | HTML | Regulatory definitions from prarulebook.co.uk |
| **Metadata sidecar** | `PRA Glossary/json/*.json` | JSON | `normative_weight = mandatory` — definitions are binding |

### PRA Legal Instruments (16 documents)

| What to ingest | Path | Raw Format | Notes |
|---------------|------|------------|-------|
| **Raw content** | `PRA Legal Instruments/html/*.html` | HTML | Statutory instruments and legal orders |
| **Metadata sidecar** | `PRA Legal Instruments/json/*.json` | JSON | `authority_level = 1` — primary legal authority |

### PRA Sectors (5 documents) and PRA Forms (1 document)

Lower priority reference content.

| What to ingest | Path | Raw Format |
|---------------|------|------------|
| `PRA Sectors/html/*.html` + `PRA Sectors/json/*.json` | HTML + JSON |
| `PRA Forms/html/*.html` + `PRA Forms/json/*.json` | HTML + JSON |

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
| `effective_date_start` | Date the document became effective | 92% |
| `effective_date_end` | End date (for superseded/deleted docs) | deleted/superseded only |
| `current_version_flag` | `true` for active documents | 100% |
| `authority_class` | `primary_normative`, `guidance_interpretive`, etc. | 100% |
| `authority_level` | 1 (binding rules) to 7 (contextual) | 100% |
| `nova_tier` | 1 (core binding) to 5 (administrative) | 100% |
| `jurisdiction` | `United Kingdom` | 100% |
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
