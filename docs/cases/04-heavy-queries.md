# Case #4: Heavy Queries

## Problem

One expensive query can affect the entire system.

## Reproduction

Heavy endpoint: GET /tasks/heavy
Light endpoint: GET /tasks

Test: 1 heavy request + 5 lightweight requests, parallel execution.

## Investigation

Light requests: 5–20 ms → 6–9 s
Heavy request: 2–4 s → 8.9 s

## Solution

- optimize queries
- cache results
- move expensive work to background processing

## Lessons Learned

Heavy database operations affect unrelated endpoints.

Async does not solve database contention.