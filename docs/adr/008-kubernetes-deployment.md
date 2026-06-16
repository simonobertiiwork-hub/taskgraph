# ADR-008: Kubernetes Deployment

## Context

TaskGraph supports Docker-based deployment.

Need practical experience with container orchestration and Kubernetes fundamentals.

## Decision

Use:
- Kubernetes Namespace
- Deployment
- Service (NodePort)

Deploy TaskGraph inside a local Kubernetes cluster.

## Alternatives

- Docker Compose only
- Virtual machine deployment
- Managed Kubernetes service

## Why

- Industry-standard orchestration platform
- Common interview topic
- Demonstrates deployment beyond Docker Compose

## Tradeoff

- Additional infrastructure
- More complex debugging
- Extra configuration files