# ADR-004: Redis Cache

## Context

Need faster access to task statistics.

## Decision

Use:
- Redis cache
- Cache Aside pattern
- 30 seconds TTL

## Alternatives

- Query PostgreSQL every request
- Materialized view
- In-memory application cache

## Why

- reduces database load
- improves response time
- simple integration

## Tradeoff

- possible stale data during TTL
- additional infrastructure component