from celery import shared_task
import logging
import redis

from .task import TaskAnalyserClient

from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video


@PluginManager.export("clip")
class CLIP:
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(self, parameters=None, **kwargs):
        video = kwargs.get("video")
        if not parameters:
            parameters = []

        task_parameter = {"timeline": "clip"}
        for p in parameters:
            if p["name"] in ["timeline", "search_term"]:
                task_parameter[p["name"]] = str(p["value"])
            elif p["name"] in ["fps"]:
                task_parameter[p["name"]] = int(p["value"])
            else:
                return False

        video_analyse = PluginRun.objects.create(video=video, type="clip", status=PluginRun.STATUS_QUEUED)

        task = clip.apply_async(
            (
                {
                    "id": video_analyse.id.hex,
                    "video": video.to_dict(),
                    "config": self.config,
                    "parameters": task_parameter,
                },
            )
        )
        return True


@shared_task(bind=True)
def clip(self, args):

    config = args.get("config")
    parameters = args.get("parameters")
    video = args.get("video")
    id = args.get("id")
    output_path = config.get("output_path")
    analyser_host = config.get("analyser_host", "localhost")
    analyser_port = config.get("analyser_port", 50051)

    print(f"[CLIP] {video}: {parameters}", flush=True)

    video_db = Video.objects.get(id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))
    plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

    plugin_run_db.status = PluginRun.STATUS_WAITING
    plugin_run_db.save()

    # print(f"{analyser_host}, {analyser_port}")
    client = TaskAnalyserClient(host=analyser_host, port=analyser_port, plugin_run_db=plugin_run_db)

    r = redis.Redis()
    data_id = r.get(f"video_{video.get('id')}")
    # data_id = None
    if data_id is None:
        print(f"Video not exist in the analyser", flush=True)
        data_id = client.upload_file(video_file)
        if data_id is None:
            return
        r.set(f"video_{video.get('id')}", data_id)
        # print(f"{data_id}", flush=True)

    embd_id = r.get(f"data_{data_id}")
    if embd_id is None:
        print(f"Video Embedding not exist in the analyser", flush=True)
        # generate image embeddings
        job_id = client.run_plugin(
            "clip_image_embedding",
            [{"id": data_id, "name": "video"}],
            [{"name": k, "value": v} for k, v in parameters.items()],
        )
        if job_id is None:
            return
        logging.info(f"Job clip_image_embedding started: {job_id}")

        result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)
        if result is None:
            logging.error("Job is crashing")
            return

        embd_id = None
        for output in result.outputs:
            if output.name == "embeddings":
                embd_id = output.id
                break

        if embd_id is None:
            return
        r.set(f"data_{data_id}", embd_id)
    logging.info(f"finished job with resulting embedding id: {embd_id}")
    # calculate similarities between image embeddings and search term
    job_id = client.run_plugin(
        "clip_probs",
        [{"id": embd_id, "name": "embeddings"}],
        [{"name": k, "value": v} for k, v in parameters.items()],
    )
    if job_id is None:
        return
    logging.info(f"Job clip_probs started: {job_id}")

    result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)
    if result is None:
        logging.error("Job is crashing")
        return

    probs_id = None
    for output in result.outputs:
        if output.name == "probs":
            probs_id = output.id

    if probs_id is None:
        return
    # logging.info(f"Job clip done: {freq_id}")

    data = client.download_data(probs_id, output_path)
    if data is None:
        return

    plugin_run_result_db = PluginRunResult.objects.create(
        plugin_run=plugin_run_db, data_id=data.id, name="clip", type=PluginRunResult.TYPE_SCALAR
    )

    _ = Timeline.objects.create(
        video=video_db,
        name=parameters.get("timeline"),
        type=Timeline.TYPE_PLUGIN_RESULT,
        plugin_run_result=plugin_run_result_db,
        visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
    )

    plugin_run_db.progress = 1.0
    plugin_run_db.status = PluginRun.STATUS_DONE
    plugin_run_db.save()

    return {"status": "done"}
