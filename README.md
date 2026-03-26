# PRA Corpus

Regulatory content from the UK Prudential Regulation Authority (PRA) and Bank of England (BoE), structured for the NOVA metadata pipeline.

## Contents

**677 documents** across 7 categories:

| Category | Documents | Description |
|----------|-----------|-------------|
| BoE Guidance | 293 | Bank of England prudential guidance (sourced from PDFs) |
| PRA Rules | 169 | Binding rulebook provisions |
| PRA Guidance | 168 | Supervisory statements and statements of policy |
| PRA Glossary | 25 | Defined terms and definitions |
| PRA Legal Instruments | 16 | Statutory instruments and legal orders |
| PRA Sectors | 5 | Sector-specific landing content |
| PRA Forms | 1 | Regulatory reporting forms |

## Folder Structure

Each category folder contains up to four subfolders:

```
PRA Rules/
  json/   <- Metadata only (no content embedded)
  md/     <- Readable text content (authoritative)
  html/   <- Original HTML source from prarulebook.co.uk
  pdf/    <- Rendered PDF
```

**Note:** BoE Guidance has no HTML subfolder because it was sourced from BoE-published PDFs, not HTML pages.

## File Formats

- **JSON** (metadata only): One file per document. Contains identification, classification, NOVA pipeline fields, and supersession metadata. No content fields (content_markdown, content_html, extracted_text have been removed).
- **MD** (content): The authoritative text content. Use this for ingestion, search indexing, and embedding.
- **HTML** (source): The original HTML as scraped from prarulebook.co.uk. Not available for BoE Guidance.
- **PDF** (rendered): PDF rendering of the content. Some were converted from HTML and may have minor formatting differences from the markdown.

## Key Metadata Fields

| Field | Description | Coverage |
|-------|-------------|----------|
| `doc_id` | Unique identifier (e.g., `pra.rules.capital-buffers.2026`) | 100% |
| `title` | Full document title | 100% |
| `short_title` | Abbreviated title for display | 100% |
| `status` | Document status: `active`, `superseded`, or `deleted` | 100% |
| `regulator` | `PRA` or `BoE` | 100% |
| `document_class` | Type: `rulebook_rule`, `supervisory_statement`, `statement_of_policy`, etc. | 100% |
| `nova_tier` | NOVA importance tier (1 = core binding, 5 = administrative) | 100% |
| `jurisdiction` | `United Kingdom` | 100% |
| `authority_class` | `primary_normative`, `guidance_interpretive`, etc. | 100% |
| `effective_date_start` | Date the document version became effective | 100% |
| `current_version_flag` | `True` for active docs, `False` for superseded/deleted | 100% |
| `heading_path` | Array of section headings within the document | varies |
| `citation_anchor` | Anchor for citation linking | 100% |
| `superseded_by_doc_id` | Doc ID of replacement (if superseded) | 7 docs |
| `superseded_by_text` | Human-readable supersession explanation | 7 docs |

## Status Model

- **active** (654 docs): Current and in force.
- **deleted** (16 docs): Withdrawn by the PRA. `current_version_flag` = False.
- **superseded** (7 docs): Replaced by a newer version or different document. `current_version_flag` = False. The `superseded_by_text` field explains what replaced it.

### Superseded Documents

Three categories of superseded documents exist:

1. **Genuinely superseded** (3 docs): The document itself has been retired and replaced — e.g., SS3/19 replaced by SS5/25.
2. **Version superseded** (4 docs): The underlying guidance is still active, but the specific version in this corpus is outdated — e.g., SS18/15 April 2019 version superseded by March 2021 version.

All supersession metadata was verified against the live PRA Rulebook (prarulebook.co.uk) in March 2026.

## Sources

- PRA Rulebook: https://www.prarulebook.co.uk
- Bank of England Prudential Regulation: https://www.bankofengland.co.uk/prudential-regulation

## Related Documentation

See the `docs/` folder in this repository:

| Document | Description |
|----------|-------------|
| `PRA_Corpus_Audit_Report.docx` | Detailed audit findings, remediation steps, and final status |
| `PRA_Source_Verification_Report.docx` | Source verification against live PRA Rulebook and BoE websites |
| `NOVA_Corpus_Guide.docx` | Comprehensive guide covering RAG pipeline, ADLS migration, dual-store architecture, and metadata usage |
| `NOVA_Metadata_Build_Specification.docx` | NOVA pipeline metadata field definitions, roles, and the Three Rules |
| `NOVA_RAG_Pipeline_Implementation_Guide.docx` | Pipeline implementation guidance for Databricks ingestion and retrieval |
