import os
import sys
import logging
import uuid
import math
import json

import imageio
import cv2

from celery import shared_task

from backend.models import PluginRun, Video
from django.conf import settings
from backend.analyser import Analyser
from backend.utils import media_path_to_video


@Analyser.export("thumbnail")
class Thumbnail:
    def __init__(self):
        self.config = {
            "fps": 1,
            "max_resolution": 128,
            "output_path": "/predictions/thumbnails/",
            "base_url": "http://localhost/thumbnails/",
        }

    def __call__(self, video):

        video_analyse = PluginRun.objects.create(video=video, type="thumbnail", status="Q")

        task = generate_thumbnails.apply_async(
            ({"id": video_analyse.id, "video": video.to_dict(), "config": self.config},)
        )

    def get_results(self, analyse):
        try:
            results = json.loads(bytes(analyse.results).decode("utf-8"))
            results = [{**x, "url": self.config.get("base_url") + f"{analyse.id}/{x['path']}"} for x in results]

            return results
        except:
            return []


@shared_task(bind=True)
def generate_thumbnails(self, args):

    config = args.get("config")
    video = args.get("video")
    id = args.get("id")

    print(f"Video in analyse {id}", flush=True)
    video_db = Video.objects.get(id=video.get("id"))

    PluginRun.objects.filter(video=video_db, id=id).update(status="R")

    video_file = media_path_to_video(video.get("id"), video.get("ext"))

    fps = config.get("fps", 1)

    max_resolution = config.get("max_resolution")
    if max_resolution is not None:
        res = max(video.get("height"), video.get("width"))
        scale = min(max_resolution / res, 1)
        res = (round(video.get("width") * scale), round(video.get("height") * scale))
        video_reader = imageio.get_reader(video_file, fps=fps, size=res)
    else:
        video_reader = imageio.get_reader(video_file, fps=fps)

    os.makedirs(os.path.join(config.get("output_path"), id), exist_ok=True)
    results = []
    for i, frame in enumerate(video_reader):
        thumbnail_output = os.path.join(config.get("output_path"), id, f"{i}.jpg")
        imageio.imwrite(thumbnail_output, frame)
        results.append({"time": i / fps, "path": f"{i}.jpg"})

        PluginRun.objects.filter(video=video_db, id=id).update(progress=i / (fps * video.get("duration")))

    PluginRun.objects.filter(video=video_db, id=id).update(
        progress=1.0, results=json.dumps(results).encode(), status="D"
    )
    return {"status": "done"}
