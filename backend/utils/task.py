import logging

from typing import Dict, List

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.utils import media_path_to_video


class Task:
    def __init__(self):
        pass

    def __call__(self):
        pass

    def upload_video(self, client: TaskAnalyserClient, video: Video) -> str:

        video_file = media_path_to_video(video.id, video.ext)

        data_id = client.upload_file(video_file)
        return data_id

    def run_analyser(
        self,
        client: TaskAnalyserClient,
        analyser: str,
        parameters: Dict,
        inputs: Dict,
        outputs: List,
        downloads: List,
        plugin_run: PluginRun = None,
    ) -> str:

        job_id = client.run_plugin(
            analyser,
            [{"name": k, "id": v} for k, v in inputs.items()],
            [{"name": k, "value": v} for k, v in parameters.items()],
        )
        if job_id is None:
            return None
        logging.info(f"Analyser started: {job_id}")

        result = client.get_plugin_results(job_id=job_id, plugin_run_db=plugin_run)
        if result is None:
            logging.error("Analyser is crashing: {job_id}")
            return None

        result_ids = {}
        for output in result.outputs:
            if output.name in outputs:
                result_ids[output.name] = output.id

        download_data = {}
        for output in result.outputs:
            if output.name in downloads:

                data = client.download_data(output.id)
                download_data[output.name] = data

        return result_ids, download_data
