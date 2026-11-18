"""Markdown Parser for Epistemic Invariants Auditing.

Extracts structured analytical units (The Core Thesis, In-Depth Psychological Analysis,
Verbatim Evidence, Key Takeaways) from modular subsection and chapter markdown files.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class ParsedSection:
    """Represents an analytical section or subsection subject to epistemic audit."""
    title: str
    thesis: str
    analysis: str
    quotes: List[str] = field(default_factory=list)
    takeaway: str = ""
    raw_content: str = ""
    source_file: Optional[str] = None


def extract_quotes_from_text(text: str) -> List[str]:
    """Extract anchored verbatim quotes from text.
    
    Matches patterns like:
    > [#12345 | 2024-01-01] Ismi: "verbatim text..."
    or [#12345] "..."
    """
    quotes = []
    # Match blockquotes or anchored inline quotes
    pattern = re.compile(
        r'(?:^>\s*)?(\[#\d+(?:\s*\|\s*[^\]]+)?\]\s*(?:[^"\n]+:\s*)?"[^"]+")',
        re.MULTILINE
    )
    for m in pattern.finditer(text):
        quotes.append(m.group(1).strip())
    
    # Also fallback to any quote anchors if strict quote syntax wasn't matched
    if not quotes:
        anchor_pattern = re.compile(r'(\[#\d+(?:\s*\|\s*[^\]]+)?\][^\n]+)', re.MULTILINE)
        for m in anchor_pattern.finditer(text):
            quotes.append(m.group(1).strip())

    return quotes


def parse_subsections_from_markdown(content: str, filename: Optional[str] = None) -> List[ParsedSection]:
    """Parse a markdown file into discrete analytical units for epistemic auditing.
    
    Detects whether the file contains multiple H2 subsections or represents a single
    monolithic section, extracting Thesis-First components.
    """
    content = content.strip()
    if not content:
        return []

    # Check for H2 headers (e.g. '## 1. Otwartość...')
    h2_matches = list(re.finditer(r'^##\s+(.+)$', content, re.MULTILINE))

    # If multiple H2 sections exist, split by H2
    if len(h2_matches) > 1:
        sections = []
        for i, match in enumerate(h2_matches):
            start = match.start()
            end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(content)
            sec_text = content[start:end].strip()
            sec_title = match.group(1).strip()
            sections.append(_parse_single_block(sec_title, sec_text, filename))
        return sections

    # Otherwise treat the entire content as one section (e.g. a single subsection file)
    top_header_match = re.search(r'^(?:#|##)\s+(.+)$', content, re.MULTILINE)
    default_title = top_header_match.group(1).strip() if top_header_match else (filename or "Section")
    return [_parse_single_block(default_title, content, filename)]


def _parse_single_block(title: str, text: str, filename: Optional[str] = None) -> ParsedSection:
    """Parse a single section text block into structured components."""
    # Split by H3 headers (Thesis, Analysis, Evidence, Takeaway)
    h3_pattern = re.compile(r'^###\s+(?:[^\w\s]*\s*)?([^\n]+)$', re.MULTILINE)
    h3_matches = list(h3_pattern.finditer(text))

    thesis_parts = []
    analysis_parts = []
    takeaway_parts = []
    evidence_text_parts = []

    if h3_matches:
        for i, match in enumerate(h3_matches):
            h3_title = match.group(1).strip().lower()
            start = match.end()
            end = h3_matches[i + 1].start() if i + 1 < len(h3_matches) else len(text)
            body = text[start:end].strip()

            if any(k in h3_title for k in ["thesis", "teza"]):
                thesis_parts.append(body)
            elif any(k in h3_title for k in ["analysis", "analiza", "psychological", "in-depth"]):
                analysis_parts.append(body)
            elif any(k in h3_title for k in ["evidence", "dowody", "cytaty", "case studies"]):
                evidence_text_parts.append(body)
            elif any(k in h3_title for k in ["takeaway", "wnioski"]):
                takeaway_parts.append(body)
            else:
                analysis_parts.append(body)
    else:
        # Fallback if no H3 headers: first paragraph is thesis, rest is analysis
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            thesis_parts.append(paragraphs[0])
            if len(paragraphs) > 1:
                analysis_parts.extend(paragraphs[1:])

    thesis_str = "\n\n".join(thesis_parts).strip()
    analysis_str = "\n\n".join(analysis_parts).strip()
    takeaway_str = "\n\n".join(takeaway_parts).strip()

    # Extract all quotes from the entire section (especially from evidence block)
    quotes = extract_quotes_from_text(text)

    return ParsedSection(
        title=title,
        thesis=thesis_str,
        analysis=analysis_str,
        quotes=quotes,
        takeaway=takeaway_str,
        raw_content=text,
        source_file=filename
    )
