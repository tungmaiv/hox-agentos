"""
Celery application for Blitz AgentOS async task queue.

Two queues:
  - embedding: CPU-bound bge-m3 embedding tasks (concurrency=2, memory-intensive)
  - default: LLM-backed tasks like summarize_episode (concurrency=4, I/O-bound)

Broker/backend: Redis (already required for FastAPI session/cache).
"""

from celery import Celery

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "blitz",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["scheduler.tasks.embedding"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "scheduler.tasks.embedding.embed_and_store": {"queue": "embedding"},
        "scheduler.tasks.embedding.summarize_episode": {"queue": "default"},
    },
)
