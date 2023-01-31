from typing import Dict, List

from backend.models import PluginRun, PluginRunResult, Video, Timeline, TimelineSegment
from django.conf import settings
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from analyser.data import DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task


@PluginManager.export_parser("audio_rms")
class AudioRmsParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "audio_amp"},
            "sr": {"parser": int, "default": 24000},
        }


@PluginManager.export_plugin("audio_rms")
class AudioRms(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(self, parameters: Dict, video: Video = None, plugin_run: PluginRun = None, **kwargs):

        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )

        video_id = self.upload_video(client, video)
        result = self.run_analyser(
            client,
            "video_to_audio",
            inputs={"video": video_id},
            outputs=["audio"],
        )

        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "audio_rms_analysis",
            parameters={"sr": parameters.get("sr")},
            inputs={**result[0]},
            downloads=["rms"],
        )
        if result is None:
            raise Exception

        with result[1]["rms"] as data:
            plugin_run_result_db = PluginRunResult.objects.create(
                plugin_run=plugin_run, data_id=data.id, name="audio_rms", type=PluginRunResult.TYPE_SCALAR
            )

            _ = Timeline.objects.create(
                video=video,
                name=parameters.get("timeline"),
                type=Timeline.TYPE_PLUGIN_RESULT,
                plugin_run_result=plugin_run_result_db,
                visualization=Timeline.VISUALIZATION_SCALAR_LINE,
            )
