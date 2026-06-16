# Case #9: Kubernetes Deployment

## Problem

Need a deployment option beyond Docker Compose.

Modern backend systems commonly use Kubernetes for container orchestration and service management.

## Investigation

Created:
- Namespace
- Deployment
- Service

During deployment encountered:
```text
ErrImageNeverPull
```

Used:
- kubectl describe pod
- kubectl logs
- kubectl get endpoints

to investigate startup and networking issues.

## Solution

Implemented Kubernetes deployment for TaskGraph:

TaskGraph
→ Deployment
→ Pod
→ Service

Verified application startup and service routing inside the cluster.

## Result

- Pod successfully started
- FastAPI launched inside Kubernetes
- Service endpoint registered
- HTTP requests reached application through ClusterIP

## Lessons Learned

- Kubernetes requires image availability inside the cluster.
- Deployment and Service should be validated independently.
- kubectl logs and kubectl describe are primary troubleshooting tools.
- Endpoint verification helps diagnose networking issues.