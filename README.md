# LoopForge

Archived February 2026 experiment implementing a Python state machine for tracking issue-to-PR-to-merge lifecycle transitions in AI-assisted development workflows. This repository is unmaintained and preserved for historical reference.

## What the implementation does

`LoopRecord` holds a work item's current state and recorded transition history. It checks requested transitions against `VALID_TRANSITIONS` and records the previous state, new state, caller-supplied trigger, timestamp and optional metadata.

`LoopService` loads records through a repository interface, validates a requested transition, updates its history and saves it before running registered transition hooks. The repository includes in-memory storage and an optional DynamoDB adapter. In-memory storage is temporary and not thread-safe.

The normal path is `issue_created → task_queued → pr_created → ci_pending → ci_passed → merged → closed`. The state graph also includes CI failure/retry and optional review/approval paths; review is not mandatory on every path.

## Limits

The library manages state transitions and recorded history. It does not independently verify that CI passed, a GitHub pull request was merged or an external approval occurred. State names and trigger strings represent information supplied by the caller, not verified external events. Fields such as `auto_merge` store metadata; they do not execute a GitHub merge.

Transition hooks run after persistence. Hook exceptions are caught and logged, and do not prevent or roll back a completed transition. A hook cannot serve as a pre-transition approval gate. Calling Gatekeep from a hook would provide advisory output after the transition, not enforce security or compliance.

Recorded history is not an independently verified or tamper-proof audit log. This is not a complete CI/CD approval or compliance enforcement system, and it should not be relied on as a production control.

## Repository reference

- [States and record history](src/loopforge/states.py)
- [Transition service and hooks](src/loopforge/service.py)
- [Repository interface and in-memory storage](src/loopforge/repository.py)
- [Optional DynamoDB adapter](src/loopforge/adapters/dynamodb.py)

Historical dependencies and code are preserved without an ongoing support or security-update commitment. Licensed under [MIT](LICENSE).
