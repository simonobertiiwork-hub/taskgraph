# Case #4: Recursive Graph Traversal

## Problem

Recursive graph traversal becomes expensive as graph depth grows.

## Investigation

Cleaned previous graph data.

Generated graph:
- 3000 nodes
- 2999 edges

Measured via EXPLAIN ANALYZE.

Without depth limit:
- full recursive traversal executed
- execution time ≈ 11 ms

## Solution

Limited recursive traversal depth:

WHERE t.depth < 5

Repeated the same query.

## Result

With depth limitation:
- execution time ≈ 0.2 ms
- recursive traversal became significantly cheaper

## Lessons Learned

- Recursive queries scale poorly on deep graphs.
- Traversal depth should be limited in production systems.
- EXPLAIN ANALYZE helps detect recursive bottlenecks.