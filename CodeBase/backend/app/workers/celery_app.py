from __future__ import annotations

from celery import Celery

from app.core.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "ptcl",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.workers.tasks"],
    )
    app.conf.task_always_eager = settings.celery_task_always_eager
    app.conf.task_eager_propagates = True
    return app


celery_app = create_celery_app()
