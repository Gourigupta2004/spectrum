from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    verbose_name = "System"

    def ready(self):
        from django.utils.module_loading import autodiscover_modules

        from . import signals  # noqa: F401

        # Each app registers its background jobs in jobs.py. Those modules import
        # heavy libraries inside the job functions only, so web processes stay small.
        autodiscover_modules("jobs")
