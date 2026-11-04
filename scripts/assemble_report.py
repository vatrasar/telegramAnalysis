#!/usr/bin/env python3
"""
Personality Profile Report Assembler.
Concatenates modular section files into a unified, publication-ready Markdown report.
Generates an automatic Table of Contents, validates code fence closure, and verifies document integrity.
"""

import os
import re
import sys
import argparse
from typing import List, Tuple, Optional


def find_section_files(sections_dir: str) -> List[str]:
    """Find and return naturally sorted Markdown files in the given directory."""
    if not os.path.isdir(sections_dir):
        raise FileNotFoundError(f"Sections directory not found: '{sections_dir}'")

    files = [
        os.path.join(sections_dir, f)
        for f in os.listdir(sections_dir)
        if f.endswith(".md") and not f.startswith(".")
    ]
    # Natural sort based on leading digits or filename
    def sort_key(path: str) -> Tuple[int, str]:
        base = os.path.basename(path)
        match = re.match(r"^(\d+)", base)
        if match:
            return (int(match.group(1)), base)
        return (999999, base)

    return sorted(files, key=sort_key)


def validate_markdown_integrity(filepath: str, content: str) -> List[str]:
    """Check for formatting issues such as unclosed code fences."""
    warnings = []
    # Count fenced code blocks
    fences = re.findall(r"^```", content, re.MULTILINE)
    if len(fences) % 2 != 0:
        warnings.append(f"Unclosed code fence (```) detected in: {os.path.basename(filepath)}")

    # Check for empty content
    if not content.strip():
        warnings.append(f"Section file is empty: {os.path.basename(filepath)}")

    return warnings


def generate_table_of_contents(content: str, max_level: int = 2) -> str:
    """Generate a clean GitHub-compatible Markdown Table of Contents from # and ## headers."""
    toc_lines = ["## Table of Contents\n"]
    lines = content.splitlines()

    in_code_block = False
    found_headers = 0

    for line in lines:
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()

            # Skip the main title (#) and the TOC header itself
            if level == 1 or title.lower() in ["table of contents", "spis treści"]:
                continue

            if level <= max_level:
                # Clean title for anchor link
                anchor = title.lower()
                anchor = re.sub(r"[^\w\s-]", "", anchor)
                anchor = re.sub(r"\s+", "-", anchor)

                indent = "  " * (level - 2)
                toc_lines.append(f"{indent}- [{title}](#{anchor})")
                found_headers += 1

    if found_headers == 0:
        return ""

    toc_lines.append("\n---\n")
    return "\n".join(toc_lines)


def assemble_report(
    section_files: List[str],
    output_path: Optional[str] = None,
    include_toc: bool = True
) -> str:
    """Read, validate, and concatenate section files into a single unified Markdown report."""
    if not section_files:
        raise ValueError("No section files provided for assembly.")

    collected_sections = []
    all_warnings = []

    for path in section_files:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        warnings = validate_markdown_integrity(path, content)
        all_warnings.extend(warnings)
        collected_sections.append(content)

    if all_warnings:
        print("[!] Warnings during markdown validation:", file=sys.stderr)
        for w in all_warnings:
            print(f"    - {w}", file=sys.stderr)

    unified_body = "\n\n---\n\n".join(collected_sections)

    final_document = unified_body
    if include_toc:
        toc = generate_table_of_contents(unified_body)
        if toc:
            # Place TOC after the first # Header or at the very beginning
            header_match = re.search(r"^(#\s+[^\n]+(?:\n+[^\n#]+)*)", final_document)
            if header_match:
                intro = header_match.group(1)
                rest = final_document[len(intro):].lstrip("\n-")
                final_document = f"{intro}\n\n{toc}\n\n{rest}"
            else:
                final_document = f"{toc}\n\n{final_document}"

    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_document.strip() + "\n")
        print(f"[✓] Successfully assembled {len(section_files)} sections into: {output_path}")

    return final_document


def main():
    parser = argparse.ArgumentParser(
        description="Assemble modular section files into a unified Markdown personality profile."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--sections-dir", "-d",
        type=str,
        help="Path to directory containing numbered section files (e.g. sections/)"
    )
    group.add_argument(
        "--files", "-f",
        nargs="+",
        help="Explicit list of section files in assembly order"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output path for the assembled Markdown file (defaults to stdout if omitted)"
    )
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable automatic Table of Contents generation"
    )

    args = parser.parse_args()

    if args.sections_dir:
        files = find_section_files(args.sections_dir)
    else:
        files = args.files

    if not files:
        print("[!] No section files found to assemble.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Assembling {len(files)} section files:")
    for f in files:
        print(f"    - {os.path.basename(f)}")

    assembled = assemble_report(files, output_path=args.output, include_toc=not args.no_toc)
    if not args.output:
        print(assembled)


if __name__ == "__main__":
    main()
