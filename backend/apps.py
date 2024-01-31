import logging

from django.apps import AppConfig
from django.db.models import Q


logger = logging.getLogger(__name__)


class BackendConfig(AppConfig):
    name = "backend"

    def ready(self):
        # import here otherwise django complains
        from tibava.celery import app
        from backend.models import PluginRun

        # set unfinished tasks to ERROR on startup
        inspect = app.control.inspect()

        celery_runs = [
            run['args'][0]['plugin_run']
            for category in (list(inspect.scheduled().values()) +
                             list(inspect.active().values()) +
                             list(inspect.reserved().values()))
            for run in category
        ]

        open_runs = PluginRun.objects.exclude(Q(status=PluginRun.STATUS_DONE)|
                                              Q(status=PluginRun.STATUS_ERROR)|
                                              Q(id__in=celery_runs))
        if len(open_runs) > 0:
            logger.warning(
                f'Setting the status of {len(open_runs)} non-running PluginRuns to ERROR'
            )
            open_runs.update(status=PluginRun.STATUS_UNKNOWN)
