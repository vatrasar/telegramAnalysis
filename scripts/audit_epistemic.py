#!/usr/bin/env python3
"""
CLI Tool for System-1 Epistemic Invariants Auditing.

Audits synthesized markdown report files or subsection directories against
constitutional epistemic invariants (Actuation/Irrealis, Diagnostic Grounding,
Thesis-Evidence Fit, Third-Party Trait Isolation) via OpenRouter Decisions API.
"""

import os
import sys
import json
import argparse
from typing import List

# Ensure scripts dir is in path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from epistemic_engine import (
    ParsedSection,
    parse_subsections_from_markdown,
    audit_sections_batch,
    EpistemicAuditReport,
)


def load_sections_from_path(target_path: str) -> List[ParsedSection]:
    """Load and parse markdown files from a single file or directory."""
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Target path does not exist: {target_path}")

    sections: List[ParsedSection] = []

    if os.path.isfile(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        sections.extend(parse_subsections_from_markdown(content, filename=os.path.basename(target_path)))
    elif os.path.isdir(target_path):
        md_files = sorted([
            os.path.join(target_path, f)
            for f in os.listdir(target_path)
            if f.endswith(".md") and not f.startswith(".")
        ])
        if not md_files:
            raise ValueError(f"No markdown files found in directory: {target_path}")
        for path in md_files:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            sections.extend(parse_subsections_from_markdown(content, filename=os.path.basename(path)))

    return sections


def print_audit_report(report: EpistemicAuditReport) -> None:
    """Render formatted terminal output of the epistemic audit."""
    print("\n" + "=" * 65)
    print(" SYSTEM-1 EPISTEMIC INVARIANTS AUDIT REPORT ")
    print("=" * 65)
    print(f"Total Sections Audited: {report.total_sections}")
    print(f"Status:                 {'[✓] ALL PASSED' if report.failed_sections == 0 else f'[!] {report.failed_sections} FAILED'}")
    print(f"Total Breaches:         {report.total_breaches}")
    print(f"Total Warnings:         {report.total_warnings}")
    print(f"Decider API Cost:       ${report.total_cost_usd:.5f} USD")
    print("-" * 65)

    for i, res in enumerate(report.results, 1):
        status_tag = "[✓ PASS]" if res.passed else "[🚨 BREACH]"
        src = f" ({res.source_file})" if res.source_file else ""
        print(f"\n{i}. {status_tag} {res.section_title}{src}")
        print(f"   Verdict: {res.verdict.upper()} | Scores: "
              f"Irrealis={res.scores.get('irrealis', 0.0):.2f}, "
              f"Psych={res.scores.get('psychiatric', 0.0):.2f}, "
              f"Fit={res.scores.get('thesis_evidence_fit', 1.0):.2f}, "
              f"Leakage={res.scores.get('trait_leakage', 0.0):.2f}")

        if res.breaches:
            print("   🚨 Breaches:")
            for b in res.breaches:
                print(f"      - {b}")

        if res.warnings:
            print("   ⚠️  Warnings:")
            for w in res.warnings:
                print(f"      - {w}")

    print("\n" + "=" * 65 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit markdown chapters or subsections against epistemic invariants using System-1 Decider."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-f", "--file", help="Path to single markdown file to audit")
    group.add_argument("-d", "--dir", help="Path to directory containing subsection markdown files")

    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Confidence probability threshold for flagging breaches (default: 0.5)")
    parser.add_argument("--model", type=str, default=None,
                        help="Override OpenRouter Decider model name")
    parser.add_argument("--strict", action="store_true",
                        help="Exit with code 1 if any epistemic breaches are detected")
    parser.add_argument("--json", action="store_true",
                        help="Output report in JSON format")

    args = parser.parse_args()
    target_path = args.file or args.dir

    try:
        sections = load_sections_from_path(target_path)
        if not sections:
            print(f"[!] No substantive analytical sections parsed from: {target_path}", file=sys.stderr)
            sys.exit(1)

        report = audit_sections_batch(
            sections=sections,
            model=args.model,
            threshold=args.threshold
        )
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"[ERROR] Epistemic audit failed: {e}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        out = {
            "total_sections": report.total_sections,
            "passed_sections": report.passed_sections,
            "failed_sections": report.failed_sections,
            "total_breaches": report.total_breaches,
            "total_warnings": report.total_warnings,
            "total_cost_usd": report.total_cost_usd,
            "results": [
                {
                    "title": r.section_title,
                    "source_file": r.source_file,
                    "passed": r.passed,
                    "verdict": r.verdict,
                    "breaches": r.breaches,
                    "warnings": r.warnings,
                    "scores": r.scores,
                    "cost_usd": r.cost_usd
                }
                for r in report.results
            ]
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print_audit_report(report)

    if args.strict and report.total_breaches > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
