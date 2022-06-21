from celery import shared_task

from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from analyser.client import AnalyserClient


@PluginManager.export("deepface_emotion")
class DeepfaceEmotion:
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "localhost",
            "analyser_port": 50051,
        }

    def __call__(self, video, parameters=None):
        print(f"[DeepfaceEmotion] {video}: {parameters}", flush=True)
        if not parameters:
            parameters = []

        task_parameter = {"timeline": "Face Detection"}
        for p in parameters:
            if p["name"] in "timeline":
                task_parameter[p["name"]] = str(p["value"])
            else:
                return False

        pluging_run_db = PluginRun.objects.create(video=video, type="deepface_emotion", status="Q")

        deepface_emotion.apply_async(
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
def deepface_emotion(self, args):
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

    # run insightface_detector
    client = AnalyserClient(analyser_host, analyser_port)
    data_id = client.upload_data(video_file)
    job_id = client.run_plugin("insightface_detector", [{"id": data_id, "name": "video"}], [])
    result = client.get_plugin_results(job_id=job_id)
    if result is None:
        return

    faceimg_output_id = None
    for output in result.outputs:
        if output.name == "images":
            faceimg_output_id = output.id

    # run deepface_emotion
    job_id = client.run_plugin("deepface_emotion", [{"id": faceimg_output_id, "name": "images"}], [])
    result = client.get_plugin_results(job_id=job_id)
    if result is None:
        return

    # get emotions
    emotions_output_id = None
    for output in result.outputs:
        if output.name == "probs":
            emotions_output_id = output.id

    data = client.download_data(emotions_output_id, output_path)

    # create timelines
    for index, sub_data in zip(data.index, data.data):
        label_lut = {
            "p_angry": "Angry",
            "p_disgust": "Disgust",
            "p_fear": "Fear",
            "p_happy": "Happy",
            "p_sad": "Sad",
            "p_surprise": "Surprise",
            "p_neutral": "Neural",
        }

        # TODO create a timeline labeled by most probable emotion (per shot)
        # TODO get shot boundaries
        # TODO assign max label to shot boundary

        plugin_run_result_db = PluginRunResult.objects.create(
            plugin_run=plugin_run_db, data_id=sub_data.id, name="face_emotion", type="S",  # S stands for SCALAR_DATA
        )
        Timeline.objects.create(
            video=video_db,
            name=parameters.get("timeline") + f" {label_lut.get(index, index)}",
            type=Timeline.TYPE_PLUGIN_RESULT,
            plugin_run_result=plugin_run_result_db,
            visualization="SC",
        )

    # set status
    plugin_run_db.progress = 1.0
    plugin_run_db.status = "D"
    plugin_run_db.save()

    return {"status": "done"}
