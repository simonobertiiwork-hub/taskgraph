# Case #2: PostgreSQL Race Condition

Generated at: `2026-08-27T12:25:59.719125+00:00`

## Environment

- Database: `taskgraph`
- PostgreSQL: `15.18 (Debian 15.18-1.pgdg13+1)`
- Fixture task id: `200001`
- Configured lock hold: `1.000 s`
- Transaction isolation: `read committed`

## Results

| Strategy | Second transaction observed | Final state | Evidence |
| --- | --- | --- | --- |
| Last write wins | `race demo original`, version 1 | `race demo task B`, version 1 | stale write overwrote task A |
| `SELECT FOR UPDATE` | `race demo task A` | `race demo task B`, version 1 | waited 1.009599 s and re-read committed state |
| Version predicate | version 1 | `race demo task A`, version 2 | stale update affected 0 rows |

## Verification

| Check | Result |
| --- | --- |
| last_write_wins / `transactions_used_distinct_connections` | PASS |
| last_write_wins / `both_transactions_read_original` | PASS |
| last_write_wins / `first_write_was_lost` | PASS |
| pessimistic_lock / `transactions_used_distinct_connections` | PASS |
| pessimistic_lock / `second_writer_observed_first_commit` | PASS |
| pessimistic_lock / `second_writer_waited_for_lock` | PASS |
| pessimistic_lock / `writes_completed_in_lock_order` | PASS |
| optimistic_lock / `transactions_used_distinct_connections` | PASS |
| optimistic_lock / `first_writer_updated_one_row` | PASS |
| optimistic_lock / `stale_second_writer_updated_no_rows` | PASS |
| optimistic_lock / `conflict_was_detected` | PASS |
| optimistic_lock / `first_write_and_incremented_version_remain` | PASS |

Overall status: **PASSED**

Machine-readable scenario details and verification checks are stored in
`summary.json`. The fixture is deleted after the run.
