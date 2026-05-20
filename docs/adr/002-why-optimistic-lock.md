# ADR-002: Optimistic Lock

## Context
Concurrent updates can overwrite data.

## Decision
Use:
- version field
- atomic UPDATE
- 409 Conflict on version mismatch

## Alternatives
- SELECT FOR UPDATE
- last write wins

## Why
- avoids row locks
- prevents silent overwrite
- explicit conflict handling

## Tradeoff
- client handles 409 Conflict