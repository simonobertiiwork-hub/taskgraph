# Case #5: Recursive Graph Incident

## Problem

Graph cycles can trigger infinite recursive traversal.

Example: A → B → C → A

## Investigation

Recursive CTE traversal.

Cycle causes:

- resource growth
- blocked execution
- database degradation

Diagnostics: pg_stat_activity

## Solution

Protection added:

- cycle validation
- visited path
- depth limit
- stable traversal ordering

## Result

Recursive traversal remains stable.

Infinite recursion prevented.

## Lessons Learned

Cycle protection should exist both before insert and during execution.