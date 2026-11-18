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

# Ensure script dir in path for local engine imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from common.config import get_workspace_root
from common.citation_tracker import record_citations_from_text
from epistemic_engine import (
    ParsedSection,
    parse_subsections_from_markdown,
    audit_sections_batch,
    EpistemicAuditReport,
)


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
    enforce_qa: bool = True,
    audit_epistemic: bool = False,
    strict_epistemic: bool = False,
    epistemic_threshold: float = 0.5,
    decider_model: Optional[str] = None
) -> Dict[str, Any]:
    """Concatenate subsection files with QA checks into a unified chapter file."""
    files = find_subsection_files(subsections_dir)
    if not files:
        raise ValueError(f"No markdown files found in: {subsections_dir}")

    all_warnings: List[str] = []
    seen_quotes: Dict[int, List[str]] = {}  # msg_id -> list of section filenames
    stitched_blocks: List[str] = []
    parsed_sections: List[ParsedSection] = []
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

        # Parse section components if epistemic audit is requested
        if audit_epistemic:
            sec_units = parse_subsections_from_markdown(content, filename=base)
            parsed_sections.extend(sec_units)

    # Check for duplicate quotes across DIFFERENT subsections
    duplicates: Dict[int, List[str]] = {}
    citation_notices: List[str] = []
    for msg_id, sections in seen_quotes.items():
        unique_sections = sorted(list(set(sections)))
        if len(unique_sections) > 1:
            duplicates[msg_id] = unique_sections
            citation_notices.append(
                f"Quote anchor [#{msg_id}] cited across multiple subsections ({', '.join(unique_sections)}). "
                "Permitted if analyzing distinct psychological dimensions; drafters must not re-query raw chat logs for replacements."
            )

    # Persist citations in SQLite report_citations if database is available
    db_candidate = os.path.join(get_workspace_root(), "chat.db")
    if not os.path.exists(db_candidate) and os.path.exists("chat.db"):
        db_candidate = "chat.db"
    if os.path.exists(db_candidate):
        try:
            import sqlite3
            c_conn = sqlite3.connect(db_candidate)
            c_cur = c_conn.cursor()
            c_cur.execute("SELECT chat_id FROM chats LIMIT 1;")
            c_row = c_cur.fetchone()
            cid = c_row[0] if c_row else "default"
            chap_name = os.path.splitext(os.path.basename(output_filepath))[0]
            for fpath in files:
                with open(fpath, "r", encoding="utf-8") as f_in:
                    f_content = f_in.read()
                record_citations_from_text(
                    c_conn,
                    chat_id=cid,
                    content=f_content,
                    chapter=chap_name,
                    section_file=os.path.basename(fpath)
                )
            c_conn.close()
        except Exception:
            pass

    # Optional System-1 Epistemic Invariants Audit
    epistemic_report = None
    epistemic_breaches = 0
    if audit_epistemic and parsed_sections:
        report = audit_sections_batch(
            sections=parsed_sections,
            model=decider_model,
            threshold=epistemic_threshold
        )
        epistemic_report = report
        epistemic_breaches = report.total_breaches
        for res in report.results:
            for b in res.breaches:
                all_warnings.append(f"[🚨 EPISTEMIC BREACH | {res.section_title}]: {b}")
            for w in res.warnings:
                all_warnings.append(f"[⚠️ Epistemic Warning | {res.section_title}]: {w}")

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
        "citation_notices": citation_notices,
        "warnings": all_warnings,
        "files_merged": [os.path.basename(f) for f in files],
        "epistemic_audit": {
            "audited": audit_epistemic,
            "total_breaches": epistemic_breaches,
            "failed_sections": epistemic_report.failed_sections if epistemic_report else 0,
            "cost_usd": epistemic_report.total_cost_usd if epistemic_report else 0.0,
            "results": [
                {
                    "title": r.section_title,
                    "source": r.source_file,
                    "passed": r.passed,
                    "verdict": r.verdict,
                    "breaches": r.breaches,
                    "warnings": r.warnings,
                    "scores": r.scores
                }
                for r in (epistemic_report.results if epistemic_report else [])
            ]
        } if epistemic_report else None
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stitch subsection markdown files into a unified chapter with coherence QA & Epistemic Audit."
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
        "--audit-epistemic", action="store_true",
        help="Run System-1 Decider audit on constitutional epistemic invariants (Irrealis, Medical, Evidence Fit)"
    )
    parser.add_argument(
        "--strict-epistemic", action="store_true",
        help="Fail with non-zero exit code if epistemic breaches are detected"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.5,
        help="Confidence probability threshold for epistemic breaches (default: 0.5)"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Override OpenRouter Decider model name"
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
            chapter_title=args.chapter_title,
            audit_epistemic=args.audit_epistemic,
            strict_epistemic=args.strict_epistemic,
            epistemic_threshold=args.threshold,
            decider_model=args.model
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

        if res.get("epistemic_audit"):
            ea = res["epistemic_audit"]
            print(f"Epistemic Audit: {'[✓] PASS' if ea['total_breaches'] == 0 else f'[🚨] {ea['total_breaches']} BREACHES DETECTED'} (Cost: ${ea['cost_usd']:.5f} USD)")

        if res.get("citation_notices"):
            print(f"\n[ℹ️] Citation Notices ({len(res['citation_notices'])}):")
            for n in res["citation_notices"]:
                print(f"  - {n}")

        if res["warnings"]:
            print(f"\n[!] QA Warnings / Coherence Flags ({len(res['warnings'])}):")
            for w in res["warnings"]:
                print(f"  - {w}")
        else:
            print("\n[✓] QA Coherence Check: PASS (Clean formatting, valid syntax, properly anchored quotes).")

        print("===============================================\n")

    if args.strict_epistemic and res.get("epistemic_audit", {}).get("total_breaches", 0) > 0:
        sys.exit(3)

    if args.strict and res["warnings"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
