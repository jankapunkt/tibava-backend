import logging
import traceback
import json

from django.views import View
from django.http import JsonResponse


from backend.models import ClusterItem, Video


class ClusterItemFetch(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error_user_auth"})

            entries = []
            video = Video.objects.get(id=request.GET.get("video_id"))
            for cluster_item in ClusterItem.objects.filter(video=video):
                entries.append(cluster_item.to_dict())

            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class ClusterItemSetDeleted(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error"})

            if "plugin_item_ref_list" not in data:
                return JsonResponse(
                    {"status": "error", "type": "missing_values_plugin_item_ref_list"}
                )
            if "cluster_id" not in data:
                return JsonResponse(
                    {"status": "error", "type": "missing_values_cluster_id"}
                )

            plugin_item_ref_list = list(data.get("plugin_item_ref_list"))
            for plugin_item_ref in plugin_item_ref_list:
                cluster_items = ClusterItem.objects.filter(
                    plugin_item_ref=plugin_item_ref
                )  # TODO change filter to "get" as soon as old clusters are deleted
                if len(cluster_items) > 1:
                    cluster_items = [
                        f
                        for f in cluster_items
                        if f.cluster_timeline_item.cluster_id.hex
                        == data.get("cluster_id")
                    ]
                assert (
                    len(cluster_items) == 1
                ), f"still more than one cluster_item: {cluster_items} \n {data}"
                cluster_items[0].deleted = True
                cluster_items[0].save()

            return JsonResponse({"status": "ok", "entries": plugin_item_ref_list})

        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error_cluster_item_set_deleted"})

        import logging
