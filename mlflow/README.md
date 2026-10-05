# Optional MLflow tracking

MLflow is not required for the application or contributor checks. Experiments
always save their results in the application database.

From the repo root, enable Compose tracking with:

```bash
INSTALL_EXTRAS=true COMPOSE_MLFLOW_TRACKING_URI=http://mlflow:5000 NEXT_PUBLIC_MLFLOW_URL=http://localhost:5000 ./scripts/optiq compose --profile tracking up --build
```

The UI is at http://localhost:5000. Artifacts are served by MLflow and stored in
the `mlflow_artifacts` volume, so clients do not need that filesystem mounted.
See the root [README](../README.md#optional-mlflow-and-ragas) for native tracking.
