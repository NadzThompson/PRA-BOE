#!/usr/bin/env python3
"""
Enhance PRA metadata with full section hierarchy.
Parses existing markdown content to extract:
- Chapter numbers and titles
- Rule/paragraph numbers under each chapter
- First-line summary of each rule/paragraph
"""

import json
import re
import warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

OUTPUT_DIR = Path(r"C:\Users\nadin\OneDrive\Documents\NOVA\PRA")


def extract_sections_from_markdown(md_text):
    """Parse markdown content to build full section hierarchy."""
    sections = []
    current_chapter = None
    current_rules = []
    lines = md_text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Chapter heading: "###  Chapter Title" or "### Chapter Title"
        chapter_match = re.match(r'^#{2,3}\s+(.+)$', line)
        if chapter_match:
            # Save previous chapter
            if current_chapter:
                sections.append({
                    "chapter_number": current_chapter.get("number", ""),
                    "chapter_title": current_chapter["title"],
                    "rules": current_rules,
                })

            title = chapter_match.group(1).strip()
            # Check if there's a chapter number on the line above
            chapter_num = ""
            if i > 0:
                prev_line = lines[i - 1].strip()
                if re.match(r'^\d+$', prev_line):
                    chapter_num = prev_line

            current_chapter = {"title": title, "number": chapter_num}
            current_rules = []
            i += 1
            continue

        # Rule/paragraph number: standalone "1.1" or "2.3A" etc.
        rule_match = re.match(r'^(\d+\.\d+[A-Z]?)$', line)
        if rule_match and current_chapter:
            rule_num = rule_match.group(1)

            # Get first line of rule text (next non-empty line)
            summary = ""
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith('*Effective:') and next_line != '':
                    # Clean up the summary
                    summary = next_line[:200]
                    # Remove markdown formatting
                    summary = re.sub(r'_([^_]+)_', r'\1', summary)
                    summary = re.sub(r'\*\*([^*]+)\*\*', r'\1', summary)
                    summary = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', summary)
                    break
                j += 1

            # Get effective date for this rule
            eff_date = ""
            k = i + 1
            while k < min(i + 20, len(lines)):
                eff_match = re.match(r'^\*Effective:\s*(\d{2}/\d{2}/\d{4})\*$', lines[k].strip())
                if eff_match:
                    eff_date = eff_match.group(1)
                    break
                # Stop if we hit the next rule number
                if re.match(r'^\d+\.\d+[A-Z]?$', lines[k].strip()):
                    break
                k += 1

            current_rules.append({
                "rule_number": rule_num,
                "summary": summary,
                "as_at_date": eff_date,
            })

            i += 1
            continue

        i += 1

    # Save last chapter
    if current_chapter:
        sections.append({
            "chapter_number": current_chapter.get("number", ""),
            "chapter_title": current_chapter["title"],
            "rules": current_rules,
        })

    return sections


def extract_guidance_sections(md_text):
    """Parse guidance markdown for section hierarchy (different structure)."""
    sections = []
    current_chapter = None
    current_paragraphs = []
    lines = md_text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Chapter heading in guidance: "### Chapter Title" or "## Chapter Title"
        chapter_match = re.match(r'^#{2,3}\s+(.+)$', line)
        if chapter_match:
            if current_chapter:
                sections.append({
                    "chapter_number": current_chapter.get("number", ""),
                    "chapter_title": current_chapter["title"],
                    "paragraphs": current_paragraphs,
                })

            title = chapter_match.group(1).strip()
            chapter_num = ""
            if i > 0:
                prev = lines[i - 1].strip()
                if re.match(r'^\d+$', prev):
                    chapter_num = prev

            current_chapter = {"title": title, "number": chapter_num}
            current_paragraphs = []
            i += 1
            continue

        # Paragraph number in guidance: "1.1", "2.3", etc.
        para_match = re.match(r'^(\d+\.\d+[A-Z]?)$', line)
        if para_match and current_chapter:
            para_num = para_match.group(1)

            summary = ""
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith('*Effective:') and next_line != '':
                    summary = next_line[:200]
                    summary = re.sub(r'_([^_]+)_', r'\1', summary)
                    summary = re.sub(r'\*\*([^*]+)\*\*', r'\1', summary)
                    summary = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', summary)
                    break
                j += 1

            eff_date = ""
            k = i + 1
            while k < min(i + 20, len(lines)):
                eff_match = re.match(r'^\*Effective:\s*(\d{2}/\d{2}/\d{4})\*$', lines[k].strip())
                if eff_match:
                    eff_date = eff_match.group(1)
                    break
                if re.match(r'^\d+\.\d+[A-Z]?$', lines[k].strip()):
                    break
                k += 1

            current_paragraphs.append({
                "paragraph_number": para_num,
                "summary": summary,
                "as_at_date": eff_date,
            })

            i += 1
            continue

        i += 1

    if current_chapter:
        sections.append({
            "chapter_number": current_chapter.get("number", ""),
            "chapter_title": current_chapter["title"],
            "paragraphs": current_paragraphs,
        })

    return sections


def enhance_metadata():
    """Enhance all JSON files with full section hierarchy."""
    total = 0
    enhanced = 0

    for cat in ['rules', 'guidance']:
        json_dir = OUTPUT_DIR / "json" / cat
        files = sorted(json_dir.glob("*.json"))

        print(f"\nProcessing {cat} ({len(files)} files)...")

        for jf in files:
            if jf.name.startswith('_'):
                continue

            total += 1
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)

            md = data.get('content_markdown', '')
            if not md or len(md.strip()) < 50:
                continue

            # Extract sections
            if cat == 'rules':
                sections = extract_sections_from_markdown(md)
            else:
                sections = extract_guidance_sections(md)

            if sections:
                data['metadata']['sections'] = sections

                # Summary stats
                total_rules = sum(
                    len(s.get('rules', s.get('paragraphs', [])))
                    for s in sections
                )
                data['metadata']['section_count'] = len(sections)
                data['metadata']['rule_count'] = total_rules

                with open(jf, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                enhanced += 1

                if enhanced <= 5 or enhanced % 50 == 0:
                    print(f"  {jf.stem[:50]}: {len(sections)} sections, {total_rules} rules/paragraphs")

    print(f"\nEnhanced {enhanced}/{total} files with section hierarchy")
    return enhanced


def update_markdown_frontmatter():
    """Update MD files with section info in frontmatter."""
    count = 0
    for cat in ['rules', 'guidance']:
        json_dir = OUTPUT_DIR / "json" / cat
        md_dir = OUTPUT_DIR / "md" / cat

        for jf in sorted(json_dir.glob("*.json")):
            if jf.name.startswith('_'):
                continue

            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)

            sections = data.get('metadata', {}).get('sections', [])
            if not sections:
                continue

            md_file = md_dir / f"{jf.stem}.md"
            if not md_file.exists():
                continue

            with open(md_file, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # Build enhanced frontmatter
            title = data.get('title', jf.stem)
            meta = data.get('metadata', {})

            sections_yaml = ""
            for s in sections:
                chapter_num = s.get('chapter_number', '')
                chapter_title = s.get('chapter_title', '')
                rules = s.get('rules', s.get('paragraphs', []))
                rule_nums = [r.get('rule_number', r.get('paragraph_number', '')) for r in rules]
                rules_str = ", ".join(rule_nums) if rule_nums else "N/A"
                sections_yaml += f"\n  - chapter: \"{chapter_num}. {chapter_title}\"\n    rules: [{rules_str}]"

            applies_to = ", ".join(meta.get('applies_to', []))
            timeline = meta.get('timeline', {})
            versions = ", ".join(timeline.get('version_dates', []))

            new_frontmatter = f"""---
title: "{title}"
source: "{meta.get('source_url', '')}"
as_at_date: "{meta.get('as_at_date', '')}"
content_type: "{meta.get('content_type', '')}"
scrape_date: "{meta.get('scrape_date', '')}"
applies_to: "{applies_to}"
section_count: {meta.get('section_count', 0)}
rule_count: {meta.get('rule_count', 0)}
version_dates: "{versions}"
sections:{sections_yaml}
---"""

            # Replace old frontmatter
            if md_content.startswith('---'):
                end_idx = md_content.find('---', 3)
                if end_idx > 0:
                    body = md_content[end_idx + 3:]
                    md_content = new_frontmatter + body
                    with open(md_file, 'w', encoding='utf-8') as f:
                        f.write(md_content)
                    count += 1

    print(f"Updated {count} MD files with enhanced frontmatter")
    return count


if __name__ == "__main__":
    print("=" * 60)
    print("ENHANCING METADATA WITH FULL SECTION HIERARCHY")
    print("=" * 60)

    enhanced = enhance_metadata()
    md_updated = update_markdown_frontmatter()

    print(f"\nDone. {enhanced} JSON files enhanced, {md_updated} MD files updated.")
