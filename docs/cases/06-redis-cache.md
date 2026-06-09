# Case #6: Redis Cache

## Problem

Repeated statistics requests generate unnecessary PostgreSQL load.

## Investigation

Without cache:
- Every request hits PostgreSQL
- Same calculations executed repeatedly

With Redis cache:
- First request → Cache Miss
- Subsequent requests → Cache Hit

Measured via application logs and Redis inspection.

## Solution

Implemented Redis caching layer.

Cache flow:
- Check Redis
- Return cached value if exists
- Query PostgreSQL on cache miss
- Store result in Redis

## Result

- Reduced PostgreSQL load
- Faster repeated requests
- Improved scalability

## Lessons Learned

- Redis is effective for frequently requested data.
- Cache invalidation strategy is important.
- Not every endpoint benefits from caching.