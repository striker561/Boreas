# Contributing to Boreas

Read [docs/system-design.md](docs/system-design.md) before making architectural changes. It documents the current intent and the tradeoffs behind it.

Boreas is intentionally small. Keep changes explicit, measurable, and easy to reason about under load.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./start.sh
```

For VS Code debugging, use [.vscode/launch.json](.vscode/launch.json).

## Ownership Rules

- `app/features/media` owns the public media API, upload validation, staging, normalization, and ingest worker.
- `app/features/rembg` owns background-removal compute only.
- `app/features/health` owns `/` and `/health`.
- `app/core` owns bootstrap, middleware, shared config, Redis, ARQ, and shared storage primitives.

If a module crosses those lines, stop and fix the ownership instead of adding another wrapper around it.

## Performance Rules

- keep the request path short
- keep queue payloads small and identifier-based
- keep staged uploads short-lived
- prefer SSE over aggressive status polling
- reuse warmed worker dependencies where possible
- do not add queue hops unless there is a concrete runtime reason

## Abuse And Safety Rules

- default rate limits are conservative on purpose
- do not loosen them in code just because local development feels slower
- keep upload validation at the edge
- preserve explicit object cleanup semantics

If you change retention or cleanup behavior, update the docs and the health payload if operators need that visibility.

## Logging Rules

Logs should answer:

- what request or job failed
- where it failed
- whether the failure is transient or permanent

Do not add noisy logs just because a code path exists. Add logs at state transitions, failures, and operational boundaries.

## Before Opening A Change

Make sure your change still preserves this flow:

1. API stages the upload and creates the job quickly.
2. Media worker uploads the normalized source to object storage.
3. Background-removal worker processes the stored source and uploads the final result.
4. Prepared source objects are deleted after successful compute.
5. Final result objects expire through storage lifecycle policy.

## Review Standard

Prefer:

- simpler control flow
- fewer abstractions
- clearer feature ownership
- explicit cleanup
- tighter docs when architecture changes

If a helper exists only for hypothetical future use, delete it.# Contributing to Boreas

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
