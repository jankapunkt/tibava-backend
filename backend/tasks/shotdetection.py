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
from backend.analyser import Analyser
from backend.utils import media_path_to_video

from analyser.client import AnalyserClient
from analyser.data import DataManager


@Analyser.export("shotdetection")
class Thumbnail:
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "localhost",
            "analyser_port": 50051,
        }

    def __call__(self, video):

        video_analyse = PluginRun.objects.create(video=video, type="shotdetection", status="Q")

        task = detect_shots.apply_async(
            ({"id": video_analyse.id.hex, "video": video.to_dict(), "config": self.config},)
        )


@shared_task(bind=True)
def detect_shots(self, args):

    config = args.get("config")
    video = args.get("video")
    id = args.get("id")
    output_path = config.get("output_path")
    analyser_host = args.get("analyser_host", "localhost")
    analyser_port = args.get("analyser_port", 50051)

    video_db = Video.objects.get(id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))
    plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

    plugin_run_db.status = "R"
    plugin_run_db.save()

    print(f"{analyser_host}, {analyser_port}")
    client = AnalyserClient(analyser_host, analyser_port)

    print(f"Start uploading", flush=True)
    data_id = client.upload_data(video_file)
    print(f"{data_id}", flush=True)

    print(f"Start plugin", flush=True)
    job_id = client.run_plugin("transnet_shotdetection", [{"id": data_id, "name": "video"}], [])
    result = client.get_plugin_results(job_id=job_id)
    if result is None:
        logging.error("Job is crashing")
        return

    shots_id = None
    for output in result.outputs:
        if output.name == "shots":
            shots_id = output.id

    logging.info(f"shots_id: {shots_id} {output_path}")
    data = client.download_data(shots_id, output_path)
    logging.info(data)

    timeline_id = uuid.uuid4().hex
    # TODO translate the name
    timeline = Timeline.objects.create(video=video_db, id=timeline_id, name="shot", type="A")
    for shot in data.shots:
        segment_id = uuid.uuid4().hex
        timeline_segment = TimelineSegment.objects.create(
            timeline=timeline,
            id=segment_id,
            start=shot.start,
            end=shot.end,
        )

    plugin_run_result_db = PluginRunResult.objects.create(
        plugin_run=plugin_run_db, data_id=data.id, name="shots", type="SH"
    )

    print(f"save results {plugin_run_result_db}", flush=True)

    plugin_run_db.progress = 1.0
    plugin_run_db.status = "D"
    plugin_run_db.save()

    return {"status": "done"}
