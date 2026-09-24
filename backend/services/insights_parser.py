"""Insights report parser for DataWise.

Converts agent insights (string, dict, or None) into a structured report format
expected by the API and frontend.
"""
import re
from datetime import date, datetime
from typing import Any, Dict, List, Tuple


# Default empty insights structure
EMPTY_INSIGHTS = {
    "executive_summary": "No insights were generated for this dataset.",
    "key_findings": [],
    "significant_segments": [],
    "recommendations": [],
    "limitations": [],
    "data_quality": {"issues": [], "score": None},
}


# Section header regex patterns for plain text parsing
SECTION_PATTERNS = [
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*executive\s*summary\s*(?:\*\*)?\s*:?\s*$", "executive_summary"),
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*key\s*findings?\s*(?:\*\*)?\s*:?\s*$", "key_findings"),
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*significant\s*segments?\s*(?:\*\*)?\s*:?\s*$", "significant_segments"),
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*recommendations?\s*(?:\*\*)?\s*:?\s*$", "recommendations"),
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*limitations?\s*(?:\*\*)?\s*:?\s*$", "limitations"),
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*data\s*quality\s*(?:\*\*)?\s*:?\s*$", "data_quality"),
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*findings?\s*(?:\*\*)?\s*:?\s*$", "key_findings"),
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*analysis\s*(?:\*\*)?\s*:?\s*$", "key_findings"),
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*overview\s*(?:\*\*)?\s*:?\s*$", "executive_summary"),
    (r"(?i)^\s*(?:#{1,3}\s+|\*\*)?\s*summary\s*(?:\*\*)?\s*:?\s*$", "executive_summary"),
]

# Keys for the sections dictionary
SECTION_KEYS = [
    "executive_summary",
    "key_findings",
    "significant_segments",
    "recommendations",
    "limitations",
    "data_quality",
    "raw",
]


def _empty_insights() -> Dict[str, Any]:
    """Return a copy of the default empty insights structure."""
    return {k: v for k, v in EMPTY_INSIGHTS.items()}


def _normalize_insights_dict(insights: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a dict insights object to match the expected structure."""
    defaults = _empty_insights()
    for key in defaults:
        if key in insights:
            defaults[key] = insights[key]

    # Ensure data_quality is always a dict
    dq = defaults.get("data_quality")
    if not isinstance(dq, dict):
        defaults["data_quality"] = {"issues": [], "score": None}

    # Ensure list fields are lists
    for list_key in ("key_findings", "recommendations", "limitations", "significant_segments"):
        if not isinstance(defaults.get(list_key), list):
            defaults[list_key] = []

    return defaults


def _detect_confidence(text: str) -> str:
    """Detect confidence level from text."""
    low = text.lower()
    if any(w in low for w in ["strong", "high confidence", "clearly", "significant", "confirmed", "very high"]):
        return "high"
    if any(w in low for w in ["weak", "low confidence", "unclear", "might", "possibly", "insufficient"]):
        return "low"
    return "medium"


def _split_title_desc(text: str) -> Tuple[str, str]:
    """Split text into title and description."""
    text = text.strip()
    if ":" in text:
        parts = text.split(":", 1)
        if 5 < len(parts[0]) < 80:
            return parts[0].strip(), parts[1].strip()
    sentences = text.split(". ")
    if len(sentences) > 1 and 5 < len(sentences[0]) < 80:
        return sentences[0].strip() + ".", ". ".join(sentences[1:]).strip()
    return "Finding", text


def _extract_list_items(text: str) -> List[str]:
    """Extract list items from text (bullet points, numbered lists)."""
    items = re.split(r"\n\s*(?:[-*•]|\d+\.)\s+", "\n" + text)
    return [i.strip() for i in items if i.strip()]


def _extract_findings(text: str) -> List[Dict[str, Any]]:
    """Extract findings from text."""
    items = re.split(r"\n\s*(?:[-*•]|\d+\.)\s+", "\n" + text)
    items = [i.strip() for i in items if len(i.strip()) > 10]
    findings = []
    for item in items:
        title, desc = _split_title_desc(item)
        findings.append({
            "title": title,
            "description": desc,
            "evidence": "",
            "confidence": _detect_confidence(desc),
        })
    return findings


def _extract_segments(text: str) -> List[Dict[str, Any]]:
    """Extract segment information from text."""
    items = re.split(r"\n\s*(?:[-*•]|\d+\.)\s+", "\n" + text)
    segments = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        lines = item.split("\n")
        name = lines[0][:60]
        desc = " ".join(lines[1:]) if len(lines) > 1 else item
        segments.append({"name": name, "description": desc, "metrics": {}})
    return segments


# --- Markdown parsing ---

def _parse_list_text(text: str) -> List[str]:
    """Parse list text from markdown."""
    if not text:
        return []
    items = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith(("-", "*", "•")) or re.match(r"^\d+\.", s):
            items.append(re.sub(r"^[-*•\d.\s]+", "", s).strip())
        elif s and not items:
            items.append(s)
    return items


def _parse_segments_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse segment lines from markdown."""
    if not lines:
        return []
    segments = []
    name: str | None = None
    content: List[str] = []

    def flush():
        nonlocal name, content
        if name is not None:
            segments.append({
                "name": name,
                "description": "\n".join(content).strip(),
                "metrics": {},
            })
        name = None
        content = []

    for line in lines:
        s = line.strip()
        if s.startswith("__SUB:"):
            flush()
            name = s[6:].strip()
        else:
            content.append(line)
    flush()

    if not segments and lines:
        text = "\n".join(lines).strip()
        if text:
            segments.append({"name": "Primary Segment", "description": text, "metrics": {}})
    return segments


def _parse_findings_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse findings lines from markdown."""
    if not lines:
        return []
    findings = []
    title: str | None = None
    content: List[str] = []

    def flush():
        nonlocal title, content
        if title is not None:
            desc = "\n".join(content).strip()
            evidence = ""
            if "evidence:" in desc.lower():
                parts = re.split(r"(?i)evidence[:：]\s*", desc, maxsplit=1)
                if len(parts) == 2:
                    desc = parts[0].strip()
                    evidence = parts[1].strip()
            findings.append({
                "title": title,
                "description": desc,
                "evidence": evidence,
                "confidence": _detect_confidence(desc),
            })
        title = None
        content = []

    for line in lines:
        s = line.strip()
        if s.startswith("__SUB:"):
            flush()
            title = s[6:].strip()
        else:
            content.append(line)
    flush()

    if not findings:
        text = "\n".join(lines).strip()
        items = re.split(r"\n\s*(?:[-*•]|\d+\.)\s+", text)
        items = [i.strip() for i in items if i.strip()]
        for item in items:
            t, d = _split_title_desc(item)
            findings.append({
                "title": t,
                "description": d,
                "evidence": "",
                "confidence": _detect_confidence(d),
            })
    return findings


def _parse_markdown_insights(text: str) -> Dict[str, Any]:
    """Parse markdown-formatted insights into structured sections."""
    sections: Dict[str, List[str]] = {}
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if re.match(r"^#{1,2}\s", stripped):
            header = re.sub(r"^#{1,2}\s*", "", stripped).strip()
            key = header.lower().replace(" ", "_").replace("-", "_")
            current_section = key
            sections[current_section] = []

        elif current_section and re.match(r"^#{3}\s", stripped):
            sub = re.sub(r"^#{3}\s*", "", stripped).strip()
            sections[current_section].append(f"__SUB:{sub}")

        elif current_section and re.match(r"^\*\*[^*]+\*\*$", stripped):
            sub = stripped.strip("*").strip()
            sections[current_section].append(f"__SUB:{sub}")

        elif current_section is not None:
            sections[current_section].append(line)

    def get_text(*names: str) -> str:
        for n in names:
            if n in sections:
                return "\n".join(sections[n]).strip()
        return ""

    def get_lines(*names: str) -> List[str]:
        for n in names:
            if n in sections:
                return sections[n]
        return []

    result = {
        "executive_summary": "Analysis completed. See detailed findings below.",
        "key_findings": [],
        "significant_segments": [],
        "recommendations": [],
        "limitations": [],
        "data_quality": {"issues": [], "score": None},
    }

    result["executive_summary"] = get_text("executive_summary", "summary", "overview") or "Analysis completed. See detailed findings below."

    findings_lines = get_lines("key_findings", "findings", "analysis")
    if findings_lines:
        result["key_findings"] = _parse_findings_lines(findings_lines)

    seg_lines = get_lines("significant_segments", "segments", "clusters")
    if seg_lines:
        result["significant_segments"] = _parse_segments_lines(seg_lines)

    rec_text = get_text("recommendations", "recommendation", "suggestions", "actions")
    if rec_text:
        result["recommendations"] = _parse_list_text(rec_text)

    lim_text = get_text("limitations", "limitation", "caveats", "constraints")
    if lim_text:
        result["limitations"] = _parse_list_text(lim_text)

    dq_text = get_text("data_quality", "dataquality", "quality", "data_issues")
    if dq_text:
        result["data_quality"]["issues"] = _parse_list_text(dq_text)

    return result


def _parse_plain_insights_enhanced(text: str) -> Dict[str, Any]:
    """Parse plain text / agent logs into structured sections."""
    lines = text.splitlines()

    sections: Dict[str, List[str]] = {k: [] for k in SECTION_KEYS}
    current = "raw"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        matched = False
        for pattern, section in SECTION_PATTERNS:
            if re.match(pattern, stripped):
                current = section
                matched = True
                break

        if not matched:
            sections[current].append(line)

    result = {
        "executive_summary": "Analysis completed. See detailed findings below.",
        "key_findings": [],
        "significant_segments": [],
        "recommendations": [],
        "limitations": [],
        "data_quality": {"issues": [], "score": None},
    }

    exec_lines = sections["executive_summary"] or sections["raw"]
    exec_text = "\n".join(exec_lines).strip()
    if exec_text:
        first_para = exec_text.split("\n\n")[0].strip()
        result["executive_summary"] = first_para[:800]

    findings_text = "\n".join(sections["key_findings"]).strip()
    raw_text = "\n".join(sections["raw"]).strip()

    if findings_text:
        result["key_findings"] = _extract_findings(findings_text)
    elif raw_text and raw_text != result["executive_summary"]:
        remaining = raw_text.replace(result["executive_summary"], "", 1).strip()
        if remaining:
            result["key_findings"] = _extract_findings(remaining)

    rec_text = "\n".join(sections["recommendations"]).strip()
    if rec_text:
        result["recommendations"] = _extract_list_items(rec_text)

    lim_text = "\n".join(sections["limitations"]).strip()
    if lim_text:
        result["limitations"] = _extract_list_items(lim_text)

    dq_text = "\n".join(sections["data_quality"]).strip()
    if dq_text:
        result["data_quality"]["issues"] = _extract_list_items(dq_text)

    seg_text = "\n".join(sections["significant_segments"]).strip()
    if seg_text:
        result["significant_segments"] = _extract_segments(seg_text)

    if not result["key_findings"] and not result["recommendations"] and raw_text:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_text) if len(s.strip()) > 20]
        result["key_findings"] = [
            {
                "title": s[:80] + ("..." if len(s) > 80 else ""),
                "description": s,
                "evidence": "",
                "confidence": _detect_confidence(s),
            }
            for s in sentences[:6]
        ]

    return result


def parse_insights_report(insights: Any) -> Dict[str, Any]:
    """Convert agent insights (string, dict, or None) into structured report.

    This is the main entry point for parsing insights from the agent workflow.

    Args:
        insights: Can be a string (markdown or plain text), a dict (already structured),
                  or None/empty.

    Returns:
        Structured insights dict with keys:
        - executive_summary
        - key_findings
        - significant_segments
        - recommendations
        - limitations
        - data_quality
    """
    # 1. Handle None / empty
    if not insights:
        return _empty_insights()

    # 2. If it's ALREADY a structured dict, use it directly
    if isinstance(insights, dict):
        return _normalize_insights_dict(insights)

    # 3. Must be string by now
    if not isinstance(insights, str):
        insights = str(insights)

    text = insights.strip()
    if not text:
        return _empty_insights()

    # 4. Try markdown headers
    if re.search(r"^#{1,3}\s", text, re.MULTILINE):
        result = _parse_markdown_insights(text)
        if result["key_findings"] or result["recommendations"]:
            return result

    # 5. Try plain text with section headers
    return _parse_plain_insights_enhanced(text)