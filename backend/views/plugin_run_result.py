import os
import time
import json
import logging
import traceback

from django.views import View
from django.http import JsonResponse
from django.conf import settings

# from django.core.exceptions import BadRequest


from backend.models import PluginRunResult, Video, PluginRun
from backend.plugin_manager import PluginManager
from analyser.data import DataManager


class PluginRunResultList(View):
    def get(self, request):
        start_time = time.time()
        # analyser = Analyser()
        # TODO parameters
        data_manager = DataManager("/predictions/")
        # if True:
        try:
            video_id = request.GET.get("video_id")
            if video_id:
                video_db = Video.objects.get(id=video_id)
                analyses = PluginRunResult.objects.filter(plugin_run__video=video_db)
            else:
                analyses = PluginRunResult.objects.all()

            add_results = request.GET.get("add_results", True)
            if add_results:
                # print("A", flush=True)

                entries = []
                for x in analyses:
                    # print("B", flush=True)
                    cache_path = os.path.join(settings.DATA_CACHE_ROOT, f"{x.data_id}.json")
                    # print("C", flush=True)
                    # print(cache_path, flush=True)
                    if os.path.exists(cache_path):
                        with open(cache_path, "r") as f:
                            entries.append(json.load(f))
                    else:
                        # print(f"x {x}")
                        # TODO fix me
                        data = data_manager.load(x.data_id)
                        if data is None:
                            entries.append({**x.to_dict()})
                            continue
                        # print(data)
                        with data:
                            result_dict = {**x.to_dict(), "data": data.to_dict()}
                            with open(cache_path, "w") as f:
                                json.dump(result_dict, f)
                            entries.append(result_dict)

            else:
                entries = [x.to_dict() for x in analyses]
            logging.warning(f"PluginRunResultList {time.time() - start_time}")
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
