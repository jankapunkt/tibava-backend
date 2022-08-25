import time
import logging

import grpc

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
    def __init__(self, *args, plugin_run_db=None, timeout=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_run_db = plugin_run_db
        self.timeout = timeout

    def list_plugins(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().list_plugins(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logging.error(f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}")
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def upload_data(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().upload_data(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logging.error(f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}")
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def upload_file(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().upload_file(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logging.error(f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}")
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def run_plugin(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().run_plugin(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logging.error(f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}")
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def get_plugin_status(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().get_plugin_status(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logging.error(f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}")
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def download_data(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().download_data(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logging.error(f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}")
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def download_data_to_blob(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().download_data_to_blob(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logging.error(f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}")
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def get_plugin_results(self, job_id, plugin_run_db=None, progress_fn=None, status_fn=None, timeout=None):
        plugin_run_db = plugin_run_db if plugin_run_db is not None else self.plugin_run_db

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
            try:
                result = self.get_plugin_status(job_id)
            except grpc.RpcError as rpc_error:
                logging.error(f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}")
                if plugin_run_db:
                    plugin_run_db.status = PluginRun.STATUS_ERROR
                    plugin_run_db.save()

                return None
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
