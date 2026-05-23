# Case #1: Race Condition

## Problem

Concurrent updates can overwrite data.

Two clients update the same task simultaneously.

Without protection:

PATCH /tasks/1 {"title":"A"} → 200
PATCH /tasks/1 {"title":"B"} → 200

Last write silently overwrites previous data.

## Alternatives

1. Last write wins ❌
2. Pessimistic lock ❌
3. Optimistic lock (version field) ✅

## Solution

Version-based optimistic locking.

Atomic update validates version before commit.

Conflict detected → 409 Conflict

## Result

PATCH /tasks/1 {"version":1} → 200
PATCH /tasks/1 {"version":1} → 409

- no silent overwrite
- no row locking
- controlled concurrent updates

## Lessons Learned

Optimistic locking prevents data loss without blocking reads.