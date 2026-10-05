# Contributing

Use a Linux or WSL2 checkout with Python 3.11+ and Node.js 20+ (Node 22 in `.nvmrc`). No Docker or provider account is required for routine development.

```bash
./scripts/optiq setup
./scripts/optiq dev
./scripts/optiq check --build
```

Setup preserves existing secrets/data. Rerun it after pulling requirement, package-lock, or Alembic changes. To update frontend dependencies, update `package.json` and `package-lock.json` together. Pin Python direct dependencies in the appropriate core, dev, or extras requirements file. Heavy optional packages belong in extras and must be imported lazily.

Tests must avoid live providers and external billing. Add meaningful tests for behavior changes, including the API boundary when relevant. Use the existing native integration test as a reference for mocked adapters and temporary database/mail storage.

For schema changes, add an Alembic migration and verify it against both SQLite and Postgres. Use `./scripts/optiq compose up --build` for Postgres/RQ integration work; CI also checks Postgres upgrades. Mailpit exposes Compose verification messages at http://localhost:8025.

Keep `.env`, `.local/`, provider keys, and verification messages out of commits. Provider credentials are encrypted using the local Fernet key, so preserve that key when retaining a database.

For issues/PRs, include the behavior, reproduction steps, relevant runtime versions, and checks run. Do not include secrets or complete environment dumps. `./scripts/optiq doctor` prints configuration modes and database connectivity without credential values.

Local thread jobs are interrupted by API reload/restart. Use Redis/RQ when validating job durability. SQLite is not a substitute for testing database-specific or high-concurrency changes against Postgres.
