# Supabase and FastAPI setup

This backend uses Supabase for managed PostgreSQL, Auth, private file storage and pgvector.
FastAPI authenticates each request, owns the upload workflow and calls the verification core.

## 1. Create and initialize Supabase

1. Create a Supabase project and keep its database password private.
2. Open the Supabase SQL Editor.
3. Run `supabase/migrations/202609080001_initial_backend.sql` once.
4. In Authentication, create a synthetic demo officer account. Do not use real bidder data.

The migration creates the private `mosaic-documents` bucket, the case/document/run/finding/audit
tables, RLS policies, an append-only audit trigger, and a 1024-dimensional HNSW pgvector index
for BGE-M3 embeddings.

## 2. Configure the API

Copy `.env.example` to `.env`, then fill in values from the Supabase dashboard. Keep `.env`
uncommitted. Use the direct database connection or session pooler connection string; append
`?sslmode=require` when it is not already present.

The publishable key may be used by a browser. `MOSAIC_SUPABASE_SECRET_KEY` and
`MOSAIC_DATABASE_URL` are server-only and must never use a `NEXT_PUBLIC_` prefix.

Install and launch from the repository root:

```powershell
uv pip install --cache-dir .\.uv-cache --python .\.venv\Scripts\python.exe -r requirements-api.txt
.\run-api.ps1
```

Open `http://127.0.0.1:8000/docs`.

## 3. Test through Swagger

1. Call `POST /v1/auth/login` with the synthetic officer email and password.
2. Copy `access_token` from the response.
3. Select **Authorize** and paste the access token.
4. Call `GET /v1/me`.
5. Call `POST /v1/cases` and copy the returned case ID.
6. Call `POST /v1/cases/{case_id}/documents` twice: once with `kind=tender` and once with
   `kind=bidder`. Select a PDF for each request.
7. Call `GET /v1/cases/{case_id}/documents` and confirm both stored documents are listed.
8. Call `POST /v1/cases/{case_id}/verification-runs`. Enable `force_ocr_bidder` when the bidder
   PDFs are scanned images.
9. Copy the run ID and poll `GET /v1/verification-runs/{run_id}`. The status moves through
   `queued`, `running`, and then `completed`, `needs_manual_review`, or `failed`. A successful
   response includes the complete grounded report in `result`.

Uploads are limited to 50 MiB by default. The API checks the media type, size, and PDF header,
stores the original in the private bucket, records its SHA-256 digest, and removes the object if
the metadata transaction fails. The verification background task downloads the private files,
merges multiple bidder PDFs, runs Docling/RapidOCR, stores and searches BGE-M3 embeddings in
Supabase pgvector, compares the evidence with local Qwen3-VL, and persists the criteria, findings,
score and report in PostgreSQL. Keep the API process and Ollama running until the job completes.
