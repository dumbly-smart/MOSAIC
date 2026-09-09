# MOSAIC officer workspace

The dashboard calls the FastAPI service only through `NEXT_PUBLIC_MOSAIC_API_URL`.
It stores only the Supabase access token in browser session storage. Do not put
Supabase secrets, database credentials, or storage credentials in this folder.

## Local connected demo

1. Configure the API and create a synthetic local officer account using
   `docs/supabase-api-setup.md` from the repository root.
2. In the repository root, create the ignored API virtual environment and install
   dependencies:

   ```sh
   python -m venv .venv
   .venv/bin/python -m pip install -r requirements-api.txt
   ```

3. Start the API with its server-only environment configuration:

   ```sh
   .venv/bin/uvicorn services.api.app.main:app --reload --host 127.0.0.1 --port 8000
   ```

4. Copy `.env.example` to a local uncommitted `.env.local`, then start the web app:

   ```sh
   npm install --allow-remote=all
   npm run dev
   ```

Open `http://127.0.0.1:3000/government`. The flow accepts PDF documents only,
creates a case, uploads one tender and one or more bidder PDFs, starts a run, and
polls the documented run endpoint. MOSAIC is decision support only: final
qualification, disqualification, and clarification decisions remain with a
Procurement Officer. This demo uses local/mock-sandbox services only.

## Checks

```sh
npm run typecheck
npm run lint
npm test
npm run build
```
