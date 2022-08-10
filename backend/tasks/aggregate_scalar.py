from celery import shared_task

from backend.models import (
    PluginRun,
    PluginRunResult,
    Video,
    Timeline,
)
from backend.plugin_manager import PluginManager

from analyser.client import AnalyserClient
from analyser.data import DataManager, ListData

PLUGIN_NAME = "AggregateScalar"


@PluginManager.export("aggregate_scalar")
class AggregateScalar:
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

        task_parameter = {"timeline": "Aggregated Timeline"}
        for p in parameters:
            if p["name"] in ["timeline", "aggregation"]:
                task_parameter[p["name"]] = str(p["value"])
            elif p["name"] in ["timeline_ids"]:
                task_parameter[p["name"]] = p["value"]
            else:
                return False

        pluging_run_db = PluginRun.objects.create(video=video, type="aggregate_scalar", status="Q")
        aggregate_scalar.apply_async(
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
def aggregate_scalar(self, args):

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
    Get probabilities from scalar timelines
    """
    timelines = []
    for timeline_id in parameters.get("timeline_ids"):
        print(
            f"[{PLUGIN_NAME}] Get probabilities from scalar timeline with id: {timeline_id}",
            flush=True,
        )

        timeline_db = Timeline.objects.get(id=timeline_id)
        plugin_data_id = timeline_db.plugin_run_result.data_id

        data_manager = DataManager("/predictions/")
        data = data_manager.load(plugin_data_id)

        timelines.append(data)

    data_id = client.upload_data(ListData(data=[x for x in timelines]))

    """
    Create timeline(s) with probability of each class as scalar data
    """
    print(f"[{PLUGIN_NAME}] Aggregate probabilities", flush=True)

    job_id = client.run_plugin(
        "aggregate_scalar",
        [{"id": data_id, "name": "timelines"}],
        [{"name": k, "value": v} for k, v in parameters.items()],
    )
    result = client.get_plugin_results(job_id=job_id)
    if result is None:
        return

    probs_id = None
    for output in result.outputs:
        if output.name == "probs":
            probs_id = output.id

    data = client.download_data(probs_id, output_path)

    plugin_run_result_db = PluginRunResult.objects.create(
        plugin_run=plugin_run_db,
        data_id=data.id,
        name="aggregate_scalar",
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
