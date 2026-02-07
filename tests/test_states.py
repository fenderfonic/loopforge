"""Tests for the core state machine."""

import pytest

from loopforge.states import (
    LoopState,
    LoopRecord,
    VALID_TRANSITIONS,
    create_record,
)


class TestLoopState:
    def test_all_states_have_transition_entry(self):
        for state in LoopState:
            assert state in VALID_TRANSITIONS

    def test_closed_is_terminal(self):
        assert VALID_TRANSITIONS[LoopState.CLOSED] == []

    def test_no_state_can_transition_to_issue_created(self):
        for state, targets in VALID_TRANSITIONS.items():
            assert LoopState.ISSUE_CREATED not in targets


class TestLoopRecord:
    def test_create_record_defaults(self):
        record = create_record(ref="https://github.com/org/repo/issues/1")
        assert record.state == LoopState.ISSUE_CREATED
        assert record.record_id.startswith("loop-")
        assert len(record.transitions) == 1
        assert record.transitions[0].to_state == "issue_created"
        assert record.closed_at is None

    def test_create_record_with_options(self):
        record = create_record(
            ref="JIRA-123",
            ref_number=123,
            repo="org/repo",
            auto_merge=True,
            labels={"team": "platform"},
        )
        assert record.ref == "JIRA-123"
        assert record.ref_number == 123
        assert record.repo == "org/repo"
        assert record.auto_merge is True
        assert record.labels == {"team": "platform"}

    def test_can_transition_to_valid(self):
        record = create_record(ref="test")
        assert record.can_transition_to(LoopState.TASK_QUEUED) is True

    def test_can_transition_to_invalid(self):
        record = create_record(ref="test")
        assert record.can_transition_to(LoopState.MERGED) is False

    def test_transition_to_valid(self):
        record = create_record(ref="test")
        ok = record.transition_to(LoopState.TASK_QUEUED, "worker.picked_up")
        assert ok is True
        assert record.state == LoopState.TASK_QUEUED
        assert len(record.transitions) == 2

    def test_transition_to_invalid_returns_false(self):
        record = create_record(ref="test")
        ok = record.transition_to(LoopState.MERGED, "bad")
        assert ok is False
        assert record.state == LoopState.ISSUE_CREATED

    def test_transition_to_closed_sets_closed_at(self):
        record = create_record(ref="test")
        record.transition_to(LoopState.TASK_QUEUED, "t")
        record.transition_to(LoopState.PR_CREATED, "t")
        record.transition_to(LoopState.CI_PENDING, "t")
        record.transition_to(LoopState.CI_PASSED, "t")
        record.transition_to(LoopState.MERGED, "t")
        record.transition_to(LoopState.CLOSED, "t")
        assert record.closed_at is not None
        assert record.state == LoopState.CLOSED

    def test_full_happy_path(self):
        record = create_record(ref="issue-1", repo="org/repo")
        steps = [
            (LoopState.TASK_QUEUED, "queued"),
            (LoopState.PR_CREATED, "pr.opened"),
            (LoopState.CI_PENDING, "ci.started"),
            (LoopState.CI_PASSED, "ci.passed"),
            (LoopState.MERGED, "pr.merged"),
            (LoopState.CLOSED, "issue.closed"),
        ]
        for state, trigger in steps:
            assert record.transition_to(state, trigger) is True
        assert record.state == LoopState.CLOSED
        assert len(record.transitions) == 7  # 1 initial + 6 steps

    def test_ci_retry_path(self):
        record = create_record(ref="test")
        record.transition_to(LoopState.TASK_QUEUED, "t")
        record.transition_to(LoopState.PR_CREATED, "t")
        record.transition_to(LoopState.CI_PENDING, "t")
        record.transition_to(LoopState.CI_FAILED, "ci.failed")
        # Retry: CI_FAILED -> CI_PENDING
        assert record.transition_to(LoopState.CI_PENDING, "ci.retry") is True
        assert record.state == LoopState.CI_PENDING

    def test_review_path(self):
        record = create_record(ref="test")
        record.transition_to(LoopState.TASK_QUEUED, "t")
        record.transition_to(LoopState.PR_CREATED, "t")
        record.transition_to(LoopState.CI_PENDING, "t")
        record.transition_to(LoopState.CI_PASSED, "t")
        record.transition_to(LoopState.AWAITING_REVIEW, "review.requested")
        record.transition_to(LoopState.APPROVED, "review.approved")
        record.transition_to(LoopState.MERGED, "pr.merged")
        assert record.state == LoopState.MERGED

    def test_to_dict_and_from_dict_roundtrip(self):
        record = create_record(ref="test", repo="org/repo", labels={"env": "prod"})
        record.transition_to(LoopState.TASK_QUEUED, "t")
        data = record.to_dict()
        restored = LoopRecord.from_dict(data)
        assert restored.record_id == record.record_id
        assert restored.state == record.state
        assert restored.ref == record.ref
        assert restored.repo == record.repo
        assert restored.labels == record.labels
        assert len(restored.transitions) == len(record.transitions)


class TestValidTransitions:
    @pytest.mark.parametrize(
        "from_state,to_state,expected",
        [
            (LoopState.ISSUE_CREATED, LoopState.TASK_QUEUED, True),
            (LoopState.ISSUE_CREATED, LoopState.MERGED, False),
            (LoopState.TASK_QUEUED, LoopState.PR_CREATED, True),
            (LoopState.CI_PENDING, LoopState.CI_PASSED, True),
            (LoopState.CI_PENDING, LoopState.CI_FAILED, True),
            (LoopState.CI_FAILED, LoopState.CI_PENDING, True),
            (LoopState.CI_PASSED, LoopState.MERGED, True),
            (LoopState.CI_PASSED, LoopState.AWAITING_REVIEW, True),
            (LoopState.AWAITING_REVIEW, LoopState.APPROVED, True),
            (LoopState.AWAITING_REVIEW, LoopState.CI_PENDING, True),
            (LoopState.APPROVED, LoopState.MERGED, True),
            (LoopState.MERGED, LoopState.CLOSED, True),
            (LoopState.CLOSED, LoopState.ISSUE_CREATED, False),
        ],
    )
    def test_transition_validity(self, from_state, to_state, expected):
        record = LoopRecord(ref="test", state=from_state)
        assert record.can_transition_to(to_state) is expected
