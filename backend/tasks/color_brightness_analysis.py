from typing import Dict, List

from backend.models import PluginRun, PluginRunResult, Video, Timeline, TimelineSegment
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

import logging

from ..utils.analyser_client import TaskAnalyserClient
from analyser.data import DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task


@PluginManager.export_parser("color_brightness_analysis")
class ColorBrightnessAnalyserParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Color Brightness"},
            "fps": {"parser": float, "default": 2.0},
        }


@PluginManager.export_plugin("color_brightness_analysis")
class ColorBrightnessAnalyser(Task):
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
            "color_brightness_analyser",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            downloads=["brightness"],
        )

        if result is None:
            raise Exception

        with result[1]["brightness"] as data:
            plugin_run_result_db = PluginRunResult.objects.create(
                plugin_run=plugin_run,
                data_id=data.id,
                name="color_brightness_analysis",
                type=PluginRunResult.TYPE_SCALAR,
            )

            _ = Timeline.objects.create(
                video=video,
                name=parameters.get("timeline"),
                type=Timeline.TYPE_PLUGIN_RESULT,
                plugin_run_result=plugin_run_result_db,
                visualization=Timeline.VISUALIZATION_SCALAR_LINE,
            )
