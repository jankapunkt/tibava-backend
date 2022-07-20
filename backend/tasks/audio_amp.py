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

from analyser.client import AnalyserClient
from analyser.data import DataManager


@PluginManager.export("audio_amp")
class AudioAmp:
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "localhost",
            "analyser_port": 50051,
        }

    def __call__(self, parameters=None, **kwargs):

        video = kwargs.get("video")
        if not parameters:
            parameters = []

        task_parameter = {"timeline": "audio_amp"}
        for p in parameters:
            if p["name"] in ["timeline"]:
                task_parameter[p["name"]] = str(p["value"])
            elif p["name"] in ["sr"]:
                task_parameter[p["name"]] = int(p["value"])
            else:
                return False

        video_analyse = PluginRun.objects.create(video=video, type="audio_amp", status="Q")

        task = audio_amp.apply_async(
            (
                {
                    "id": video_analyse.id.hex,
                    "video": video.to_dict(),
                    "config": self.config,
                    "parameters": task_parameter,
                },
            )
        )
        return True


@shared_task(bind=True)
def audio_amp(self, args):

    config = args.get("config")
    parameters = args.get("parameters")
    video = args.get("video")
    id = args.get("id")
    output_path = config.get("output_path")
    analyser_host = args.get("analyser_host", "localhost")
    analyser_port = args.get("analyser_port", 50051)

    print(f"[AudioAmp] {video}: {parameters}", flush=True)

    video_db = Video.objects.get(id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))
    plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

    plugin_run_db.status = "R"
    plugin_run_db.save()

    # print(f"{analyser_host}, {analyser_port}")
    client = AnalyserClient(analyser_host, analyser_port)

    # print(f"Start uploading", flush=True)
    data_id = client.upload_file(video_file)
    # print(f"{data_id}", flush=True)

    # print(f"Start plugin", flush=True)
    job_id = client.run_plugin("video_to_audio", [{"id": data_id, "name": "video"}], [])
    # logging.info(f"Job video_to_audio started: {job_id}")

    result = client.get_plugin_results(job_id=job_id)
    if result is None:
        # logging.error("Job is crashing")
        return

    audio_id = None
    for output in result.outputs:
        if output.name == "audio":
            audio_id = output.id

    # logging.info(f"Job video_to_audio done: {audio_id}")

    job_id = client.run_plugin(
        "audio_amp_analysis",
        [{"id": audio_id, "name": "audio"}],
        [{"name": k, "value": v} for k, v in parameters.items()],
    )
    # logging.info(f"Job audio_amp started: {job_id}")

    result = client.get_plugin_results(job_id=job_id)
    if result is None:
        # logging.error("Job is crashing")
        return

    amp_id = None
    for output in result.outputs:
        if output.name == "amp":
            amp_id = output.id

    # logging.info(f"Job audio_amp done: {amp_id}")

    data = client.download_data(amp_id, output_path)
    plugin_run_result_db = PluginRunResult.objects.create(
        plugin_run=plugin_run_db, data_id=data.id, name="audio_amp", type="S"
    )

    _ = Timeline.objects.create(
        video=video_db,
        name=parameters.get("timeline"),
        type=Timeline.TYPE_PLUGIN_RESULT,
        plugin_run_result=plugin_run_result_db,
        visualization="SL",
    )

    plugin_run_db.progress = 1.0
    plugin_run_db.status = "D"
    plugin_run_db.save()

    return {"status": "done"}
