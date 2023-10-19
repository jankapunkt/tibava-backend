import logging
import traceback
import sys
from typing import List

from celery import shared_task
from backend.models import PluginRun, Video, TibavaUser


# class PluginRunResults(datacla):


class PluginManager:
    _plugins = {}
    _parser = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def export_parser(cls, name):
        def export_helper(parser):
            cls._parser[name] = parser
            return parser

        return export_helper

    @classmethod
    def export_plugin(cls, name):
        def export_helper(plugin):
            cls._plugins[name] = plugin
            return plugin

        return export_helper

    def __contains__(self, plugin):
        return plugin in self._plugins

    def __call__(
        self, plugin: str, video: Video, user: TibavaUser, parameters: List = None, run_async: bool = True, **kwargs
    ):
        if parameters is None:
            parameters = []

        if plugin not in self._plugins:
            print("Unknown Plugin")
            return {"status": False}

        if plugin in self._parser:
            parameters = self._parser[plugin]()(parameters)

        result = {"status": True}
        plugin_run = PluginRun.objects.create(video=video, type=plugin, status=PluginRun.STATUS_QUEUED)
        if run_async:
            run_plugin.apply_async(
                (
                    {
                        "plugin": plugin,
                        "parameters": parameters,
                        "video": video.id,
                        "user": user.id,
                        "plugin_run": plugin_run.id,
                        "kwargs": kwargs,
                    },
                )
            )
        else:
            try:
                plugin_result = self._plugins[plugin]()(parameters, user=user, video=video, plugin_run=plugin_run, **kwargs)
                plugin_run.progress = 1.0
                plugin_run.status = PluginRun.STATUS_DONE
                plugin_run.save()
                if plugin_result:
                    result["result"] = plugin_result

            except Exception as e:
                logging.error(f"{plugin} {e}")
                plugin_run.status = PluginRun.STATUS_ERROR
                plugin_run.save()
                result["status"] = False
                return result
        return result

    def get_results(self, analyse):
        if not hasattr(analyse, "type"):
            return None
        if analyse.type not in self._plugins:
            return None
        analyser = self._plugins[analyse.type]()
        if not hasattr(analyser, "get_results"):
            return {}
        return analyser.get_results(analyse)


@shared_task(bind=True)
def run_plugin(self, args):
    plugin = args.get("plugin")
    parameters = args.get("parameters")
    video = args.get("video")
    user = args.get("user")
    plugin_run = args.get("plugin_run")
    kwargs = args.get("kwargs")

    video_db = Video.objects.get(id=video)
    user_db = TibavaUser.objects.get(id=user)
    plugin_run_db = PluginRun.objects.get(id=plugin_run)
    # this job is already started in another jobqueue https://github.com/celery/celery/issues/4400
    if plugin_run_db.in_scheduler:
        logging.warning("Job was rescheduled and will be canceled")
        return
    plugin_run_db.in_scheduler = True
    plugin_run_db.save()

    plugin_manager = PluginManager()
    try:
        plugin_manager._plugins[plugin]()(parameters, user=user_db, video=video_db, plugin_run=plugin_run_db, **kwargs)
        plugin_run_db.progress = 1.0
        plugin_run_db.status = PluginRun.STATUS_DONE
        plugin_run_db.save()
        return

    except Exception as e:
        logging.error(f"{plugin}: {e}")
        exc_type, exc_value, exc_traceback = sys.exc_info()

        traceback.print_exception(
            exc_type,
            exc_value,
            exc_traceback,
            limit=2,
            file=sys.stdout,
        )
    plugin_run_db.status = PluginRun.STATUS_ERROR
    plugin_run_db.save()
