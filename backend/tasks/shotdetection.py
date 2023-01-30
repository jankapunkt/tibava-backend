import os
import sys
import logging
import uuid
import math

import imageio
import requests
import json

from time import sleep

from celery import shared_task

from backend.models import PluginRun, PluginRunResult, Video, Timeline, TimelineSegment
from django.conf import settings
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from analyser.data import DataManager


@PluginManager.export_plugin("shotdetection")
class Thumbnail:
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(self, parameters=None, **kwargs):
        video = kwargs.get("video")

        video_analyse = PluginRun.objects.create(video=video, type="shotdetection", status=PluginRun.STATUS_QUEUED)

        task = detect_shots.apply_async(
            ({"id": video_analyse.id.hex, "video": video.to_dict(), "config": self.config},)
        )


@shared_task(bind=True)
def detect_shots(self, args):

    config = args.get("config")
    video = args.get("video")
    id = args.get("id")
    output_path = config.get("output_path")
    analyser_host = config.get("analyser_host", "localhost")
    analyser_port = config.get("analyser_port", 50051)

    video_db = Video.objects.get(id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))
    plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

    plugin_run_db.status = PluginRun.STATUS_WAITING
    plugin_run_db.save()

    print(f"{analyser_host}, {analyser_port}")
    client = TaskAnalyserClient(host=analyser_host, port=analyser_port, plugin_run_db=plugin_run_db)

    print(f"Start uploading", flush=True)
    data_id = client.upload_file(video_file)
    if data_id is None:
        return
    print(f"{data_id}", flush=True)

    print(f"Start plugin", flush=True)
    job_id = client.run_plugin("transnet_shotdetection", [{"id": data_id, "name": "video"}], [])
    if job_id is None:
        return
    result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)

    if result is None:
        logging.error("Job is crashing")
        return

    shots_id = None
    for output in result.outputs:
        if output.name == "shots":
            shots_id = output.id
    if shots_id is None:
        return
    logging.info(f"shots_id: {shots_id} {output_path}")
    data = client.download_data(shots_id, output_path)
    if data is None:
        return
    logging.info(data)
    with data:

        timeline_id = uuid.uuid4().hex
        # TODO translate the name
        timeline = Timeline.objects.create(video=video_db, id=timeline_id, name="Shots", type=Timeline.TYPE_ANNOTATION)
        for shot in data.shots:
            segment_id = uuid.uuid4().hex
            timeline_segment = TimelineSegment.objects.create(
                timeline=timeline,
                id=segment_id,
                start=shot.start,
                end=shot.end,
            )

        plugin_run_result_db = PluginRunResult.objects.create(
            plugin_run=plugin_run_db, data_id=data.id, name="shots", type=PluginRunResult.TYPE_SHOTS
        )

        print(f"save results {plugin_run_result_db}", flush=True)

        plugin_run_db.progress = 1.0
        plugin_run_db.status = PluginRun.STATUS_DONE
        plugin_run_db.save()

        return {"status": "done"}
