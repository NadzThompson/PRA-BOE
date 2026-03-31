#!/usr/bin/env python3
"""
PRA Corpus — NOVA 3-Layer Metadata Enrichment
===============================================
Fixes all data quality issues and adds 15 missing NOVA fields to all 677
JSON metadata files in the PRA corpus.

Fixes:
  1. BoE Guidance sector bug (character-exploded arrays)
  2. Jurisdiction normalization (UK -> United Kingdom (UK))
  3. Sector type normalization (string -> array)
  4. 15 missing NOVA fields (normative_weight, structural_level, etc.)
  5. sha256 backfill from raw_sha256 where missing
  6. raw_path backfill from actual file locations
  7. effective_date_end for deleted/superseded docs
  8. approval_status derived from status

Usage:
    python scripts/enrich_pra_metadata.py [--output-dir .]
"""

import hashlib
import json
import re
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# SECTOR FIX — reconstruct from character-exploded arrays
# ═══════════════════════════════════════════════════════════════════════════

KNOWN_SECTORS = [
    "Banking",
    "Insurance",
    "Financial_Conglomerates",
    "Credit_Unions",
    "Designated_Investment_Firms",
    "Building_Societies",
]


def fix_sector(sector_val):
    """Fix sector field — normalize to array of proper strings."""
    if sector_val is None:
        return ["Banking"]

    # Already a proper array of full strings
    if isinstance(sector_val, list):
        # Check if it's character-exploded
        if all(len(s) <= 1 for s in sector_val):
            # Reconstruct from characters
            joined = "".join(sector_val).strip()
            if not joined:
                return ["Banking"]
            # Split on comma-space or comma
            parts = [p.strip().replace(" ", "_") for p in joined.split(",") if p.strip()]
            # Validate against known sectors
            result = []
            for part in parts:
                for known in KNOWN_SECTORS:
                    if part.lower().replace("_", "") == known.lower().replace("_", ""):
                        result.append(known)
                        break
                else:
                    # Fuzzy match: if the joined chars contain a known sector name
                    for known in KNOWN_SECTORS:
                        if known.lower().replace("_", "") in part.lower().replace("_", ""):
                            result.append(known)
                            break
            if not result:
                # Last resort: try to match the joined string
                j = joined.lower()
                if "bank" in j:
                    result.append("Banking")
                if "insur" in j:
                    result.append("Insurance")
                if "conglo" in j:
                    result.append("Financial_Conglomerates")
                if "credit" in j and "union" in j:
                    result.append("Credit_Unions")
            return result if result else ["Banking"]
        else:
            # Already proper array
            return sector_val

    # String value — convert to array
    if isinstance(sector_val, str):
        if not sector_val.strip():
            return ["Banking"]
        parts = [p.strip() for p in sector_val.split(",") if p.strip()]
        return parts

    return ["Banking"]


# ═══════════════════════════════════════════════════════════════════════════
# NORMATIVE WEIGHT DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def detect_normative_weight_from_class(doc_class, authority_class=None):
    """Derive normative_weight from document_class."""
    mandatory_classes = {
        "rulebook_rule", "rulebook_chapter", "statutory_instrument",
        "legal_instrument", "binding_technical_standard",
    }
    advisory_classes = {
        "supervisory_statement", "statement_of_policy",
        "consultation_paper", "policy_statement",
    }
    informational_classes = {
        "glossary_definition", "sector_overview", "reporting_form",
        "rule_timeline", "index", "context",
    }

    if doc_class in mandatory_classes:
        return "mandatory"
    if doc_class in advisory_classes:
        return "advisory"
    if doc_class in informational_classes:
        return "informational"

    # Fallback on authority_class
    if authority_class in ("primary_normative", "primary normative"):
        return "mandatory"
    if authority_class in ("guidance_interpretive", "interpretive"):
        return "advisory"
    return "informational"


def detect_normative_weight_from_text(text):
    """Detect normative weight from markdown text content."""
    if not text:
        return None

    t = text.lower()
    mandatory_count = len(re.findall(r'\b(?:must|shall|is required to|are required to)\b', t))
    advisory_count = len(re.findall(r'\b(?:should|is expected to|are expected to)\b', t))
    permissive_count = len(re.findall(r'\b(?:may|at the discretion of)\b', t))

    total = mandatory_count + advisory_count + permissive_count
    if total == 0:
        return None

    if mandatory_count >= advisory_count and mandatory_count >= permissive_count:
        return "mandatory"
    elif advisory_count >= permissive_count:
        return "advisory"
    return "permissive"


# ═══════════════════════════════════════════════════════════════════════════
# CONTENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def detect_cross_references(text):
    """Extract PRA cross-references from text."""
    if not text:
        return []
    refs = set()
    # PRA rule references like "Capital Buffers 3.1" or "SS13/13"
    for m in re.finditer(r'\b(SS\d+/\d+|SoP\s+\S+|PS\d+/\d+|CP\d+/\d+)\b', text):
        refs.add(m.group(1))
    # CRR article references
    for m in re.finditer(r'\b(?:Article|article)\s+(\d+(?:\(\d+\))?)\b', text):
        refs.add(f"CRR Art.{m.group(1)}")
    return sorted(refs)


def detect_contains_deadline(text):
    if not text:
        return None
    patterns = [
        r'\bby\s+\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)',
        r'\bno later than\b', r'\bdeadline\b', r'\btransition(?:al)?\s+(?:period|date)\b',
        r'\bphase[- ]in\b', r'\bby\s+\d{4}\b',
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def detect_contains_assignment(text):
    if not text:
        return None
    patterns = [
        r'\b(?:firm|firms|bank|banks|institution|institutions)\s+(?:must|shall|should|are required)\b',
        r'\b(?:board|senior management|CRO|CEO)\s+(?:must|shall|should|is responsible)\b',
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def detect_contains_parameter(text):
    if not text:
        return None
    patterns = [
        r'\b\d+(?:\.\d+)?%\b',
        r'\b(?:threshold|limit|ratio|floor|cap|minimum|maximum)\s+(?:of\s+)?\d',
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


# ═══════════════════════════════════════════════════════════════════════════
# STRUCTURAL CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════

def determine_structural_level(doc_class):
    if doc_class in ("rulebook_rule", "rulebook_chapter"):
        return "chapter"
    if doc_class in ("supervisory_statement", "statement_of_policy"):
        return "document"
    if doc_class == "glossary_definition":
        return "definition"
    return "document"


def determine_paragraph_role(doc_class):
    role_map = {
        "rulebook_rule": "requirement",
        "rulebook_chapter": "requirement",
        "supervisory_statement": "guidance",
        "statement_of_policy": "guidance",
        "consultation_paper": "proposal",
        "policy_statement": "guidance",
        "glossary_definition": "definition",
        "reporting_form": "procedure_step",
        "sector_overview": "scope_statement",
        "rule_timeline": "reference",
        "legal_instrument": "requirement",
        "statutory_instrument": "requirement",
        "binding_technical_standard": "requirement",
    }
    return role_map.get(doc_class, None)


def determine_audience(doc_class, regulator):
    if doc_class in ("rulebook_rule", "rulebook_chapter", "legal_instrument"):
        return "PRA-regulated firms"
    if doc_class in ("supervisory_statement", "statement_of_policy"):
        return "PRA-regulated firms and their boards"
    if doc_class == "glossary_definition":
        return "PRA-regulated firms, compliance teams"
    return "PRA-regulated firms"


def determine_approval_status(status):
    if status == "active":
        return "approved"
    if status in ("superseded", "deleted"):
        return "superseded"
    return "approved"


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════════

GROUPS = [
    ("BoE Guidance", "BoE Guidance"),
    ("PRA Forms", "PRA Forms"),
    ("PRA Glossary", "PRA Glossary"),
    ("PRA Guidance", "PRA Guidance"),
    ("PRA Legal Instruments", "PRA Legal Instruments"),
    ("PRA Rules", "PRA Rules"),
    ("PRA Sectors", "PRA Sectors"),
]


def enrich_file(jf, md_dir=None):
    """Enrich a single JSON metadata file with all missing NOVA fields."""
    meta = json.load(open(jf, "r", encoding="utf-8"))
    changes = []

    # --- Fix 1: Sector bug ---
    old_sector = meta.get("sector")
    meta["sector"] = fix_sector(old_sector)
    if meta["sector"] != old_sector:
        changes.append("sector")

    # --- Fix 2: Jurisdiction normalization ---
    if meta.get("jurisdiction") == "UK":
        meta["jurisdiction"] = "United Kingdom (UK)"
        changes.append("jurisdiction")

    # --- Fix 3: sha256 backfill ---
    if not meta.get("sha256") and meta.get("raw_sha256"):
        meta["sha256"] = meta["raw_sha256"]
        changes.append("sha256")

    # --- Fix 4: effective_date_end for deleted/superseded ---
    if meta.get("status") in ("deleted", "superseded") and not meta.get("effective_date_end"):
        # Use superseded_by info or scrape date as proxy
        meta["effective_date_end"] = meta.get("scraped_at", "")[:10] or meta.get("effective_date_start")
        changes.append("effective_date_end")

    # --- Read markdown for content analysis ---
    md_text = None
    if md_dir:
        stem = jf.stem
        md_file = md_dir / f"{stem}.md"
        if md_file.exists():
            try:
                md_text = md_file.read_text(encoding="utf-8")
            except Exception:
                pass

    doc_class = meta.get("document_class", "")
    authority_class = meta.get("authority_class", "")
    regulator = meta.get("regulator", "PRA")
    status = meta.get("status", "active")

    # --- Add 15 missing NOVA fields ---

    # Layer 1
    if "structural_level" not in meta:
        meta["structural_level"] = determine_structural_level(doc_class)
        changes.append("structural_level")

    if "section_number" not in meta:
        meta["section_number"] = meta.get("guideline_number") or None
        changes.append("section_number")

    if "normative_weight" not in meta:
        nw = detect_normative_weight_from_text(md_text)
        if not nw:
            nw = detect_normative_weight_from_class(doc_class, authority_class)
        meta["normative_weight"] = nw
        changes.append("normative_weight")

    # Layer 2
    if "is_appendix" not in meta:
        meta["is_appendix"] = bool(meta.get("has_appendices", False))
        changes.append("is_appendix")

    if "paragraph_role" not in meta:
        meta["paragraph_role"] = determine_paragraph_role(doc_class)
        changes.append("paragraph_role")

    if "cross_references" not in meta:
        meta["cross_references"] = detect_cross_references(md_text)
        changes.append("cross_references")

    if "contains_deadline" not in meta:
        meta["contains_deadline"] = detect_contains_deadline(md_text)
        changes.append("contains_deadline")

    if "contains_assignment" not in meta:
        meta["contains_assignment"] = detect_contains_assignment(md_text)
        changes.append("contains_assignment")

    if "contains_parameter" not in meta:
        meta["contains_parameter"] = detect_contains_parameter(md_text)
        changes.append("contains_parameter")

    if "approval_status" not in meta:
        meta["approval_status"] = determine_approval_status(status)
        changes.append("approval_status")

    if "audience" not in meta:
        meta["audience"] = determine_audience(doc_class, regulator)
        changes.append("audience")

    if "confidentiality" not in meta:
        meta["confidentiality"] = "public"
        changes.append("confidentiality")

    if "approval_date" not in meta:
        meta["approval_date"] = meta.get("effective_date_start")
        changes.append("approval_date")

    if "review_date" not in meta:
        meta["review_date"] = meta.get("pra_metadata", {}).get("scrape_date", "")[:10] or meta.get("effective_date_start")
        changes.append("review_date")

    if "next_review_date" not in meta:
        meta["next_review_date"] = None
        changes.append("next_review_date")

    # --- Fix raw_path ---
    if not meta.get("raw_path"):
        # Determine raw format and path
        group_dir = jf.parent.parent
        stem = jf.stem
        for fmt in ["html", "pdf"]:
            raw = group_dir / fmt / f"{stem}.{fmt}"
            if raw.exists():
                meta["raw_path"] = str(raw)
                changes.append("raw_path")
                break

    # Write back
    with open(jf, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return changes


def main():
    import argparse
    p = argparse.ArgumentParser(description="PRA NOVA 3-Layer Metadata Enrichment")
    p.add_argument("--output-dir", "-o", default=".", help="PRA corpus root")
    args = p.parse_args()

    root = Path(args.output_dir)
    total = 0
    total_changes = 0

    print("=" * 70)
    print("PRA CORPUS — NOVA 3-LAYER METADATA ENRICHMENT")
    print("=" * 70)

    for group_name, group_dir in GROUPS:
        json_dir = root / group_dir / "json"
        md_dir = root / group_dir / "md"

        if not json_dir.exists():
            continue

        files = sorted(json_dir.glob("*.json"))
        group_changes = 0

        print(f"\n-- {group_name} ({len(files)} files) --")

        for jf in files:
            changes = enrich_file(jf, md_dir if md_dir.exists() else None)
            if changes:
                group_changes += 1
                if len(changes) > 3:
                    print(f"  {jf.name[:55]:55s} +{len(changes)} fields")

        total += len(files)
        total_changes += group_changes
        print(f"  {group_name}: {group_changes}/{len(files)} files updated")

    print(f"\n{'='*70}")
    print(f"ENRICHMENT COMPLETE: {total_changes}/{total} files updated")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
