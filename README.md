# LoopForge

A typed, auditable state machine for the **issue → PR → CI → merge → close** development lifecycle.

Every transition is validated, timestamped, and recorded. LoopForge gives you a complete audit trail of how every work item moved through your pipeline — who triggered it, when it happened, and what metadata was attached. Built for teams that need to prove what happened and when, whether for compliance (SOC 2, ISO 27001, GDPR) or just to debug why that PR got merged at 3am.

## Why

AI-generated code is everywhere. Tools are opening PRs from issues, running CI, and auto-merging — but most teams track this with ad-hoc if/else logic and no formal audit trail. LoopForge gives you:

- **Validated transitions** — Can't merge before CI passes. Can't close before merging. The state machine enforces the rules.
- **Full audit trail** — Every state change is recorded with timestamp, trigger, and metadata. Queryable, exportable, auditable.
- **Transition hooks** — Fire custom logic on every state change: audit logging, Slack notifications, webhook calls, metrics.
- **Storage-agnostic** — Bring your own backend. DynamoDB, Postgres, SQLite, Redis, a JSON file. LoopForge doesn't care.

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
from loopforge import LoopService, LoopState
from loopforge.repository import MemoryRepository

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

# Every transition is recorded
for t in record.transitions:
    print(f"{t.timestamp} | {t.from_state} → {t.to_state} | {t.trigger}")
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

## Audit Trail

Every `LoopRecord` carries its full transition history:

```python
record = service.get(record_id)

for t in record.transitions:
    print(f"[{t.timestamp}] {t.from_state} → {t.to_state}")
    print(f"  trigger: {t.trigger}")
    print(f"  metadata: {t.metadata}")
```

Each transition captures:
- `from_state` / `to_state` — what changed
- `trigger` — what caused it (e.g. `"ci.passed"`, `"reviewer.approved"`)
- `timestamp` — ISO 8601 UTC
- `metadata` — arbitrary dict for context (commit SHA, user ID, CI job URL, etc.)

This gives you a complete, queryable history of every work item. Export it, pipe it to your SIEM, or use it for compliance reporting.

## Transition Hooks

Fire custom logic on every successful transition — audit logging, notifications, webhooks, metrics:

```python
def audit_hook(record, previous_state, new_state, trigger):
    log_to_audit_system(
        record_id=record.record_id,
        change=f"{previous_state.value} → {new_state.value}",
        trigger=trigger,
        timestamp=record.updated_at,
    )

def slack_hook(record, previous_state, new_state, trigger):
    if new_state == LoopState.CI_FAILED:
        send_slack_alert(f"CI failed for {record.ref}")

service = LoopService(repository=repo, hooks=[audit_hook, slack_hook])
```

Hooks that raise exceptions are caught and logged — they won't break the transition.

## Invalid Transitions

LoopForge won't let your pipeline do something illegal:

```python
result = service.transition(record_id, LoopState.MERGED, "yolo")

if not result.success:
    print(result.error)
    # "Invalid transition: issue_created → merged.
    #  Allowed from issue_created: task_queued"
```

## Custom Storage

Implement the `Repository` protocol to use any backend:

```python
from loopforge.repository import Repository
from loopforge.states import LoopRecord

class PostgresRepository:
    def save(self, record: LoopRecord) -> LoopRecord: ...
    def get(self, record_id: str) -> LoopRecord | None: ...
    def delete(self, record_id: str) -> bool: ...
    def list_by_state(self, state: str, limit: int = 100) -> list[LoopRecord]: ...
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

- **AI code generation pipelines** — Track issues through automated fix/feature workflows with full auditability
- **GitHub Actions / CI bots** — State machine for issue-to-merge automation
- **Compliance-sensitive environments** — SOC 2, ISO 27001, GDPR audit trails for automated processes
- **Release management** — Governed deployment workflows with transition history
- **Custom DevOps tooling** — Any pipeline where you need to prove what happened and when

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
