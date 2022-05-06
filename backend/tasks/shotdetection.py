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

from backend.models import PluginRun, Video, Timeline, TimelineSegment
from django.conf import settings
from backend.analyser import Analyser
from backend.utils import media_path_to_video


@Analyser.export("shotdetection")
class Thumbnail:
    def __init__(self):
        self.config = {
            "backend_url": "http://localhost:5000/detect_shots",
            "output_path": "/predictions/shotdetection/",
        }

    def __call__(self, video):
        analyse_id = uuid.uuid4().hex

        video_analyse = PluginRun.objects.create(video=video, id=analyse_id, type="shotdetection", status="Q")

        task = detect_shots.apply_async(({"id": analyse_id, "video": video.to_dict(), "config": self.config},))

    def get_results(self, analyse):
        try:
            return json.loads(bytes(analyse.results).decode("utf-8"))
        except:
            return []


@shared_task(bind=True)
def detect_shots(self, args):

    config = args.get("config")
    video = args.get("video")
    id = args.get("id")

    video_db = Video.objects.get(id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))

    PluginRun.objects.filter(video=video_db, id=id).update(status="R")
    try:
        job_args = {"video_id": video.get("id"), "path": video_file}

        job_id = requests.post(config.get("backend_url"), json=job_args).json()["job_id"]

        def get_response(url, args):
            while True:
                response = requests.get(url, args)
                response = response.json()
                logging.debug(response)

                if "status" in response and response["status"] == "SUCCESS":
                    logging.info("JOB DONE!")
                    return response
                elif "status" in response and response["status"] == "PENDING":
                    sleep(0.5)
                else:
                    print(response)
                    logging.error("Something went wrong")
                    break

            return None

        pull_args = {"job_id": job_id, "fps": video.get("fps")}
        response = get_response(config.get("backend_url"), args=pull_args)
    except:
        PluginRun.objects.filter(video=video_db, id=id).update(progress=1.0, status="E")
        return {"status": "error"}
    shots = []
    if response:
        shots = response["shots"]

    # class Timeline(models.Model):
    #     video = models.ForeignKey(Video, on_delete=models.CASCADE)
    #     id = models.CharField(max_length=256)
    #     name = models.CharField(max_length=256)
    #     type = models.CharField(max_length=256)

    # class TimelineSegment(models.Model):
    #     timeline = models.ForeignKey(Timeline, on_delete=models.CASCADE)
    #     id = models.CharField(max_length=256)
    #     color = models.CharField(max_length=256)
    #     start = models.FloatField()
    #     end = models.FloatField()

    # check if there is already a shot detection result

    timeline_id = uuid.uuid4().hex
    # TODO translate the name
    timeline = Timeline.objects.create(video=video_db, id=timeline_id, name="shot", type="A")
    for shot in shots:
        segment_id = uuid.uuid4().hex
        timeline_segment = TimelineSegment.objects.create(
            timeline=timeline,
            id=segment_id,
            start=shot["start_time_sec"],
            end=shot["end_time_sec"],
        )

    PluginRun.objects.filter(video=video_db, id=id).update(progress=1.0, results=json.dumps(shots).encode(), status="D")
    return {"status": "done"}
