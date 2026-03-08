"""
Celery application for Blitz AgentOS async task queue.

Two queues:
  - embedding: CPU-bound bge-m3 embedding tasks (concurrency=2, memory-intensive)
  - default: LLM-backed tasks like summarize_episode (concurrency=4, I/O-bound)

Broker/backend: Redis (already required for FastAPI session/cache).
"""

from celery import Celery
from celery.schedules import crontab

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "blitz",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "scheduler.tasks.embedding",
        "scheduler.tasks.workflow_execution",
        "scheduler.tasks.cron_trigger",
        "scheduler.tasks.check_skill_updates",
    ],
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
        "scheduler.tasks.workflow_execution.execute_workflow_task": {"queue": "default"},
        "scheduler.tasks.cron_trigger.fire_cron_triggers_task": {"queue": "default"},
        "scheduler.tasks.check_skill_updates.check_skill_updates_task": {"queue": "default"},
    },
)

celery_app.conf.beat_schedule = {
    "fire-cron-triggers-every-minute": {
        "task": "scheduler.tasks.cron_trigger.fire_cron_triggers_task",
        "schedule": 60.0,  # seconds
    },
    "check-skill-updates-daily": {
        "task": "scheduler.tasks.check_skill_updates.check_skill_updates_task",
        "schedule": crontab(hour=2, minute=0),  # 2:00 AM UTC daily
    },
}
