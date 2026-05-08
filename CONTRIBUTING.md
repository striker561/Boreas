# Contributing to Boreas

Thanks for contributing.

Boreas is intentionally small. Keep changes narrow, explicit, and easy to reason about under load.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./start.sh
```

## Architecture Rules

Use these boundaries consistently:

- `app/features/media`
  Public API, upload validation, staging, normalization, and media ingest worker.
- `app/features/rembg`
  Background-removal compute logic only.
- `app/core`
  App bootstrapping, middleware, shared infrastructure, config, worker registry, and shared media persistence.

Do not reintroduce compatibility wrapper packages or ambiguous “service” layers that hide ownership.

## Performance Expectations

Boreas is expected to handle high traffic on small hardware.

When changing the code:

- keep the HTTP path thin
- avoid moving large byte payloads through the queue
- reuse warmed worker dependencies from `ctx` when possible
- avoid repeated object construction in hot worker paths
- prefer short-lived staged data and explicit cleanup

## Naming Guidance

- Use `media` for the public ingest/orchestration domain.
- Use `background removal` for the compute stage.
- Keep `rembg` limited to the internal library integration and model configuration.

If a name leaks low-level implementation details into the public layer, rename it.

## Validation Guidance

Prefer strong validation close to the edges:

- use Pydantic models for structured payload checks
- validate uploaded media dimensions and content type before queueing
- enforce the normalized source size limit before compute begins

## Before Opening a Change

Make sure your change still preserves this flow:

1. API stages upload and creates a job quickly.
2. Media worker uploads the normalized source to object storage.
3. Background-removal worker processes the stored source and uploads the final result.
4. Prepared source objects are deleted after compute, and final result objects expire after one hour through storage lifecycle policy.

## Review Standard

Changes should favor:

- simpler control flow
- fewer cross-feature dependencies
- predictable retry behavior
- explicit cleanup on failure
- minimal public API churn unless the API is getting clearer

If a change makes the boundaries fuzzier or adds queue hops without a concrete benefit, it should probably be reworked.
