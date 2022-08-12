import time
import logging

from analyser.client import AnalyserClient
from analyser import analyser_pb2
from backend.models import PluginRun


def analyser_status_to_task_status(analyser_status):
    if analyser_status == analyser_pb2.GetPluginStatusResponse.WAITING:
        return PluginRun.STATUS_WAITING
    if analyser_status == analyser_pb2.GetPluginStatusResponse.RUNNING:
        return PluginRun.STATUS_RUNNING
    if analyser_status == analyser_pb2.GetPluginStatusResponse.ERROR:
        return PluginRun.STATUS_ERROR
    return None


def analyser_progress_to_task_progress(analyser_progress):
    return min(max(0.0, analyser_progress), 1.0)


class TaskAnalyserClient(AnalyserClient):
    def get_plugin_results(self, job_id, plugin_run_db=None, progress_fn=None, status_fn=None, timeout=None):
        result = None
        start_time = time.time()
        if progress_fn is None:
            progress_fn = analyser_progress_to_task_progress
        if status_fn is None:
            status_fn = analyser_status_to_task_status
        while True:
            if timeout:
                if time.time() - start_time > timeout:
                    return None
            result = self.get_plugin_status(job_id)
            print("get_plugin_result_loop")
            if plugin_run_db is not None:
                plugin_run_db.progress = progress_fn(result.progress)
                status = status_fn(result.status)
                if status is not None:
                    plugin_run_db.status = status
                print(f"{result.status} {plugin_run_db.progress} task_analyser", flush=True)
                plugin_run_db.save()

            if result.status == analyser_pb2.GetPluginStatusResponse.UNKNOWN:
                logging.error("Job is unknown by the analyser")
                return
            elif result.status == analyser_pb2.GetPluginStatusResponse.WAITING:
                pass
            elif result.status == analyser_pb2.GetPluginStatusResponse.RUNNING:
                pass
            elif result.status == analyser_pb2.GetPluginStatusResponse.ERROR:
                logging.error("Job is crashing")
                return
            elif result.status == analyser_pb2.GetPluginStatusResponse.DONE:
                break
            time.sleep(1.0)

        return result
