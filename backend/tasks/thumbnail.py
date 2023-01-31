import os
import sys
import logging
import uuid
import math
import json
from typing import Dict, List

import imageio
import cv2

from celery import shared_task

from backend.models import PluginRun, Video, PluginRunResult
from django.conf import settings
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video
from ..utils.analyser_client import TaskAnalyserClient
from analyser.data import DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task


# @PluginManager.export_parser("thumbnail")
# class ThumbnailParser(Parser):
#     def __init__(self):

#         self.valid_parameter = {
#             "timeline": {"parser": str, "default": "clip"},
#             "search_term": {"parser": str, "required": True},
#             "fps": {"parser": float, "default": 2.0},
#         }


@PluginManager.export_plugin("thumbnail")
class Thumbnail(Task):
    def __init__(self):
        self.config = {
            "fps": 5,
            "max_resolution": 128,
            "output_path": "/predictions/",
            "base_url": "http://localhost/thumbnails/",
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
            "thumbnail_generator",
            inputs={"video": video_id},
            downloads=["images"],
        )

        if result is None:
            raise Exception

        # TODO extract all images
        with result[1]["images"] as d:
            # extract thumbnails
            d.extract_all(manager)
            plugin_run_result_db = PluginRunResult.objects.create(
                plugin_run=plugin_run, data_id=d.id, name="images", type=PluginRunResult.TYPE_IMAGES
            )

    def get_results(self, analyse):
        try:
            results = json.loads(bytes(analyse.results).decode("utf-8"))
            results = [{**x, "url": self.config.get("base_url") + f"{analyse.id}/{x['path']}"} for x in results]

            return results
        except:
            return []


# @shared_task(bind=True)
# def generate_thumbnails(self, args):
#     print(f"Start thumbnail", flush=True)
#     config = args.get("config")
#     video = args.get("video")
#     id = args.get("id")
#     analyser_host = config.get("analyser_host", "localhost")
#     analyser_port = config.get("analyser_port", 50051)

#     video_db = Video.objects.get(id=video.get("id"))
#     plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

#     video_file = media_path_to_video(video.get("id"), video.get("ext"))

#     plugin_run_db = PluginRun.objects.get(video=video_db, id=id)
#     plugin_run_db.status = PluginRun.STATUS_WAITING
#     plugin_run_db.save()

#     print(f"{analyser_host}, {analyser_port}")
#     client = TaskAnalyserClient(host=analyser_host, port=analyser_port, plugin_run_db=plugin_run_db)
#     logging.info(f"Start uploading")
#     data_id = client.upload_file(video_file)
#     if data_id is None:
#         return
#     logging.info(f"Upload done: {data_id}")

#     job_id = client.run_plugin("thumbnail_generator", [{"id": data_id, "name": "video"}], [])
#     if job_id is None:
#         return
#     logging.info(f"Job thumbnail started: {job_id}")

#     result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)
#     if result is None:
#         logging.error("Job is crashing")
#         return
#     print(result, flush=True)
#     images_id = None
#     for output in result.outputs:
#         if output.name == "images":
#             images_id = output.id

#     if images_id is None:
#         return
#     data = client.download_data(images_id, config.get("output_path"))
#     if data is None:
#         return
#     with data:
#         plugin_run_result_db = PluginRunResult.objects.create(
#             plugin_run=plugin_run_db, data_id=data.id, name="images", type=PluginRunResult.TYPE_IMAGES
#         )

#     plugin_run_db.progress = 1.0
#     plugin_run_db.status = PluginRun.STATUS_DONE
#     plugin_run_db.save()

#     return {"status": "done"}
