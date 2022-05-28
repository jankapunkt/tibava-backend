import os
import sys
import logging
import uuid

import json
import numpy as np

from time import sleep

from celery import shared_task

from backend.models import PluginRun, Video, Timeline, PluginRunResult
from django.conf import settings
from backend.analyser import Analyser
from backend.utils import media_path_to_video

from sklearn.cluster import KMeans

import imageio


@Analyser.export("mean_color")
class Thumbnail:
    def __init__(self):
        self.config = {
            "k": 8,
            "fps": 0.2,
            "max_iter": 20,
            "max_samples": 2000,
            "max_resolution": 128,
            "output_path": "/predictions/mean_color/",
        }

    def __call__(self, video):

        plugin_run_db = PluginRun.objects.create(video=video, type="mean_color", status="Q")

        task = mean_color.apply_async(
            ({"hash_id": plugin_run_db.hash_id, "video": video.to_dict(), "config": self.config},)
        )

    def get_results(self, analyse):
        try:
            return json.loads(bytes(analyse.results).decode("utf-8"))
        except:
            return []


@shared_task(bind=True)
def mean_color(self, args):
    logging.info("mean_color:start")
    config = args.get("config")
    video = args.get("video")
    hash_id = args.get("hash_id")

    video_db = Video.objects.get(hash_id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))

    plugin_run_db = PluginRun.objects.get(hash_id=hash_id)

    plugin_run_db.status = "R"
    plugin_run_db.save()

    os.makedirs(config.get("output_path"), exist_ok=True)

    fps = config.get("fps", 1)

    max_resolution = config.get("max_resolution")
    if max_resolution is not None:
        res = max(video.get("height"), video.get("width"))
        scale = min(max_resolution / res, 1)
        res = (round(video.get("width") * scale), round(video.get("height") * scale))
        video_reader = imageio.get_reader(video_file, fps=fps, size=res)
    else:
        video_reader = imageio.get_reader(video_file, fps=fps)

    y = []
    time = []
    for i, frame in enumerate(video_reader):
        image = frame.reshape((frame.shape[0] * frame.shape[1], 3))
        cls = KMeans(n_clusters=config.get("k"), max_iter=config.get("max_iter"))
        cls.fit(image)
        y.append(cls.cluster_centers_)
        time.append(i / fps)
    # result = json.dumps({"y": y.tolist(), "time": (np.arange(len(y)) / sr).tolist()}).encode()
    # # TODO translate the name
    # plugin_run_result_db = PluginRunResult.objects.create(plugin_run=plugin_run_db, type="S", data=result)

    # timeline_db = Timeline.objects.create(
    #     video=video_db, name="audio", type="R", plugin_run_result=plugin_run_result_db
    # )

    logging.info("mean_color:end")
    plugin_run_db.progress = 1.0
    # plugin_run_db.results = result
    plugin_run_db.status = "D"
    plugin_run_db.save()
    return {"status": "done"}
