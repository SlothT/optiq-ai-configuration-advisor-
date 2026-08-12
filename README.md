# Optiq

AI Configuration Advisor — analyze prompts, benchmark models, and get constraint-aware recommendations. Experiments are tracked in MLflow.

**Docs:** [PRD](./Optiq_PRD_v1.md) · [Build Planner](./planner.md)

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Node.js 20+](https://nodejs.org/) (for local frontend dev without Docker)
- [Python 3.11+](https://www.python.org/) (for local backend dev without Docker)

Optional for open-source model benchmarking:

- [Ollama](https://ollama.com/) running locally (`ollama pull llama3.2`)

## Quick start (Docker)

1. Copy environment file and generate a Fernet key:

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste output into FERNET_KEY in .env
```

2. Start all services:

```bash
cd infra
docker compose up --build
```

3. Open the apps:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| MLflow UI | http://localhost:5000 |
| Health check | http://localhost:8000/health |

## Project structure

```
optiq/
├── backend/          # FastAPI API + workers
├── frontend/         # Next.js App Router UI
├── infra/            # Docker Compose
├── mlflow/           # MLflow artifact notes
├── docs/             # Documentation
├── Optiq_PRD_v1.md
└── planner.md
```

## Local development (without Docker)

**Backend:**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Ensure Postgres, Redis, and MLflow are running (via Docker Compose infra services only):

```bash
cd infra
docker compose up postgres redis mlflow -d
```

## Model registry

Models and pricing live in `backend/app/config/models.yaml`. Add a model by editing the YAML — no code changes required for new entries.

## Phase 0 status

Phase 0 scaffolds repo structure, Docker infra, backend health check, frontend shell, and model registry loader. Feature work starts in Phase 1 (auth + prompt analyzer).

## License

Private — Toshi Srivastava
