# Boreas Integration Guide

This document is for developers who want to integrate Boreas into an existing app without reverse-engineering the API contract first.

If Boreas saves you time, star the repo: <https://github.com/striker561/Boreas>

## What Boreas Does

Boreas is an async background-removal service.

Your app uploads an image to Boreas.
Boreas stages the upload, runs image preparation and background removal in the background, and returns a short-lived URL for the final PNG when the job is complete.

The simplest mental model is:

1. your app uploads an image
2. Boreas returns a `job_id`
3. Boreas moves the job through background states
4. your app polls job status or listens with SSE
5. your app downloads or redirects to the final PNG URL

## Base Paths

The public paths you usually need are:

- `POST /v1/media/jobs`
  Create a background-removal job from a multipart upload.
- `GET /v1/media/jobs/{job_id}`
  Read the current job state and final result URL when available.
- `GET /v1/media/jobs/{job_id}/stream`
  Subscribe to raw job snapshots with Server-Sent Events.
- `GET /`
  Lightweight reachability endpoint. Useful for operators, not normal product flow.
- `GET /health`
  Public operational report. Useful for diagnostics, not normal app flow.

Treat `job_id` as an opaque string. It currently looks like a UUID, but clients should not build logic around its format.

## API Contract

Boreas uses two top-level JSON envelopes.

Successful JSON responses use:

```json
{
  "msg": "Success",
  "data": {}
}
```

Error JSON responses use:

```json
{
  "msg": "Something went wrong",
  "errors": []
}
```

Do not expect:

- a top-level `success` boolean
- a top-level `message` field
- SSE events to use the normal success envelope

The SSE endpoint is different. Its `data:` payload is the raw serialized job snapshot, not `{ "msg": ..., "data": ... }`.

## Schemas You Should Model

TypeScript example interfaces that match the app today:

```typescript
export type JobStatus =
  | "queued"
  | "preparing"
  | "processing"
  | "complete"
  | "failed";

export interface APIResponse<T> {
  msg: string;
  data: T | null;
}

export interface ValidationIssue {
  loc: string;
  msg: string;
  type: string;
}

export interface APIErrorResponse {
  msg: string;
  errors: ValidationIssue[] | Record<string, unknown> | [];
}

export interface MediaJobQueuedResponse {
  job_id: string;
  status: "queued";
}

export interface MediaJobResponse {
  job_id: string;
  status: JobStatus;
  result_url: string | null;
  error: string | null;
  attempts: number;
  created_at: string;
  updated_at: string;
}
```

Important field behavior:

- `status` can be `queued`, `preparing`, `processing`, `complete`, or `failed`
- `result_url` is only populated when `status === "complete"`
- `error` is usually only populated when `status === "failed"`
- `attempts` reflects processing attempts, not frontend poll count
- `created_at` and `updated_at` are ISO-8601 timestamps serialized from UTC datetimes
- the final output is always a PNG, even if the uploaded file was JPEG or WEBP

## Recommended Integration Pattern

For most teams, the cleanest setup is:

1. keep Boreas as a separate internal service
2. let your backend call Boreas server-to-server
3. store the returned `job_id` in your own domain record
4. expose Boreas job state to your frontend through your own API if you want a unified client contract

That keeps Boreas isolated as an image-processing worker system instead of leaking its internals into your product code.

## Create Job Request

Send a multipart upload with the form field name `file`.

Current request constraints:

- accepted image types: PNG, JPEG, WEBP
- HTTP request size limit: 10 MB
- maximum image dimensions: `4000x4000`
- Boreas may internally recompress or resize the prepared source image so the worker input fits the configured 2 MB source budget

Example with `curl`:

```bash
curl -X POST "https://boreas.your-domain.com/v1/media/jobs" \
  -F "file=@/absolute/path/to/image.png"
```

Successful response:

```json
{
  "msg": "Media job queued",
  "data": {
    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "queued"
  }
}
```

The API returns HTTP `201` for successful job creation.

## Get Job Request

Use the job id to query status:

```bash
curl "https://boreas.your-domain.com/v1/media/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6"
```

Typical successful response:

```json
{
  "msg": "Success",
  "data": {
    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "processing",
    "result_url": null,
    "error": null,
    "attempts": 1,
    "created_at": "2026-05-08T20:00:00Z",
    "updated_at": "2026-05-08T20:00:12Z"
  }
}
```

Terminal complete response example:

```json
{
  "msg": "Success",
  "data": {
    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "complete",
    "result_url": "https://example.r2.cloudflarestorage.com/jobs/media/result/job.png?...",
    "error": null,
    "attempts": 1,
    "created_at": "2026-05-08T20:00:00Z",
    "updated_at": "2026-05-08T20:00:24Z"
  }
}
```

Status transitions you should handle:

- `queued`: Boreas accepted the upload and enqueued ingest
- `preparing`: Boreas is normalizing and uploading the prepared worker source
- `processing`: rembg compute is running
- `complete`: final PNG is ready and `result_url` is available
- `failed`: the job is terminal and `error` explains why

## Polling Strategy

Poll the job endpoint if SSE is not practical.

Recommended polling behavior:

- poll every 2 to 5 seconds, not aggressively
- stop polling on `complete` or `failed`
- expect `404` if the job has expired from Redis later in its lifecycle
- copy the result into your own permanent storage if your product needs long retention

Do not treat `result_url` as permanent. Boreas is designed around short-lived result access.

## SSE Stream Contract

If you want a faster UX than polling, subscribe to the stream endpoint.

The response content type is `text/event-stream`.
Each SSE event contains the raw job snapshot in the `data:` field.

Example event payload:

```text
data: {"job_id":"3fa85f64-5717-4562-b3fc-2c963f66afa6","status":"queued","result_url":null,"error":null,"attempts":0,"created_at":"2026-05-08T20:00:00Z","updated_at":"2026-05-08T20:00:00Z"}

```

Important SSE behavior:

- the payload is a raw `MediaJobResponse`, not the normal API envelope
- Boreas only emits when the serialized job snapshot changes
- the stream closes once the job reaches `complete` or `failed`

Browser example:

```javascript
const stream = new EventSource(
  `https://boreas.your-domain.com/v1/media/jobs/${jobId}/stream`,
);

stream.onmessage = (event) => {
  const job = JSON.parse(event.data);
  console.log(job);

  if (job.status === "complete" || job.status === "failed") {
    stream.close();
  }
};
```

Use SSE when:

- you want live progress updates in a browser UI
- you want to avoid aggressive polling
- you are processing many user uploads and want lower request churn

## Backend Example

Python example with `httpx` that parses the real response contract:

```python
import httpx


async def create_boreas_job(file_bytes: bytes, filename: str) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://boreas.your-domain.com/v1/media/jobs",
            files={"file": (filename, file_bytes)},
        )
        response.raise_for_status()
        payload = response.json()
        return payload["data"]


async def get_boreas_job(job_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://boreas.your-domain.com/v1/media/jobs/{job_id}"
        )
        response.raise_for_status()
        payload = response.json()
        return payload["data"]
```

If you want stronger handling, branch on Boreas error envelopes before raising:

```python
async def parse_boreas_response(response: httpx.Response) -> dict:
    payload = response.json()
    if response.is_error:
        raise RuntimeError(payload.get("msg", "Boreas request failed"))
    return payload["data"]
```

## Frontend Example

TypeScript example with `fetch` that matches the actual schema:

```typescript
type JobStatus = "queued" | "preparing" | "processing" | "complete" | "failed";

interface APIResponse<T> {
  msg: string;
  data: T | null;
}

interface ValidationIssue {
  loc: string;
  msg: string;
  type: string;
}

interface APIErrorResponse {
  msg: string;
  errors: ValidationIssue[] | Record<string, unknown> | [];
}

interface MediaJobQueuedResponse {
  job_id: string;
  status: "queued";
}

interface MediaJobResponse {
  job_id: string;
  status: JobStatus;
  result_url: string | null;
  error: string | null;
  attempts: number;
  created_at: string;
  updated_at: string;
}

export async function createBoreasJob(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("https://boreas.your-domain.com/v1/media/jobs", {
    method: "POST",
    body: formData,
  });

  const payload = (await response.json()) as
    | APIResponse<MediaJobQueuedResponse>
    | APIErrorResponse;

  if (!response.ok) {
    throw new Error(
      (payload as APIErrorResponse).msg ||
        `Boreas upload failed: ${response.status}`,
    );
  }

  return (payload as APIResponse<MediaJobQueuedResponse>).data;
}

export async function getBoreasJob(jobId: string) {
  const response = await fetch(
    `https://boreas.your-domain.com/v1/media/jobs/${jobId}`,
  );
  const payload = (await response.json()) as
    | APIResponse<MediaJobResponse>
    | APIErrorResponse;

  if (!response.ok) {
    throw new Error(
      (payload as APIErrorResponse).msg ||
        `Boreas job lookup failed: ${response.status}`,
    );
  }

  return (payload as APIResponse<MediaJobResponse>).data;
}
```

## What Your App Should Persist

Persist at least:

- your own resource id
- Boreas `job_id`
- Boreas status snapshot
- Boreas `attempts`
- Boreas `error`
- Boreas `created_at` and `updated_at`
- final result URL only as a short-lived convenience, not as permanent state

Do not treat Boreas as your system of record.
Treat it as an image-processing subsystem.

## Error Shapes And Edge Cases

These are the public failure cases developers should plan for:

- missing multipart file field
  Boreas returns `422` with `{"msg":"Validation failed","errors":[{"loc":"body.file",...}]}`.
- empty upload body
  Boreas returns `400` with `{"msg":"Upload is empty","errors":[]}`.
- invalid image bytes
  Boreas returns `400` with `{"msg":"Upload must be a valid PNG, JPEG, or WEBP image","errors":[]}`.
- image too large for the HTTP request limit
  Boreas returns `413` with `{"msg":"Upload exceeds the maximum request size","errors":[]}`.
- image dimensions above `4000x4000`
  Boreas returns `400` with a friendly dimension message explaining the limit.
- unsupported media type after content sniffing
  Boreas returns `400` with a validation-style message such as `Only PNG, JPEG, and WEBP images are supported`.
- queue or staging failure during job creation
  Boreas returns `503` with `{"msg":"Unable to enqueue media job","errors":[]}`.
- polling or streaming a missing or expired job id
  Boreas returns `404` with `{"msg":"Job not found","errors":[]}`.
- rate limiting
  Boreas returns `429` with `{"msg":"Too many requests. Please slow down and try again later.","errors":[]}`.
- job fails after acceptance
  The request itself already succeeded, but later polling or SSE shows `status: "failed"` and `error` explains the failure.

Recommended behavior:

1. show upload validation messages directly to the user
2. parse `errors` when Boreas returns `422` and bind them to form fields where possible
3. retry transient `503` responses with backoff
4. do not blindly retry permanent `400`, `404`, `413`, or `422` responses unchanged
5. treat `status: "failed"` as a business-visible outcome, not as an invisible background detail

## Integration Edge Cases That Matter

- Boreas may accept an upload and still fail the job later if the staged upload expires before ingestion or if processing fails.
- Boreas may internally normalize the source image into JPEG, WEBP, or PNG before compute begins. Clients should not assume the worker input matches the original upload format.
- The final downloadable result is always PNG.
- `result_url` is short-lived. If users need durable access, your app should copy the PNG into its own storage.
- If you poll too aggressively, you can hit the Boreas API rate limit. Prefer SSE for user-facing progress.
- Every response includes `X-Request-ID`, which is useful for support logs and tracing request-specific failures through Boreas.

## Production Integration Notes

- Keep Boreas behind your own domain, gateway, or internal network boundary.
- If your app exposes Boreas directly to browsers, make sure `CORS_ORIGINS` matches your frontend origins.
- Boreas result URLs are intentionally short-lived. If users need long-term storage, copy the final image into your own permanent storage.
- Boreas is optimized for background processing, so build your UX around asynchronous completion rather than synchronous “upload and wait” behavior.
- Do not build normal client flows around `/health`. Use the media endpoints for product behavior and reserve `/health` for diagnostics.

## Deployment Expectations For Integrators

If you are integrating against a self-hosted Boreas instance, the operator needs:

- Redis
- S3-compatible object storage
- a persistent `U2NET_HOME` volume if they want rembg model downloads to survive redeploys

See [deployment-guide.md](deployment-guide.md) for operator-facing deployment details.

## Suggested Product UX

Good UX usually looks like this:

1. user uploads an image
2. your app immediately shows a queued or processing state
3. your app switches to SSE or short polling
4. your app swaps in the transparent PNG when ready
5. your app offers download, replace, or continue-editing actions

That matches how Boreas is built instead of forcing users to wait on a synchronous request.
For operator-facing deployment details, see [deployment-guide.md](deployment-guide.md).
