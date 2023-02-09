from typing import Dict, List
import imageio.v3 as iio

from analyser.data import DataManager
from backend.models import PluginRun, PluginRunResult, Video, Timeline, User
from backend.plugin_manager import PluginManager

from ..utils.analyser_client import TaskAnalyserClient
from backend.utils.parser import Parser
from backend.utils.task import Task


PLUGIN_NAME = "InsightfaceIdentification"


@PluginManager.export_parser("insightface_identification")
class InsightfaceIdentificationParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Face Identification"},
            "fps": {"parser": float, "default": 2},
            "query_images": {"parser": str, "required": True},
            "normalize": {"parser": float, "default": 1},
            "normalize_min_val": {"parser": float, "default": 0.3},
            "normalize_max_val": {"parser": float, "default": 1.0},
        }


@PluginManager.export_plugin("insightface_identification")
class InsightfaceIdentification(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(
        self, parameters: Dict, video: Video = None, user: User = None, plugin_run: PluginRun = None, **kwargs
    ):
        # Debug
        # parameters["fps"] = 0.1

        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )
        # upload all data
        video_id = self.upload_video(client, video)
        image_data = manager.create_data("ImagesData")
        with image_data:
            print(parameters.get("query_images"), flush=True)
            image_path = parameters.get("query_images")
            image = iio.imread(image_path)
            image_data.save_image(image)

        query_image_id = client.upload_data(image_data)

        # start plugins
        video_result = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            outputs=["kpss", "faces"],
        )

        if video_result is None:
            raise Exception

        video_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={"video": video_id, "kpss": video_result[0]["kpss"]},
            outputs=["features"],
        )

        if video_feature_result is None:
            raise Exception

        # start plugins
        image_result = self.run_analyser(
            client,
            "insightface_image_detector_torch",
            inputs={"images": query_image_id},
            outputs=["kpss", "faces"],
        )

        if image_result is None:
            raise Exception

        image_feature_result = self.run_analyser(
            client,
            "insightface_image_feature_extractor",
            inputs={"images": query_image_id, "kpss": image_result[0]["kpss"], "faces": image_result[0]["faces"]},
            outputs=["features"],
        )

        if image_feature_result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "cosine_similarity",
            parameters={
                "normalize": 1,
            },
            inputs={
                "target_features": video_feature_result[0]["features"],
                "query_features": image_feature_result[0]["features"],
            },
            outputs=["probs"],
        )

        if result is None:
            raise Exception

        aggregated_result = self.run_analyser(
            client,
            "aggregate_scalar_per_time",
            inputs={"scalar": result[0]["probs"]},
            downloads=["aggregated_scalar"],
        )

        if aggregated_result is None:
            raise Exception

        with aggregated_result[1]["aggregated_scalar"] as data:
            plugin_run_result_db = PluginRunResult.objects.create(
                plugin_run=plugin_run,
                data_id=data.id,
                name="face_identification",
                type=PluginRunResult.TYPE_SCALAR,
            )
            Timeline.objects.create(
                video=video,
                name=parameters.get("timeline"),
                type=Timeline.TYPE_PLUGIN_RESULT,
                plugin_run_result=plugin_run_result_db,
                visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
            )
