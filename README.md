# LoopForge

A typed, validated state machine for automating the **issue → PR → CI → merge → close** development lifecycle.

LoopForge gives you a clean, storage-agnostic framework for tracking work items through a closed-loop development pipeline. Bring your own storage backend, Git provider, and CI system.

## Install

```bash
pip install loopforge
```

With DynamoDB support:

```bash
pip install loopforge[dynamodb]
```

## Quick Start

```python
from loopforge import LoopService, LoopState, create_record
from loopforge.repository import MemoryRepository

# Set up
repo = MemoryRepository()
service = LoopService(repository=repo)

# Create a record for a new issue
record = service.create(
    ref="https://github.com/org/repo/issues/42",
    repo="org/repo",
    auto_merge=True,
)

# Walk it through the lifecycle
service.transition(record.record_id, LoopState.TASK_QUEUED, "worker.picked_up")
service.transition(record.record_id, LoopState.PR_CREATED, "pr.opened")
service.transition(record.record_id, LoopState.CI_PENDING, "ci.started")
service.transition(record.record_id, LoopState.CI_PASSED, "ci.completed")
service.transition(record.record_id, LoopState.MERGED, "auto.merged")
service.transition(record.record_id, LoopState.CLOSED, "issue.closed")
```

## State Machine

```
issue_created → task_queued → pr_created → ci_pending ─┬→ ci_passed ─┬→ merged → closed
                                                        │             │
                                                        └→ ci_failed ─┘  (retry)
                                                                      │
                                                                      └→ awaiting_review → approved → merged
```

### States

| State | Description |
|-------|-------------|
| `issue_created` | Work item identified |
| `task_queued` | Picked up by a worker |
| `pr_created` | Pull request opened |
| `ci_pending` | CI checks running |
| `ci_passed` | All checks green |
| `ci_failed` | CI failed (can retry) |
| `awaiting_review` | Waiting for human review |
| `approved` | Review approved |
| `merged` | PR merged |
| `closed` | Issue closed (terminal) |

## Transition Hooks

Fire custom logic on every successful transition — audit logging, notifications, webhooks, metrics, whatever you need:

```python
def audit_hook(record, previous_state, new_state, trigger):
    print(f"{record.record_id}: {previous_state.value} → {new_state.value}")

service = LoopService(repository=repo, hooks=[audit_hook])
```

Hooks that raise exceptions are caught and logged — they won't break the transition.

## Custom Storage

Implement the `Repository` protocol to use any backend:

```python
from loopforge.repository import Repository
from loopforge.states import LoopRecord

class PostgresRepository:
    def save(self, record: LoopRecord) -> LoopRecord:
        # INSERT or UPDATE ...
        return record

    def get(self, record_id: str) -> LoopRecord | None:
        # SELECT ... WHERE record_id = ?
        ...

    def delete(self, record_id: str) -> bool:
        # DELETE ... WHERE record_id = ?
        ...

    def list_by_state(self, state: str, limit: int = 100) -> list[LoopRecord]:
        # SELECT ... WHERE state = ? LIMIT ?
        ...
```

## DynamoDB Adapter

```python
from loopforge.adapters.dynamodb import DynamoDBRepository
from loopforge import LoopService

repo = DynamoDBRepository(table_name="my-loops", region_name="us-east-1")
service = LoopService(repository=repo)
```

Table schema: partition key `record_id` (S). Optional GSI `state-index` on `state` (S) + `updated_at` (S) for `list_by_state` queries.

## TransitionResult

Every `service.transition()` call returns a `TransitionResult`:

```python
result = service.transition(record_id, LoopState.CI_PASSED, "ci.completed")

if result.success:
    print(f"Moved from {result.previous_state} to {result.new_state}")
else:
    print(f"Failed: {result.error}")
```

## Use Cases

- **GitHub Actions / CI bots** — Track issues through automated fix pipelines
- **Dev automation platforms** — Manage the lifecycle of AI-generated code
- **Release management** — State machine for deployment workflows
- **Custom DevOps tooling** — Any issue-to-merge automation

## Development

```bash
git clone https://github.com/fenderfonic/loopforge.git
cd loopforge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT
