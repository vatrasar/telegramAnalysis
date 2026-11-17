#!/usr/bin/env python3
"""
Chapter Subsection Stitcher & Coherence Verifier.

Combines modular subsection markdown files produced by subsection-drafters
into a single cohesive chapter file. Automatically audits for:
1. Duplicate quote message IDs across subsections.
2. Unclosed code fences and prohibited diagram syntax (Mermaid/ASCII trees).
3. Missing Thesis-First section anchors.
"""

import os
import re
import sys
import argparse
from typing import List, Dict, Tuple, Set, Optional, Any


def find_subsection_files(subsections_dir: str) -> List[str]:
    """Find naturally sorted Markdown files in the subsections directory."""
    if not os.path.isdir(subsections_dir):
        raise FileNotFoundError(f"Subsections directory not found: '{subsections_dir}'")

    files = [
        os.path.join(subsections_dir, f)
        for f in os.listdir(subsections_dir)
        if f.endswith(".md") and not f.startswith(".")
    ]

    def sort_key(path: str) -> Tuple[int, str]:
        base = os.path.basename(path)
        m = re.match(r"^(\d+)", base)
        if m:
            return (int(m.group(1)), base)
        return (999999, base)

    return sorted(files, key=sort_key)


def extract_quote_anchors(content: str) -> List[Tuple[int, str]]:
    """Extract message IDs and raw tags from quote anchors [#<msg_id> | ...]."""
    # Pattern matching [#12345 | 2022-01-01] or [#12345]
    pattern = r"\[#(\d+)(?:\s*\|\s*[^\]]+)?\]"
    matches = re.finditer(pattern, content)
    quotes = []
    for m in matches:
        msg_id = int(m.group(1))
        quotes.append((msg_id, m.group(0)))
    return quotes


def audit_markdown_integrity(filepath: str, content: str) -> List[str]:
    """Validate markdown syntax, formatting constraints, and epistemic invariants."""
    warnings = []
    base = os.path.basename(filepath)

    # 1. Check code fences
    fences = re.findall(r"^```", content, re.MULTILINE)
    if len(fences) % 2 != 0:
        warnings.append(f"Unclosed code fence detected in: {base}")

    # 2. Ban on mermaid
    if re.search(r"^```mermaid", content, re.MULTILINE | re.IGNORECASE):
        warnings.append(f"Prohibited mermaid diagram detected in: {base}")

    # 3. Ban on ASCII art trees
    if re.search(r"[│├└]──", content):
        warnings.append(f"Prohibited ASCII tree pseudo-diagram detected in: {base}")

    # 4. Check Thesis-First markers (warning if completely absent in substantive sections)
    if len(content.splitlines()) > 30:
        has_thesis = bool(re.search(r"The Core Thesis|Teza|Główna Teza", content, re.IGNORECASE))
        has_evidence = bool(re.search(r"Verbatim Evidence|Dowody|Cytaty", content, re.IGNORECASE))
        if not has_thesis:
            warnings.append(f"Section {base} appears to lack 'Core Thesis' anchor.")
        if not has_evidence:
            warnings.append(f"Section {base} appears to lack 'Verbatim Evidence' anchor.")

    return warnings


def stitch_subsections(
    subsections_dir: str,
    output_filepath: str,
    chapter_title: Optional[str] = None,
    enforce_qa: bool = True
) -> Dict[str, Any]:
    """Concatenate subsection files with QA checks into a unified chapter file."""
    files = find_subsection_files(subsections_dir)
    if not files:
        raise ValueError(f"No markdown files found in: {subsections_dir}")

    all_warnings: List[str] = []
    seen_quotes: Dict[int, List[str]] = {}  # msg_id -> list of section filenames
    stitched_blocks: List[str] = []
    total_words = 0

    if chapter_title:
        title_block = chapter_title.strip()
        if not title_block.startswith("#"):
            title_block = f"# {title_block}"
        stitched_blocks.append(f"{title_block}\n")

    for fpath in files:
        base = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            all_warnings.append(f"Subsection file is empty: {base}")
            continue

        # Audit formatting
        integrity_issues = audit_markdown_integrity(fpath, content)
        all_warnings.extend(integrity_issues)

        # Track quotes and duplicates
        quotes = extract_quote_anchors(content)
        for msg_id, tag in quotes:
            if msg_id not in seen_quotes:
                seen_quotes[msg_id] = []
            seen_quotes[msg_id].append(base)

        words = len(content.split())
        total_words += words

        stitched_blocks.append(content)

    # Check for duplicate quotes across DIFFERENT subsections
    duplicates: Dict[int, List[str]] = {}
    for msg_id, sections in seen_quotes.items():
        unique_sections = sorted(list(set(sections)))
        if len(unique_sections) > 1:
            duplicates[msg_id] = unique_sections
            all_warnings.append(
                f"Duplicate quote anchor [#{msg_id}] reused across subsections: {', '.join(unique_sections)}"
            )

    unified_content = "\n\n---\n\n".join(stitched_blocks) + "\n"

    # Ensure output parent directory exists
    out_dir = os.path.dirname(os.path.abspath(output_filepath))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_filepath, "w", encoding="utf-8") as out:
        out.write(unified_content)

    return {
        "output_file": output_filepath,
        "sections_count": len(files),
        "total_words": total_words,
        "unique_quotes_count": len(seen_quotes),
        "duplicate_quotes": duplicates,
        "warnings": all_warnings,
        "files_merged": [os.path.basename(f) for f in files]
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stitch subsection markdown files into a unified chapter with coherence QA."
    )
    parser.add_argument(
        "-d", "--subsections-dir", required=True,
        help="Directory containing subsection markdown files (e.g. reports/subject_sections/04_ocean_subsections/)"
    )
    parser.add_argument(
        "-o", "--output", required=True,
        help="Output chapter markdown filepath (e.g. reports/subject_sections/04_attachment_ocean.md)"
    )
    parser.add_argument(
        "--chapter-title", default=None,
        help="Optional top-level chapter header (e.g. '# Rozdział 4: Styl Przywiązania i OCEAN')"
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Fail with non-zero exit code if duplicate quotes or formatting warnings are found"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output compilation metrics as JSON"
    )

    args = parser.parse_args()

    try:
        res = stitch_subsections(
            subsections_dir=args.subsections_dir,
            output_filepath=args.output,
            chapter_title=args.chapter_title
        )
    except Exception as e:
        if args.json:
            import json
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"[!] Compilation error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        import json
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print("\n=== Chapter Subsection Stitcher & QA Report ===")
        print(f"Output File:     {res['output_file']}")
        print(f"Subsections:     {res['sections_count']} files merged ({', '.join(res['files_merged'])})")
        print(f"Word Count:      {res['total_words']} words")
        print(f"Quote Anchors:   {res['unique_quotes_count']} unique citations")

        if res["warnings"]:
            print(f"\n[!] QA Warnings / Coherence Flags ({len(res['warnings'])}):")
            for w in res["warnings"]:
                print(f"  - {w}")
        else:
            print("\n[✓] QA Coherence Check: PASS (Zero duplicate quotes, clean formatting, valid syntax).")

        print("===============================================\n")

    if args.strict and res["warnings"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
