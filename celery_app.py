from __future__ import annotations

import os

from celery import Celery
from celery.signals import worker_process_init

from api.ml_preflight import check_required_models

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "documind",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.parse_pipeline", "workers.extraction_pipeline"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@worker_process_init.connect
def _check_ml_dependencies_on_worker_start(**_: object) -> None:
    check_required_models()
    _warm_sentence_transformer()


def _warm_sentence_transformer() -> None:
    import logging

    logger = logging.getLogger(__name__)
    try:
        from workers.classify_worker import _get_st_model

        _get_st_model()
        logger.info("Sentence-transformer model warmed at worker startup")
    except Exception as exc:
        logger.warning("Sentence-transformer warm-up failed (non-fatal): %s", exc)
