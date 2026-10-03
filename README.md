# 31stFile Tax Position Advisor

This app retrieves Indian direct-tax sections, official 1961/2025 section correspondences, Indian Kanoon cases, and imported circulars for preliminary review. It is not a certified tax advisory.

## Configure

1. Set `NEON_DATABASE_URL` to the external Neon PostgreSQL connection string. The app deliberately ignores `DATABASE_URL` so a platform-managed database cannot be selected accidentally. Use `NEON_DATABASE_URL` in local and Docker environments too.
2. Set `KANOON_API_TOKEN`, `ADMIN_PASSWORD`, and `SESSION_SECRET` as server-side secrets. Never use a `VITE_` prefix for secrets. The admin password is only used to create a short-lived HTTP-only session cookie; it is not retained in browser storage.
3. Copy `.env.example` to `.env` for local development. It contains variable names only.
4. Install the Python dependencies with `uv sync`.
5. Apply the schema and load any official data:

   ```sh
   uv run --project . alembic upgrade head
   uv run --project . python scripts/seed.py
   uv run --project . python scripts/validate_map.py
   ```

The database uses PostgreSQL and the `vector` extension. The initial migration creates the extension and schema. Ensure the Neon role can create/use that extension before applying it.

## Run in Replit

The `artifacts/api-server` workflow runs FastAPI. The `artifacts/tax-position-advisor` workflow runs the React/Vite app. The web artifact calls the API under `/api`.

For Replit, configure `NEON_DATABASE_URL` to keep the app on the requested external Neon database rather than platform-managed storage. Start the API and web workflows after setting the environment values and applying migrations.

## Run locally

```sh
uv run --project . python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8080
```

API health check: `http://localhost:8080/api/healthz`. API docs: `http://localhost:8080/api/docs`.

## Docker

Build and run the API container:

```sh
docker build -t 31stfile-tax-position-advisor .
docker run --rm -p 8000:8000 \
  -e NEON_DATABASE_URL="$NEON_DATABASE_URL" \
  -e KANOON_API_TOKEN="$KANOON_API_TOKEN" \
  -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  -e SESSION_SECRET="$SESSION_SECRET" \
  31stfile-tax-position-advisor
```

Run migrations and seed scripts from a one-off container or the host after setting the same database URL:

```sh
docker run --rm --env-file .env 31stfile-tax-position-advisor \
  alembic -c alembic.ini upgrade head
docker run --rm --env-file .env 31stfile-tax-position-advisor \
  python scripts/seed.py
```

## Official seed data

`data/sections_old.json`, `data/sections_new.json`, `data/section_map.json`, and `data/circulars_seed.json` are empty until official source data is supplied. Do not fill these with generated or guessed legal content.

`data/issues_seed.json` contains only the two requested issues, “Software as royalty” and “FTS under DTAA,” with those exact labels as their initial search keywords. The seed script attaches them to 1961 section 9(1)(vi) and to a 2025 section only when that correspondence is present in the supplied official mapping file.

## Scope and privacy

- The search page asks users to anonymize client names. Submitted facts and retrieval results are persisted in `analyses`.
- Kanoon searches run separately for the Supreme Court, high courts, and ITAT. Each search returns up to 10 documents per category and is capped at 25 unique documents per request.
- Cached case documents are checked before `/doc/{id}/` calls. The default call ceiling is 28 API calls per request (three searches plus up to 25 document fetches).
- Search requests and API logs do not include the submitted facts. Search queries are returned to the debug view.
- Analysis, position scoring, drafting, review workflows, and export are intentionally outside this foundation.