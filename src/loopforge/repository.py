"""
Abstract repository protocol for LoopRecord persistence.

Implement this protocol to plug in any storage backend
(DynamoDB, Postgres, SQLite, Redis, in-memory, etc.).
"""

from typing import Optional, Protocol, runtime_checkable

from loopforge.states import LoopRecord


@runtime_checkable
class Repository(Protocol):
    """
    Storage interface for LoopRecords.

    Implement this protocol to use any backend. LoopForge ships
    with an in-memory implementation for testing and a DynamoDB
    adapter as an optional extra.
    """

    def save(self, record: LoopRecord) -> LoopRecord:
        """Persist a record (create or update)."""
        ...

    def get(self, record_id: str) -> Optional[LoopRecord]:
        """Retrieve a record by ID. Returns None if not found."""
        ...

    def delete(self, record_id: str) -> bool:
        """Delete a record by ID. Returns True if deleted."""
        ...

    def list_by_state(self, state: str, limit: int = 100) -> list[LoopRecord]:
        """List records in a given state."""
        ...


class MemoryRepository:
    """
    In-memory repository for testing and prototyping.

    Not thread-safe. Not for production use.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def save(self, record: LoopRecord) -> LoopRecord:
        self._store[record.record_id] = record.to_dict()
        return record

    def get(self, record_id: str) -> Optional[LoopRecord]:
        data = self._store.get(record_id)
        if data is None:
            return None
        return LoopRecord.from_dict(data)

    def delete(self, record_id: str) -> bool:
        if record_id in self._store:
            del self._store[record_id]
            return True
        return False

    def list_by_state(self, state: str, limit: int = 100) -> list[LoopRecord]:
        results = []
        for data in self._store.values():
            if data.get("state") == state and len(results) < limit:
                results.append(LoopRecord.from_dict(data))
        return results
