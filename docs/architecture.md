# Architecture

## Overview

NAAS is a thin async wrapper around [Netmiko](https://github.com/ktbyers/netmiko). The API accepts requests, enqueues jobs, and returns immediately. Workers pick up jobs from the queue and execute them against network devices.

```mermaid
sequenceDiagram
    participant Client
    participant API as NAAS API
    participant Queue as Redis Queue
    participant Worker as RQ Worker
    participant Device as Network Device

    Client->>API: POST /v1/send_command
    API->>Queue: enqueue job (job_id = X-Request-ID)
    API-->>Client: 202 Accepted { job_id }

    Worker->>Queue: fetch next job
    Worker->>Device: SSH via Netmiko
    Device-->>Worker: command output
    Worker->>Queue: store result

    Client->>API: GET /v1/send_command/{job_id}
    API->>Queue: fetch job result
    API-->>Client: 200 { status: finished, results: {...} }
```

## Components

```mermaid
graph TD
    Client["Client<br/>(curl / Python / etc.)"]
    API["NAAS API<br/>(Flask + Gunicorn)"]
    Redis["Redis<br/>(job queue + results)"]
    Worker["RQ Worker<br/>(one or more)"]
    Device["Network Devices<br/>(Cisco, Arista, Juniper, ...)"]

    Client -->|HTTPS| API
    API -->|enqueue / fetch| Redis
    Worker -->|dequeue / store| Redis
    Worker -->|SSH via Netmiko| Device
```

### NAAS API

The Flask application handles authentication, request validation, job enqueueing, and result retrieval. It is stateless — all state lives in Redis. Multiple API instances can run behind a load balancer.

### Redis

Redis serves two roles:

- **Job queue** — RQ uses Redis sorted sets to hold pending jobs
- **Result store** — completed job output is stored in Redis with a configurable TTL

### RQ Worker

Workers are separate processes that dequeue jobs and execute them. Each worker handles one job at a time. Scale horizontally by running more worker containers.

Workers also hold circuit breaker state in Redis, so all workers share the same per-device failure counts.

### Network Devices

NAAS connects to devices over SSH using Netmiko. The API credentials (HTTP Basic Auth) are passed directly to the device — NAAS does not maintain its own credential store.

## Request Lifecycle

1. **Client** sends `POST /v1/send_command` with device IP, platform, and commands
2. **API** validates the request (IP format, platform, auth), checks for duplicate job IDs and device lockout, then enqueues the job
3. **API** returns `202 Accepted` with the `job_id` (= `X-Request-ID`)
4. **Worker** picks up the job, checks the circuit breaker, connects to the device via SSH, runs the commands, and stores the result
5. **Client** polls `GET /v1/send_command/{job_id}` until `status` is `finished` or `failed`

## Why Async?

SSH connections to network devices can take seconds to minutes depending on device responsiveness, command complexity, and network latency. A synchronous API would hold HTTP connections open for the duration, limiting throughput and causing timeouts.

The async model lets the API return immediately and lets clients poll at their own pace. It also enables horizontal scaling — add more workers to increase throughput without changing the API layer.

## Scaling

```mermaid
graph LR
    LB["Load Balancer"]
    API1["API instance 1"]
    API2["API instance 2"]
    Redis["Redis"]
    W1["Worker 1"]
    W2["Worker 2"]
    W3["Worker 3"]

    LB --> API1
    LB --> API2
    API1 --> Redis
    API2 --> Redis
    W1 --> Redis
    W2 --> Redis
    W3 --> Redis
```

- **API** scales horizontally — stateless, any instance can handle any request
- **Workers** scale horizontally — add containers with `docker compose up -d --scale worker=N`
- **Redis** is the single coordination point — use Redis Sentinel or Cluster for HA
