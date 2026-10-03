---
name: External database migration URL handling
description: Preserve encoded PostgreSQL credentials when building migration engines.
---

Keep externally supplied PostgreSQL connection strings as parsed URL objects when creating migration engines. Avoid converting them to config strings and hand-escaping `%` for config interpolation; that can leave credentials altered.

**Why:** A direct Neon connection succeeded while the Alembic config path failed authentication; a sanitized test with percent-encoded dummy credentials reproduced the mismatch.

**How to apply:** When an external database secret includes URL-encoded credentials, pass a parsed URL directly to the SQLAlchemy engine rather than routing it through config interpolation. Never print the URL.