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
- `app/features/tasks` owns hourly ARQ cron cleanup (Redis job state + orphan S3 objects).
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

If you change retention or cleanup behavior, update the docs.

## Logging Rules

Logs should answer:

- what request or job failed
- where it failed
- whether the failure is transient or permanent

Do not add noisy logs just because a code path exists. Add logs at state transitions, failures, and operational boundaries.

## Naming Guidance

- Use `media` for the public ingest/orchestration domain.
- Use `background removal` for the compute stage.
- Use `tasks` for scheduled background maintenance (cron jobs).
- Keep `rembg` limited to the internal library integration and model configuration.

## Before Opening A Change

Make sure your change still preserves this flow:

1. API stages the upload and creates the job quickly.
2. Media worker uploads the normalized source to object storage.
3. Background-removal worker processes the stored source and uploads the final result.
4. Prepared source objects are deleted after successful compute.
5. Final result objects expire through storage lifecycle policy; the hourly tasks cron sweeps orphans.

## Review Standard

Prefer:

- simpler control flow
- fewer abstractions
- clearer feature ownership
- explicit cleanup
- tighter docs when architecture changes

If a helper exists only for hypothetical future use, delete it.
