from celery import shared_task

from backend.models import (
    PluginRun,
    PluginRunResult,
    Video,
    Timeline,
    TimelineSegment,
)
from backend.plugin_manager import PluginManager

from analyser.client import AnalyserClient
from analyser.data import Shot, ShotsData

PLUGIN_NAME = "ShotDensity"


@PluginManager.export("shot_density")
class ShotDensity:
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

        task_parameter = {"timeline": "Shot Density"}
        for p in parameters:
            if p["name"] in ["timeline", "shot_timeline_id"]:
                task_parameter[p["name"]] = str(p["value"])
            elif p["name"] in ["bandwidth", "fps"]:
                task_parameter[p["name"]] = int(p["value"])
            else:
                return False

        pluging_run_db = PluginRun.objects.create(video=video, type="shot_density", status="Q")

        shot_density.apply_async(
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
def shot_density(self, args):

    config = args.get("config")
    parameters = args.get("parameters")
    video = args.get("video")
    # user = args.get("user")
    id = args.get("id")
    output_path = config.get("output_path")
    analyser_host = config.get("analyser_host", "localhost")
    analyser_port = config.get("analyser_port", 50051)

    print(f"[{PLUGIN_NAME}] {video}: {parameters}", flush=True)

    # user_db = User.objects.get(id=user.get("id"))
    video_db = Video.objects.get(id=video.get("id"))
    # video_file = media_path_to_video(video.get("id"), video.get("ext"))
    plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

    plugin_run_db.status = "R"
    plugin_run_db.save()

    client = AnalyserClient(analyser_host, analyser_port)

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
    Create timeline(s) with probability of each class as scalar data
    """
    print(f"[{PLUGIN_NAME}] Get shot density", flush=True)

    job_id = client.run_plugin(
        "shot_density", [{"id": shots_id, "name": "shots"}], [{"name": k, "value": v} for k, v in parameters.items()]
    )
    result = client.get_plugin_results(job_id=job_id)
    if result is None:
        return

    shot_density_id = None
    for output in result.outputs:
        if output.name == "shot_density":
            shot_density_id = output.id

    data = client.download_data(shot_density_id, output_path)
    print(data)

    plugin_run_result_db = PluginRunResult.objects.create(
        plugin_run=plugin_run_db,
        data_id=data.id,
        name="shot_density",
        type="S",  # S stands for SCALAR_DATA
    )
    Timeline.objects.create(
        video=video_db,
        name=parameters.get("timeline"),
        type=Timeline.TYPE_PLUGIN_RESULT,
        plugin_run_result=plugin_run_result_db,
        visualization="SC",
    )

    plugin_run_db.progress = 1.0
    plugin_run_db.status = "D"
    plugin_run_db.save()

    return {"status": "done"}
