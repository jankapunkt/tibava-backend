from celery import shared_task

from backend.models import (
    Annotation,
    AnnotationCategory,
    PluginRun,
    PluginRunResult,
    Video,
    User,
    Timeline,
    TimelineSegment,
    TimelineSegmentAnnotation,
)
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from analyser.data import Shot, ShotsData


LABEL_LUT = {
    "p_ECU": "Extreme Close-Up",
    "p_CU": "Close-Up",
    "p_MS": "Medium Shot",
    "p_FS": "Full Shot",
    "p_LS": "Long Shot",
}
PLUGIN_NAME = "InsightfaceFacesize"


@PluginManager.export("insightface_facesize")
class InsightfaceFacesize:
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

        task_parameter = {"timeline": "Face Detection"}
        for p in parameters:
            if p["name"] in ["timeline", "shot_timeline_id"]:
                task_parameter[p["name"]] = str(p["value"])
            elif p["name"] in ["fps"]:
                task_parameter[p["name"]] = int(p["value"])
            else:
                return False

        pluging_run_db = PluginRun.objects.create(
            video=video, type="insightface_facesize", status=PluginRun.STATUS_QUEUED
        )

        insightface_detection.apply_async(
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
def insightface_detection(self, args):

    config = args.get("config")
    parameters = args.get("parameters")
    video = args.get("video")
    user = args.get("user")
    id = args.get("id")
    output_path = config.get("output_path")
    analyser_host = config.get("analyser_host", "localhost")
    analyser_port = config.get("analyser_port", 50051)

    print(f"[{PLUGIN_NAME}] {video}: {parameters}", flush=True)

    user_db = User.objects.get(id=user.get("id"))
    video_db = Video.objects.get(id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))
    plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

    plugin_run_db.status = PluginRun.STATUS_WAITING
    plugin_run_db.save()

    """
    Run insightface_video_detector_torch
    """
    print(f"[{PLUGIN_NAME}] Run insightface_video_detector_torch", flush=True)
    client = TaskAnalyserClient(host=analyser_host, port=analyser_port, plugin_run_db=plugin_run_db)
    data_id = client.upload_file(video_file)
    if data_id is None:
        return
    job_id = client.run_plugin(
        "insightface_video_detector_torch",
        [{"id": data_id, "name": "video"}],
        [{"name": k, "value": v} for k, v in parameters.items()],
    )
    if job_id is None:
        return
    result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)
    if result is None:
        return

    bbox_output_id = None
    for output in result.outputs:
        if output.name == "bboxes":
            bbox_output_id = output.id

    if bbox_output_id is None:
        return
    """
    Get Shot Size from Face Size
    """
    print(f"[{PLUGIN_NAME}] Predict shot sizes from face sizes", flush=True)
    job_id = client.run_plugin(
        "insightface_facesize",
        [{"id": bbox_output_id, "name": "bboxes"}],
        [{"name": k, "value": v} for k, v in parameters.items()],
    )
    if job_id is None:
        return
    result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)
    if result is None:
        return

    # get results
    facesize_output_id = None
    for output in result.outputs:
        if output.name == "probs":
            facesize_output_id = output.id

    if facesize_output_id is None:
        return
    data = client.download_data(facesize_output_id, output_path)

    if data is None:
        return
    """
    Get shots from timeline with shot boundaries (if selected by the user)
    """
    print(
        f"[{PLUGIN_NAME}] Get shot boundaries from timeline with id: {parameters.get('shot_timeline_id')}", flush=True
    )
    shots_id = None
    if parameters.get("shot_timeline_id"):
        shot_timeline_db = Timeline.objects.get(id=parameters.get("shot_timeline_id"))
        shot_timeline_segments = TimelineSegment.objects.filter(timeline=shot_timeline_db)
        shots_id = client.upload_data(ShotsData(shots=[Shot(start=x.start, end=x.end) for x in shot_timeline_segments]))

    """
    Assign most probable label to each shot boundary
    """
    print(f"[{PLUGIN_NAME}] Assign most probable class to each shot", flush=True)
    if shots_id:
        job_id = client.run_plugin(
            "shot_annotator", [{"id": shots_id, "name": "shots"}, {"id": facesize_output_id, "name": "probs"}], []
        )
        if job_id is None:
            return

        result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)
        if result is None:
            return

        annotation_id = None
        for output in result.outputs:
            if output.name == "annotations":
                annotation_id = output.id
        if annotation_id is None:
            return
        result_annotations = client.download_data(annotation_id, output_path)
        if result_annotations is None:
            return

    """
    Create a timeline labeled by most probable class (per shot)
    """
    print(f"[{PLUGIN_NAME}] Create annotation timeline", flush=True)
    annotation_timeline = Timeline.objects.create(
        video=video_db, name=parameters.get("timeline"), type=Timeline.TYPE_ANNOTATION
    )

    category_db, _ = AnnotationCategory.objects.get_or_create(name="Shot Size", video=video_db, owner=user_db)

    for annotation in result_annotations.annotations:
        # create TimelineSegment
        timeline_segment_db = TimelineSegment.objects.create(
            timeline=annotation_timeline,
            start=annotation.start,
            end=annotation.end,
        )

        for label in annotation.labels:
            # add annotion to TimelineSegment
            annotation_db, _ = Annotation.objects.get_or_create(
                name=LABEL_LUT.get(label, label), video=video_db, category=category_db, owner=user_db
            )

            TimelineSegmentAnnotation.objects.create(annotation=annotation_db, timeline_segment=timeline_segment_db)

    """
    Create timeline(s) with probability of each class as scalar data
    """
    print(f"[{PLUGIN_NAME}] Create scalar color (SC) timeline with probabilities for each class", flush=True)
    for index, sub_data in zip(data.index, data.data):

        plugin_run_result_db = PluginRunResult.objects.create(
            plugin_run=plugin_run_db,
            data_id=sub_data.id,
            name="insightface_facesizes",
            type=PluginRunResult.TYPE_SCALAR,
        )
        Timeline.objects.create(
            video=video_db,
            name=LABEL_LUT.get(index, index),
            type=Timeline.TYPE_PLUGIN_RESULT,
            plugin_run_result=plugin_run_result_db,
            visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
            parent=annotation_timeline,
        )

    plugin_run_db.progress = 1.0
    plugin_run_db.status = PluginRun.STATUS_DONE
    plugin_run_db.save()

    return {"status": "done"}
