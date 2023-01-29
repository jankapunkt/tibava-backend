from ..utils.analyser_client import TaskAnalyserClient

from analyser.data import Shot, ShotsData
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
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from celery import shared_task


CATEGORY_LUT = {"probs_places365": "Places365", "probs_places16": "Places16", "probs_places3": "Places3"}
PLUGIN_NAME = "PlacesClassifier"


@PluginManager.export("places_classification")
class PlacesClassifier:
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

        task_parameter = {"timeline": "Places"}
        for p in parameters:
            if p["name"] in ["timeline", "shot_timeline_id"]:  # defines standard parameter of the task
                task_parameter[p["name"]] = str(p["value"])
            elif p["name"] in ["fps"]:
                task_parameter[p["name"]] = int(p["value"])
            else:
                return False

        pluging_run_db = PluginRun.objects.create(
            video=video, type="places_classification", status=PluginRun.STATUS_QUEUED
        )

        places_classification.apply_async(
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
def places_classification(self, args):

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

    """
    Place Classification
    """
    print(f"[{PLUGIN_NAME}] Run place classification", flush=True)

    data_manager = DataManager(output_path)
    client = TaskAnalyserClient(
        host=analyser_host, port=analyser_port, plugin_run_db=plugin_run_db, manager=data_manager
    )
    data_id = client.upload_file(video_file)
    if data_id is None:
        return
    job_id = client.run_plugin(
        "places_classifier",
        [{"id": data_id, "name": "video"}],
        [{"name": k, "value": v} for k, v in parameters.items()],
    )
    if job_id is None:
        return
    result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)
    if result is None:
        return

    result_ids = {"probs_places365": None, "probs_places16": None, "probs_places3": None}
    for output in result.outputs:
        if output.name in result_ids.keys():  # and parameters.get(output.name):
            result_ids[output.name] = output.id

    if result_ids is None:
        return
    result_probs = {}
    for key in result_ids:
        result_probs[key] = None
        if result_ids[key]:
            result_probs[key] = client.download_data(result_ids[key], output_path)
            if result_probs[key] is None:
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
        # shots = ShotsData(shots=[Shot(start=x.start, end=x.end) for x in shot_timeline_segments])
        shots = data_manager.create_data("ShotsData")
        with shots:
            for x in shot_timeline_segments:
                shots.shots.append(Shot(start=x.start, end=x.end))
        shots_id = client.upload_data(shots)

    """
    Assign most probable label to each shot boundary
    """
    print(f"[{PLUGIN_NAME}] Assign most probable class to each shot", flush=True)
    result_annotations = {}
    if shots_id:
        for key in result_ids:
            result_annotations[key] = None

            if not result_ids[key]:
                continue

            job_id = client.run_plugin(
                "shot_annotator", [{"id": shots_id, "name": "shots"}, {"id": result_ids[key], "name": "probs"}], []
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
            result_annotations[key] = client.download_data(annotation_id, output_path)

    """
    Create a timeline labeled by most probable places category (per shot)
    """
    print(f"[{PLUGIN_NAME}] Create annotation timeline", flush=True)
    annotation_timeline = Timeline.objects.create(
        video=video_db, name=parameters.get("timeline"), type=Timeline.TYPE_ANNOTATION
    )

    segments = {}
    for shot in shots.shots:
        timeline_segment_db = TimelineSegment.objects.create(
            timeline=annotation_timeline,
            start=shot.start,
            end=shot.end,
        )
        segments[shot.start] = timeline_segment_db

    category_lut = {"probs_places365": "Places365", "probs_places16": "Places16", "probs_places3": "Places3"}
    for key in result_annotations:
        category_db, _ = AnnotationCategory.objects.get_or_create(name=category_lut[key], video=video_db, owner=user_db)
        with result_annotations[key] as annotations:
            for annotation in annotations.annotations:
                for label in annotation.labels:
                    # add annotion to TimelineSegment
                    annotation_db, _ = Annotation.objects.get_or_create(
                        name=label, video=video_db, category=category_db, owner=user_db
                    )

                    TimelineSegmentAnnotation.objects.create(
                        annotation=annotation_db, timeline_segment=segments[annotation.start]
                    )

    """
    TODO: Create hierarchical timeline(s) with probability of each place category (per hierarchy level) as scalar data
    """
    print(f"[{PLUGIN_NAME}] Create scalar color (SC) timeline with probabilities for each class", flush=True)
    # if parameters.get("show_probs"):
    with result_probs["probs_places3"] as probs:
        probs.extract_all(data_manager)

        for index, sub_data in zip(probs.index, probs.data):

            plugin_run_result_db = PluginRunResult.objects.create(
                plugin_run=plugin_run_db,
                data_id=sub_data,
                name="places_classification",
                type=PluginRunResult.TYPE_SCALAR,
            )
            Timeline.objects.create(
                video=video_db,
                name=index,
                type=Timeline.TYPE_PLUGIN_RESULT,
                plugin_run_result=plugin_run_result_db,
                visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
                parent=annotation_timeline,
            )

    plugin_run_db.progress = 1.0
    plugin_run_db.status = PluginRun.STATUS_DONE
    plugin_run_db.save()

    return {"status": "done"}
