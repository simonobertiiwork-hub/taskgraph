# Case #3: Race Condition

## Problem

Concurrent updates can overwrite data.

Without synchronization:
PATCH /tasks/1 {"title":"A"} → 200
PATCH /tasks/1 {"title":"B"} → 200

Last update silently overwrote previous changes.

## Investigation

Three update strategies were reproduced:
1. Last write wins
2. Pessimistic locking
3. Optimistic locking

Measured with concurrent update tests.

## Solution

Implemented version-based optimistic locking.
Atomic update validates row version before commit.
Conflict returns HTTP 409.

## Result

Without synchronization:
- Lost Update reproduced
- previous update overwritten

With pessimistic locking:
- overwrite prevented
- second transaction waited

With optimistic locking:
- version conflict detected
- update safely rejected

## Lessons Learned

- Lost Update is a real production issue.
- Pessimistic locking increases waiting time.
- Optimistic locking protects consistency without blocking reads.