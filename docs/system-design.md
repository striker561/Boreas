# Boreas System Design

This document exists to explain the current shape of Boreas in plain terms, including the tradeoffs behind it.

If someone wants to challenge the architecture, this is the baseline they should challenge instead of guessing at intent.

## Design Goals

Boreas is optimized for a narrow job:

- accept an image upload quickly
- keep the HTTP path thin
- move the heavy work off-request
- run well on small hardware
- make object lifecycle explicit
- keep feature ownership obvious for contributors

That means Boreas is intentionally not a general media pipeline, not a generic job framework, and not a place to hide behavior behind convenience abstractions.

## Constraints That Drive The Design

- background removal is CPU-heavy compared to HTTP request handling
- uploads can be larger than the final source size we want workers to process
- queue payloads should stay small and predictable
- final artifacts live in object storage, not in Redis
- abuse protection matters because uploads are expensive
- operators need enough telemetry to understand failures without reverse-engineering the code

## Current Runtime Shape

### Public feature: `media`

`app/features/media` owns:

- the upload API
- upload inspection and validation
- short-lived Redis staging of raw uploads
- source normalization and compression
- the ingest worker that uploads the prepared source object

### Compute feature: `rembg`

`app/features/rembg` owns:

- background removal execution
- the compute worker
- prepared-source cleanup after a successful run

### Operational feature: `health`

`app/features/health` owns:

- `/`
- `/health`
- queue depth and staging metrics
- the health-specific service logic

Health is kept as a feature because it is public API surface with its own behavior and ownership. It does not belong in `main.py` once the app grows beyond a trivial bootstrap.

### Shared infrastructure: `core`

`app/core` owns:

- FastAPI bootstrap
- middleware
- Redis lifecycle
- ARQ pool and worker registry
- configuration
- shared media persistence primitives

Shared storage lives in `core/storage` because it is infrastructure used across feature boundaries, not a public product domain.

## Request And Job Flow

1. `POST /v1/media/jobs`
   The API reads the upload in bounded chunks, validates the media constraints, stores the raw bytes temporarily in Redis, creates the job record, and queues the ingest worker.
2. `media` worker
   The worker reads the staged upload, normalizes it to the configured source cap, uploads the prepared source object, clears staged Redis data, and queues compute.
3. `background removal` worker
   The worker downloads the prepared source, runs `rembg`, uploads the final PNG, deletes the prepared source, and marks the job complete.
4. `GET /v1/media/jobs/{job_id}` or `GET /v1/media/jobs/{job_id}/stream`
   Clients read job state or stream updates until the result is ready.

## Why The Pipeline Is Split

The split between `media` and `rembg` is deliberate.

We do not want the request handler uploading directly to object storage and also doing normalization logic before the response returns. That would make the slowest part of the system user-facing.

We also do not want `rembg` workers to own input normalization because that blurs two different responsibilities:

- preparing a safe, bounded input
- performing the expensive compute step

Keeping them separate gives clearer ownership, cleaner retries, and better control over where CPU and network time are spent.

## Why Raw Uploads Are Staged In Redis

The API process receives the upload bytes first. Those bytes have to go somewhere while the ingest worker picks them up.

We stage them in Redis briefly because:

- it keeps the request path short
- it avoids pushing binary payloads through the queue itself
- it lets the ingest worker own normalization and source upload
- the data is short-lived and explicitly deleted after ingest

To keep upload staging from turning into the request bottleneck, the API reads `UploadFile` in bounded chunks, stages the raw upload only once, and leaves object-storage upload work to the worker side.

We do not keep staged uploads around longer than necessary. Redis is a handoff buffer here, not a durable media store.

## Why Jobs Use Explicit Redis JSON And Bytes Keys

Job metadata and staged binary payloads have different operational needs.

- job state should be readable, inspectable, and safe to decode
- staged upload bytes should stay raw bytes

That is why Boreas stores:

- job metadata as explicit JSON
- staged upload metadata as explicit JSON
- staged upload payload as raw bytes

We do not use a generic pickle cache path because it hides the data shape, makes debugging harder, and creates an unnecessary deserialization surface.

## Why Results Live In Object Storage

Prepared sources and final results are object-storage concerns, not Redis concerns.

Redis stores coordination state. Object storage stores files.

That separation keeps Redis memory bounded and makes result delivery cheaper through presigned URLs.

The storage client is tuned for connection reuse and short network timeouts so worker uploads do not spend unnecessary time rebuilding slow outbound storage paths.

## Result Lifecycle Policy

- staged uploads expire quickly in Redis
- job metadata expires after the configured job TTL
- prepared source objects should be deleted immediately after successful compute
- final result objects are intentionally short-lived and should expire through an object storage lifecycle rule after one hour

The app issues one-hour result URLs because the design assumes the bucket lifecycle matches that retention window.

## Abuse Protection And Rate Limits

Boreas defaults to `5/minute` per client IP for both API reads and uploads.

That default is intentionally conservative because uploads and image processing are expensive. It is also environment-configurable so operators can loosen it later without editing code.

The service uses Redis-backed SlowAPI moving-window limiting because it gives better burst control than a naive fixed window while still staying simple enough for this project.

If a client needs near-real-time job updates, SSE is the preferred path over repeated polling because it spends one request instead of many.

## Logging And Observability

Boreas logs at the places that actually matter operationally:

- startup and shutdown
- request summaries for non-health endpoints
- rate limit violations
- validation failures
- job enqueue failures
- ingest completion
- compute start and completion
- job failure state transitions
- degraded health checks

Logfire is configured through environment variables so operators can keep local logging only in development or forward telemetry when a token is present.

The point of the current logging setup is insight, not verbosity. We want enough signal to answer “what failed, where, and for which job?” without drowning the service in noise.

## Why `main.py` Is Kept Lean

`main.py` should stay a thin composition entrypoint:

- import the app
- include routers

Anything with real behavior belongs in a feature or core module. That is why status and health moved into `app/features/health`.

## What We Intentionally Avoid

- generic service wrappers that hide ownership
- compatibility packages for old names
- queue payloads full of binary data
- persistence abstractions that obscure whether data is JSON or bytes
- routing logic living in `main.py`
- response helpers that exist only for hypothetical future use

## Change Standard

When changing Boreas, preserve these rules unless there is a concrete measured reason not to:

- keep the HTTP path short
- keep feature ownership obvious
- keep file lifecycle explicit
- prefer SSE over aggressive polling
- add configuration only when operators genuinely need it
- delete unused helpers instead of carrying them around “just in case”
