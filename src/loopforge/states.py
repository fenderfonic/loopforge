"""
Core state machine for the development closed-loop lifecycle.

Defines states, transitions, and records for tracking work items
through the issue → PR → CI → merge → close pipeline.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LoopState(str, Enum):
    """States in the closed-loop development lifecycle."""

    ISSUE_CREATED = "issue_created"
    TASK_QUEUED = "task_queued"
    PR_CREATED = "pr_created"
    CI_PENDING = "ci_pending"
    CI_PASSED = "ci_passed"
    CI_FAILED = "ci_failed"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    MERGED = "merged"
    CLOSED = "closed"


VALID_TRANSITIONS: dict[LoopState, list[LoopState]] = {
    LoopState.ISSUE_CREATED: [LoopState.TASK_QUEUED],
    LoopState.TASK_QUEUED: [LoopState.PR_CREATED],
    LoopState.PR_CREATED: [LoopState.CI_PENDING],
    LoopState.CI_PENDING: [LoopState.CI_PASSED, LoopState.CI_FAILED],
    LoopState.CI_PASSED: [LoopState.MERGED, LoopState.AWAITING_REVIEW],
    LoopState.CI_FAILED: [LoopState.CI_PENDING],
    LoopState.AWAITING_REVIEW: [LoopState.APPROVED, LoopState.CI_PENDING],
    LoopState.APPROVED: [LoopState.MERGED],
    LoopState.MERGED: [LoopState.CLOSED],
    LoopState.CLOSED: [],
}


def _now() -> str:
    """UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class LoopTransition(BaseModel):
    """Record of a single state transition."""

    from_state: Optional[str] = Field(default=None, description="Previous state (None for initial)")
    to_state: str = Field(..., description="New state")
    trigger: str = Field(..., description="Event that triggered the transition")
    timestamp: str = Field(default_factory=_now, description="When the transition occurred (ISO 8601)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class LoopRecord(BaseModel):
    """
    Tracks a single work item through the closed-loop lifecycle.

    This is the core data structure. It holds the current state,
    transition history, and metadata about the work item.
    """

    record_id: str = Field(default_factory=lambda: f"loop-{uuid4().hex[:8]}", description="Unique record ID")
    ref: str = Field(..., description="External reference (issue URL, ticket ID, etc.)")
    ref_number: Optional[int] = Field(default=None, description="Numeric reference (issue number, etc.)")
    repo: Optional[str] = Field(default=None, description="Repository identifier (e.g. owner/repo)")
    pr_url: Optional[str] = Field(default=None, description="Pull request URL once created")
    pr_number: Optional[int] = Field(default=None, description="Pull request number")
    state: LoopState = Field(default=LoopState.ISSUE_CREATED, description="Current state")
    auto_merge: bool = Field(default=False, description="Whether to auto-merge when CI passes")
    ci_status: dict[str, str] = Field(default_factory=dict, description="CI check statuses")
    transitions: list[LoopTransition] = Field(default_factory=list, description="Transition history")
    labels: dict[str, str] = Field(default_factory=dict, description="User-defined labels/tags")
    created_at: str = Field(default_factory=_now, description="Creation timestamp")
    updated_at: str = Field(default_factory=_now, description="Last update timestamp")
    closed_at: Optional[str] = Field(default=None, description="When the record reached terminal state")

    def can_transition_to(self, new_state: LoopState) -> bool:
        """Check if a transition to new_state is valid."""
        return new_state in VALID_TRANSITIONS.get(self.state, [])

    def transition_to(
        self,
        new_state: LoopState,
        trigger: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Transition to a new state if valid.

        Returns True if the transition succeeded, False if invalid.
        """
        if not self.can_transition_to(new_state):
            return False

        self.transitions.append(
            LoopTransition(
                from_state=self.state.value,
                to_state=new_state.value,
                trigger=trigger,
                metadata=metadata or {},
            )
        )

        self.state = new_state
        self.updated_at = _now()

        if new_state == LoopState.CLOSED:
            self.closed_at = _now()

        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (for storage adapters)."""
        data = self.model_dump(mode="json")
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopRecord":
        """Deserialize from a plain dict."""
        return cls.model_validate(data)


def create_record(
    ref: str,
    ref_number: Optional[int] = None,
    repo: Optional[str] = None,
    auto_merge: bool = False,
    labels: Optional[dict[str, str]] = None,
) -> LoopRecord:
    """
    Create a new LoopRecord in the ISSUE_CREATED state.

    Args:
        ref: External reference (issue URL, ticket ID, etc.)
        ref_number: Numeric reference (issue number, etc.)
        repo: Repository identifier
        auto_merge: Whether to auto-merge when CI passes
        labels: User-defined labels/tags

    Returns:
        A new LoopRecord with the initial transition recorded.
    """
    record = LoopRecord(
        ref=ref,
        ref_number=ref_number,
        repo=repo,
        auto_merge=auto_merge,
        labels=labels or {},
    )

    record.transitions.append(
        LoopTransition(
            from_state=None,
            to_state=LoopState.ISSUE_CREATED.value,
            trigger="created",
            metadata={"ref": ref, "repo": repo},
        )
    )

    return record
