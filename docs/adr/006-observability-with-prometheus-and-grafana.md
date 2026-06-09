# ADR-006: Observability with Prometheus and Grafana

## Context

Performance investigations require measurable data.

Application logs alone are insufficient for latency analysis and load testing.

## Decision

Use:

- Prometheus
- Grafana

Collect:

- Request count
- Endpoint activity
- P95 latency
- P99 latency

## Alternatives

- Application logs only
- Custom monitoring solution

## Why

- Industry standard
- Easy integration
- Supports investigation-driven development

## Tradeoff

- Additional infrastructure
- Dashboard maintenance