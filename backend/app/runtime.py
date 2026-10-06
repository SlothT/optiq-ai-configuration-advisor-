"""Single-container beta runtime; dedicated RQ workers remain the production default."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

from app.core.config import settings


def main() -> int:
    api = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", os.environ.get("PORT", "8000")]
    if not settings.embedded_worker:
        os.execv(sys.executable, api)
    if settings.job_backend != "rq":
        raise ValueError("EMBEDDED_WORKER requires JOB_BACKEND=rq")
    children: list[subprocess.Popen] = []
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        # Read credentials inside the worker, rather than exposing them in process arguments.
        children.append(subprocess.Popen([sys.executable, "-m", "app.workers.embedded"]))
        children.append(subprocess.Popen(api))
        while not stopping:
            if any(child.poll() is not None for child in children):
                return 1  # Render restarts the container if either service exits.
            time.sleep(0.5)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
