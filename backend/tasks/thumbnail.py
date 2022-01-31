import os
import sys
import logging
import uuid
import math

import imageio

from celery import shared_task

from backend.models import VideoAnalyse, Video
from django.conf import settings
from backend.analyser import Analyser
from backend.utils import media_path_to_video


@Analyser.export("thumbnail")
class Thumbnail:
    def __init__(self):
        self.config = {"fps": 1, "max_resolution": 128, "output_path": "/predictions/thumbnails/"}

    def __call__(self, video):

        analyse_hash_id = uuid.uuid4().hex

        video_analyse = VideoAnalyse.objects.create(video=video, hash_id=analyse_hash_id, type="thumbnail", status="Q")

        task = generate_thumbnails.apply_async(
            ({"hash_id": analyse_hash_id, "video": video.to_dict(), "config": self.config},)
        )


@shared_task(bind=True)
def generate_thumbnails(self, args):

    config = args.get("config")
    video = args.get("video")
    hash_id = args.get("hash_id")

    video_db = Video.objects.get(hash_id=video.get("hash_id"))

    VideoAnalyse.objects.filter(video=video_db, hash_id=hash_id).update(status="R")

    video_file = media_path_to_video(video.get("hash_id"), video.get("ext"))

    fps = config.get("fps", 1)

    max_resolution = config.get("max_resolution")
    if max_resolution is not None:
        res = max(video.get("height"), video.get("width"))
        scale = min(max_resolution / res, 1)
        res = (round(video.get("width") * scale), round(video.get("height") * scale))
        video_reader = imageio.get_reader(video_file, fps=fps, size=res)
    else:
        video_reader = imageio.get_reader(video_file, fps=fps)

    os.makedirs(os.path.join(config.get("output_path"), video.get("hash_id")), exist_ok=True)
    for i, frame in enumerate(video_reader):
        thumbnail_output = os.path.join(config.get("output_path"), video.get("hash_id"), f"{i}.jpg")
        imageio.imwrite(thumbnail_output, frame)

        VideoAnalyse.objects.filter(video=video_db, hash_id=hash_id).update(progres=i / (fps * video.get("duration")))

    VideoAnalyse.objects.filter(video=video_db, hash_id=hash_id).update(progres=1.0, status="D")
    return {"status": "done"}
