<p align="center">
  <img src="assets/logo.png" alt="Boreas" width="300" />
</p>

# Boreas

Boreas is a FastAPI background-removal backend built for a narrow job: accept uploads quickly, push heavy work off-request, and stay understandable under load.

Architecture rationale lives in [docs/system-design.md](docs/system-design.md). Contributor rules live in [CONTRIBUTING.md](CONTRIBUTING.md).
Deployment and model-tuning guidance lives in [docs/deployment-guide.md](docs/deployment-guide.md).

## What It Does

- `POST /v1/media/jobs` accepts an image and returns a job id immediately.
- `GET /v1/media/jobs/{job_id}` returns job state and a result URL when ready.
- `GET /v1/media/jobs/{job_id}/stream` streams job updates through SSE.
- `/health` exposes public runtime health, queue depth, and staging metrics.

## Runtime Shape

- `app/features/media`: public upload API, validation, staging, normalization, ingest worker
- `app/features/rembg`: background-removal compute and compute worker
- `app/features/health`: status and health endpoints
- `app/core`: bootstrap, middleware, config, Redis, ARQ, shared storage primitives

The public request path stays thin. The queue carries job ids, not images. Redis stages uploads briefly, object storage holds prepared sources and final results, and the workers own the expensive work.

## Why It Is Built This Way

- the API should return fast even when processing is expensive
- input normalization and background removal are different responsibilities
- Redis is good for short-lived state handoff, not long-lived file storage
- object lifecycle has to be explicit or it turns into cost and cleanup drift
- contributor ownership should be obvious from the folder layout

The longer explanation is in [docs/system-design.md](docs/system-design.md).

## Abuse Protection

By default Boreas allows `5/minute` per client IP for API reads and uploads.

That is intentionally conservative because uploads and rembg work are expensive. Both limits are environment-configurable through `API_RATE_LIMIT` and `UPLOAD_RATE_LIMIT`.

If clients want frequent job updates, SSE is the intended path. Repeated polling will hit the limit faster and costs more.

## Object Lifecycle

- staged uploads expire from Redis quickly
- job metadata expires through Redis TTL
- prepared source objects should be deleted immediately after successful compute
- final result objects should expire after one hour through an object storage lifecycle rule

The app assumes the bucket lifecycle matches the one-hour result retention policy.

## Configuration

Copy `.env.example` to `.env` and set the required values.

Important settings:

- `REDIS_URL`
- `API_RATE_LIMIT`
- `UPLOAD_RATE_LIMIT`
- `JOB_TTL_SECONDS`
- `RESULT_URL_TTL_SECONDS`
- `MEDIA_SOURCE_MAX_BYTES`
- `MEDIA_STAGING_TTL_SECONDS`
- `MEDIA_WORKERS`
- `BACKGROUND_REMOVAL_WORKERS`
- `STORAGE_ENDPOINT_URL`
- `STORAGE_ACCESS_KEY_ID`
- `STORAGE_SECRET_ACCESS_KEY`
- `STORAGE_BUCKET_NAME`
- `REMBG_MODEL`
- `REMBG_POST_PROCESS_MASK`
- `REMBG_ALPHA_MATTING`
- `REMBG_ALPHA_MATTING_FOREGROUND_THRESHOLD`
- `REMBG_ALPHA_MATTING_BACKGROUND_THRESHOLD`
- `REMBG_ALPHA_MATTING_ERODE_SIZE`
- `REMBG_OMP_NUM_THREADS`
- `LOG_LEVEL`
- `LOGFIRE_SEND_TO_LOGFIRE`
- `LOGFIRE_TOKEN`
- `LOGFIRE_SERVICE_NAME`
- `LOGFIRE_ENVIRONMENT`

If `LOGFIRE_SEND_TO_LOGFIRE=false`, Boreas keeps logs local even when Logfire is installed.

## Coolify On Hostinger KVM2

For a small CPU-only VPS, keep the deployment conservative:

- keep `MEDIA_WORKERS=1`
- keep `BACKGROUND_REMOVAL_WORKERS=1`
- use `REMBG_MODEL=isnet-general-use` for a better edge-quality and latency balance than `u2netp`
- keep `REMBG_POST_PROCESS_MASK=true`
- leave `REMBG_ALPHA_MATTING=false` by default and only enable it if you can afford lower throughput for finer edges like hair or fur
- set `REMBG_OMP_NUM_THREADS=2` so ONNX does not oversubscribe the VM

If Coolify lets you mount persistent storage, mount `U2NET_HOME` so model downloads survive redeploys instead of re-downloading on the next cold worker start.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./start.sh
```

## VS Code Launching

Use [.vscode/launch.json](.vscode/launch.json) for local debugging.

It includes:

- `Boreas API`
- `Boreas Media Worker`
- `Boreas Background Removal Worker`
- `Boreas API + Workers` compound launch

That gives you a clean way to debug the API and both worker processes without relying on the shell script.

## Validation

Run the current v1 test surface with:

```bash
./.venv/bin/python -m unittest discover -s tests
```

The suite currently covers:

- ingest lifecycle behavior
- source deletion after compute
- one-hour result URL assumptions
- health metrics payload
