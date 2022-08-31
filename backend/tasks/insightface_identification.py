from celery import shared_task
import imageio.v3 as iio

from analyser.data import DataManager, ImageData, ImagesData, generate_id, create_data_path
from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from .task import TaskAnalyserClient


PLUGIN_NAME = "InsightfaceIdentification"


@PluginManager.export("insightface_identification")
class InsightfaceIdentification:
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": "analyser",
            "analyser_port": 50051,
        }

    def __call__(self, parameters=None, **kwargs):

        video = kwargs.get("video")
        user = kwargs.get("user")

        print(f"PARAMETERS ############# {parameters}")
        if not parameters:
            parameters = []

        task_parameter = {"timeline": "Face Identification"}
        for p in parameters:
            if p["name"] in ["aggregation", "timeline"]:
                task_parameter[p["name"]] = str(p["value"])
            elif p["name"] in ["fps"]:
                task_parameter[p["name"]] = int(p["value"])
            elif p["name"] in ["query_images"]:
                task_parameter[p["name"]] = [str(p["path"])]
            else:
                return False

        pluging_run_db = PluginRun.objects.create(
            video=video, type="insightface_identification", status=PluginRun.STATUS_QUEUED
        )

        insightface_identification.apply_async(
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
def insightface_identification(self, args):
    config = args.get("config")
    parameters = args.get("parameters")
    video = args.get("video")
    query_images = parameters.get("query_images")
    id = args.get("id")
    output_path = config.get("output_path")
    analyser_host = config.get("analyser_host", "localhost")
    analyser_port = config.get("analyser_port", 50051)
    print(f"[InsightfaceVideoDetector] {video}: {parameters}", flush=True)

    video_db = Video.objects.get(id=video.get("id"))
    video_file = media_path_to_video(video.get("id"), video.get("ext"))
    plugin_run_db = PluginRun.objects.get(video=video_db, id=id)

    plugin_run_db.status = PluginRun.STATUS_WAITING
    plugin_run_db.save()

    manager = DataManager()
    client = TaskAnalyserClient(host=analyser_host, port=analyser_port, plugin_run_db=plugin_run_db, manager=manager)
    """
    UPLOAD QUERY IMAGE(S)
    """
    print(f"[InsightfaceImageDetector] Upload query images", flush=True)
    images = []
    for image_path in query_images:
        image_id = generate_id()
        image = iio.imread(image_path)
        tmp_output_path = create_data_path(manager.data_dir, image_id, "jpg")
        iio.imwrite(tmp_output_path, image)
        images.append(ImageData(id=image_id, ext="jpg"))

    data = ImagesData(images=images)
    query_image_ids = client.upload_data(data)

    """
    UPLOAD VIDEO
    """
    data_id = client.upload_file(video_file)
    if data_id is None:
        return

    """
    FACE DETECTION FROM TARGET VIDEO
    """
    print(f"[InsightfaceVideoDetector] Detect faces in video: {data_id}", flush=True)
    job_id = client.run_plugin(
        "insightface_video_detector",
        [{"id": data_id, "name": "video"}],
        [{"name": k, "value": v} for k, v in parameters.items()],
    )
    if job_id is None:
        return
    result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run_db)
    if result is None:
        return

    target_kpss_id = None
    for output in result.outputs:
        if output.name == "kpss":
            target_kpss_id = output.id

    if target_kpss_id is None:
        return

    """
    FACIAL FEATURE EXTRACTION FROM TARGET VIDEO
    """
    print(f"[InsightfaceVideoDetector] Extract facial features from faces: {data_id}", flush=True)

    job_id = client.run_plugin(
        "insightface_video_feature_extractor",
        [{"id": data_id, "name": "video"}, {"id": target_kpss_id, "name": "kpss"}],
        [],
    )

    result = client.get_plugin_results(job_id=job_id)
    target_features_id = None
    for output in result.outputs:
        if output.name == "features":
            target_features_id = output.id

    """
    FACE DETECTION FROM QUERY IMAGE(S)
    """
    print(f"[InsightfaceImageDetector] Detect faces in query images: {query_image_ids}", flush=True)
    job_id = client.run_plugin("insightface_image_detector", [{"id": query_image_ids, "name": "images"}], [])

    result = client.get_plugin_results(job_id=job_id)
    if result is None:
        return

    query_kpss_id = None
    for output in result.outputs:
        if output.name == "kpss":
            query_kpss_id = output.id

    """
    FACIAL FEATURE EXTRACTION FROM QUERY IMAGE(S)
    """
    print(f"[InsightfaceImageDetector] Detect faces in query images: {data_id}", flush=True)
    job_id = client.run_plugin(
        "insightface_image_feature_extractor",
        [{"id": query_image_ids, "name": "images"}, {"id": query_kpss_id, "name": "kpss"}],
        [],
    )

    result = client.get_plugin_results(job_id=job_id)
    query_features_id = None
    for output in result.outputs:
        if output.name == "features":
            query_features_id = output.id

    """
    FACE SIMILARITY
    """
    print(f"[CosineSimilarity] Calculate cosine similarity", flush=True)
    job_id = client.run_plugin(
        "cosine_similarity",
        [{"id": target_features_id, "name": "target_features"}, {"id": query_features_id, "name": "query_features"}],
        [],
    )

    result = client.get_plugin_results(job_id=job_id)
    for output in result.outputs:
        if output.name == "probs":
            similarities_id = output.id

    data = client.download_data(similarities_id, output_path)

    """
    Create timeline with similarity of the faces in the video to the query images
    """
    print(f"[{PLUGIN_NAME}] Create scalar color (SC) timeline with face similarities", flush=True)

    plugin_run_result_db = PluginRunResult.objects.create(
        plugin_run=plugin_run_db,
        data_id=data.id,
        name="face_identification",
        type=PluginRunResult.TYPE_SCALAR,
    )
    Timeline.objects.create(
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
