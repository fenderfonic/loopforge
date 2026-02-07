"""LoopForge — A typed state machine for the issue → PR → CI → merge → close lifecycle."""

from loopforge.states import (
    LoopState,
    LoopTransition,
    LoopRecord,
    VALID_TRANSITIONS,
    create_record,
)
from loopforge.service import (
    LoopService,
    TransitionResult,
)
from loopforge.repository import Repository

__version__ = "0.1.0"

__all__ = [
    # State machine
    "LoopState",
    "LoopTransition",
    "LoopRecord",
    "VALID_TRANSITIONS",
    "create_record",
    # Service
    "LoopService",
    "TransitionResult",
    # Repository protocol
    "Repository",
]
