# 31stFile Tax Position Advisor

Preliminary Indian direct-tax authority research with an explicit non-advisory disclaimer.

## Run & operate

- `pnpm --filter @workspace/api-server run dev` — FastAPI at the API artifact's assigned port (currently 8080).
- `pnpm --filter @workspace/tax-position-advisor run dev` — React/Vite advisor.
- `pnpm run typecheck` — typecheck the workspace.
- `pnpm --filter @workspace/api-spec run codegen` — regenerate React Query hooks and Zod schemas from `lib/api-spec/openapi.yaml`.
- `uv run --project . alembic upgrade head` — create the PostgreSQL schema.
- `uv run --project . python scripts/seed.py` — import the supplied official data files.
- `uv run --project . python scripts/validate_map.py` — list sections without an imported correspondence.

Set `NEON_DATABASE_URL`, `KANOON_API_TOKEN`, `ADMIN_PASSWORD`, and `SESSION_SECRET` as server-side environment values. Use `NEON_DATABASE_URL` for the external Neon connection in every environment; the API intentionally ignores `DATABASE_URL` so it cannot point at Replit-managed storage. The admin password is only used to establish a short-lived HTTP-only session cookie and must never be persisted in browser storage. `GEMINI_API_KEY` is reserved for later prompts and is unused here.

## Stack

- React, Vite, TypeScript, generated Orval client
- FastAPI, SQLAlchemy, Alembic, PostgreSQL with pgvector
- Indian Kanoon REST API for case-law search and document retrieval
- External PostgreSQL is the system of record; no local database fallback is used. `DATABASE_URL` is ignored; only `NEON_DATABASE_URL` configures the database.

## Product boundaries

- This prompt implements section selection, approved issues, official mapping display, anonymized facts, retrieval, circular listing, password-protected curation, and retrieved-authority debugging.
- It does not implement AI legal analysis, scoring, drafting, human review, or export. Those are later prompts.
- No case, citation, mapping, or circular may be invented. The section and circular seed files stay empty until official data is supplied. The two requested issue labels are seeded only when their 1961 section data is present; 2025 links come only from imported official mappings.
- Search uses the selected issue keywords and all mapped section numbers. Kanoon uses its documented `ANDD` / `ORR` operators; the high-court category is queried with the API's `highcourts` doctype filter.
- Cases are cached by Kanoon document ID before document fetches. Case treatment is left unknown unless supplied by verified source data.
- Facts are stored in the analyses table with retrieved results. Users must anonymize client names before submission.

## Source-of-truth files

- API contract: `lib/api-spec/openapi.yaml`
- Data model: `backend/models.py`
- Migrations: `backend/migrations/`
- Search/cache behavior: `backend/services/search.py`
- Official seed templates and user-provided issue labels: `data/`
- Browser app: `artifacts/tax-position-advisor/`

## Gotchas

- Run Alembic before seed scripts or data endpoints.
- Configure the external Neon URL in `NEON_DATABASE_URL`; the platform's `DATABASE_URL` is ignored so it cannot silently choose a different database.
- The Kanoon API uses `highcourts` (plural) as its high-court filter. Its search operators are case-sensitive `ANDD` and `ORR`.
- The external database must have permission to install/use the PostgreSQL `vector` extension.