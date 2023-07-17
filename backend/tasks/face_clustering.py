from typing import Dict, List
import imageio.v3 as iio

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
        
        print("1", flush=True)
        # start plugins
        video_id = self.upload_video(client, video)
        result = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
                "min_facesize": parameters.get("min_facesize"),
            },
            inputs={"video": video_id},
            outputs=["images", "kpss", "faces"],
        )

        if result is None:
            raise Exception
        
        print(result, flush=True)
        #({
        # 'images': '5df91888509e4dea968cf16e13789121', 
        # 'kpss': '86571594e76e4012964c2685df42a08b', 
        # 'faces': '6568051f2c6b40d7b381b681ec3787d9'
        # }, 
        # {})
        print("2", flush=True)
        # TypeError: tuple indices must be integers or slices, not str
        image_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={"video": video_id, "kpss": result[0]["kpss"], "faces": result[0]["faces"]},
            outputs=["features"],
        )

        if image_feature_result is None:
            raise Exception

        print("3", flush=True)
        # ({'features': '51b0fcb4ff794540b5656912ba685a1d'}, {})

        # start plugins
        cluster_result = self.run_analyser(
            client,
            "face_clustering",
            parameters={},
            inputs={"embeddings": image_feature_result[0]["features"], "faces": result[0]["faces"]},
            downloads=["face_cluster_data"],
        )

        if cluster_result is None:
            raise Exception

        print(result)

        print("TASK DONE")