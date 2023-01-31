from typing import Dict, List


from backend.models import PluginRun, PluginRunResult, Video, Timeline, TimelineSegment
from django.conf import settings
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from backend.utils.parser import Parser
from backend.utils.task import Task
from analyser.data import DataManager


@PluginManager.export_parser("audio_freq")
class AudioFreqParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "audio_freq"},
            "sr": {"parser": int, "default": 24000},
            "n_fft": {"parser": int, "default": 256},
        }


@PluginManager.export_plugin("audio_freq")
class AudioFreq(Task):
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
            "audio_freq_analysis",
            parameters={"sr": parameters.get("sr"), "n_fft": parameters.get("n_fft")},
            inputs={**result[0]},
            downloads=["freq"],
        )
        if result is None:
            raise Exception

        with result[1]["freq"] as data:

            plugin_run_result_db = PluginRunResult.objects.create(
                plugin_run=plugin_run, data_id=data.id, name="audio_freq", type=PluginRunResult.TYPE_HIST
            )

            _ = Timeline.objects.create(
                video=video,
                name=parameters.get("timeline"),
                type=Timeline.TYPE_PLUGIN_RESULT,
                plugin_run_result=plugin_run_result_db,
                visualization=Timeline.VISUALIZATION_HIST,
            )
