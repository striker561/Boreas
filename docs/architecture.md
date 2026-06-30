# Boreas Architecture

Visual overview of how Boreas runs today. For rationale and tradeoffs, see [system-design.md](system-design.md).

## What Boreas Is

A narrow async pipeline: accept an image upload over HTTP, return a job id immediately, process background removal off-request, and deliver a result URL when ready.

```mermaid
flowchart LR
    Client([Client])

    subgraph Process["Single deployment unit"]
        API[FastAPI API]
        MW[Media worker]
        CW[Compute worker]
        TW[Tasks worker]
    end

    Redis[(Redis)]
    S3[(Object storage)]

    Client -->|POST upload / GET status| API
    API <-->|job state, staged bytes| Redis
    API -->|enqueue job id| Redis
    MW <-->|staging + metadata| Redis
    MW -->|prepared source| S3
    MW -->|enqueue job id| Redis
    CW <-->|job metadata| Redis
    CW <-->|download source / upload result| S3
    TW -->|hourly cleanup| Redis
    TW -->|hourly cleanup| S3
```

## Feature Ownership

```mermaid
flowchart TB
    subgraph HTTP["Public HTTP"]
        media_feat["features/media<br/>upload API + ingest worker"]
        health_feat["features/health<br/>/ and /health"]
    end

    subgraph Workers["Background workers"]
        rembg_feat["features/rembg<br/>ONNX compute worker"]
        tasks_feat["features/tasks<br/>hourly cleanup cron"]
    end

    subgraph Core["Shared infrastructure"]
        core["core/<br/>app bootstrap, config, middleware"]
        queue["core/queue<br/>ARQ pools + worker registry"]
        storage["core/storage<br/>Redis + MediaStorageService"]
        lib["lib/<br/>S3 backend, rembg runtime"]
    end

    media_feat --> storage
    media_feat --> queue
    rembg_feat --> storage
    rembg_feat --> lib
    tasks_feat --> storage
    health_feat --> storage
    health_feat --> queue
    media_feat --> lib
```

## End-to-End Job Flow

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as FastAPI (media)
    participant R as Redis
    participant Q as ARQ queues
    participant M as Media worker
    participant S as Object storage
    participant B as Compute worker

    C->>API: POST /v1/media/jobs (image)
    API->>API: validate dimensions / type / size
    API->>R: write staged upload bytes + metadata
    API->>R: create job record (queued)
    API->>Q: enqueue ingest (job id only)
    API-->>C: 202 job_id

    Q->>M: ingest_media_job(job_id)
    M->>R: read staged upload
    M->>M: normalize + compress source
    M->>S: upload jobs/media/source/{id}
    M->>R: delete staged upload
    M->>R: update job (preparing → queued for compute)
    M->>Q: enqueue compute (job id only)

    Q->>B: remove_background_job(job_id)
    B->>R: mark processing
    B->>S: download prepared source
    B->>B: rembg / ONNX inference
    B->>S: upload jobs/media/result/{id}.png
    B->>S: delete prepared source
    B->>R: mark complete

    C->>API: GET /v1/media/jobs/{id} or SSE stream
    API->>R: read job metadata
    API-->>C: status + presigned result URL
```

## Queues And Workers

ARQ uses Redis as the broker. Queue payloads are **job ids only** — never image bytes.

| Queue            | Worker         | Responsibility                   |
| ---------------- | -------------- | -------------------------------- |
| `boreas:media`   | Media worker   | ingest, normalize, upload source |
| `boreas:compute` | Compute worker | background removal               |
| `boreas:tasks`   | Tasks worker   | hourly cleanup cron              |

```mermaid
flowchart LR
    API[API process] -->|job id| QM[boreas:media]
    QM --> MW[Media worker]
    MW -->|job id| QC[boreas:compute]
    QC --> BW[Compute worker]

    subgraph Supervision["start.sh"]
        loop1["respawn loop"]
        loop2["respawn loop"]
        loop3["respawn loop"]
    end

    loop1 --> MW
    loop2 --> BW
    loop3 --> TW[Tasks worker]
    TW -->|cron minute=0| QT[boreas:tasks]
```

Worker crash recovery: bash respawn loop in `start.sh` (restart after exit). Hung ONNX: `REMBG_INFERENCE_TIMEOUT_SECONDS` inside the compute worker, then retry via ARQ.

## Data Placement

Redis holds **coordination state**. Object storage holds **files**.

```mermaid
flowchart TB
    subgraph RedisKeys["Redis keys (examples)"]
        JK["jobs:media:{job_id}<br/>JSON job metadata"]
        SK["jobs:media:staged-upload:{job_id}<br/>bytes + meta JSON"]
        AQ["boreas:media / boreas:compute / boreas:tasks<br/>ARQ queue data"]
    end

    subgraph S3Keys["Object storage keys"]
        SRC["jobs/media/source/{job_id}"]
        RES["jobs/media/result/{job_id}.png"]
    end

    JK -.->|references| SRC
    JK -.->|references| RES
```

| Data                | Store       | Lifetime                                                     |
| ------------------- | ----------- | ------------------------------------------------------------ |
| Raw upload (staged) | Redis bytes | Short (`MEDIA_STAGING_TTL_SECONDS`); deleted after ingest    |
| Job metadata        | Redis JSON  | Until terminal sweep or age cutoff                           |
| Prepared source     | S3          | Deleted after successful compute                             |
| Final result        | S3          | Presigned URL TTL + bucket lifecycle; orphan sweep as backup |

## Cleanup Policy (Hourly Tasks Cron)

The cleaner does **not** wipe all jobs. It removes **finished work** and **stale/orphan data** so Redis and S3 do not grow without bound.

```mermaid
flowchart TD
    START([Hourly cron fires]) --> SCAN[SCAN jobs:media:* keys]
    SCAN --> FILTER[Skip staged-upload keys]
    FILTER --> LOOP{For each job id}

    LOOP --> LOAD[Load job metadata]
    LOAD --> DECIDE{Delete?}

    DECIDE -->|status is complete or failed| DEL[Delete job + staged-upload keys]
    DECIDE -->|updated_at older than JOB_TTL_SECONDS| DEL
    DECIDE -->|active and recent| KEEP[Keep job]

    DEL --> LOOP
    KEEP --> LOOP

    LOOP --> S3[S3 sweep]
    S3 --> S3DEL[Delete objects under<br/>jobs/media/source/ and<br/>jobs/media/result/<br/>older than JOB_TTL_SECONDS]
    S3DEL --> DONE([Log cleanup summary])
```

### Redis — what gets deleted

| Condition                                          | Action                                                      |
| -------------------------------------------------- | ----------------------------------------------------------- |
| `complete` or `failed`                             | Delete immediately on next hourly run                       |
| Any status, `updated_at` ≤ now − `JOB_TTL_SECONDS` | Delete (covers stuck `queued` / `preparing` / `processing`) |
| Active job, recently updated                       | **Kept**                                                    |

Default `JOB_TTL_SECONDS` = 3600 (1 hour).

### S3 — what gets deleted

Objects under `jobs/media/source/` and `jobs/media/result/` whose `LastModified` is older than `JOB_TTL_SECONDS`. This catches orphans when workers fail or lifecycle rules are misconfigured. Normal happy path already deletes the source after compute.

### What the cleaner does not do

- Does not stop in-flight workers or cancel active jobs that are still within TTL
- Does not replace bucket lifecycle rules for results (those remain the primary expiry mechanism)
- Does not scan unrelated Redis keys (rate limits, ARQ internals, etc.)

## HTTP Surface

```mermaid
flowchart LR
    C([Client]) --> R1["GET /"]
    C --> R2["GET /health"]
    C --> R3["POST /v1/media/jobs"]
    C --> R4["GET /v1/media/jobs/{id}"]
    C --> R5["GET /v1/media/jobs/{id}/stream"]

    R1 --> H[health feature]
    R2 --> H
    R3 --> M[media feature]
    R4 --> M
    R5 --> M
```

## Configuration Knobs (Operational)

| Variable                                                         | Role                                                              |
| ---------------------------------------------------------------- | ----------------------------------------------------------------- |
| `JOB_TTL_SECONDS`                                                | Max job age before forced Redis delete; S3 orphan sweep threshold |
| `MEDIA_STAGING_TTL_SECONDS`                                      | Staged upload expiry in Redis                                     |
| `RESULT_URL_TTL_SECONDS`                                         | Presigned download URL lifetime                                   |
| `REMBG_INFERENCE_TIMEOUT_SECONDS`                                | ONNX wall-clock timeout per attempt                               |
| `MEDIA_WORKERS` / `BACKGROUND_REMOVAL_WORKERS` / `TASKS_WORKERS` | Worker process counts                                             |

## Related Docs

- [system-design.md](system-design.md) — design goals, tradeoffs, what we intentionally avoid
- [deployment-guide.md](deployment-guide.md) — production setup and lifecycle
- [integration-guide.md](integration-guide.md) — client integration patterns
