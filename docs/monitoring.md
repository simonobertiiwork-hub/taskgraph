# Monitoring

## Stack

- Prometheus
- Grafana

## Dashboards

### TaskGraph Monitoring

Panels:
- HTTP Requests Total
- HTTP Requests By Endpoint
- HTTP Latency P95
- HTTP Latency P99

Metrics:
- http_requests_total
- http_request_duration_seconds_bucket
- http_request_duration_seconds_sum
- http_request_duration_seconds_count

## Purpose

Monitoring is used to validate performance-related investigation cases.

Examples:
- Connection Pool Exhaustion
- Heavy Queries
- API Latency Investigation

## Usage

Open:
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

Verify:
- Request throughput
- Endpoint activity
- P95 latency
- P99 latency