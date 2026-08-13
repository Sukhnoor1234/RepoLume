# Analysis worker lifecycle

This document defines the job-state contract shared by the analysis API and
worker. The API now exposes submission and status shapes through an injected
job-service boundary. The worker pipeline connects repository retrieval, source
analysis, architecture composition, lifecycle history, and cleanup. The bounded
runtime connects Redis Stream delivery to durable lifecycle and result
persistence.

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> cloning
    cloning --> analyzing
    analyzing --> completed
    queued --> failed
    cloning --> failed
    analyzing --> failed
    completed --> [*]
    failed --> [*]
```

## State meanings

| State | Meaning |
| --- | --- |
| `queued` | The request has been accepted but not claimed by a worker. |
| `cloning` | The worker is retrieving the approved repository source. |
| `analyzing` | Static analysis is running against the isolated source. |
| `completed` | The expected analysis artifacts were produced successfully. |
| `failed` | Processing stopped and a safe failure reason was recorded. |

## Transition rules

- Jobs move forward one successful state at a time.
- Any active state may transition to `failed`.
- `completed` and `failed` are terminal.
- A worker must reject skipped, repeated, or backward transitions.
- Retrying a failed job will create a new attempt rather than reopen a
  terminal state.

## Runtime behavior

Lifecycle transitions use compare-and-set updates so duplicate delivery cannot
advance the same job twice. The worker stores a completed architecture and its
terminal state atomically, or records a safe controlled failure, before it
acknowledges Redis. Persistence availability failures leave the delivery
pending for recovery.

See [analysis runtime wiring](analysis-runtime.md) for duplicate and stale
delivery behavior.

## Deferred details

- Continuous worker supervision and heartbeat renewal
- Retry limits, backoff, and dead-letter policy
- Cancellation
- Progress events
