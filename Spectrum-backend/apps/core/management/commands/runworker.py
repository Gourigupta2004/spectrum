import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.db.models import F

from apps.core.models import Task
from apps.core.tasks import claim, execute, run_inline

log = logging.getLogger("worker")


class Command(BaseCommand):
    help = "Run the background worker (image processing, fulfilment, deliveries). One process is enough."

    def add_arguments(self, parser):
        parser.add_argument("--max-tasks", type=int, default=500,
                            help="Exit after this many tasks so systemd restarts a fresh process (0 = never).")
        parser.add_argument("--idle-max", type=float, default=5.0, help="Longest sleep between polls, seconds.")

    def handle(self, *args, max_tasks, idle_max, **options):
        self.stopping = False
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

        # A single worker owns the queue, so anything left running was interrupted
        # (for example killed for using too much memory). Out of attempts means failed,
        # so one bad file can never crash-loop the worker and block everything else.
        Task.objects.filter(status=Task.RUNNING, attempts__gte=F("max_attempts")).update(
            status=Task.FAILED, last_error="Worker stopped while running this task (out of memory or killed)."
        )
        Task.objects.filter(status=Task.RUNNING).update(status=Task.QUEUED)
        log.info("Worker started")

        done = 0
        idle = 0.5
        last_housekeeping = 0.0
        while not self.stopping:
            close_old_connections()
            if time.monotonic() - last_housekeeping > 3600:
                run_inline("core.housekeeping", ())
                last_housekeeping = time.monotonic()
            task = claim()
            if task is None:
                time.sleep(idle)
                idle = min(idle * 2, idle_max)
                continue
            idle = 0.5
            execute(task)
            done += 1
            if max_tasks and done >= max_tasks:
                log.info("Processed %s tasks, exiting for a fresh process", done)
                break
        log.info("Worker stopped")

    def _stop(self, *_):
        self.stopping = True
