from typing import Dict, List
import imageio.v3 as iio
import json
import os

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


@PluginManager.export_parser("face_clustering")
class FaceClusteringParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "cluster_threshold": {"parser": float, "default": 0.5},
            "fps": {"parser": float, "default": 2.0},
            "max_cluster": {"parser": int, "default": 50},
            "max_faces": {"parser": int, "default": 50},
        }


@PluginManager.export_plugin("face_clustering")
class FaceClustering(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "base_url": settings.THUMBNAIL_URL,
            "analyser_host": settings.GRPC_HOST,
            "analyser_port": settings.GRPC_PORT,
        }

    def __call__(
        self,
        parameters: Dict,
        video: Video = None,
        user: TibavaUser = None,
        plugin_run: PluginRun = None,
        **kwargs,
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
        video_data_id = self.upload_video(client, video)
        facedetector_result = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
                "min_facesize": parameters.get("min_facesize"),
            },
            inputs={"video": video_data_id},
            outputs=["images", "kpss", "faces", "bboxes"],
            downloads=["images", "faces"],
        )

        if facedetector_result is None:
            raise Exception

        # create image embeddings
        image_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={
                "video": video_data_id,
                "kpss": facedetector_result[0]["kpss"],
                "faces": facedetector_result[0]["faces"],
            },
            outputs=["features"],
            downloads=["features"],
        )

        if image_feature_result is None:
            raise Exception

        # cluster faces
        cluster_result = self.run_analyser(
            client,
            "clustering",
            parameters={
                "cluster_threshold": parameters.get("cluster_threshold"),
            },
            inputs={
                "embeddings": image_feature_result[0]["features"],
            },
            downloads=["cluster_data"],
        )

        if cluster_result is None:
            raise Exception

        # save thumbnails
        with facedetector_result[1]["images"] as d:
            # extract thumbnails
            d.extract_all(manager)

        embedding_face_lut = {}
        with image_feature_result[1]["features"] as d:
            for embedding in d.embeddings:
                embedding_face_lut[embedding.id] = embedding.ref_id

        with transaction.atomic():
            with cluster_result[1]["cluster_data"] as data:
                # save cluster results
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=data.id,
                    name="clustering",
                    type=PluginRunResult.TYPE_CLUSTER,
                )

                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=facedetector_result[1]["faces"].id,
                    name="faces",
                    type=PluginRunResult.TYPE_FACE,
                )

                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=facedetector_result[1]["images"].id,
                    name="images",
                    type=PluginRunResult.TYPE_IMAGES,
                )

                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=image_feature_result[1]["features"].id,
                    name="features",
                    type=PluginRunResult.TYPE_IMAGE_EMBEDDINGS,
                )

                # create a cti for every detected cluster
                for cluster_index, cluster in enumerate(data.clusters):
                    cluster_timeline_item_db = ClusterTimelineItem.objects.create(
                        video=video,
                        cluster_id=cluster.id,
                        name=f"Cluster {cluster_index+1}",
                        plugin_run=plugin_run,
                    )

                    # create a face db item for every detected face
                    for face_index, embedding_id in enumerate(cluster.object_refs):
                        image = [
                            f
                            for f in facedetector_result[1]["images"].images
                            if f.ref_id == embedding_face_lut[embedding_id]
                        ][0]
                        image_path = os.path.join(
                            self.config.get("base_url"),
                            image.id[0:2],
                            image.id[2:4],
                            f"{image.id}.{image.ext}",
                        )
                        _ = Face.objects.create(
                            cti=cluster_timeline_item_db,
                            video=video,
                            face_ref=embedding_face_lut[embedding_id],
                            embedding_index=face_index,
                            image_path=image_path,
                        )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [plugin_run_result_db.id.hex],
                    "timelines": {},
                    "data": {"cluster_data": cluster_result[1]["cluster_data"].id},
                }

    def get_results(self, analyse):
        try:
            results = json.loads(bytes(analyse.results).decode("utf-8"))
            results = [
                {**x, "url": self.config.get("base_url") + f"{analyse.id}/{x['path']}"}
                for x in results
            ]

            return results
        except:
            return []
