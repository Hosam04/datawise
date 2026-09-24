"""Optional, deterministic feature engineering.

This module is intentionally separate from the Cleaning Engine. Feature
engineering creates new analytical columns; it is not evidence-driven data
repair and therefore must not be mixed into the cleaning audit trail.
"""
import re
from typing import Any, Optional, Tuple, Dict

import pandas as pd



def _fe_norm_name(name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def _fe_find_column(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    normalized = {_fe_norm_name(c): c for c in df.columns}
    for candidate in candidates:
        key = _fe_norm_name(candidate)
        if key in normalized:
            return normalized[key]
    return None


def _add_step(report: Dict[str, Any], step: str, **details: Any) -> None:
    report.setdefault("cleaning_steps", []).append({"step": step, **details})

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _extract_title(name: Any) -> Optional[str]:
    if pd.isna(name):
        return None
    match = re.search(r",\s*([^.,]+)\.", str(name))
    return match.group(1).strip() if match else None


def _group_title(title: Optional[str]) -> str:
    """Group rare titles into meaningful categories."""
    if pd.isna(title):
        return "Rare"
    t = str(title).strip().lower()
    if t in {"mr"}:
        return "Mr"
    if t in {"mrs", "mme"}:
        return "Mrs"
    if t in {"miss", "mlle", "ms"}:
        return "Miss"
    if t == "master":
        return "Master"
    if t in {"dr", "rev", "col", "major", "capt"}:
        return "Officer"
    if t in {"don", "sir", "jonkheer", "the countess", "lady", "dona"}:
        return "Royalty"
    return "Rare"


def _split_ticket(ticket: Any) -> Tuple[Optional[str], Optional[str]]:
    if pd.isna(ticket):
        return None, None

    value = re.sub(r"\s+", " ", str(ticket).strip())
    
    # FIX: Handle LINE tickets (no numeric part)
    if value.upper() == "LINE":
        return "LINE", "NONE"
    
    # Ticket number is the final numeric token; everything before it is prefix.
    match = re.search(r"(\d+)\s*$", value)
    if not match:
        return (value if value else "NONE"), "NONE"

    number = match.group(1)
    prefix = value[:match.start()].strip(" .-/")
    prefix = re.sub(r"[.\-/]+", "_", prefix).strip("_ ")
    return (prefix or "NONE"), number


def _feature_engineering(df: pd.DataFrame, report: Dict[str, Any]) -> pd.DataFrame:
    df = df.copy()

    name_col = _fe_find_column(df, "Name")
    if name_col and "Title" not in df.columns:
        titles = df[name_col].map(_extract_title)
        # Only create Title features when extraction succeeds for a meaningful
        # share of rows. Airbnb-style free-text names yield ~0% titles and
        # would otherwise produce near-empty Title / all-"Rare" TitleGrouped
        # columns that pollute the schema and get charts skipped.
        extract_rate = float(titles.notna().mean()) if len(titles) else 0.0
        if extract_rate >= 0.30:
            df["Title"] = titles
            _add_step(
                report,
                "feature_engineering",
                feature="Title",
                source_column=name_col,
                created=True,
                unique_values=int(titles.nunique(dropna=True)),
                extract_rate=round(extract_rate, 3),
            )

            df["TitleGrouped"] = df["Title"].map(_group_title)
            _add_step(
                report,
                "feature_engineering",
                feature="TitleGrouped",
                source_column="Title",
                created=True,
                unique_values=int(df["TitleGrouped"].nunique()),
            )
        elif titles.notna().any():
            _add_step(
                report,
                "feature_engineering",
                feature="Title",
                source_column=name_col,
                created=False,
                reason=f"title extraction rate too low ({extract_rate:.1%} < 30%)",
            )

    sibsp = _fe_find_column(df, "SibSp", "SiblingsSpouses", "Siblings_Spouses")
    parch = _fe_find_column(df, "Parch", "ParentsChildren", "Parents_Children")
    if sibsp and parch and "FamilySize" not in df.columns:
        a = pd.to_numeric(df[sibsp], errors="coerce")
        b = pd.to_numeric(df[parch], errors="coerce")
        df["FamilySize"] = a.fillna(0) + b.fillna(0) + 1
        df["IsAlone"] = (df["FamilySize"] == 1).astype("int8")
        _add_step(
            report,
            "feature_engineering",
            features=["FamilySize", "IsAlone"],
            source_columns=[sibsp, parch],
            created=True,
        )

    cabin = _fe_find_column(df, "Cabin")
    if cabin and "Deck" not in df.columns:
        deck = (
            df[cabin]
            .astype("string")
            .str.strip()
            .str.extract(r"^([A-Za-z])", expand=False)
            .str.upper()
        )
        deck = deck.fillna("Unknown")
        df["Deck"] = deck
        # FIX: Add CabinCount (number of cabins listed)
        df["CabinCount"] = df[cabin].astype("string").str.split().str.len().fillna(0).astype("int8")
        _add_step(
            report,
            "feature_engineering",
            feature="Deck",
            source_column=cabin,
            created=True,
        )

    ticket = _fe_find_column(df, "Ticket")
    if ticket:
        if "TicketPrefix" not in df.columns or "TicketNumber" not in df.columns:
            split = df[ticket].map(_split_ticket)
            df["TicketPrefix"] = split.map(lambda x: x[0])
            # Convert to nullable integer; non-numeric tokens (e.g. LINE -> "NONE")
            # become <NA> then filled with 0 so the column is fully dense.
            raw_num = split.map(lambda x: x[1])
            df["TicketNumber"] = (
                pd.to_numeric(raw_num, errors="coerce")
                .fillna(0)
                .astype("int64")
            )
            _add_step(
                report,
                "feature_engineering",
                features=["TicketPrefix", "TicketNumber"],
                source_column=ticket,
                created=True,
            )

        if "TicketCount" not in df.columns:
            normalized_ticket = (
                df[ticket].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
            )
            counts = normalized_ticket.groupby(normalized_ticket).transform("count")
            df["TicketCount"] = counts.astype("Int64")
            _add_step(
                report,
                "feature_engineering",
                features=["TicketCount"],
                source_column=ticket,
                created=True,
            )
            
            # FIX: IsFamily based on FamilySize, not TicketCount
            family_size_col = _fe_find_column(df, "FamilySize")
            if family_size_col:
                df["IsFamily"] = (df[family_size_col] > 1).astype("int8")
            else:
                df["IsFamily"] = (counts > 1).astype("int8")
            _add_step(
                report,
                "feature_engineering",
                features=["IsFamily"],
                source_column="FamilySize" if family_size_col else ticket,
                created=True,
            )

    return df