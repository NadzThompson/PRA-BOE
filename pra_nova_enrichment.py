#!/usr/bin/env python3
"""
PRA NOVA Metadata Enrichment Pipeline
=======================================
Takes existing scraped PRA Rulebook and BoE Guidance JSON files and enriches
them with full NOVA-compatible metadata fields, aligning with the metadata
spec in 01_metadata_spec.py.

Key mappings:
  PRA content_type  →  NOVA document_class / authority_class / nova_tier
  PRA as_at_date    →  NOVA effective_date_start
  PRA applies_to    →  NOVA sector
  PRA timeline      →  NOVA version chain (supersedes/superseded_by)
  PRA title         →  NOVA guideline_number (extracted)

Output:
  - Enriched canonical JSON per document (PRA Rules/json_nova/, PRA Guidance/json_nova/)
  - Master metadata index (pra_metadata.json)
  - Enrichment report (pra_enrichment_report.json)

Usage:
    python pra_nova_enrichment.py [--dry-run] [--rules-only] [--guidance-only]
"""

import os
import sys
import json
import re
import hashlib
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional


# ─── CONFIGURATION ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
RULES_JSON_DIR = BASE_DIR / "PRA Rules" / "json"
GUIDANCE_JSON_DIR = BASE_DIR / "PRA Guidance" / "json"
# Output goes back into the same json folder (in-place enrichment)
RULES_OUTPUT_DIR = BASE_DIR / "PRA Rules" / "json"
GUIDANCE_OUTPUT_DIR = BASE_DIR / "PRA Guidance" / "json"

JURISDICTION = "United Kingdom"
REGULATOR_RULES = "PRA"
REGULATOR_GUIDANCE_SS = "PRA"
REGULATOR_GUIDANCE_BOE = "BoE"
PARSER_VERSION = "pra-nova-enrichment-v1.0.0"


# ─── DOCUMENT TYPE CLASSIFICATION ────────────────────────────────────────────

DOCTYPE_MAP = {
    "PRA Rule": {
        "document_class": "rulebook_rule",
        "authority_class": "primary_normative",
        "authority_level": 1,
        "nova_tier": 1,
        "source_type": "external_regulatory",
    },
    "Supervisory Statement": {
        "document_class": "supervisory_statement",
        "authority_class": "interpretive",
        "authority_level": 2,
        "nova_tier": 2,
        "source_type": "external_regulatory",
    },
    "Statement of Policy": {
        "document_class": "statement_of_policy",
        "authority_class": "interpretive",
        "authority_level": 2,
        "nova_tier": 2,
        "source_type": "external_regulatory",
    },
    "BoE Hosted Guidance": {
        "document_class": "boe_guidance",
        "authority_class": "interpretive",
        "authority_level": 2,
        "nova_tier": 2,
        "source_type": "external_regulatory",
    },
    "Legal Instrument": {
        "document_class": "legal_instrument",
        "authority_class": "primary_normative",
        "authority_level": 1,
        "nova_tier": 1,
        "source_type": "external_regulatory",
    },
}

# Default for unknown types
DEFAULT_DOCTYPE = {
    "document_class": "regulatory_other",
    "authority_class": "context",
    "authority_level": 3,
    "nova_tier": 3,
    "source_type": "external_regulatory",
}


# ─── SECTOR MAPPING (PRA applies_to → NOVA sector) ──────────────────────────

SECTOR_MAP = {
    # PRA Rulebook firm categories
    "CRR Firms": "Banking",
    "Non CRR Firms": "Banking",
    "Non-CRR Firms": "Banking",
    "Solvency II Firms": "Insurance",
    "SII Firms": "Insurance",
    "Non Solvency II Firms": "Insurance",
    "Non-SII Firms": "Insurance",
    "Non SII Firms": "Insurance",
    "Non-authorised parent undertakings": "Financial_Conglomerates",
    "Non-authorised persons": "Financial_Conglomerates",
    "Incoming firms": "Cross_Border",
    "All firms": "All",
}


def map_sectors(applies_to: list[str]) -> list[str]:
    """Map PRA firm categories to NOVA sector labels."""
    sectors = set()
    for firm_type in applies_to:
        mapped = SECTOR_MAP.get(firm_type.strip())
        if mapped:
            sectors.add(mapped)
        else:
            # Try partial matching
            lower = firm_type.lower()
            if "crr" in lower or "bank" in lower:
                sectors.add("Banking")
            elif "solvency" in lower or "insur" in lower:
                sectors.add("Insurance")
            else:
                sectors.add("Other")
    return sorted(sectors) if sectors else ["All"]


# ─── GUIDELINE NUMBER EXTRACTION ─────────────────────────────────────────────

LSS_PATTERN = re.compile(r"LSS\s*(\d+/\d+)", re.IGNORECASE)
SS_PATTERN = re.compile(r"(?<!L)SS\s*(\d+/\d+)", re.IGNORECASE)  # Negative lookbehind to skip LSS
SOP_PATTERN = re.compile(r"SoP\b", re.IGNORECASE)
PS_PATTERN = re.compile(r"PS\s*(\d+/\d+)", re.IGNORECASE)
CP_PATTERN = re.compile(r"CP\s*(\d+/\d+)", re.IGNORECASE)


def extract_guideline_number(title: str, content_type: str) -> Optional[str]:
    """Extract the official guideline number from the title."""
    # LSS (Legacy Supervisory Statement) — check BEFORE SS to avoid false match
    m = LSS_PATTERN.search(title)
    if m:
        return f"LSS{m.group(1)}"

    # SS (Supervisory Statement)
    m = SS_PATTERN.search(title)
    if m:
        return f"SS{m.group(1)}"

    # PS (Policy Statement)
    m = PS_PATTERN.search(title)
    if m:
        return f"PS{m.group(1)}"

    # CP (Consultation Paper)
    m = CP_PATTERN.search(title)
    if m:
        return f"CP{m.group(1)}"

    # PRA Rules: use the title itself as the "part name" identifier
    if content_type == "PRA Rule":
        return title  # e.g. "Capital Buffers", "Credit Risk"

    # SoP: extract from title
    if content_type == "Statement of Policy" or SOP_PATTERN.search(title):
        # Clean up "SoP – ..." prefix
        cleaned = re.sub(r"^SoP\s*[-–—]\s*", "", title, flags=re.IGNORECASE)
        return f"SoP: {cleaned}" if cleaned != title else title

    return None


# ─── DATE PARSING ─────────────────────────────────────────────────────────────

def parse_pra_date(date_str: str) -> Optional[str]:
    """Parse PRA date formats to ISO YYYY-MM-DD."""
    if not date_str:
        return None

    # Try DD-MM-YYYY (PRA as_at_date format)
    for fmt in ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%B %Y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ─── DOC_ID GENERATION ────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a slug suitable for doc_id."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = s.strip("-")
    return s[:80]


def generate_doc_id(title: str, content_type: str, as_at_date: str, slug_from_file: str) -> str:
    """Generate a stable NOVA doc_id."""
    guideline_num = extract_guideline_number(title, content_type)
    date_part = parse_pra_date(as_at_date) or "undated"
    year = date_part[:4] if date_part != "undated" else "undated"

    if content_type == "PRA Rule":
        return f"pra.rules.{slug_from_file}.{year}"

    if guideline_num:
        num_slug = slugify(guideline_num)
        return f"pra.{num_slug}.{year}"

    # Fallback: use content type + slug
    type_prefix = slugify(content_type) if content_type else "doc"
    return f"pra.{type_prefix}.{slug_from_file}.{year}"


def generate_doc_family_id(title: str, content_type: str, slug_from_file: str) -> str:
    """Generate a stable family ID (version-independent)."""
    guideline_num = extract_guideline_number(title, content_type)

    if content_type == "PRA Rule":
        return f"pra.rules.{slug_from_file}"

    if guideline_num:
        return f"pra.{slugify(guideline_num)}"

    type_prefix = slugify(content_type) if content_type else "doc"
    return f"pra.{type_prefix}.{slug_from_file}"


# ─── SHORT TITLE GENERATION ──────────────────────────────────────────────────

def generate_short_title(title: str, content_type: str) -> str:
    """Generate a compact short_title from the full title."""
    guideline_num = extract_guideline_number(title, content_type)

    if content_type == "PRA Rule":
        # e.g. "Capital Buffers" → "Capital Buffers (PRA Rule)"
        return f"{title} (PRA Rule)"

    if guideline_num:
        # e.g. "SS6/14 – Implementing CRD: Capital buffers" → "SS6/14"
        return guideline_num

    # Truncate long titles
    if len(title) > 60:
        return title[:57] + "..."
    return title


# ─── VERSION CHAIN BUILDING ──────────────────────────────────────────────────

def build_version_chain(timeline: dict, slug_from_file: str, content_type: str, title: str) -> dict:
    """Extract version chain info from PRA timeline data."""
    result = {
        "version_dates": [],
        "total_amendments": 0,
        "current_version_date": None,
    }

    if not timeline:
        return result

    # version_dates is a list of date strings
    version_dates = timeline.get("version_dates", [])
    past_versions = timeline.get("past_versions", [])
    total_amendments = timeline.get("total_amendments", 0)

    result["version_dates"] = version_dates
    result["total_amendments"] = total_amendments

    # Past versions have {date, url} or similar structure
    if past_versions:
        result["past_versions"] = past_versions

    return result


# ─── STATUS DETERMINATION ─────────────────────────────────────────────────────

def determine_status(timeline: dict, as_at_date: str) -> str:
    """Determine document status from timeline and as_at_date."""
    # PRA documents shown on the current rulebook are active
    # Documents with "(Deleted)" in title would be superseded
    # For now, all current-view documents are active
    return "active"


# ─── NOISE CLEANING ───────────────────────────────────────────────────────────

# Patterns that mark the start of page-chrome noise at end of content
NOISE_MARKERS = [
    r"Convert this page to PDF",
    r"\[?\s*Prudential Regulation\s*//",           # Footer publication cards
    r"Other prudential regulation releases",
    r"View more Other prudential regulation",
    r"Back to top\s*$",
]
NOISE_RE = re.compile(
    r"(?:\n|\r\n)*\s*(?:" + "|".join(NOISE_MARKERS) + r").*",
    re.DOTALL | re.IGNORECASE,
)

# Social media / irrelevant links in timeline boe_references
SOCIAL_DOMAINS = {"facebook.com", "twitter.com", "linkedin.com", "youtube.com",
                  "instagram.com", "x.com"}


def clean_content(text: str) -> str:
    """Strip page-chrome noise from the end of markdown/html content."""
    if not text:
        return text

    # 1. Cut everything from the first noise marker onwards
    cleaned = NOISE_RE.sub("", text)

    # 2. Strip trailing whitespace
    cleaned = cleaned.rstrip()

    return cleaned


def clean_html_content(html_str: str) -> str:
    """Strip noise from HTML content."""
    if not html_str:
        return html_str

    # Remove "Convert this page to PDF" link and everything after it
    # in common HTML patterns
    patterns = [
        r'<a[^>]*>Convert this page to PDF</a>.*',
        r'<div[^>]*class="[^"]*other-releases[^"]*".*',
        r'<footer.*',
    ]
    cleaned = html_str
    for pat in patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.DOTALL | re.IGNORECASE)

    return cleaned.rstrip()


def clean_timeline_refs(timeline: dict) -> dict:
    """Remove social media and noise links from timeline boe_references."""
    if not timeline:
        return timeline

    boe_refs = timeline.get("boe_references", [])
    if boe_refs:
        cleaned = []
        for ref in boe_refs:
            if isinstance(ref, dict):
                url = ref.get("url", "")
                # Skip social media links
                if any(domain in url.lower() for domain in SOCIAL_DOMAINS):
                    continue
                cleaned.append(ref)
            elif isinstance(ref, str):
                if any(domain in ref.lower() for domain in SOCIAL_DOMAINS):
                    continue
                cleaned.append(ref)
            else:
                cleaned.append(ref)
        timeline["boe_references"] = cleaned

    return timeline


def extract_boe_pdf_urls(content_md: str, content_html: str) -> list[str]:
    """Extract Bank of England PDF URLs referenced in the content."""
    pdfs = set()
    for link in re.findall(r'\((/\-/media/boe/[^)\s]*\.pdf)', content_md or ""):
        pdfs.add(f"https://www.bankofengland.co.uk{link}")
    for link in re.findall(r'href="(/\-/media/boe/[^"\s]*\.pdf)', content_html or ""):
        pdfs.add(f"https://www.bankofengland.co.uk{link}")
    return sorted(pdfs)


# ─── CONTENT QUALITY FLAGS ────────────────────────────────────────────────────

def detect_content_flags(content_md: str) -> dict:
    """Detect content characteristics from markdown."""
    flags = {
        "contains_definition": False,
        "contains_formula": False,
        "contains_requirement": False,
    }

    if not content_md:
        return flags

    lower = content_md.lower()

    # Definitions: "means", "is defined as", "for the purposes of"
    if re.search(r'\bmeans\b|\bdefined as\b|\bfor the purposes of\b|\brefers to\b', lower):
        flags["contains_definition"] = True

    # Formulas: mathematical expressions, "=" with numbers, percentage calculations
    if re.search(r'[=×÷∑∏]|\bformula\b|\bcalculat[ei]', lower):
        flags["contains_formula"] = True

    # Requirements: "must", "shall", "required to", "a firm must"
    if re.search(r'\bmust\b|\bshall\b|\brequired to\b|\bmust not\b', lower):
        flags["contains_requirement"] = True

    return flags


# ─── SHA256 HELPER ────────────────────────────────────────────────────────────

def compute_sha256(content: str) -> str:
    """Compute SHA256 of content string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ─── MAIN ENRICHMENT FUNCTION ────────────────────────────────────────────────

def enrich_document(file_path: Path, is_rule: bool = True) -> dict:
    """Enrich a single PRA JSON file with NOVA metadata.

    Returns the enriched document dict.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    metadata = raw.get("metadata", {})
    title = raw.get("title", metadata.get("title", ""))
    content_type = metadata.get("content_type", "PRA Rule" if is_rule else "Supervisory Statement")
    as_at_date = metadata.get("as_at_date", "")
    source_url = metadata.get("source_url", "")
    content_md_raw = raw.get("content_markdown", "")
    content_html_raw = raw.get("content_html", "")
    applies_to = metadata.get("applies_to", [])
    timeline = metadata.get("timeline", {})
    sections = metadata.get("sections", [])
    related_guidance = metadata.get("related_guidance", [])
    related_ps = metadata.get("related_policy_statements", [])
    related_li = metadata.get("related_legal_instruments", [])

    # --- CLEAN NOISE from content ---
    content_md = clean_content(content_md_raw)
    content_html = clean_html_content(content_html_raw)
    timeline = clean_timeline_refs(timeline)

    # --- Extract BoE PDF URLs (before cleaning removes links) ---
    boe_pdf_urls = extract_boe_pdf_urls(content_md_raw, content_html_raw)

    # Derive slug from filename
    slug = file_path.stem
    if slug.startswith("_"):
        slug = slug[1:]

    # --- NOVA field generation ---
    dtype_info = DOCTYPE_MAP.get(content_type, DEFAULT_DOCTYPE)
    doc_id = generate_doc_id(title, content_type, as_at_date, slug)
    family_id = generate_doc_family_id(title, content_type, slug)
    short_title = generate_short_title(title, content_type)
    guideline_number = extract_guideline_number(title, content_type)
    effective_date = parse_pra_date(as_at_date)
    sectors = map_sectors(applies_to)
    status = determine_status(timeline, as_at_date)
    content_flags = detect_content_flags(content_md)
    sha256 = compute_sha256(content_md or content_html or "")

    # Version info
    version_chain = build_version_chain(timeline, slug, content_type, title)
    version_dates = version_chain.get("version_dates", [])

    # Determine current_version_flag (if this is the latest version date)
    current_version_flag = True  # Default: all scraped from current view
    version_label = effective_date[:4] if effective_date else None

    # Regulator assignment
    regulator = REGULATOR_RULES
    if content_type in ("BoE Hosted Guidance",):
        regulator = REGULATOR_GUIDANCE_BOE

    # Build the enriched document
    enriched = {
        # === NOVA Common Fields ===
        "doc_id": doc_id,
        "title": title,
        "short_title": short_title,
        "document_class": dtype_info["document_class"],
        "source_type": dtype_info["source_type"],
        "raw_path": str(file_path.relative_to(BASE_DIR)),
        "canonical_path": None,  # Set during ingestion
        "sha256": sha256,
        "parser_version": PARSER_VERSION,
        "quality_score": 1.0,

        # === NOVA Regulatory Fields ===
        "regulator": regulator,
        "regulator_acronym": regulator,
        "doc_family_id": family_id,
        "version_id": effective_date or "current",
        "version_label": version_label,
        "version_sort_key": effective_date or "9999-99-99",
        "guideline_number": guideline_number,
        "status": status,
        "current_version_flag": current_version_flag,
        "effective_date_start": effective_date,
        "effective_date_end": None,
        "authority_class": dtype_info["authority_class"],
        "authority_level": dtype_info["authority_level"],
        "nova_tier": dtype_info["nova_tier"],
        "jurisdiction": JURISDICTION,
        "sector": sectors[0] if len(sectors) == 1 else ", ".join(sectors),
        "supersedes_doc_id": None,
        "superseded_by_doc_id": None,

        # === Content flags ===
        "contains_definition": content_flags["contains_definition"],
        "contains_formula": content_flags["contains_formula"],
        "contains_requirement": content_flags["contains_requirement"],

        # === BoE-hosted PDF URLs (full content lives here) ===
        "boe_pdf_urls": boe_pdf_urls,

        # === PRA-specific metadata (preserved, cleaned) ===
        "pra_metadata": {
            "source_url": source_url,
            "content_type": content_type,
            "scrape_date": metadata.get("scrape_date"),
            "as_at_date": as_at_date,
            "applies_to": applies_to,
            "chapters": metadata.get("chapters", []),
            "related_guidance": related_guidance,
            "related_policy_statements": related_ps,
            "related_legal_instruments": related_li,
            "timeline": timeline,  # cleaned of social media noise
            "sections": sections,
            "section_count": metadata.get("section_count", 0),
            "rule_count": metadata.get("rule_count", 0),
        },

        # === Content (cleaned of page-chrome noise) ===
        "content_markdown": content_md,
        "content_html": content_html,
    }

    return enriched


# ─── VERSION CHAIN RESOLUTION ────────────────────────────────────────────────

def resolve_version_chains(enriched_docs: list[dict]) -> list[dict]:
    """After enriching all docs, resolve supersedes/superseded_by across families.

    Groups documents by doc_family_id, sorts by version_sort_key, and sets:
      - supersedes_doc_id → previous version's doc_id
      - superseded_by_doc_id → next version's doc_id
      - current_version_flag → True only for the latest version
      - status → 'superseded' for non-latest versions
    """
    from collections import defaultdict

    families: dict[str, list[dict]] = defaultdict(list)
    for doc in enriched_docs:
        fid = doc.get("doc_family_id")
        if fid:
            families[fid].append(doc)

    for fid, members in families.items():
        if len(members) <= 1:
            continue

        # Sort by version_sort_key ascending
        members.sort(key=lambda d: d.get("version_sort_key", ""))

        for i, doc in enumerate(members):
            if i > 0:
                doc["supersedes_doc_id"] = members[i - 1]["doc_id"]
            if i < len(members) - 1:
                doc["superseded_by_doc_id"] = members[i + 1]["doc_id"]
                doc["current_version_flag"] = False
                doc["status"] = "superseded"
            else:
                doc["current_version_flag"] = True
                doc["status"] = "active"

    return enriched_docs


# ─── MASTER METADATA INDEX ───────────────────────────────────────────────────

def build_master_index(enriched_docs: list[dict]) -> dict:
    """Build a master metadata index (like osfi_guidance_metadata.json)."""
    documents = []
    for doc in enriched_docs:
        entry = {
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "short_title": doc["short_title"],
            "document_class": doc["document_class"],
            "source_type": doc["source_type"],
            "regulator": doc["regulator"],
            "guideline_number": doc["guideline_number"],
            "status": doc["status"],
            "current_version_flag": doc["current_version_flag"],
            "effective_date_start": doc["effective_date_start"],
            "jurisdiction": doc["jurisdiction"],
            "sector": doc["sector"],
            "authority_class": doc["authority_class"],
            "nova_tier": doc["nova_tier"],
            "doc_family_id": doc["doc_family_id"],
            "version_id": doc["version_id"],
            "supersedes_doc_id": doc["supersedes_doc_id"],
            "superseded_by_doc_id": doc["superseded_by_doc_id"],
            "sha256": doc["sha256"],
            "pra_source_url": doc["pra_metadata"]["source_url"],
            "pra_applies_to": doc["pra_metadata"]["applies_to"],
            "pra_rule_count": doc["pra_metadata"]["rule_count"],
            "pra_section_count": doc["pra_metadata"]["section_count"],
            "pra_related_guidance_count": len(doc["pra_metadata"]["related_guidance"]),
            "pra_related_ps_count": len(doc["pra_metadata"]["related_policy_statements"]),
            "contains_definition": doc["contains_definition"],
            "contains_formula": doc["contains_formula"],
            "contains_requirement": doc["contains_requirement"],
        }
        documents.append(entry)

    return {
        "metadata": {
            "title": "PRA / Bank of England Regulatory Corpus — Master Metadata Index",
            "regulator": "PRA",
            "jurisdiction": JURISDICTION,
            "generated_date": datetime.now().isoformat(),
            "generator": PARSER_VERSION,
            "document_count": len(documents),
        },
        "documents": documents,
    }


# ─── ENRICHMENT REPORT ───────────────────────────────────────────────────────

def build_report(enriched_docs: list[dict], errors: list[dict]) -> dict:
    """Build a report summarizing the enrichment run."""
    from collections import Counter

    doc_classes = Counter(d["document_class"] for d in enriched_docs)
    statuses = Counter(d["status"] for d in enriched_docs)
    sectors = Counter(d["sector"] for d in enriched_docs)
    tiers = Counter(d["nova_tier"] for d in enriched_docs)
    has_guideline_num = sum(1 for d in enriched_docs if d["guideline_number"])
    has_effective_date = sum(1 for d in enriched_docs if d["effective_date_start"])
    has_definition = sum(1 for d in enriched_docs if d["contains_definition"])
    has_formula = sum(1 for d in enriched_docs if d["contains_formula"])
    has_requirement = sum(1 for d in enriched_docs if d["contains_requirement"])

    return {
        "run_date": datetime.now().isoformat(),
        "total_processed": len(enriched_docs),
        "errors": len(errors),
        "error_details": errors,
        "by_document_class": dict(doc_classes),
        "by_status": dict(statuses),
        "by_sector": dict(sectors),
        "by_nova_tier": dict(tiers),
        "field_coverage": {
            "doc_id": len(enriched_docs),
            "guideline_number": has_guideline_num,
            "effective_date_start": has_effective_date,
            "contains_definition": has_definition,
            "contains_formula": has_formula,
            "contains_requirement": has_requirement,
        },
    }


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PRA NOVA Metadata Enrichment")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--rules-only", action="store_true", help="Process only PRA Rules")
    parser.add_argument("--guidance-only", action="store_true", help="Process only PRA Guidance")
    args = parser.parse_args()

    enriched_docs = []
    errors = []

    # --- Process PRA Rules ---
    if not args.guidance_only:
        print(f"\n{'='*60}")
        print("ENRICHING PRA RULES")
        print(f"{'='*60}")

        if RULES_JSON_DIR.exists():
            SKIP_FILES = {"_rule-change-timelines.json", "guidance-index.json",
                          "pra-rules-index.json", "_boe-hosted-guidance-index.json"}
            json_files = sorted(f for f in RULES_JSON_DIR.glob("*.json")
                               if not f.name.startswith("_") and f.name not in SKIP_FILES
                               and "index" not in f.name.lower())
            print(f"Found {len(json_files)} PRA Rules JSON files")

            for fpath in json_files:
                try:
                    doc = enrich_document(fpath, is_rule=True)
                    enriched_docs.append(doc)
                    print(f"  ✓ {doc['doc_id']} — {doc['short_title']}")
                except Exception as exc:
                    errors.append({"file": str(fpath), "error": str(exc)})
                    print(f"  ✗ {fpath.name}: {exc}")

    # --- Process PRA Guidance ---
    if not args.rules_only:
        print(f"\n{'='*60}")
        print("ENRICHING PRA GUIDANCE")
        print(f"{'='*60}")

        if GUIDANCE_JSON_DIR.exists():
            SKIP_GUIDANCE = {"_boe-hosted-guidance-index.json", "guidance-index.json",
                             "pra-rules-index.json"}
            json_files = sorted(f for f in GUIDANCE_JSON_DIR.glob("*.json")
                               if not f.name.startswith("_") and f.name not in SKIP_GUIDANCE
                               and f.name != "guidance-index.json")
            print(f"Found {len(json_files)} PRA Guidance JSON files")

            for fpath in json_files:
                try:
                    doc = enrich_document(fpath, is_rule=False)
                    enriched_docs.append(doc)
                    print(f"  ✓ {doc['doc_id']} — {doc['short_title']}")
                except Exception as exc:
                    errors.append({"file": str(fpath), "error": str(exc)})
                    print(f"  ✗ {fpath.name}: {exc}")

    # --- Resolve version chains ---
    print(f"\n{'='*60}")
    print("RESOLVING VERSION CHAINS")
    print(f"{'='*60}")
    enriched_docs = resolve_version_chains(enriched_docs)
    print(f"Processed {len(enriched_docs)} documents across version families")

    # --- Build outputs ---
    if not args.dry_run:
        # Write enriched JSONs
        rules_written = 0
        guidance_written = 0

        for doc in enriched_docs:
            raw_path = doc.get("raw_path", "")
            if "PRA Rules" in raw_path:
                out_dir = RULES_OUTPUT_DIR
                rules_written += 1
            else:
                out_dir = GUIDANCE_OUTPUT_DIR
                guidance_written += 1

            out_dir.mkdir(parents=True, exist_ok=True)

            # Write back to original filename (in-place enrichment)
            original_fname = Path(raw_path).name
            out_path = out_dir / original_fname

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2, ensure_ascii=False, default=str)

        print(f"\nWrote {rules_written} enriched rule JSONs to {RULES_OUTPUT_DIR}")
        print(f"Wrote {guidance_written} enriched guidance JSONs to {GUIDANCE_OUTPUT_DIR}")

        # Write master index
        index = build_master_index(enriched_docs)
        index_path = BASE_DIR / "pra_metadata.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False, default=str)
        print(f"Wrote master index ({len(enriched_docs)} docs) to {index_path}")

        # Write report
        report = build_report(enriched_docs, errors)
        report_path = BASE_DIR / "pra_enrichment_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"Wrote enrichment report to {report_path}")

    else:
        print("\n[DRY RUN] No files written.")

    # --- Summary ---
    report = build_report(enriched_docs, errors)
    print(f"\n{'='*60}")
    print("ENRICHMENT SUMMARY")
    print(f"{'='*60}")
    print(f"Total processed: {report['total_processed']}")
    print(f"Errors:          {report['errors']}")
    print(f"\nBy document class:")
    for cls, count in sorted(report["by_document_class"].items()):
        print(f"  {cls}: {count}")
    print(f"\nBy sector:")
    for sec, count in sorted(report["by_sector"].items()):
        print(f"  {sec}: {count}")
    print(f"\nField coverage:")
    for field_name, count in report["field_coverage"].items():
        pct = (count / report["total_processed"] * 100) if report["total_processed"] else 0
        print(f"  {field_name}: {count}/{report['total_processed']} ({pct:.0f}%)")

    if errors:
        print(f"\nERRORS:")
        for e in errors:
            print(f"  {e['file']}: {e['error']}")


if __name__ == "__main__":
    main()
