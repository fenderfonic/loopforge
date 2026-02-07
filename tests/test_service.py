"""Tests for the LoopService."""

import pytest

from loopforge.states import LoopState
from loopforge.repository import MemoryRepository
from loopforge.service import LoopService


@pytest.fixture
def repo():
    return MemoryRepository()


@pytest.fixture
def service(repo):
    return LoopService(repository=repo)


class TestLoopService:
    def test_create_and_get(self, service):
        record = service.create(ref="issue-1", repo="org/repo")
        fetched = service.get(record.record_id)
        assert fetched is not None
        assert fetched.ref == "issue-1"
        assert fetched.state == LoopState.ISSUE_CREATED

    def test_transition_success(self, service):
        record = service.create(ref="issue-1")
        result = service.transition(
            record_id=record.record_id,
            new_state=LoopState.TASK_QUEUED,
            trigger="worker.picked_up",
        )
        assert result.success is True
        assert result.previous_state == LoopState.ISSUE_CREATED
        assert result.new_state == LoopState.TASK_QUEUED
        assert result.record.state == LoopState.TASK_QUEUED

    def test_transition_persists(self, service, repo):
        record = service.create(ref="issue-1")
        service.transition(record.record_id, LoopState.TASK_QUEUED, "t")
        fetched = repo.get(record.record_id)
        assert fetched.state == LoopState.TASK_QUEUED

    def test_transition_not_found(self, service):
        result = service.transition("nonexistent", LoopState.TASK_QUEUED, "t")
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_transition_invalid(self, service):
        record = service.create(ref="issue-1")
        result = service.transition(record.record_id, LoopState.MERGED, "bad")
        assert result.success is False
        assert "Invalid transition" in result.error

    def test_transition_with_metadata(self, service):
        record = service.create(ref="issue-1")
        result = service.transition(
            record.record_id,
            LoopState.TASK_QUEUED,
            "worker",
            metadata={"worker_id": "w-123"},
        )
        assert result.success is True
        last_transition = result.record.transitions[-1]
        assert last_transition.metadata["worker_id"] == "w-123"

    def test_full_lifecycle(self, service):
        record = service.create(ref="issue-42", repo="org/repo", auto_merge=True)
        rid = record.record_id

        steps = [
            (LoopState.TASK_QUEUED, "queued"),
            (LoopState.PR_CREATED, "pr.opened"),
            (LoopState.CI_PENDING, "ci.started"),
            (LoopState.CI_PASSED, "ci.passed"),
            (LoopState.MERGED, "auto.merged"),
            (LoopState.CLOSED, "issue.closed"),
        ]

        for state, trigger in steps:
            result = service.transition(rid, state, trigger)
            assert result.success is True, f"Failed at {state}: {result.error}"

        final = service.get(rid)
        assert final.state == LoopState.CLOSED
        assert final.closed_at is not None


class TestHooks:
    def test_hook_fires_on_transition(self, service):
        calls = []

        def my_hook(record, prev, new, trigger):
            calls.append((prev, new, trigger))

        service.add_hook(my_hook)
        record = service.create(ref="issue-1")
        service.transition(record.record_id, LoopState.TASK_QUEUED, "t")

        assert len(calls) == 1
        assert calls[0] == (LoopState.ISSUE_CREATED, LoopState.TASK_QUEUED, "t")

    def test_hook_not_fired_on_failure(self, service):
        calls = []
        service.add_hook(lambda r, p, n, t: calls.append(1))
        record = service.create(ref="issue-1")
        service.transition(record.record_id, LoopState.MERGED, "bad")
        assert len(calls) == 0

    def test_hook_error_doesnt_break_transition(self, service):
        def bad_hook(record, prev, new, trigger):
            raise RuntimeError("hook exploded")

        service.add_hook(bad_hook)
        record = service.create(ref="issue-1")
        result = service.transition(record.record_id, LoopState.TASK_QUEUED, "t")
        assert result.success is True


class TestMemoryRepository:
    def test_list_by_state(self, repo, service):
        service.create(ref="a")
        r2 = service.create(ref="b")
        service.transition(r2.record_id, LoopState.TASK_QUEUED, "t")

        created = repo.list_by_state("issue_created")
        queued = repo.list_by_state("task_queued")
        assert len(created) == 1
        assert len(queued) == 1

    def test_delete(self, repo, service):
        record = service.create(ref="a")
        assert repo.delete(record.record_id) is True
        assert repo.get(record.record_id) is None

    def test_delete_nonexistent(self, repo):
        assert repo.delete("nope") is False
