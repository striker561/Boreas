# Boreas

Boreas is a small, high-throughput FastAPI service for background removal.

The public API is intentionally simple:

- upload an image
- receive a job id immediately
- poll or stream job status
- fetch the processed result from object storage when the job completes

Internally, Boreas is optimized around two worker stages so the HTTP layer stays thin and fast:

1. `media` worker
   Stages the raw upload in Redis, validates it, compresses it to the source size limit when needed, and uploads the prepared source image to Cloudflare R2 / S3-compatible storage.
2. `background removal` worker
   Downloads the prepared source from object storage, runs `rembg`, uploads the final PNG result, and marks the job complete.

This split keeps request latency low while avoiding large byte payloads on the job queue itself.

## How It Works

### Request lifecycle

1. `POST /v1/media/jobs`
   The API validates the upload metadata, stores the raw upload temporarily in Redis, creates the job record, and enqueues the media worker.
2. `media` worker
   The worker reads the staged upload from Redis, normalizes it to the configured source size cap, uploads the prepared source to object storage, clears the staged payload, and enqueues background removal.
3. `background removal` worker
   The worker downloads the prepared source, removes the background, uploads the result image, and updates the job state in Redis.
4. `GET /v1/media/jobs/{job_id}` or `GET /v1/media/jobs/{job_id}/stream`
   Clients fetch the job state or subscribe to SSE updates until the result is ready.

### Data ownership

- `app/features/media`
  Owns the public API, upload inspection, staging, normalization, and ingest worker.
- `app/features/rembg`
  Owns the background-removal processor and compute worker.
- `app/features/storage`
  Owns job persistence, staged upload persistence, and object storage access helpers.
- `app/core`
  Owns app bootstrap, middleware, Redis/ARQ lifecycle, configuration, and worker registry.

## Why This Shape

Boreas is designed for small infrastructure with high request volume:

- the API does lightweight validation and queues work quickly
- worker services are warmed once on startup and reused from worker context
- storage and Redis backends are shared singletons per process
- the queue carries job ids, not binary blobs
- staged raw uploads in Redis are short-lived and deleted after ingest

The only binary payload stored outside object storage is the short-lived staged upload used to hand work from the API process to the media worker.

## Configuration

Copy `.env.example` to `.env` and set the required values.

Important settings:

- `REDIS_URL`
- `STORAGE_ENDPOINT_URL`
- `STORAGE_ACCESS_KEY_ID`
- `STORAGE_SECRET_ACCESS_KEY`
- `STORAGE_BUCKET_NAME`
- `MEDIA_SOURCE_MAX_BYTES`
- `MEDIA_STAGING_TTL_SECONDS`
- `MEDIA_WORKERS`
- `BACKGROUND_REMOVAL_WORKERS`
- `REMBG_MODEL`

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./start.sh
```

The startup script launches:

- one or more media workers
- one or more background-removal workers
- the FastAPI app through Uvicorn

## API Summary

### Create job

`POST /v1/media/jobs`

Accepts a single file upload.

### Get job

`GET /v1/media/jobs/{job_id}`

Returns the current job state and result URL when complete.

### Stream job

`GET /v1/media/jobs/{job_id}/stream`

Sends Server-Sent Events as the job status changes.

## Operational Notes

- Incoming request size can be larger than the final source cap.
- The media worker is responsible for shrinking oversized uploads before compute begins.
- Background removal outputs PNG because transparency must be preserved.
- Jobs and staged uploads expire automatically through Redis TTLs.

## Project Goal

Boreas is meant to stay small, explicit, and contributor-friendly.

The codebase prefers clear ownership boundaries over convenience wrappers:

- public upload/orchestration logic lives in `media`
- compute logic lives in `rembg`
- persistence logic lives in `storage`

That separation is the main architectural rule to preserve as the project grows.
