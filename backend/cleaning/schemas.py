"""Schemas for the DataWise Cleaning Engine actions.

This module contains the public, Pydantic-backed contracts used to describe
cleaning actions and the specifications passed to action factories.

The action taxonomy intentionally matches ``backend.cleaning.contracts.ActionKind``:
- content: modifies existing cell values
- annotation: adds metadata/flag columns without changing source values
- row_removal: removes complete rows
- schema: changes the table structure, including dropping columns
- transformation: general data transformations

Important: column removal is a *schema* mutation.  There is deliberately no
``column_removal`` action kind.
"""

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Action taxonomy
# ---------------------------------------------------------------------------

ActionKind = Literal[
    "content",
    "annotation",
    "row_removal",
    "schema",
    "transformation",
]

ActionScope = Literal[
    "column",
    "dataset",
    "schema",
]


# ---------------------------------------------------------------------------
# Action definition
# ---------------------------------------------------------------------------

class CleaningActionDefinition(BaseModel):
    """Static metadata describing a cleaning action.

    This is descriptive metadata only; it does not execute an action.
    """

    name: str = Field(
        ...,
        min_length=1,
        description="Action class name, e.g. 'DropColumnAction'",
    )
    kind: ActionKind = Field(
        ...,
        description=(
            "Primary mutation category. Column removal uses 'schema', "
            "not 'column_removal'."
        ),
    )
    scope: ActionScope = Field(
        ...,
        description="Scope affected by the action",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the action",
    )
    is_reversible: bool = Field(
        default=False,
        description="Whether the action can be safely reversed",
    )


# ---------------------------------------------------------------------------
# Action execution specification
# ---------------------------------------------------------------------------

class CleaningActionSpec(BaseModel):
    """Execution specification consumed by action factories/engine logic.

    ``parameters`` contains action-specific values approved by the Decision
    Engine.  The schema intentionally remains generic because different
    actions require different parameter sets.
    """

    kind: ActionKind = Field(
        ...,
        description="Kind of action to execute",
    )
    scope: ActionScope = Field(
        default="column",
        description="Scope of the action",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific execution parameters",
    )
    self_validating: bool = Field(
        default=False,
        description=(
            "If True, the action performs its own validation instead of "
            "relying solely on generic engine checks."
        ),
    )


__all__ = [
    "ActionKind",
    "ActionScope",
    "CleaningActionDefinition",
    "CleaningActionSpec",
]
