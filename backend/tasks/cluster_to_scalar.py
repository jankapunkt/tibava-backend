from typing import Dict, List
import imageio.v3 as iio
import json
import os
import numpy as np

from backend.models import (
    ClusterTimelineItem,
    Face,
    PluginRun,
    PluginRunResult,
    Video,
    TibavaUser,
)

from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from analyser.data import FaceClusterData, DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("cluster_to_scalar")
class ClusterToScalarParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Cluster Similarity"},
            "cluster_id": {"parser": str},
            "data_id": {"parser": str},
        }


@PluginManager.export_plugin("cluster_to_scalar")
class ClusterToScalar(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": settings.GRPC_HOST,
            "analyser_port": settings.GRPC_PORT,
        }

    def __call__(
        self,
        parameters: Dict,
        video: Video = None,
        user: TibavaUser = None,
        plugin_run: PluginRun = None,
        **kwargs
    ):
        # Debug
        # parameters["fps"] = 0.1
        print("###############", flush=True)
        print(parameters, flush=True)

        # check whether we compare by input embedding or input image
        manager = DataManager(self.config["output_path"])

        selected_cluster = None
        with manager.load(parameters.get("data_id")) as clusters_data:
            for cluster in clusters_data.clusters:
                if cluster.id == parameters.get("cluster_id"):
                    selected_cluster = cluster

        if cluster is None:
            return

        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )

        # upload all data
        video_id = self.upload_video(client, video)

        # face detection on video
        video_facedetection = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            outputs=["kpss", "faces"],
        )

        if video_facedetection is None:
            raise Exception

        video_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={"video": video_id, "kpss": video_facedetection[0]["kpss"]},
            outputs=["features"],
        )

        if video_feature_result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "cosine_similarity",
            parameters={
                "normalize": 1,
                "index": parameters.get("index"),
            },
            inputs={
                "target_features": video_feature_result[0]["features"],
                "query_features": query_image_feature_result[0]["features"],
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

        with transaction.atomic():
            with aggregated_result[1]["aggregated_scalar"] as data:
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=data.id,
                    name="face_identification",
                    type=PluginRunResult.TYPE_SCALAR,
                )
                timeline_db = Timeline.objects.create(
                    video=video,
                    name=parameters.get("timeline"),
                    type=Timeline.TYPE_PLUGIN_RESULT,
                    plugin_run_result=plugin_run_result_db,
                    visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
                )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [plugin_run_result_db.id.hex],
                    "timelines": {"annotations": timeline_db},
                    "data": {
                        "annotations": aggregated_result[1]["aggregated_scalar"].id
                    },
                }
