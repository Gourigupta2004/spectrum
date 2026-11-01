"""A tiny database-backed job queue. One `manage.py runworker` process drains it."""

import logging
import traceback
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

log = logging.getLogger(__name__)
REGISTRY: dict = {}
# Catch-up work that can come in thousands at once (re-marking every portal
# photo). The worker runs it only when nothing else is waiting, so a buyer's
# delivery or a fresh upload never queues behind it.
LOW_PRIORITY = frozenset({"core.refresh_watermark"})


def job(name: str):
    def decorator(func):
        REGISTRY[name] = func
        return func

    return decorator


def enqueue(name: str, *args, delay_seconds: int = 0, max_attempts: int = 3) -> None:
    if name not in REGISTRY:
        raise KeyError(f"Unknown job {name}")
    if settings.TASKS_EAGER and not delay_seconds:
        transaction.on_commit(lambda: run_inline(name, args))
        return
    from .models import Task

    Task.objects.create(
        name=name,
        args=list(args),
        max_attempts=max_attempts,
        run_after=timezone.now() + timedelta(seconds=delay_seconds),
    )


def run_inline(name: str, args) -> None:
    try:
        REGISTRY[name](*args)
    except Exception:
        log.exception("Inline job %s%r failed", name, tuple(args))


def claim():
    from .models import Task

    now = timezone.now()
    due = Task.objects.filter(status=Task.QUEUED, run_after__lte=now, attempts__lt=F("max_attempts"))
    for _ in range(5):
        pk = None
        for tasks in (due.exclude(name__in=LOW_PRIORITY), due.filter(name__in=LOW_PRIORITY)):
            pk = tasks.order_by("run_after", "id").values_list("pk", flat=True).first()
            if pk is not None:
                break
        if pk is None:
            return None
        if Task.objects.filter(pk=pk, status=Task.QUEUED).update(status=Task.RUNNING, attempts=F("attempts") + 1):
            return Task.objects.get(pk=pk)
    return None


def execute(task) -> bool:
    from .models import Task

    func = REGISTRY.get(task.name)
    try:
        if func is None:
            raise KeyError(f"Unknown job {task.name}")
        func(*task.args)
    except Exception:
        error = traceback.format_exc()[-4000:]
        log.error("Job %s failed (attempt %s/%s)\n%s", task, task.attempts, task.max_attempts, error)
        if task.attempts >= task.max_attempts:
            Task.objects.filter(pk=task.pk).update(status=Task.FAILED, last_error=error)
        else:
            backoff = timedelta(seconds=30 * 2 ** (task.attempts - 1))
            Task.objects.filter(pk=task.pk).update(
                status=Task.QUEUED, last_error=error, run_after=timezone.now() + backoff
            )
        return False
    Task.objects.filter(pk=task.pk).delete()
    return True
