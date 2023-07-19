from typing import Dict, List
import imageio.v3 as iio
import json

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
            "base_url": "http://localhost/thumbnails/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(
        self, parameters: Dict, video: Video = None, user: TibavaUser = None, plugin_run: PluginRun = None, **kwargs
    ):
        # Debug
        # parameters["fps"] = 0.05

        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )
        
        # face detector
        video_id = self.upload_video(client, video)
        facedetector_result = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
                "min_facesize": parameters.get("min_facesize"),
            },
            inputs={"video": video_id},
            outputs=["images", "kpss", "faces", "bboxes"],
            downloads=["images"]
        )

        if facedetector_result is None:
            raise Exception
        
        # create image embeddings
        image_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={"video": video_id, "kpss": facedetector_result[0]["kpss"], "faces": facedetector_result[0]["faces"]},
            outputs=["features"],
        )

        if image_feature_result is None:
            raise Exception

        # cluster faces
        cluster_result = self.run_analyser(
            client,
            "face_clustering",
            parameters={},
            inputs={
                "embeddings": image_feature_result[0]["features"], 
                "faces": facedetector_result[0]["faces"], 
                "bboxes": facedetector_result[0]["bboxes"], 
                "kpss": facedetector_result[0]["kpss"],
                "images": facedetector_result[0]["images"]
                },
            downloads=["face_cluster_data"],
        )
        
        if cluster_result is None:
            raise Exception
        
        # TODO extract all images
        with facedetector_result[1]["images"] as d:
            # extract thumbnails
            d.extract_all(manager)
            _ = PluginRunResult.objects.create(
                plugin_run=plugin_run, 
                data_id=d.id, 
                name="facedetector_images", 
                type=PluginRunResult.TYPE_IMAGES
            )

        with cluster_result[1]["face_cluster_data"] as data:
            _ = PluginRunResult.objects.create(
                plugin_run=plugin_run, 
                data_id=data.id, 
                name="faceclustering", 
                type=PluginRunResult.TYPE_CLUSTER
            )
    
    def get_results(self, analyse):
        try:
            results = json.loads(bytes(analyse.results).decode("utf-8"))
            results = [{**x, "url": self.config.get("base_url") + f"{analyse.id}/{x['path']}"} for x in results]

            return results
        except:
            return []
