from typing import Dict, List
import logging

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video
from backend.utils.parser import Parser
from backend.utils.task import Task
from analyser.data import DataManager
from backend.models import AnnotationCategory, TimelineSegment, Annotation, TimelineSegmentAnnotation, TibavaUser
from django.db import transaction


@PluginManager.export_parser("blip_vqa")
class BLIPVQAParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "blip_vqa"},
            "query_term": {"parser": str, "required": True},
            "fps": {"parser": float, "default": 2.0},
            "normalize": {"parser": float, "default": 1},
        }


@PluginManager.export_plugin("blip_vqa")
class BLIPVQA(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(
        self, parameters: Dict, user: TibavaUser = None, video: Video = None, plugin_run: PluginRun = None, **kwargs
    ):
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
            "blip_image_embedding",
            parameters={"fps": parameters.get("fps")},
            inputs={"video": video_id},
            outputs=["embeddings"],
        )

        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "blip_vqa",
            parameters={"query_term": parameters.get("query_term")},
            inputs={**result[0]},
            downloads=["annotations"],
        )
        if result is None:
            raise Exception

        with transaction.atomic():
            with result[1]["annotations"] as data:
                """
                Create a timeline labeled
                """
                # print(f"[{PLUGIN_NAME}] Create annotation timeline", flush=True)
                annotation_timeline_db = Timeline.objects.create(
                    video=video, name=parameters.get("timeline"), type=Timeline.TYPE_ANNOTATION
                )

                category_db, _ = AnnotationCategory.objects.get_or_create(name="Blib", video=video, owner=user)

                for annotation in data.annotations:
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=annotation_timeline_db,
                        start=annotation.start,
                        end=annotation.end,
                    )
                    for label in annotation.labels:
                        annotation_db, _ = Annotation.objects.get_or_create(
                            name=str(label),
                            video=video,
                            category=category_db,
                            owner=user,
                            # color=color,
                        )

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db, timeline_segment=timeline_segment_db
                        )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [],
                    "timelines": {"annotations":annotation_timeline_db.id.hex},
                    "data": {"annotations": result[1]["annotations"].id}
                }
