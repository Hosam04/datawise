import os
import re
import csv
import json
from io import StringIO
from typing import Optional, Union, List, Dict, Any
import pandas as pd

from backend.core.exceptions import FileProcessingError
from backend.cleaning.file_integrity import check_csv_file_integrity, summarize_for_error
from backend.utils.logger import setup_logger

_csv_integrity_logger = setup_logger("CsvIntegrity")

try:
    import chardet
except ImportError:
    try:
        import charset_normalizer as chardet
    except ImportError:
        chardet = None

# ─────────────────────────────────────────────
# 1. ENCODING DETECTOR 
# ─────────────────────────────────────────────

def _detect_encoding(file_path: str, sample_size: int = 500_000) -> str:
    """Detect encoding with fixes for common misdetections."""
    try:
        with open(file_path, 'rb') as f:
            raw = f.read(sample_size)
    except Exception as e:
        raise IOError(f"Cannot read file for encoding detection: {e}")

    if chardet is not None:
        result = chardet.detect(raw)
        enc = result.get('encoding')
        confidence = result.get('confidence', 0.0)
    else:
        enc = None
        confidence = 0.0


    # Fixes: chardet often misdetects
    if not enc:
        return 'utf-8-sig'
    
    enc = enc.lower()
    
    # UTF-8 with BOM
    if raw.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    
    # ASCII means probably UTF-8
    if enc == 'ascii':
        return 'utf-8-sig'
    
    # Low confidence fallback
    if confidence and confidence < 0.6:
        return 'utf-8-sig'
    
    # Windows Arabic (cp1256) often detected as ISO-8859-1
    if enc in ('iso-8859-1', 'iso-8859-2', 'windows-1252'):
        # Try cp1256 first (Arabic support)
        try:
            raw.decode('cp1256')
            return 'cp1256'
        except:
            try:
                raw.decode('cp1252')
                return 'cp1252'
            except:
                return 'utf-8-sig'
    
    return enc


# ─────────────────────────────────────────────
# 2. DELIMITER DETECTOR 
# ─────────────────────────────────────────────

def _detect_delimiter(file_path: str, encoding: str) -> str:
    """Auto-detect CSV delimiter using csv.Sniffer + fallback counting."""
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            sample = f.read(8192)
        
        if not sample:
            return ','
        
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=',\t;|~^')
        return dialect.delimiter
    
    except Exception:
        # Fallback: count delimiters in first 8KB
        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                sample = f.read(8192)
        except:
            return ','
        
        delimiters = [',', '\t', ';', '|', '~', '^']
        counts = {d: sample.count(d) for d in delimiters}
        best = max(counts, key=counts.get)
        return best if counts[best] > 5 else ','


# ─────────────────────────────────────────────
# 3. CSV / TSV / TXT READER
# ─────────────────────────────────────────────

def _read_csv_robust(file_path: str, nrows: Optional[int] = None, 
                     forced_sep: Optional[str] = None, **kwargs) -> pd.DataFrame:
    """
    Reads CSV/TSV/TXT with aggressive encoding fallback and auto-delimiter.
    """
    # Priority encoding list (covers every language on Earth)
    priority_encodings = [
        'utf-8-sig', 'utf-8', 'utf-16', 'utf-16-le', 'utf-16-be',
        'utf-32', 'utf-32-le', 'utf-32-be',
        'cp1256', 'cp1252', 'cp1251', 'cp1255',
        'iso-8859-1', 'iso-8859-2', 'iso-8859-6', 'iso-8859-15',
        'windows-1252', 'windows-1256', 'windows-1251',
        'gb2312', 'gbk', 'gb18030', 'big5', 'big5hkscs',
        'shift_jis', 'euc-jp', 'euc-kr', 'euc-cn',
        'koi8-r', 'koi8-u', 'koi8-t',
        'mac_roman', 'mac_cyrillic', 'mac_arabic',
        'cp437', 'cp850', 'cp866', 'cp932',
        'latin1', 'ascii'
    ]
    
    # Insert detected encoding at top
    detected = _detect_encoding(file_path)
    if detected and detected not in priority_encodings:
        priority_encodings.insert(0, detected)
    elif detected in priority_encodings:
        priority_encodings.remove(detected)
        priority_encodings.insert(0, detected)
    
    last_error = None
    
    for enc in priority_encodings:
        try:
            sep = forced_sep or _detect_delimiter(file_path, enc)
            df = pd.read_csv(
                file_path,
                encoding=enc,
                sep=sep,
                nrows=nrows,
                engine='python',           # More flexible than C engine
                on_bad_lines='warn',       # Skip bad lines, don't crash
                encoding_errors='replace', # Replace un-decodable chars
                **kwargs
            )
            
            if df.empty:
                continue
                
            # Clean column names (remove BOM, spaces, special chars)
            df.columns = [
                str(col).strip().replace('\ufeff', '').replace('\x00', '')
                for col in df.columns
            ]
            
            return df
            
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            last_error = e
            continue
    
    # Ultimate fallback: binary read + force decode
    try:
        with open(file_path, 'rb') as f:
            content = f.read().decode('utf-8', errors='replace')
        
        sep = forced_sep or ','
        df = pd.read_csv(
            StringIO(content),
            sep=sep,
            nrows=nrows,
            engine='python',
            on_bad_lines='skip'
        )
        if not df.empty:
            return df
    except Exception:
        pass
    
    raise ConnectionError(
        f"Critical failure: Could not read file after trying {len(priority_encodings)} encodings. "
        f"Last error: {last_error}"
    )


# ─────────────────────────────────────────────
# 4. EXCEL READER (.xlsx, .xls, .xlsm)
# ─────────────────────────────────────────────

def _read_excel_robust(file_path: str, nrows: Optional[int] = None, **kwargs) -> pd.DataFrame:
    """Reads Excel, merges all non-empty sheets."""
    try:
        xl = pd.ExcelFile(file_path)
        sheets = xl.sheet_names
        
        if not sheets:
            raise ValueError("Excel file contains no sheets")
        
        dfs = []
        for sheet in sheets:
            df = pd.read_excel(file_path, sheet_name=sheet, nrows=nrows, **kwargs)
            if not df.empty:
                if len(sheets) > 1:
                    df['__sheet_name__'] = sheet
                dfs.append(df)
        
        if not dfs:
            raise ValueError("All sheets are empty")
        
        return pd.concat(dfs, ignore_index=True)
        
    except Exception as e:
        raise ConnectionError(f"Excel read failed: {e}")


# ─────────────────────────────────────────────
# 5. JSON / JSONL READER
# ─────────────────────────────────────────────

def _read_json_robust(file_path: str, nrows: Optional[int] = None, **kwargs) -> pd.DataFrame:
    """Reads JSON (object/list) or JSONL (lines)."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read(50_000_000)  # 50MB limit for JSON
            data = json.loads(raw)
    except json.JSONDecodeError:
        # Try JSONL
        try:
            df = pd.read_json(file_path, lines=True, nrows=nrows, **kwargs)
            return df
        except Exception as e:
            raise ConnectionError(f"JSON/JSONL read failed: {e}")
    except Exception as e:
        raise ConnectionError(f"JSON read failed: {e}")
    
    # Handle structures
    if isinstance(data, list):
        df = pd.json_normalize(data)
    elif isinstance(data, dict):
        # Find the largest array inside the dict
        arrays = {k: v for k, v in data.items() if isinstance(v, list)}
        if arrays:
            key = max(arrays, key=lambda k: len(arrays[k]))
            df = pd.json_normalize(arrays[key])
        else:
            df = pd.json_normalize([data])
    else:
        raise ValueError("Unsupported JSON structure")
    
    return df.head(nrows) if nrows else df


# ─────────────────────────────────────────────
# 6. PARQUET READER
# ─────────────────────────────────────────────

def _read_parquet_robust(file_path: str, nrows: Optional[int] = None, **kwargs) -> pd.DataFrame:
    try:
        df = pd.read_parquet(file_path, **kwargs)
        if nrows:
            df = df.head(nrows)
        if df.empty:
            raise ValueError("Parquet file is empty")
        return df
    except Exception as e:
        raise ConnectionError(f"Parquet read failed: {e}")


# ─────────────────────────────────────────────
# 7. FIXED-WIDTH READER
# ─────────────────────────────────────────────

def _read_fwf_robust(file_path: str, nrows: Optional[int] = None, **kwargs) -> pd.DataFrame:
    try:
        df = pd.read_fwf(file_path, nrows=nrows, **kwargs)
        if df.empty:
            raise ValueError("Fixed-width file is empty")
        return df
    except Exception as e:
        raise ConnectionError(f"Fixed-width read failed: {e}")


# ─────────────────────────────────────────────
# 9. FILE TYPE DETECTOR (Magic + Extension)
# ─────────────────────────────────────────────

def detect_file_type(file_path: str) -> str:
    """
    Detects file type from extension AND binary content (magic bytes).
    Returns: 'csv' | 'tsv' | 'txt' | 'excel' | 'json' | 'jsonl' |
             'parquet' | 'fwf' | 'unknown'
    """
    ext = os.path.splitext(file_path)[1].lower()

    # Extension map (SQLite / .db uploads are not supported)
    ext_map = {
        '.csv': 'csv', '.tsv': 'tsv', '.tab': 'tsv',
        '.txt': 'txt',
        '.xlsx': 'excel', '.xls': 'excel', '.xlsm': 'excel', '.xlsb': 'excel',
        '.json': 'json', '.jsonl': 'jsonl',
        '.parquet': 'parquet', '.pq': 'parquet',
        '.fwf': 'fwf',
    }

    if ext in ext_map:
        return ext_map[ext]

    # Explicit rejection of SQLite database files by extension
    if ext in ('.db', '.sqlite', '.sqlite3'):
        raise ValueError(
            f"SQLite database files ({ext}) are not supported. "
            "Export the table to CSV, Excel, JSON, or Parquet and upload that instead."
        )

    # Binary magic bytes detection (for files without extension)
    try:
        with open(file_path, 'rb') as f:
            magic = f.read(16)
    except Exception:
        return 'unknown'

    if magic[:4] == b'PAR1':
        return 'parquet'
    if magic[:16] == b'SQLite format 3\x00':
        raise ValueError(
            "SQLite database files are not supported. "
            "Export the table to CSV, Excel, JSON, or Parquet and upload that instead."
        )
    if magic[:2] == b'PK':  # ZIP-based (Excel xlsx)
        return 'excel'
    if magic[:1] == b'{' or magic[:1] == b'[':
        return 'json'
    if magic[:2] == b'\xff\xfe' or magic[:2] == b'\xfe\xff':
        return 'csv'  # UTF-16 text
    if magic[:3] == b'\xef\xbb\xbf':
        return 'csv'  # UTF-8 BOM text

    # Default: assume CSV (most common)
    return 'csv'


# ─────────────────────────────────────────────
# 10. THE UNIVERSAL READER 
# ─────────────────────────────────────────────

def _pre_parse_integrity_gate(file_path: str, file_type: str) -> None:
    """Pre-parse structural integrity gate for delimited text files.

    BLOCKED sources raise FileProcessingError BEFORE any DataFrame exists,
    so corrupted records can never be silently skipped by the parser.
    FLAGGED sources load normally but are logged for review.

    Raises:
        FileProcessingError: when structural corruption blocks ingestion.
    """
    try:
        report = check_csv_file_integrity(file_path)
    except Exception as exc:  # noqa: BLE001 - gate must never block loading
        _csv_integrity_logger.warning(
            "Pre-parse integrity check failed for %s (%s); proceeding.",
            os.path.basename(file_path), exc,
        )
        return

    status = report.get("status")
    if status == "blocked":
        raise FileProcessingError(
            f"CSV blocked by pre-parse integrity checks "
            f"({summarize_for_error(report)}). Corrupted rows must not be "
            "silently dropped; fix the source export before ingestion."
        )
    if status == "flagged":
        checks = ", ".join(sorted({
            f.get("check", "?") for f in report.get("findings", [])
        }))
        _csv_integrity_logger.warning(
            "CSV integrity flags for %s [%s]: %s",
            os.path.basename(file_path),
            checks,
            summarize_for_error(report),
        )


def read_any_file(file_path: str, nrows: Optional[int] = None, **kwargs) -> pd.DataFrame:
    """
    Universal data reader. Reads a data file and returns a clean DataFrame.

    Supports:
        CSV, TSV, TXT, Excel (.xlsx/.xls/.xlsm), JSON, JSONL,
        Parquet, Fixed-Width

    SQLite database files (.db / .sqlite / .sqlite3) are not supported.

    Args:
        file_path: Path to the file
        nrows: Limit rows (for preview)
        **kwargs: Extra args passed to pandas readers

    Returns:
        pd.DataFrame: Clean dataframe with normalized column names

    Raises:
        FileNotFoundError, ValueError, ConnectionError
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if os.path.getsize(file_path) == 0:
        raise ValueError("File is empty (0 bytes)")

    file_type = detect_file_type(file_path)

    # Pre-parse structural integrity gate (Phase 2): delimited text only.
    if file_type in ("csv", "tsv", "txt"):
        _pre_parse_integrity_gate(file_path, file_type)

    # Route to appropriate reader
    if file_type == 'csv':
        df = _read_csv_robust(file_path, nrows=nrows, **kwargs)
    elif file_type == 'tsv':
        df = _read_csv_robust(file_path, nrows=nrows, forced_sep='\t', **kwargs)
    elif file_type == 'txt':
        # Auto-detect delimiter (handles | ; ~ tab comma etc.) then fall back to FWF
        try:
            df = _read_csv_robust(file_path, nrows=nrows, **kwargs)
            # If still single-column and content looks multi-field, retry common seps
            if df.shape[1] == 1:
                for sep_try in ['|', ';', '\t', ',', '~']:
                    try:
                        df2 = _read_csv_robust(file_path, nrows=nrows, forced_sep=sep_try, **kwargs)
                        if df2.shape[1] > 1:
                            df = df2
                            break
                    except Exception:
                        continue
        except Exception:
            try:
                df = _read_fwf_robust(file_path, nrows=nrows, **kwargs)
            except Exception:
                raise
    elif file_type == 'excel':
        df = _read_excel_robust(file_path, nrows=nrows, **kwargs)
    elif file_type in ('json', 'jsonl'):
        df = _read_json_robust(file_path, nrows=nrows, **kwargs)
    elif file_type == 'parquet':
        df = _read_parquet_robust(file_path, nrows=nrows, **kwargs)
    elif file_type == 'fwf':
        df = _read_fwf_robust(file_path, nrows=nrows, **kwargs)
    else:
        # Brute force: try every reader until one works
        errors: Dict[str, str] = {}
        for name, func in [
            ('CSV', lambda: _read_csv_robust(file_path, nrows=nrows, **kwargs)),
            ('Excel', lambda: _read_excel_robust(file_path, nrows=nrows, **kwargs)),
            ('JSON', lambda: _read_json_robust(file_path, nrows=nrows, **kwargs)),
            ('Fixed-Width', lambda: _read_fwf_robust(file_path, nrows=nrows, **kwargs)),
            ('Parquet', lambda: _read_parquet_robust(file_path, nrows=nrows, **kwargs)),
        ]:
            try:
                df = func()
                break
            except Exception as e:
                errors[name] = str(e)
        else:
            raise ConnectionError(
                f"Could not determine file format. Tried:\n" + 
                "\n".join([f"  {k}: {v}" for k, v in errors.items()])
            )
    
    # ─── Post-processing: Clean the dataframe ───
    
    # 1. Reset index
    df = df.reset_index(drop=True)
    
    # 2. Clean column names
    def _clean_col(col: Any) -> str:
        s = str(col).strip()
        # Remove BOM, null bytes, control chars
        s = s.replace('\ufeff', '').replace('\x00', '')
        s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
        # Replace multiple spaces/special chars with underscore
        s = re.sub(r'[^\w\s-]', '_', s)
        s = re.sub(r'[-\s]+', '_', s)
        # Remove leading/trailing underscores
        s = s.strip('_')
        # Handle empty names
        return s if s else f"column_{hash(str(col)) & 0xFFFFFFFF}"
    
    df.columns = [_clean_col(c) for c in df.columns]
    
    # 3. Remove completely empty rows/columns
    df = df.dropna(how='all').dropna(axis=1, how='all')
    
    # 4. Reset index again after drops
    df = df.reset_index(drop=True)
    
    if df.empty:
        raise ValueError("File contains no usable data after cleaning")
    
    return df


# ─────────────────────────────────────────────
# 11. BACKWARD COMPATIBLE ALIAS
# ─────────────────────────────────────────────

def read_csv_tool(file_path: str, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Backward-compatible wrapper. Same signature as your old function.
    Now supports ALL file types automatically.
    """
    return read_any_file(file_path, nrows=nrows)