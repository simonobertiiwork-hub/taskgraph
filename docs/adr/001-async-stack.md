# ADR-001: Async Stack

## Context
Backend workload:
- database operations
- concurrent requests
- I/O-bound tasks

## Decision
Use:
- FastAPI
- SQLAlchemy Async
- asyncpg

## Alternatives
- synchronous stack

## Why
- single async model
- good FastAPI integration
- efficient handling of concurrent I/O

## Tradeoff
- async required across repositories and services