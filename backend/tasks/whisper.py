from typing import Dict, List

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from backend.utils.parser import Parser
from backend.utils.task import Task

from analyser.data import DataManager
from backend.models import (
    Annotation,
    AnnotationCategory,
    PluginRun,
    PluginRunResult,
    TimelineSegmentAnnotation,
    Video,
    User,
    Timeline,
    TimelineSegment,
)

@PluginManager.export_parser("whisper")
class WhisperParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Speech Recognition"},
        }


@PluginManager.export_plugin("whisper")
class Whisper(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(self, parameters: Dict, video: Video = None, user: User = None, plugin_run: PluginRun = None, **kwargs):

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
            "video_to_audio",
            inputs={"video": video_id},
            outputs=["audio"],
        )

        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "whisper",
            inputs={**result[0]},
            downloads=["annotations"],
        )
        if result is None:
            raise Exception
            


        with result[1]["annotations"] as data:
            """
            Create a timeline labeled
            """
            # print(f"[{PLUGIN_NAME}] Create annotation timeline", flush=True)
            annotation_timeline = Timeline.objects.create(
                video=video, name=parameters.get("timeline"), type=Timeline.TYPE_ANNOTATION
            )

            category_db, _ = AnnotationCategory.objects.get_or_create(name="value", video=video, owner=user)


            for annotation in data.annotations:
                timeline_segment_db = TimelineSegment.objects.create(
                    timeline=annotation_timeline,
                    start=annotation.start,
                    end=annotation.end,
                )
                for label in annotation.labels:
                    # color = rgb_to_hex(hsv_to_rgb(h, s, v))
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
