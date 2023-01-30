import random

from backend.utils import rgb_to_hex, hsv_to_rgb

from ..utils.analyser_client import TaskAnalyserClient

from analyser.data import Shot, ShotsData

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
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from celery import shared_task
from analyser.data import DataManager

PLUGIN_NAME = "ShotScalarAnnotation"


@PluginManager.export_plugin("shot_scalar_annotation")
class ShotScalarAnnotation:
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(self, parameters=None, **kwargs):
        video = kwargs.get("video")
        user = kwargs.get("user")
        if not parameters:
            parameters = []

        task_parameter = {"timeline": "Shot Scalar Annotation"}
        for p in parameters:
            if p["name"] in [
                "timeline",
                "shot_timeline_id",
                "scalar_timeline_id",
            ]:  # defines standard parameter of the task
                task_parameter[p["name"]] = str(p["value"])
            else:
                return False

        try:
            shot_timeline_db = Timeline.objects.get(id=task_parameter.get("shot_timeline_id"))
            if shot_timeline_db.type != Timeline.TYPE_ANNOTATION:
                return False
        except Timeline.DoesNotExist:
            return False

        try:
            scalar_timeline_db = Timeline.objects.get(id=task_parameter.get("scalar_timeline_id"))
            if scalar_timeline_db.type != Timeline.TYPE_PLUGIN_RESULT:
                return False
            if scalar_timeline_db.plugin_run_result.type != PluginRunResult.TYPE_SCALAR:
                return False
        except Timeline.DoesNotExist:
            return False

        pluging_run_db = PluginRun.objects.create(
            video=video, type="shot_scalar_annotation", status=PluginRun.STATUS_QUEUED
        )

        shot_scalar_annotation.apply_async(
            (
                {
                    "id": pluging_run_db.id.hex,
                    "video": video.to_dict(),
                    "user": {
                        "username": user.get_username(),
                        "email": user.email,
                        "date": user.date_joined,
                        "id": user.id,
                    },
                    "config": self.config,
                    "parameters": task_parameter,
                },
            )
        )
        return True


@shared_task(bind=True)
def shot_scalar_annotation(self, args):

    config = args.get("config")
    parameters = args.get("parameters")
    video = args.get("video")
    user = args.get("user")
    id = args.get("id")
    output_path = config.get("output_path")
    analyser_host = config.get("analyser_host", "localhost")
    analyser_port = config.get("analyser_port", 50051)

    user_db = User.objects.get(id=user.get("id"))
    print(f"[{PLUGIN_NAME}] {video}: {parameters}", flush=True)

    video_db = Video.objects.get(id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))
    plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

    plugin_run_db.status = PluginRun.STATUS_WAITING
    plugin_run_db.save()

    client = TaskAnalyserClient(host=analyser_host, port=analyser_port, plugin_run_db=plugin_run_db)

    try:
        shot_timeline_db = Timeline.objects.get(id=parameters.get("shot_timeline_id"))
        if shot_timeline_db.type != Timeline.TYPE_ANNOTATION:

            plugin_run_db.status = PluginRun.STATUS_ERROR
            plugin_run_db.save()
            return False

        shot_timeline_segments = TimelineSegment.objects.filter(timeline=shot_timeline_db)
        shots = ShotsData(shots=[Shot(start=x.start, end=x.end) for x in shot_timeline_segments])
        shots_id = client.upload_data(shots)
    except Timeline.DoesNotExist:

        plugin_run_db.status = PluginRun.STATUS_ERROR
        plugin_run_db.save()
        return False

    try:
        scalar_timeline_db = Timeline.objects.get(id=parameters.get("scalar_timeline_id"))
        if scalar_timeline_db.type != Timeline.TYPE_PLUGIN_RESULT:

            plugin_run_db.status = PluginRun.STATUS_ERROR
            plugin_run_db.save()
            return False
        if scalar_timeline_db.plugin_run_result.type != PluginRunResult.TYPE_SCALAR:

            plugin_run_db.status = PluginRun.STATUS_ERROR
            plugin_run_db.save()
            return False

        data_manager = DataManager("/predictions/")
        data = data_manager.load(scalar_timeline_db.plugin_run_result.data_id)
        scalar_id = client.upload_data(data)
    except Timeline.DoesNotExist:

        plugin_run_db.status = PluginRun.STATUS_ERROR
        plugin_run_db.save()
        return False

    """
    
    """

    print(f"[{PLUGIN_NAME}] Run shot_scalar_annotation", flush=True)
    job_id = client.run_plugin(
        "shot_scalar_annotator", [{"id": shots_id, "name": "shots"}, {"id": scalar_id, "name": "scalar"}], []
    )

    if job_id is None:
        return
    result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)
    if result is None:
        return

    annotations_id = None
    for output in result.outputs:
        if output.name == "annotations":  # and parameters.get(output.name):
            annotations_id = output.id

    if annotations_id is None:
        return

    annotations = client.download_data(annotations_id, output_path)

    """
    Create a timeline labeled
    """
    print(f"[{PLUGIN_NAME}] Create annotation timeline", flush=True)
    annotation_timeline = Timeline.objects.create(
        video=video_db, name=parameters.get("timeline"), type=Timeline.TYPE_ANNOTATION
    )

    category_db, _ = AnnotationCategory.objects.get_or_create(name="value", video=video_db, owner=user_db)

    values = []
    for annotation in annotations.annotations:
        for label in annotation.labels:
            try:
                values.append(float(label))
            except:
                continue
    min_val = min(values)
    max_val = max(values)

    h = random.random() * 359 / 360
    s = 0.6

    for annotation in annotations.annotations:
        timeline_segment_db = TimelineSegment.objects.create(
            timeline=annotation_timeline,
            start=annotation.start,
            end=annotation.end,
        )
        for label in annotation.labels:
            value = label
            try:
                v = (float(label) - min_val) / (max_val - min_val)
                value = round(float(label), 3)
            except:
                v = 0.6
            color = rgb_to_hex(hsv_to_rgb(h, s, v))
            annotation_db, _ = Annotation.objects.get_or_create(
                name=str(value),
                video=video_db,
                category=category_db,
                owner=user_db,
                color=color,
            )

            TimelineSegmentAnnotation.objects.create(annotation=annotation_db, timeline_segment=timeline_segment_db)

    plugin_run_db.progress = 1.0
    plugin_run_db.status = PluginRun.STATUS_DONE
    plugin_run_db.save()

    return {"status": "done"}
