"""Fallback answer generation for the Chat Agent."""
import json
from typing import Any, Dict


def _fallback_answer(
    question: str,
    context: Dict[str, Any],
) -> str:
    """Fallback answer if Gemini fails."""
    real_facts = context.get(
        "REAL_DATA_FACTS",
        {},
    )

    overview = context.get(
        "dataset_overview",
        {},
    )

    if (
        isinstance(real_facts, dict)
        and "error" not in real_facts
    ):

        missing = real_facts.get(
            "missing_values",
            {},
        )

        rows = real_facts.get(
            "total_rows",
            overview.get(
                "total_rows",
                "unknown",
            ),
        )

        cols = real_facts.get(
            "total_columns",
            overview.get(
                "total_columns",
                "unknown",
            ),
        )

        col_names = real_facts.get(
            "column_names",
            overview.get(
                "columns",
                [],
            ),
        )

        answer = (
            "## Dataset Overview\n\n"
        )

        answer += (
            f"- **Rows:** {rows}\n"
        )

        answer += (
            f"- **Columns:** {cols}\n"
        )

        if col_names:
            answer += (
                f"- **Column Names:** "
                f"{', '.join(col_names[:15])}"
            )

            if len(col_names) > 15:
                answer += (
                    f" (and "
                    f"{len(col_names) - 15} more)"
                )

            answer += "\n"

        if missing and isinstance(
            missing,
            dict,
        ):

            if "status" in missing:

                answer += (
                    f"- **Missing Values:** "
                    f"{missing['status']}\n"
                )

            else:

                answer += (
                    f"- **Missing Values:** "
                    f"{len(missing)} "
                    f"column(s) have missing data:\n"
                )

                for col, count in missing.items():
                    answer += (
                        f"  - {col}: "
                        f"{count} missing\n"
                    )

        else:

            answer += (
                "- **Missing Values:** "
                "None reported\n"
            )

        return answer

    return (
        "I apologize, but I encountered "
        "an issue processing your request."
    )