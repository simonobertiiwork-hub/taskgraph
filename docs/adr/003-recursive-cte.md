# ADR-003: Recursive CTE

## Context
Need graph traversal with cycle protection.

## Decision
Use:
- recursive CTE
- depth limit

## Alternatives
- Python recursion
- PL/pgSQL procedure

## Why
- traversal stays inside database
- prevents infinite recursion
- predictable depth control

## Tradeoff
- query complexity increases