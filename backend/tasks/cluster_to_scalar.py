from typing import Dict, List
import imageio.v3 as iio
import json
import os
import logging
import numpy as np

from backend.models import (
    ClusterTimelineItem,
    ClusterItem,
    PluginRun,
    PluginRunResult,
    Video,
    TibavaUser,
    Timeline,
)

from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from analyser.data import DataManager, ImageEmbedding
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


logger = logging.getLogger(__name__)


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
        **kwargs,
    ):
        # Debug
        # parameters["fps"] = 0.1
        print("###############", flush=True)
        print(parameters, flush=True)

        # check whether we compare by input embedding or input image
        manager = DataManager(self.config["output_path"])

        cluster_items = ClusterItem.objects.filter(
            plugin_run_result__data_id=parameters.get("data_id"), deleted=False
        )

        # find common plugin run result reference
        clustering_plugin_run_result_db = None
        for x in cluster_items:
            if clustering_plugin_run_result_db is None:
                clustering_plugin_run_result_db = x.plugin_run_result

            if clustering_plugin_run_result_db.id != x.plugin_run_result.id:
                logger.error(
                    f"Found different plugin_run_result {x.plugin_run_result.id} in cluster_to_scalar"
                )
                return None

        cluster_items_ids = [x.plugin_item_ref.hex for x in cluster_items]

        # go over all plugin run results and find the embeddings
        embedding_plugin_run_result_db = None
        cluster_plugin_run_result_db = None
        for (
            plugin_run_result_db
        ) in clustering_plugin_run_result_db.plugin_run.pluginrunresult_set.all():
            if plugin_run_result_db.type == PluginRunResult.TYPE_IMAGE_EMBEDDINGS:
                embedding_plugin_run_result_db = plugin_run_result_db
            if plugin_run_result_db.type == PluginRunResult.TYPE_CLUSTER:
                cluster_plugin_run_result_db = plugin_run_result_db

        if embedding_plugin_run_result_db is None:
            return None

        if cluster_plugin_run_result_db is None:
            return None

        selected_cluster = None
        with manager.load(cluster_plugin_run_result_db.data_id) as clusters_data:
            for cluster in clusters_data.clusters:
                if cluster.id == parameters.get("cluster_id"):
                    selected_cluster = cluster

        print("##############+++++", flush=True)
        print(selected_cluster, flush=True)
        print(cluster_items_ids, flush=True)
        print("##############+++++", flush=True)

        # load embeddings and compute mean of all non deleted embeddings from a cluster
        with manager.load(embedding_plugin_run_result_db.data_id) as embedding_data:
            cluster_feature = []
            for x in embedding_data.embeddings:
                print(x.ref_id, flush=True)
                if (
                    x.ref_id in cluster_items_ids
                    and x.id in selected_cluster.embedding_ids
                ):
                    cluster_feature.append(x.embedding)

            # print(cluster_feature, flush=True)
            print(len(cluster_feature), flush=True)
            query_feature = np.mean(cluster_feature, axis=0)
            print(np.mean(cluster_feature, axis=0), flush=True)

        query_image_feature = manager.create_data("ImageEmbeddings")
        with query_image_feature:
            query_image_feature.embeddings.append(
                ImageEmbedding(
                    embedding=query_feature,
                    time=0,
                    delta_time=1,
                )
            )

        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )
        query_image_feature_id = client.upload_data(query_image_feature)

        print("##############", flush=True)
        print(selected_cluster, flush=True)
        print(
            ClusterItem.objects.filter(
                plugin_run_result__data_id=parameters.get("data_id")
            ),
            flush=True,
        )
        print("##############", flush=True)

        if cluster is None:
            return

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
        plugin_run.progress = 0.25
        plugin_run.save()

        if video_facedetection is None:
            raise Exception

        video_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={"video": video_id, "kpss": video_facedetection[0]["kpss"]},
            outputs=["features"],
        )
        plugin_run.progress = 0.5
        plugin_run.save()

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
                "query_features": query_image_feature_id,
            },
            outputs=["probs"],
        )
        plugin_run.progress = 0.75
        plugin_run.save()

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
