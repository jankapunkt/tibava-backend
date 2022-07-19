from celery import shared_task

from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from analyser.client import AnalyserClient


@PluginManager.export("places_classification")
class PlacesClassifier:
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "localhost",
            "analyser_port": 50051,
        }

    def __call__(self, video, parameters=None):
        print(f"[PlacesClassifier] {video}: {parameters}", flush=True)
        if not parameters:
            parameters = []

        task_parameter = {"timeline": "Places"}
        for p in parameters:
            if p["name"] in "timeline":
                task_parameter[p["name"]] = str(p["value"])
            else:
                return False

        pluging_run_db = PluginRun.objects.create(video=video, type="places_classification", status="Q")

        places_classification.apply_async(
            (
                {
                    "id": pluging_run_db.id.hex,
                    "video": video.to_dict(),
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
    id = args.get("id")
    output_path = config.get("output_path")
    analyser_host = args.get("analyser_host", "localhost")
    analyser_port = args.get("analyser_port", 50051)

    video_db = Video.objects.get(id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))
    plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

    plugin_run_db.status = "R"
    plugin_run_db.save()

    # print(f"{analyser_host}, {analyser_port}")

    client = AnalyserClient(analyser_host, analyser_port)
    data_id = client.upload_data(video_file)
    job_id = client.run_plugin("places_classifier", [{"id": data_id, "name": "video"}], [])
    result = client.get_plugin_results(job_id=job_id)
    if result is None:
        return

    embeddings_id = None
    places365_id = None
    places16_id = None
    places3_id = None

    for output in result.outputs:
        if output.name == "embeddings":
            embeddings_id = output.id
        if output.name == "probs_places365":
            places365_id = output.id
        if output.name == "probs_places16":
            places16_id = output.id
        if output.name == "probs_places3":
            places3_id = output.id

    data = client.download_data(places3_id, output_path)

    # TODO create a timeline labeled by most probable places category (per shot)
    # TODO get shot boundaries
    # TODO assign max label to shot boundary
    parent_timeline = Timeline.objects.create(video=video_db, name=parameters.get("timeline"), type="R")

    for index, sub_data in zip(data.index, data.data):

        plugin_run_result_db = PluginRunResult.objects.create(
            plugin_run=plugin_run_db,
            data_id=sub_data.id,
            name="places_classification",
            type="S",  # S stands for SCALAR_DATA
        )
        Timeline.objects.create(
            video=video_db,
            name=index,
            type=Timeline.TYPE_PLUGIN_RESULT,
            plugin_run_result=plugin_run_result_db,
            visualization="SC",
            parent=parent_timeline,
        )

    plugin_run_db.progress = 1.0
    plugin_run_db.status = "D"
    plugin_run_db.save()

    return {"status": "done"}
