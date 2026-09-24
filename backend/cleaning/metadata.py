"""Explicit metadata / constraints for the DataWise Cleaning Engine.

Callers may declare domain truths instead of relying purely on inferred
semantics. Rules NEVER bypass the evidence pipeline: they sharpen detection
(explicit ranges, protected identifiers, declared formulas) while decisions,
actions, validation and rollback work exactly as before.

Security note: there is deliberately NO expression language. Declared
formulas are limited to the engine's existing deterministic operations.
"""
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from backend.cleaning.contracts import SemanticType

if TYPE_CHECKING:
    from backend.cleaning.contracts import ColumnProfile


class DerivedFormula(BaseModel):
    """A declared deterministic relationship for one target column."""

    op: Literal["sum_offset", "product", "string_length", "day_of_week"]
    # sum_offset / product -> exactly two sources [a, b]
    # string_length        -> exactly one source (text column)
    # day_of_week          -> exactly one source (datetime column)
    sources: List[str] = Field(default_factory=list)
    offset: Optional[float] = None


class ColumnRule(BaseModel):
    """Explicit domain knowledge about ONE column."""

    name: str
    # Overrides inferred semantic typing (e.g. force identifier protection
    # for a numeric-looking 'account_number', or declare a true numeric).
    semantic_type: Optional[SemanticType] = None
    # Objective validity bounds (InvalidValueDetector, confidence 1.0).
    valid_min: Optional[float] = None
    valid_max: Optional[float] = None
    # Closed domain: any other observed value is reported (flag-only).
    allowed_values: Optional[List[str]] = None
    # Extra suppression tokens treated as CLASSIFICATION evidence only;
    # they are never converted, imputed or used as fill values.
    suppression_tokens: List[str] = Field(default_factory=list)
    # Declared deterministic relationship (verified mathematically).
    derived_formula: Optional[DerivedFormula] = None


class DatasetRules(BaseModel):
    """Dataset-level explicit metadata."""

    column_rules: Dict[str, ColumnRule] = Field(default_factory=dict)
    # Global suppression tokens applied to every column.
    suppression_tokens: List[str] = Field(default_factory=list)
    # Additional ordered name pairs (left_word, right_word) meaning left<=right.
    constraint_pairs: List[Tuple[str, str]] = Field(default_factory=list)

    def rule_for(self, column: str) -> Optional[ColumnRule]:
        return self.column_rules.get(str(column))


def apply_rules_to_profiles(
    profiles: List["ColumnProfile"],
    rules: Optional[DatasetRules],
) -> List["ColumnProfile"]:
    """Merge caller-declared rules into freshly built column profiles.

    Profiles are engine-owned objects created per run, so mutation here is
    safe and never touches the DataFrame.
    """
    if not rules:
        return profiles
    for profile in profiles:
        rule = rules.rule_for(profile.name)
        if rule is None:
            continue
        if rule.semantic_type is not None:
            profile.semantic_type = rule.semantic_type
        if rule.valid_min is not None:
            profile.valid_min = float(rule.valid_min)
        if rule.valid_max is not None:
            profile.valid_max = float(rule.valid_max)
        if rule.allowed_values is not None:
            profile.allowed_values = [str(v) for v in rule.allowed_values]
        merged_tokens = list(dict.fromkeys(
            list(rule.suppression_tokens) + list(rules.suppression_tokens)
        ))
        if merged_tokens:
            profile.suppression_tokens = merged_tokens
        if rule.derived_formula is not None:
            formula = rule.derived_formula
            profile.declared_formula = {
                "op": formula.op,
                "sources": list(formula.sources),
                "offset": formula.offset,
            }
    return profiles
