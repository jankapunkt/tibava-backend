import os
import sys
import logging
import uuid
import math

import imageio
import requests
import json
from typing import Dict, List

from time import sleep

from celery import shared_task

from backend.models import PluginRun, PluginRunResult, Video, Timeline, TimelineSegment
from django.conf import settings
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from analyser.data import DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task


@PluginManager.export_parser("shotdetection")
class ShotDetectionParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Shots"},
            "fps": {"parser": float, "default": 2.0},
        }


@PluginManager.export_plugin("shotdetection")
class ShotDetection(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
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
            "transnet_shotdetection",
            parameters={"fps": parameters.get("fps")},
            inputs={"video": video_id},
            downloads=["shots"],
        )

        if result is None:
            raise Exception

        with result[1]["shots"] as d:
            timeline_id = uuid.uuid4().hex
            # TODO translate the name
            timeline = Timeline.objects.create(
                video=video, id=timeline_id, name=parameters.get("timeline"), type=Timeline.TYPE_ANNOTATION
            )
            for shot in d.shots:
                segment_id = uuid.uuid4().hex
                timeline_segment = TimelineSegment.objects.create(
                    timeline=timeline,
                    id=segment_id,
                    start=shot.start,
                    end=shot.end,
                )

            plugin_run_result_db = PluginRunResult.objects.create(
                plugin_run=plugin_run, data_id=d.id, name="shots", type=PluginRunResult.TYPE_SHOTS
            )
