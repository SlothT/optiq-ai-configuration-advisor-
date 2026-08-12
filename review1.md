# Optiq Review 1

## Where the code starts

### Backend entry point

The backend starts in [backend/app/main.py](backend/app/main.py). That file creates the FastAPI app, applies CORS, and registers the API routers:

- auth
- projects
- providers
- prompts
- experiments
- recommendations
- health

### Frontend entry point

The UI starts in [frontend/app/layout.tsx](frontend/app/layout.tsx). That file defines the shared shell:

- top navigation
- page layout
- global styles
- app wrapper for the frontend routes

The home page is [frontend/app/page.tsx](frontend/app/page.tsx), and the main feature pages live under [frontend/app/](frontend/app/).

## Basic flow of the application

### 1. User opens the UI

The browser loads the Next.js app from the frontend. The layout renders the header and navigation, then each route page renders its own screen.

### 2. User registers or logs in

The auth pages call the backend through [frontend/lib/api.ts](frontend/lib/api.ts).

- Register page sends `POST /api/v1/auth/register`
- Login page sends `POST /api/v1/auth/login`
- The returned JWT is stored locally in the browser session helper

### 3. User creates or selects a project

The settings page calls:

- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}/providers`
- `POST /api/v1/projects/{project_id}/providers`

That is how the UI learns which project is active and which model providers are configured.

### 4. User analyzes a prompt

The prompt analyzer page sends a multipart request to:

- `POST /api/v1/prompts/analyze`

That request goes to the backend router in [backend/app/api/prompts.py](backend/app/api/prompts.py), which calls the Phase 1 service logic in [backend/app/services/phase1.py](backend/app/services/phase1.py).

The service does three main things:

- runs rule-based checks
- optionally calls a configured judge model
- saves the prompt record with a version number

### 5. User runs an experiment

The experiment runner page sends:

- `POST /api/v1/experiments/run`

The backend route in [backend/app/api/experiments.py](backend/app/api/experiments.py) validates the request, estimates cost, runs the experiment, stores results, and logs to MLflow.

### 6. User gets a recommendation

The recommendations page will call:

- `POST /api/v1/recommendations/model`

That route reads completed experiment output, filters candidate configurations, scores them, and stores the recommendation.

## Backend flow in order

1. [backend/app/main.py](backend/app/main.py) creates the app.
2. [backend/app/core/config.py](backend/app/core/config.py) loads environment settings.
3. [backend/app/api/auth.py](backend/app/api/auth.py) handles register/login.
4. [backend/app/core/deps.py](backend/app/core/deps.py) provides the DB session and JWT auth dependency.
5. [backend/app/api/projects.py](backend/app/api/projects.py) handles project CRUD.
6. [backend/app/api/providers.py](backend/app/api/providers.py) stores encrypted provider settings.
7. [backend/app/api/prompts.py](backend/app/api/prompts.py) analyzes prompts and saves versions.
8. [backend/app/api/experiments.py](backend/app/api/experiments.py) runs experiments and stores results.
9. [backend/app/api/recommendations.py](backend/app/api/recommendations.py) produces ranked recommendations.
10. [backend/app/services/phase1.py](backend/app/services/phase1.py) contains the shared business logic used by those routes.

## Frontend flow in order

1. [frontend/app/layout.tsx](frontend/app/layout.tsx) renders the shared shell.
2. [frontend/app/page.tsx](frontend/app/page.tsx) shows the landing page.
3. [frontend/app/auth/register/page.tsx](frontend/app/auth/register/page.tsx) creates an account and logs in.
4. [frontend/app/auth/login/page.tsx](frontend/app/auth/login/page.tsx) logs in an existing user.
5. [frontend/app/settings/page.tsx](frontend/app/settings/page.tsx) creates projects and stores provider settings.
6. [frontend/app/prompt-analyzer/page.tsx](frontend/app/prompt-analyzer/page.tsx) submits prompt analysis.
7. [frontend/app/experiment-runner/page.tsx](frontend/app/experiment-runner/page.tsx) submits experiment runs.
8. [frontend/app/recommendations/page.tsx](frontend/app/recommendations/page.tsx) will display the recommendation output.
9. [frontend/app/dashboard/page.tsx](frontend/app/dashboard/page.tsx) is reserved for MLflow browsing.

## How the UI talks to the backend

The shared fetch helper is [frontend/lib/api.ts](frontend/lib/api.ts). It:

- prefixes requests with `NEXT_PUBLIC_API_URL`
- adds the bearer token when one exists
- sends JSON by default
- supports multipart requests for prompt uploads

## How to start the application

### Local frontend only

1. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Start the UI:
   ```bash
   npm run dev
   ```
3. Open `http://localhost:3000`

### Local backend only

1. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
2. Start the API:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
3. Open `http://localhost:8000/health`

### Full stack with Docker Compose

1. Make sure the root `.env` file exists.
2. Start the stack:
   ```bash
   cd infra
   docker compose up --build
   ```
3. Open:
   - Frontend: `http://localhost:3000`
   - Backend: `http://localhost:8000`
   - Docs: `http://localhost:8000/docs`
   - MLflow: `http://localhost:5000`

## Notes

- Backend database and model registry wiring are already in place.
- Frontend uses browser-local token storage for the current prototype.
- The `review1.md` file is meant as a quick map of the current code path and startup flow.
