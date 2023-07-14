from typing import Dict, List

from backend.models import (
    Annotation,
    AnnotationCategory,
    PluginRun,
    PluginRunResult,
    Video,
    TibavaUser,
    Timeline,
    TimelineSegment,
    TimelineSegmentAnnotation,
)
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from analyser.data import FaceClusterData, DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task

PLUGIN_NAME = "FaceClustering"

@PluginManager.export_parser("face_clustering")
class FaceClusteringParser(Parser):
    def __init__(self):

        self.valid_parameter = {
        #     "timeline": {"parser": str, "default": "Face Size"},
        #     "shot_timeline_id": {"default": None},
        #     "fps": {"parser": float, "default": 2.0},
        }


@PluginManager.export_plugin("face_clustering")
class FaceClustering(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(
        self, parameters: Dict, video: Video = None, user: TibavaUser = None, plugin_run: PluginRun = None, **kwargs
    ):
        # Debug
        # parameters["fps"] = 0.05

        print("TASK START")

        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )
        
        # clip embeddings
        video_id = self.upload_video(client, video)
        result = self.run_analyser(
            client,
            "clip_image_embedding",
            parameters={"fps": parameters.get("fps")},
            inputs={"video": video_id},
            outputs=["embeddings"],
        )

        print("result embeddings")
        print(result)

        # start plugins
        result = self.run_analyser(
            client,
            "face_clustering",
            parameters={
            },
            inputs={"embeddings": result["embeddings"]},
            outputs=["bboxes"],
        )

        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "insightface_facesize",
            inputs={**result[0]},
            outputs=["probs"],
            downloads=["probs"],
        )

        if result is None:
            raise Exception

        print("TASK DONE")