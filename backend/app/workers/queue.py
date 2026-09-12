from __future__ import annotations

import logging

from redis import Redis
from rq import Queue

from app.core.config import settings

logger = logging.getLogger("optiq.queue")


def experiment_queue() -> Queue:
    connection = Redis.from_url(settings.redis_url)
    return Queue("default", connection=connection)


def enqueue_experiment(experiment_id: str, temperature: float) -> str:
    try:
        job = experiment_queue().enqueue(
            "app.workers.experiments.execute_experiment_job",
            experiment_id,
            temperature,
            job_timeout=3600,
            result_ttl=86400,
            failure_ttl=86400,
        )
        logger.info("queued experiment %s as job %s", experiment_id, job.id)
        return str(job.id)
    except Exception as exc:
        logger.warning("Redis unavailable (%s); running experiment %s in-process", exc, experiment_id)
        from threading import Thread

        from app.workers.experiments import execute_experiment_job

        Thread(
            target=execute_experiment_job,
            args=(experiment_id, temperature),
            daemon=True,
            name=f"optiq-experiment-{experiment_id}",
        ).start()
        return "inline"
