# Boreas Deployment Guide

This document explains how to deploy Boreas well, what tradeoffs the runtime knobs make, and how to choose a rembg model without guessing.

It is written for operators and OSS users who want a reliable CPU-only deployment first, then want a clear path to better quality or more throughput later.

## What You Are Deploying

Boreas runs three responsibilities:

- one FastAPI process for the public API
- one media ingest worker group that normalizes uploads and pushes prepared source images to object storage
- one background-removal worker group that runs rembg and uploads the final PNG

The default container entrypoint starts all three inside one container through [start.sh](../start.sh).

That design is intentional for small deployments because:

- it keeps operations simple
- it works well in Coolify as a single application service
- it avoids premature splitting of API and worker services

The tradeoff is that API and workers share the same machine budget. If the machine is too small or the worker settings are too aggressive, compute can starve the rest of the app.

## Infrastructure You Need

Minimum external services:

- Redis for job state, staged uploads, queue data, and rate limiting
- S3-compatible object storage for prepared source objects and final result objects

Recommended production shape:

- Boreas container on Coolify
- Redis as a managed service or a separate service
- Cloudflare R2 or another S3-compatible bucket

Boreas assumes:

- Redis is reachable from the app at `REDIS_URL`
- the bucket is private
- final result objects are short-lived and expire through a lifecycle rule

Important container networking rule:

- `localhost` inside the Boreas container means the Boreas container itself, not your Redis service
- in Coolify, set `REDIS_URL` to the internal hostname or service name of the Redis service
- use `localhost` only for non-container local development

Object paths used by Boreas:

- prepared source objects: `jobs/media/source/<job_id>`
- final result objects: `jobs/media/result/<job_id>.png`

Recommended lifecycle policy:

- delete `jobs/media/result/` objects after 1 hour
- let the app delete `jobs/media/source/` objects immediately after successful compute

## Quick Start For Coolify

Use the current Dockerfile and deploy Boreas as one application service.

Set `REDIS_URL` to the Redis service host provided by Coolify, not `localhost`.

Expose:

- port `8000`

Health check:

- path: `/`

Use `/` for container liveness.

Do not use `/health` as the container liveness probe. `/health` is the operational report and includes dependency checks. Boreas already warms Redis and ARQ during startup, so the Docker healthcheck should only verify that the API process is up and answering requests.

Persist this directory if Coolify offers a volume:

- `/home/appuser/.u2net`

That cache matters because rembg models are downloaded on first use. If the directory is not persisted, cold redeploys may spend time downloading the model again.

## Recommended First Production Profile

Use this as the starting point for a small CPU-only VPS, including a Hostinger KVM2-class deployment.

```env
MEDIA_WORKERS=1
BACKGROUND_REMOVAL_WORKERS=1
REMBG_MODEL=isnet-general-use
REMBG_POST_PROCESS_MASK=true
REMBG_ALPHA_MATTING=false
REMBG_ALPHA_MATTING_FOREGROUND_THRESHOLD=240
REMBG_ALPHA_MATTING_BACKGROUND_THRESHOLD=10
REMBG_ALPHA_MATTING_ERODE_SIZE=10
REMBG_OMP_NUM_THREADS=2
LOG_LEVEL=INFO
```

Why this is the default profile:

- one media worker is enough because ingest is mostly I/O plus image normalization
- one background-removal worker avoids CPU oversubscription on a small box
- `isnet-general-use` is a better quality-versus-latency default than `u2netp`
- `post_process_mask=true` usually improves mask cleanliness at a reasonable cost
- `alpha_matting=false` protects throughput and CPU budget until you know you need finer edge treatment
- `REMBG_OMP_NUM_THREADS=2` stops ONNX from spawning too many CPU threads per worker

## Environment Variables That Matter Most

### Core request and lifecycle limits

- `MAX_BODY_SIZE`
  Hard HTTP request limit. Boreas defaults to 10 MB.
- `MEDIA_SOURCE_MAX_BYTES`
  Target maximum size for the normalized source sent to compute. Boreas defaults to 2 MB.
- `MEDIA_STAGING_TTL_SECONDS`
  How long staged uploads stay in Redis before ingestion.
- `JOB_TTL_SECONDS`
  How long job metadata remains available in Redis.
- `RESULT_URL_TTL_SECONDS`
  How long the generated presigned result URL remains valid.

### Worker concurrency

- `MEDIA_WORKERS`
  Number of ingest worker processes.
- `BACKGROUND_REMOVAL_WORKERS`
  Number of compute worker processes.
- `REMBG_OMP_NUM_THREADS`
  Number of CPU threads ONNX Runtime can use inside each compute worker.

Important rule:

- effective compute pressure is roughly `BACKGROUND_REMOVAL_WORKERS * REMBG_OMP_NUM_THREADS`

If that number is too high for the machine, latency becomes spiky, uploads back up, and API responsiveness degrades.

### Rembg behavior

- `REMBG_MODEL`
  Which upstream segmentation model Boreas uses.
- `REMBG_POST_PROCESS_MASK`
  Whether rembg post-processes the predicted mask.
- `REMBG_ALPHA_MATTING`
  Whether rembg uses alpha matting for finer edges.
- `REMBG_ALPHA_MATTING_FOREGROUND_THRESHOLD`
  Foreground threshold for alpha matting.
- `REMBG_ALPHA_MATTING_BACKGROUND_THRESHOLD`
  Background threshold for alpha matting.
- `REMBG_ALPHA_MATTING_ERODE_SIZE`
  Erosion size applied during alpha matting.

### Storage and caching

- `STORAGE_ENDPOINT_URL`
- `STORAGE_ACCESS_KEY_ID`
- `STORAGE_SECRET_ACCESS_KEY`
- `STORAGE_BUCKET_NAME`
- `STORAGE_REGION`
- `U2NET_HOME`
  Directory where rembg model files are stored.

### Network and abuse controls

- `API_RATE_LIMIT`
- `UPLOAD_RATE_LIMIT`
- `CORS_ORIGINS`
- `TRUSTED_HOSTS`

### Observability

- `LOG_LEVEL`
- `LOGFIRE_SEND_TO_LOGFIRE`
- `LOGFIRE_TOKEN`
- `LOGFIRE_SERVICE_NAME`
- `LOGFIRE_ENVIRONMENT`

## Worker And Timeout Model

Current ARQ settings:

- media worker timeout: 180 seconds
- background-removal worker timeout: 300 seconds
- retries: 3 tries for each queue
- per-process max jobs: 1

Implications:

- Boreas is tuned for predictable single-job execution per worker process, not high parallelism inside one process
- larger or heavier rembg models increase the chance of compute jobs approaching the timeout window
- if you raise worker counts, you are multiplying model memory use and CPU pressure

## Model Selection Guide

Boreas uses rembg upstream models. Boreas itself does not change the model internals; it chooses which model to load and how aggressively to post-process the mask.

### Good starting choices

| Model                   | Best for                                         | Main tradeoff                                         | Recommendation                                         |
| ----------------------- | ------------------------------------------------ | ----------------------------------------------------- | ------------------------------------------------------ |
| `u2netp`                | Very small CPU boxes and throughput-first setups | Fast and light, but weaker on difficult edges         | Use only when throughput matters more than cut quality |
| `u2net`                 | General-purpose classic option                   | Heavier than `u2netp`                                 | Fine fallback if you want a known baseline             |
| `isnet-general-use`     | General product and object cutouts               | Heavier than `u2netp`, but usually better edge detail | Best default for Boreas on CPU                         |
| `u2net_human_seg`       | Human subjects and portraits                     | More specialized, less general across object types    | Use when most traffic is portraits                     |
| `birefnet-general-lite` | Better general segmentation with more detail     | Heavier cold start and lower throughput               | Good next step when `isnet-general-use` is not enough  |
| `birefnet-general`      | Higher-detail general segmentation               | Significantly heavier on CPU                          | Use only after measuring on your box                   |
| `birefnet-portrait`     | High-quality portrait cutouts                    | Specialized and heavier                               | Good for portrait-heavy workloads with enough headroom |
| `bria-rmbg`             | Strong modern background removal                 | Can be heavier and needs real measurement             | Treat as an opt-in experiment, not a blind default     |
| `sam`                   | Prompt-driven segmentation                       | Operationally different and more complex              | Not a fit for Boreas' current automatic API path       |

### Other upstream models you can test

- `u2net_cloth_seg`
- `silueta`
- `isnet-anime`
- `birefnet-dis`
- `birefnet-hrsod`
- `birefnet-cod`
- `birefnet-massive`

Those are real upstream options, but they are more niche or more expensive. Do not switch to them in production without measuring latency, memory use, and edge quality on your own traffic.

### Recommended model progression

If you are unsure, test in this order:

1. `isnet-general-use`
2. `birefnet-general-lite`
3. `birefnet-general`

If throughput drops too much, step back to:

1. `u2net`
2. `u2netp`

If the workload is mostly people, test:

1. `u2net_human_seg`
2. `birefnet-portrait`

## Edge-Quality Tuning Tradeoffs

### `REMBG_POST_PROCESS_MASK`

What it does:

- lets rembg clean the predicted mask before returning the cutout

When to keep it on:

- most general-purpose workloads
- product images
- simple studio backgrounds

Tradeoff:

- a bit more processing for cleaner masks

Recommendation:

- keep it `true` unless you have measured a reason to disable it

### `REMBG_ALPHA_MATTING`

What it does:

- spends extra work refining foreground/background separation, especially on difficult edges

When it helps:

- hair
- fur
- feathers
- semi-transparent edges
- difficult lighting transitions

Tradeoff:

- higher CPU cost
- lower throughput
- more sensitivity to threshold tuning

Recommendation:

- keep it `false` for first production launch
- only enable it when quality on complex edges is clearly not good enough

### Alpha matting thresholds

Use these only after you have decided alpha matting is worth the cost.

- higher foreground threshold is stricter about what is definitely foreground
- higher background threshold is stricter about what is definitely background
- erode size changes how aggressively the uncertain region is contracted before matting

Practical approach:

- start with the defaults already in `.env.example`
- change one variable at a time
- compare quality on a fixed evaluation set instead of random images

## Capacity Planning

### Small CPU-only VPS

Use when:

- you want the simplest launch path
- traffic is moderate
- you are okay with queueing during bursts

Settings:

- `MEDIA_WORKERS=1`
- `BACKGROUND_REMOVAL_WORKERS=1`
- `REMBG_OMP_NUM_THREADS=2`
- `REMBG_MODEL=isnet-general-use`

This is the safest first launch profile.

### Medium CPU box

Use when:

- you have already measured queue pressure
- health checks stay stable under load
- Redis and storage are not your bottlenecks

Possible next step:

- keep `MEDIA_WORKERS=1`
- raise `BACKGROUND_REMOVAL_WORKERS` to `2`
- keep `REMBG_OMP_NUM_THREADS` low enough that total compute threads still make sense for the machine

Do not raise both worker count and per-worker thread count at the same time unless you have real headroom.

### What usually breaks first

On CPU-only deployments, the first bottleneck is usually compute saturation, not FastAPI routing and not Redis.

Symptoms:

- `/health` still answers, but queue depth grows
- background-removal latency climbs sharply
- job completion time gets worse during bursts
- API remains reachable but jobs stop clearing fast enough

That is why Boreas is conservative by default.

## Coolify Runbook

### Before first deploy

1. Provision Redis.
2. Provision an S3-compatible bucket.
3. Add a lifecycle rule to delete `jobs/media/result/` after 1 hour.
4. Decide whether `/home/appuser/.u2net` will be persisted.
5. Set the environment variables from `.env.example`.

### During deployment

1. Build from the repository Dockerfile.
2. Expose port `8000`.
3. Set the health check path to `/health`.
4. Keep the startup command as the default container command.
5. Watch the logs during the first boot in case the model cache is empty and the worker is warming a new model.

### After deployment

1. Call `/health` and confirm the service reports `ok`.
2. Submit one real upload and confirm the full queue-to-result flow works.
3. Check that final result URLs are generated.
4. Confirm the prepared source object is deleted after success.
5. Confirm the result bucket lifecycle rule removes old result objects.

## Operational Tips

- Prefer SSE clients over aggressive polling.
- Keep the bucket private and serve results through presigned URLs.
- Do not disable upload validation to make the API look more permissive. That only moves the failure into the workers.
- Keep the result lifecycle short unless you intentionally want Boreas to become a file store.
- If you change `REMBG_MODEL`, expect different cold-start behavior and re-evaluate worker timeouts.
- If you raise `BACKGROUND_REMOVAL_WORKERS`, remember that each worker warms its own model session.

## Troubleshooting

### Cold starts are slow

Check:

- whether `U2NET_HOME` is persisted
- whether you switched to a heavier model
- whether the network path to model downloads is slow

### The API is healthy but jobs are slow

Check:

- compute queue depth
- `BACKGROUND_REMOVAL_WORKERS`
- `REMBG_OMP_NUM_THREADS`
- current rembg model choice

Usually this means the machine is compute-bound.

### Cut quality is not good enough

Try, in order:

1. keep `REMBG_POST_PROCESS_MASK=true`
2. switch from `u2netp` to `isnet-general-use`
3. switch from `isnet-general-use` to `birefnet-general-lite`
4. enable `REMBG_ALPHA_MATTING=true` only if edge quality is still the problem

### Throughput is not good enough

Try, in order:

1. keep `BACKGROUND_REMOVAL_WORKERS=1` and reduce model cost first
2. switch from a heavier model to `isnet-general-use` or `u2net`
3. if needed, switch to `u2netp`
4. only then consider adding another compute worker

## Suggested Documentation Policy For OSS Users

When you publish deployment examples for Boreas, document:

- the machine class you tested on
- the rembg model used
- whether alpha matting was enabled
- the worker counts
- the ONNX thread count
- the median and tail job completion times you observed

Without that context, quality and throughput claims are not comparable.
