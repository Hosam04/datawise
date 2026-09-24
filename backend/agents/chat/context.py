"""Context formatting for the Chat Agent."""
import json
import re
from typing import Any, Dict


def format_context(context: Dict[str, Any]) -> str:
    """Format dataset context into a readable string for the LLM."""
    real_facts = context.get("REAL_DATA_FACTS", {})
    real_facts_str = ""

    if isinstance(real_facts, dict):
        if "error" in real_facts:
            real_facts_str = (
                f"Error loading dataset info: {real_facts['error']}"
            )
        else:
            real_facts_str = json.dumps(
                real_facts,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

            missing_vals = real_facts.get("missing_values", {})

            if isinstance(missing_vals, dict):
                if "status" in missing_vals:
                    missing_summary = missing_vals["status"]

                elif missing_vals:
                    missing_summary = "\n".join(
                        [
                            f"  - {col}: {count} missing values"
                            for col, count in missing_vals.items()
                        ]
                    )

                else:
                    missing_summary = "No missing values"

                real_facts_str += (
                    "\n\n=== MISSING VALUES SUMMARY ===\n"
                    f"{missing_summary}\n"
                    "================================"
                )

    else:
        real_facts_str = str(real_facts)

    ml_available = context.get("ml_available", False)

    ml_hint = (
        "ML analysis is available for this dataset."
        if ml_available
        else "No ML analysis available for this dataset."
    )

    # EVIDENCE is the unified object built once by the API layer from
    # everything the analysis pipeline already computed (dataset
    # profile, statistics, correlations, ml_results, insights,
    # target_detection). This is the primary source of truth for the
    # model — it must be consulted BEFORE anything else, and before
    # deciding a tool call is even necessary.
    #
    # IMPORTANT: each section gets its OWN truncation budget instead of
    # slicing the whole serialized dict as one blob. A single global
    # slice silently drops whichever keys happen to sit later in the
    # dict (e.g. "insights", "target_detection") whenever earlier keys
    # like dataset_profile/statistics/correlations are large — causing
    # the model to falsely report "no insights available" even though
    # insights were computed. Per-section budgets guarantee every
    # section always reaches the model, at least partially.
    evidence = context.get("evidence", {}) or {}

    section_budgets = {
        "insights": 3500,          # prioritized: needed for "top insights" questions
        "dataset_profile": 2500,
        "ml_results": 2500,
        "statistics": 2000,
        "correlations": 1500,
        "target_detection": 800,
    }

    evidence_sections = []

    for key, budget in section_budgets.items():
        value = evidence.get(key)

        if not value:
            evidence_sections.append(f"{key}: (not available)")
            continue

        value_str = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )[:budget]

        evidence_sections.append(f"{key}:\n{value_str}")

    # Include any other keys the evidence object might carry that
    # aren't in the prioritized list above, so nothing is silently lost.
    for key, value in evidence.items():
        if key in section_budgets or not value:
            continue

        value_str = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )[:1000]

        evidence_sections.append(f"{key}:\n{value_str}")

    evidence_str = "\n\n".join(evidence_sections)

    return f"""Dataset ID: {context.get('dataset_id', 'unknown')}
Dataset Path: {context.get('df_path', 'unknown')}
{ml_hint}

=== EVIDENCE (PRIMARY SOURCE OF TRUTH) ===
This object contains everything already computed for this dataset:
dataset_profile, statistics, correlations, ml_results, insights,
target_detection. Every factual claim you make must trace back to this
object, to REAL DATA FACTS below, or to an explicit tool result.
Each section below is populated independently — "(not available)" means
that section was genuinely never computed, not that it was cut off.

{evidence_str}

DATASET OVERVIEW:
{json.dumps(
    context.get('dataset_overview', {}),
    ensure_ascii=False,
    indent=2,
    default=str
)[:2000]}

REAL DATA FACTS (live, tool-fetched supplementary facts):
{real_facts_str[:4000]}"""