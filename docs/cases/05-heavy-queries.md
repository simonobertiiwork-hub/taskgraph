# Case #5: Heavy Queries Investigation

## Problem

One expensive query can affect unrelated requests and degrade overall API responsiveness.

Reproduction

Heavy endpoint:
"GET /tasks/heavy"

Light endpoint:
"GET /tasks"

Test scenario:
- 1 heavy request
- 3 lightweight requests
- parallel execution

## Investigation

Observed behavior:
- Light requests: "5-20 ms -> 6-9 s"
- Heavy request: "2-4 s -> 8-9 s"

Heavy database load affected unrelated endpoints during concurrent execution.

What Was Investigated

Tried approaches:
- query optimization
- async execution
- background processing ideas
- caching strategy discussion

The issue was partially reproduced, but stable production-style isolation for the demo was not achieved.

Because of this, the case was excluded from the final live demonstration.

## Lessons Learned

- Heavy database operations can affect unrelated endpoints.
- Async execution does not remove database bottlenecks.
- Reproducing real production incidents in isolation can be difficult.
- Not every production problem can be converted into a stable demo scenario.