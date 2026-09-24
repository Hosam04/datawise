"""Pre-parse FILE integrity checks for raw CSV/TSV/TXT sources.

Runs BEFORE any DataFrame creation. Strictly read-only: the source file is
opened and streamed, never modified.

Why this exists: pandas parsing with on_bad_lines='skip' silently DROPS
corrupted records, so structural damage (malformed quotes, concatenated
rows, column shifts) disappears without a trace and downstream cleaning
proceeds on untrustworthy data. Here the damage is detected at the byte/
record level instead:

    hard parse error / unterminated quote   -> BLOCK
    catastrophic ragged rows (>10%)         -> BLOCK
    concatenated records (2x fields+quotes) -> BLOCK
    mild raggedness, NUL bytes, mojibake    -> FLAG
    clean file                              -> ok

Dependency direction: this module must NOT import from backend.tools
(csv_reader imports THIS module), so encoding/delimiter detection is
self-contained.
"""
import csv
import re
from typing import Any, Dict, List, Optional

from backend.cleaning.contracts import (
    FILE_INTEGRITY_CONCAT_FIELD_MULTIPLE,
    FILE_INTEGRITY_CONCAT_MIN_ROWS,
    FILE_INTEGRITY_MAX_SCAN_ROWS,
    FILE_INTEGRITY_RAGGED_BLOCK_SHARE,
    FILE_INTEGRITY_RAGGED_FLAG_SHARE,
    FILE_INTEGRITY_REPLACEMENT_CHAR_SHARE,
)

_CANDIDATE_DELIMITERS = [",", ";", "\t", "|"]
_NUL_BYTES_RE = re.compile(rb"\x00")
_QUOTE_CHARS = {'"', "'"}
_SAMPLE_BYTES = 262_144  # 256KB for encoding/delimiter sniffing


def check_csv_file_integrity(
    file_path: str,
    encoding: Optional[str] = None,
    delimiter: Optional[str] = None,
) -> Dict[str, Any]:
    """Stream the raw text file and return a structural integrity report.

    Returns:
        {
          "status": "ok" | "flagged" | "blocked",
          "encoding_used": str,
          "delimiter": str,
          "records_scanned": int,
          "field_count_mode": int,
          "findings": [ {check, severity, affected_count, details}, ... ],
        }
    """
    enc = encoding or _detect_text_encoding(file_path)
    delim = delimiter or _detect_delimiter(file_path, enc)

    findings: List[Dict[str, Any]] = []

    # --- binary contamination ------------------------------------------------
    with open(file_path, "rb") as raw_f:
        head = raw_f.read(_SAMPLE_BYTES)
        if _NUL_BYTES_RE.search(head):
            findings.append({
                "check": "nul_bytes",
                "severity": "flag",
                "affected_count": 1,
                "details": {
                    "reason": "NUL bytes in the first 256KB suggest binary "
                              "content or broken export.",
                },
            })

    # --- streaming record scan -----------------------------------------------
    scan = _stream_records(file_path, enc, delim, findings)

    status = "blocked" if any(
        f["severity"] == "block" for f in findings
    ) else ("flagged" if findings else "ok")

    return {
        "status": status,
        "encoding_used": enc,
        "delimiter": delim,
        "records_scanned": scan["records_scanned"],
        "field_count_mode": scan["field_count_mode"],
        "findings": findings,
    }

# ---------------------------------------------------------------------------
# Streaming core
# ---------------------------------------------------------------------------

def _stream_records(
    file_path: str,
    encoding: str,
    delimiter: str,
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    field_counts: Dict[int, int] = {}
    records_scanned = 0
    replacement_chars = 0
    replacement_sampled = 0
    ragged_rows = 0
    hard_error: Optional[str] = None

    try:
        with open(
            file_path, "r", encoding=encoding, newline="", errors="replace"
        ) as f:
            # strict=True: unterminated quotes / stray quote characters raise
            # instead of silently swallowing subsequent records.
            reader = csv.reader(
                f, delimiter=delimiter, quotechar='"', strict=True
            )
            for record in reader:
                records_scanned += 1
                n_fields = len(record)
                field_counts[n_fields] = field_counts.get(n_fields, 0) + 1

                joined = "".join(record)
                if len(joined) < 20000:
                    replacement_chars += joined.count("\ufffd")
                    replacement_sampled += len(joined)

                if records_scanned >= FILE_INTEGRITY_MAX_SCAN_ROWS:
                    break
    except csv.Error as exc:
        hard_error = f"{type(exc).__name__}: {exc}"
    except UnicodeDecodeError as exc:  # pragma: no cover - errors='replace'
        hard_error = f"UnicodeDecodeError: {exc}"

    if hard_error is not None:
        findings.append({
            "check": "hard_parse_error",
            "severity": "block",
            "affected_count": records_scanned,
            "details": {
                "error": hard_error,
                "reason": (
                    "The CSV module failed to parse the file structurally "
                    "(typically unterminated quotes). Records cannot be "
                    "trusted; speculative repair is forbidden."
                ),
            },
        })

    mode_count = (
        max(field_counts.items(), key=lambda kv: kv[1])[0]
        if field_counts else 0
    )

    # Header-only / empty source: no data records to validate.
    if records_scanned <= 1 and hard_error is None:
        findings.append({
            "check": "no_data_records",
            "severity": "flag",
            "affected_count": 0,
            "details": {
                "reason": (
                    "Only a header (or nothing) was found; there are no "
                    "data records to validate."
                )
            },
        })

    # Raggedness + concatenation evidence (only meaningful with a mode).
    if field_counts and mode_count > 0:
        total_rows = sum(field_counts.values())
        deviant_rows = sum(
            c for n, c in field_counts.items() if n != mode_count
        )
        deviant_share = deviant_rows / max(total_rows, 1)
        ragged_rows = deviant_rows

        if deviant_share > 0:
            severity = (
                "block"
                if deviant_share >= FILE_INTEGRITY_RAGGED_BLOCK_SHARE
                else "flag"
            )
            findings.append({
                "check": "ragged_records",
                "severity": severity,
                "affected_count": deviant_rows,
                "details": {
                    "dominant_field_count": mode_count,
                    "deviating_records": deviant_rows,
                    "deviating_share": round(deviant_share, 6),
                    "field_count_distribution": dict(sorted(
                        field_counts.items())[:12]),
                    "reason": (
                        "Records with inconsistent field counts indicate "
                        "row-boundary corruption or column shifts."
                        if severity == "block" else
                        "A small share of records has an unusual field "
                        "count; review recommended."
                    ),
                },
            })

        # Concatenated-record signal: re-scan capped sample for rows whose
        # field count explodes AND which contain quote characters.
        concat_hits = _count_concatenation_signals(
            file_path, encoding, delimiter, mode_count
        )
        if concat_hits >= FILE_INTEGRITY_CONCAT_MIN_ROWS:
            findings.append({
                "check": "concatenated_records",
                "severity": "block",
                "affected_count": concat_hits,
                "details": {
                    "dominant_field_count": mode_count,
                    "signal_rows": concat_hits,
                    "reason": (
                        "Records carry a multiple of the dominant field "
                        "count together with quote characters - missing "
                        "row delimiters merged distinct observations."
                    ),
                },
            })


    # Mojibake evidence
    if (
        replacement_sampled
        and replacement_chars / max(replacement_sampled, 1)
        >= FILE_INTEGRITY_REPLACEMENT_CHAR_SHARE
    ):
        findings.append({
            "check": "replacement_characters",
            "severity": "flag",
            "affected_count": replacement_chars,
            "details": {
                "share": round(replacement_chars / replacement_sampled, 6),
                "reason": "High rate of U+FFFD replacement characters; "
                          "the file may be double-encoded or truncated.",
            },
        })

    return {
        "records_scanned": records_scanned,
        "field_count_mode": mode_count,
        "_ragged_rows": ragged_rows,
    }


def _count_concatenation_signals(
    file_path: str, encoding: str, delimiter: str, mode_count: int
) -> int:
    hits = 0
    scanned = 0
    threshold = mode_count * FILE_INTEGRITY_CONCAT_FIELD_MULTIPLE
    try:
        with open(
            file_path, "r", encoding=encoding, newline="", errors="replace"
        ) as f:
            reader = csv.reader(f, delimiter=delimiter, quotechar='"')
            for record in reader:
                scanned += 1
                if scanned > FILE_INTEGRITY_MAX_SCAN_ROWS:
                    break
                if len(record) >= threshold and any(
                    ch in _QUOTE_CHARS for cell in record[:8]
                    for ch in str(cell)[:200]
                ):
                    hits += 1
    except csv.Error:
        pass
    return hits


# ---------------------------------------------------------------------------
# Self-contained sniffing (keeps dependency direction: no tools/* imports)
# ---------------------------------------------------------------------------

_QUOTE_CHARS_SET = _QUOTE_CHARS


def _detect_text_encoding(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            raw = f.read(_SAMPLE_BYTES)
    except OSError:
        return "utf-8-sig"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        raw.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        return "utf-8-sig"


def _detect_delimiter(file_path: str, encoding: str) -> str:
    try:
        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            sample = f.read(_SAMPLE_BYTES)
    except OSError:
        return ","
    counts = {d: sample.count(d) for d in _CANDIDATE_DELIMITERS}
    if not counts:
        return ","
    best = max(counts, key=lambda d: counts[d])
    outside_quotes = _count_outside_quotes(sample, best)
    return best if outside_quotes > 5 else ","


def _count_outside_quotes(text: str, delimiter: str) -> int:
    count = 0
    in_quotes = False
    quote_char = None
    for ch in text:
        if in_quotes:
            if ch == quote_char:
                in_quotes = False
                quote_char = None
        elif ch in _QUOTE_CHARS_SET:
            in_quotes = True
            quote_char = ch
        elif ch == delimiter:
            count += 1
    return count


def summarize_for_error(report: Dict[str, Any]) -> str:
    """Compact human-readable summary used inside raised exceptions."""
    blocking = [
        f for f in report.get("findings", [])
        if f.get("severity") == "block"
    ]
    parts = [
        f"{f['check']} ({f.get('affected_count', 0)} row(s))"
        for f in blocking
    ]
    return ", ".join(parts) if parts else report.get("status", "unknown")