from typing import Dict, List

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from backend.utils.parser import Parser
from backend.utils.task import Task

from analyser.data import DataManager


@PluginManager.export_parser("x_clip")
class XCLIPParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "x_clip"},
            "search_term": {"parser": str, "required": True},
            "fps": {"parser": float, "default": 2.0},
        }


@PluginManager.export_plugin("x_clip")
class XCLIP(Task):
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
            "x_clip_video_embedding",
            parameters={"fps": parameters.get("fps")},
            inputs={"video": video_id},
            outputs=["image_features", "video_features"],
        )

        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "x_clip_probs",
            parameters={"search_term": parameters.get("search_term")},
            inputs={**result[0]},
            downloads=["probs"],
        )
        if result is None:
            raise Exception

        with result[1]["probs"] as d:
            plugin_run_result_db = PluginRunResult.objects.create(
                plugin_run=plugin_run, data_id=d.id, name="x_clip", type=PluginRunResult.TYPE_SCALAR
            )

            _ = Timeline.objects.create(
                video=video,
                name=parameters.get("timeline"),
                type=Timeline.TYPE_PLUGIN_RESULT,
                plugin_run_result=plugin_run_result_db,
                visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
            )
