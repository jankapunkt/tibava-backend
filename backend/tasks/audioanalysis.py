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
import librosa
import ffmpeg


@Analyser.export("audio_waveform")
class Thumbnail:
    def __init__(self):
        self.config = {
            "sr": 8000,
            "max_samples": 50000,
            "output_path": "/predictions/audio_waveform/",
        }

    def __call__(self, video):

        plugin_run_db = PluginRun.objects.create(video=video, type="audio_waveform", status="Q")

        task = audio_wavform.apply_async(
            ({"hash_id": plugin_run_db.hash_id, "video": video.to_dict(), "config": self.config},)
        )

    def get_results(self, analyse):
        try:
            return json.loads(bytes(analyse.results).decode("utf-8"))
        except:
            return []


@shared_task(bind=True)
def audio_wavform(self, args):
    logging.info("audio_wavform:start")
    config = args.get("config")
    video = args.get("video")
    hash_id = args.get("hash_id")

    video_db = Video.objects.get(hash_id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))

    plugin_run_db = PluginRun.objects.get(hash_id=hash_id)
    audio_file = os.path.join(config.get("output_path"), f"{plugin_run_db.hash_id}.mp3")

    plugin_run_db.status = "R"
    plugin_run_db.save()

    # try:

    os.makedirs(config.get("output_path"), exist_ok=True)

    video = ffmpeg.input(video_file)
    audio = video.audio
    stream = ffmpeg.output(audio, audio_file)
    ffmpeg.run(stream)

    y, sr = librosa.load(audio_file, sr=config.get("sr"))
    if config.get("max_samples"):
        target_sr = sr / (len(y) / int(config.get("max_samples")))

        y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
        sr = target_sr

    print(len(y))

    result = json.dumps({"y": y.tolist(), "time": (np.arange(len(y)) / sr).tolist()}).encode()
    # TODO translate the name
    plugin_run_result_db = PluginRunResult.objects.create(plugin_run=plugin_run_db, type="S", data=result)

    timeline_db = Timeline.objects.create(
        video=video_db, name="audio", type="R", plugin_run_result=plugin_run_result_db
    )

    logging.info("audio_wavform:end")
    plugin_run_db.progress = 1.0
    plugin_run_db.results = result
    plugin_run_db.status = "D"
    plugin_run_db.save()
    return {"status": "done"}
