# Case #3: PostgreSQL Race Condition

## Problem

A read-modify-write flow can lose data when two transactions read the same
task version and then update it independently. Without a concurrency strategy,
both writes can succeed and the later commit silently replaces the earlier
one.

## Reproduction

The case runs three deterministic strategies against two simultaneous
PostgreSQL connections:

```bash
docker compose exec app python -m demos race-condition --confirm-write
```

The command creates one temporary task, resets it before each strategy, writes
a report, and deletes the fixture in a `finally` block. It does not truncate
the `tasks` table.

Verified run parameters:

- PostgreSQL `15.18`;
- transaction isolation `read committed`;
- two distinct PostgreSQL backend processes per strategy;
- initial state: title `race demo original`, version `1`;
- configured pessimistic-lock hold: `1.000 s`.

## 1. Last Write Wins

Backend processes `22030` and `22031` both read the original title and version
`1`. Transaction A wrote `race demo task A`; transaction B then performed an
unconditional stale write with `race demo task B`.

Final state:

```text
title = race demo task B
version = 1
```

Both updates completed, but transaction A's change disappeared. This
reproduces the lost-update problem.

## 2. Pessimistic Locking

Transaction A acquired a row lock with `SELECT FOR UPDATE`, held it for one
second, and wrote `race demo task A`. Transaction B used another PostgreSQL
connection and waited `1.009599 s` for the lock.

After acquiring the lock, transaction B observed transaction A's committed
title rather than the original value. It then wrote `race demo task B`.

The final title still belongs to transaction B because both writes are allowed
by this scenario. The important difference is that the operations were
serialized: the second writer worked from the current committed state instead
of silently applying a stale update.

## 3. Optimistic Locking

Both transactions read version `1`. Transaction A executed an atomic update
with a version predicate, changed one row, and incremented the version to `2`.
Transaction B then attempted its stale update using version `1`:

```sql
UPDATE tasks
SET title = :title, version = 2
WHERE id = :task_id AND version = 1;
```

The stale update affected `0` rows, so the conflict was detected. Final state:

```text
title = race demo task A
version = 2
```

TaskGraph applies the same principle in the update endpoint. A zero-row update
raises `ConflictError`, which the API maps to HTTP `409 Conflict`.

## Verified Result

- lost update reproduced with two real PostgreSQL connections;
- `SELECT FOR UPDATE` serialized the writers and forced the second transaction
  to re-read committed state;
- the version predicate rejected the stale update without overwriting data;
- every automated verification check passed;
- the temporary fixture was deleted after the run.

The measured `1.009599 s` is evidence of the deliberately configured one-second
lock hold. It is not presented as production latency.

## Evidence

The captured run is stored in
[`docs/results/03-race-condition`](../results/03-race-condition/README.md):

- PostgreSQL version, isolation level, and run parameters;
- backend process identifiers for both concurrent connections;
- complete state transitions for all three strategies;
- generated report and machine-readable verification results.
