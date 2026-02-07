"""
LoopService — storage-agnostic state transition service.

Handles validation, persistence, and transition history.
Bring your own Repository implementation.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from loopforge.repository import Repository
from loopforge.states import LoopRecord, LoopState, VALID_TRANSITIONS

logger = logging.getLogger(__name__)


@dataclass
class TransitionResult:
    """Result of a state transition attempt."""

    success: bool
    record: Optional[LoopRecord]
    error: Optional[str] = None
    previous_state: Optional[LoopState] = None
    new_state: Optional[LoopState] = None


# Type alias for transition hooks
TransitionHook = Callable[[LoopRecord, LoopState, LoopState, str], None]


class LoopService:
    """
    Service for managing LoopRecord state transitions.

    Provides a high-level interface for transitioning records through
    the state machine with persistence via any Repository implementation.

    Supports optional hooks that fire on successful transitions,
    useful for audit logging, notifications, webhooks, etc.

    Example:
        from loopforge import LoopService, LoopState, create_record
        from loopforge.repository import MemoryRepository

        repo = MemoryRepository()
        service = LoopService(repository=repo)

        record = create_record(ref="https://github.com/org/repo/issues/42")
        repo.save(record)

        result = service.transition(
            record_id=record.record_id,
            new_state=LoopState.TASK_QUEUED,
            trigger="worker.picked_up",
        )
    """

    def __init__(
        self,
        repository: Repository,
        hooks: Optional[list[TransitionHook]] = None,
    ) -> None:
        self._repository = repository
        self._hooks: list[TransitionHook] = hooks or []

    @property
    def repository(self) -> Repository:
        return self._repository

    def add_hook(self, hook: TransitionHook) -> None:
        """Register a hook that fires after each successful transition."""
        self._hooks.append(hook)

    def transition(
        self,
        record_id: str,
        new_state: LoopState,
        trigger: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TransitionResult:
        """
        Transition a record to a new state.

        1. Loads the record from the repository
        2. Validates the transition against the state machine
        3. Records the transition in history
        4. Persists the updated record
        5. Fires any registered hooks

        Args:
            record_id: The record identifier
            new_state: Target state
            trigger: What caused this transition (e.g. "ci.passed")
            metadata: Optional context about the transition

        Returns:
            TransitionResult with success/failure info
        """
        record = self._repository.get(record_id)

        if record is None:
            return TransitionResult(
                success=False,
                record=None,
                error=f"Record not found: {record_id}",
            )

        previous_state = record.state

        if not record.can_transition_to(new_state):
            allowed = VALID_TRANSITIONS.get(previous_state, [])
            allowed_str = ", ".join(s.value for s in allowed) if allowed else "none (terminal)"
            return TransitionResult(
                success=False,
                record=record,
                error=(
                    f"Invalid transition: {previous_state.value} → {new_state.value}. "
                    f"Allowed from {previous_state.value}: {allowed_str}"
                ),
                previous_state=previous_state,
            )

        ok = record.transition_to(new_state, trigger, metadata)
        if not ok:
            return TransitionResult(
                success=False,
                record=record,
                error="Transition failed unexpectedly",
                previous_state=previous_state,
            )

        self._repository.save(record)

        logger.info(f"[loopforge] {record_id}: {previous_state.value} → {new_state.value} ({trigger})")

        for hook in self._hooks:
            try:
                hook(record, previous_state, new_state, trigger)
            except Exception as e:
                logger.warning(f"[loopforge] Hook error: {e}")

        return TransitionResult(
            success=True,
            record=record,
            previous_state=previous_state,
            new_state=new_state,
        )

    def get(self, record_id: str) -> Optional[LoopRecord]:
        """Get a record by ID."""
        return self._repository.get(record_id)

    def create(
        self,
        ref: str,
        ref_number: Optional[int] = None,
        repo: Optional[str] = None,
        auto_merge: bool = False,
        labels: Optional[dict[str, str]] = None,
    ) -> LoopRecord:
        """Create and persist a new record."""
        from loopforge.states import create_record

        record = create_record(
            ref=ref,
            ref_number=ref_number,
            repo=repo,
            auto_merge=auto_merge,
            labels=labels,
        )
        self._repository.save(record)
        return record
