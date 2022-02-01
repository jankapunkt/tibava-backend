import os
import sys
import logging
import uuid
import math

import imageio
import requests

from time import sleep

from celery import shared_task

from backend.models import VideoAnalyse, Video
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
        print("foo")
        analyse_hash_id = uuid.uuid4().hex

        video_analyse = VideoAnalyse.objects.create(
            video=video, hash_id=analyse_hash_id, type="shotdetection", status="Q"
        )

        task = detect_shots.apply_async(
            ({"hash_id": analyse_hash_id, "video": video.to_dict(), "config": self.config},)
        )


@shared_task(bind=True)
def detect_shots(self, args):

    config = args.get("config")
    video = args.get("video")
    hash_id = args.get("hash_id")

    video_db = Video.objects.get(hash_id=video.get("hash_id"))
    video_file = media_path_to_video(video.get("hash_id"), video.get("ext"))

    VideoAnalyse.objects.filter(video=video_db, hash_id=hash_id).update(status="R")
    try:
        job_args = {"video_id": video.get("hash_id"), "path": video_file}

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
        VideoAnalyse.objects.filter(video=video_db, hash_id=hash_id).update(progres=1.0, status="E")
        return {"status": "error"}
    shots = []
    if response:
        shots = response["shots"]

    VideoAnalyse.objects.filter(video=video_db, hash_id=hash_id).update(progres=1.0, status="D")
    return {"status": "done"}
