# from typing import Dict, List
# import imageio.v3 as iio
# import json
# import os

# from backend.models import (
#     ClusterTimelineItem,
#     Place,
#     PluginRun,
#     PluginRunResult,
#     Video,
#     TibavaUser,
#     Timeline,
#     TimelineSegment,
# )

# from backend.plugin_manager import PluginManager
# from backend.utils import media_path_to_video

# from ..utils.analyser_client import TaskAnalyserClient
# from analyser.data import PlaceClusterData, DataManager
# from analyser.data import Shot
# from backend.utils.parser import Parser
# from backend.utils.task import Task
# from django.db import transaction
# from django.conf import settings


# @PluginManager.export_parser("place_clustering")
# class PlaceClusteringParser(Parser):
#     def __init__(self):
#         self.valid_parameter = {
#             "cluster_threshold": {"parser": float, "default": 0.25},
#             "fps": {"parser": float, "default": 2.0},
#         }


# @PluginManager.export_plugin("place_clustering")
# class PlaceClustering(Task):
#     def __init__(self):

#         self.config = {
#             "output_path": "/predictions/",
#             "base_url": settings.THUMBNAIL_URL,
#             "analyser_host": settings.GRPC_HOST,
#             "analyser_port": settings.GRPC_PORT,
#         }

#     def __call__(
#         self,
#         parameters: Dict,
#         video: Video = None,
#         user: TibavaUser = None,
#         plugin_run: PluginRun = None,
#         **kwargs,
#     ):
#         # Debug
#         # parameters["fps"] = 0.05

#         manager = DataManager(self.config["output_path"])
#         client = TaskAnalyserClient(
#             host=self.config["analyser_host"],
#             port=self.config["analyser_port"],
#             plugin_run_db=plugin_run,
#             manager=manager,
#         )

#         # upload all data
#         video_id = self.upload_video(client, video)

#         shots_id = None
#         if parameters.get("shot_timeline_id"):
#             shot_timeline_db = Timeline.objects.get(id=parameters.get("shot_timeline_id"))
#             shot_timeline_segments = TimelineSegment.objects.filter(timeline=shot_timeline_db)

#             shots = manager.create_data("ShotsData")
#             with shots:
#                 for x in shot_timeline_segments:
#                     shots.shots.append(Shot(start=x.start, end=x.end))
#             shots_id = client.upload_data(shots)

#         # start plugins
#         places_result = self.run_analyser(
#             client,
#             "places_classifier",
#             parameters={
#                 "fps": parameters.get("fps"),
#             },
#             inputs={"video": video_id},
#             outputs=["embeddings", "places", "images", "probs_places365", "probs_places16", "probs_places3"],
#             downloads=["probs_places3", "images"],
#         )

#         if places_result is None:
#             raise Exception

#         # cluster places
#         cluster_result = self.run_analyser(
#             client,
#             "place_clustering",
#             parameters={
#                 "cluster_threshold": parameters.get("cluster_threshold"),
#             },
#             inputs={
#                 "embeddings":   places_result[0]["embeddings"],
#                 "places":       places_result[0]["places"],
#             },
#             downloads=["place_cluster_data"],
#         )

#         if cluster_result is None:
#             raise Exception

#         # save thumbnails
#         with places_result[1]["images"] as d:
#             # extract thumbnails
#             d.extract_all(manager)

#         with transaction.atomic():
#             with cluster_result[1]["place_cluster_data"] as data:
#                 # save cluster results
#                 plugin_run_result_db = PluginRunResult.objects.create(
#                     plugin_run=plugin_run,
#                     data_id=data.id,
#                     name="placeclustering",
#                     type=PluginRunResult.TYPE_CLUSTER,
#                 )

#                 # create a cti for every detected cluster
#                 for cluster_index, cluster in enumerate(data.clusters):
#                     cti = ClusterTimelineItem.objects.create(
#                         video=video,
#                         cluster_id=cluster.id,
#                         name=f"Cluster {cluster_index+1}",
#                         plugin_run=plugin_run,
#                     )

#                     # create a place db item for every detected place
#                     for place_index, place_ref in enumerate(cluster.object_refs):
#                         image = [
#                             f
#                             for f in places_result[1]["images"].images
#                             if f.ref_id == place_ref
#                         ][0]
#                         image_path = os.path.join(
#                             self.config.get("base_url"),
#                             image.id[0:2],
#                             image.id[2:4],
#                             f"{image.id}.{image.ext}",
#                         )
#                         _ = Place.objects.create(
#                             cti=cti,
#                             video=video,
#                             place_ref=place_ref,
#                             embedding_index=place_index,
#                             image_path=image_path,
#                         )

#                 return {
#                     "plugin_run": plugin_run.id.hex,
#                     "plugin_run_results": [plugin_run_result_db.id.hex],
#                     "timelines": {},
#                     "data": {"place_cluster_data": cluster_result[1]["place_cluster_data"].id}
#                 }

#     def get_results(self, analyse):
#         try:
#             results = json.loads(bytes(analyse.results).decode("utf-8"))
#             results = [
#                 {**x, "url": self.config.get("base_url") + f"{analyse.id}/{x['path']}"}
#                 for x in results
#             ]

#             return results
#         except:
#             return []
