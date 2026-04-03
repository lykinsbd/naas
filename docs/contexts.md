# Context Routing

Contexts allow NAAS to route jobs to workers in specific network segments, VRFs, or geographies. This is essential in enterprise environments where the same IP address exists in multiple VRFs, or where workers in different locations have different device reachability.

## Overview

A **context** is a named routing scope. Each context maps to a dedicated RQ queue. Workers declare which contexts they serve, and callers specify which context a job targets.

```text
Caller → API → naas-{context} queue → Worker serving {context} → Device
```text

## Why Contexts?

In enterprise networks, IP addresses are not globally unique:

- `10.1.1.1` in VRF `corp` is a different device than `10.1.1.1` in VRF `oob`
- A worker in the corp network cannot reach OOB management devices
- A worker in Hong Kong cannot reach London devices

Without contexts, NAAS cannot guarantee a job reaches a worker with the correct reachability.

## Configuration

### API: Define valid contexts

```bash
NAAS_CONTEXTS=default,corp,oob-dc1,oob-dc2,hk-prod,hk-oob,lon-prod,lon-oob
```text

Unknown context names in requests return `400 Bad Request`.

### Worker: Declare served contexts

```bash
# Single context
WORKER_CONTEXTS=oob-dc1

# Multiple contexts
WORKER_CONTEXTS=oob-dc1,oob-dc2

# Default (backwards compatible — omit for single-segment deployments)
# WORKER_CONTEXTS not set → serves "default" context
```text

## Usage

### Basic request with context

```json
{
  "host": "10.1.1.1",
  "context": "oob-dc1",
  "platform": "cisco_ios",
  "commands": ["show version"]
}
```text

### Default context (backwards compatible)

```json
{
  "host": "192.168.1.1",
  "platform": "cisco_ios",
  "commands": ["show version"]
}
```text

Omitting `context` defaults to `"default"`. Existing deployments require no changes.

## Use Cases

### Multi-VRF (same IP, different devices)

```json
// Corp device at 10.1.1.1
{"host": "10.1.1.1", "context": "corp", "commands": ["show version"]}

// OOB management device at same IP, different VRF
{"host": "10.1.1.1", "context": "oob-dc1", "commands": ["show version"]}
```text

### Geographic routing

```json
// Route to Hong Kong workers only
{"host": "10.100.1.1", "context": "hk-prod", "commands": ["show bgp summary"]}

// Route to London workers only
{"host": "10.200.1.1", "context": "lon-prod", "commands": ["show bgp summary"]}
```text

### OOB management plane

```json
// Target device via out-of-band management, not production network
{"host": "172.16.1.1", "context": "oob-dc1", "commands": ["show logging"]}
```text

## Context Discovery

List active contexts with worker counts and queue depths:

```bash
curl -k https://naas.example.com/v1/contexts
```text

```json
{
  "contexts": [
    {"name": "corp",    "workers": 3, "queue_depth": 2},
    {"name": "oob-dc1", "workers": 1, "queue_depth": 0},
    {"name": "hk-prod", "workers": 2, "queue_depth": 5},
    {"name": "lon-prod", "workers": 2, "queue_depth": 1}
  ]
}
```text

## Error Responses

### Unknown context (400)

```json
{"error": "Unknown context. See GET /v1/contexts for valid contexts."}
```text

### No workers available (503)

```json
{"error": "No workers available for the requested context"}
```text

This occurs when the context is valid but no workers are currently serving it. Check worker health and `WORKER_CONTEXTS` configuration.

## Kubernetes Deployment

Deploy separate worker Deployments per context:

```yaml
# Corp workers
- name: naas-worker-corp
  env:
    - name: WORKER_CONTEXTS
      value: "corp"

# OOB workers (deployed in OOB network segment)
- name: naas-worker-oob
  env:
    - name: WORKER_CONTEXTS
      value: "oob-dc1,oob-dc2"

# Hong Kong workers
- name: naas-worker-hk
  env:
    - name: WORKER_CONTEXTS
      value: "hk-prod,hk-oob"
```text

See [Kubernetes deployment guide](deployment/kubernetes.md) for full examples.
