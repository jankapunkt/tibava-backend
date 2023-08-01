import json
import logging
import traceback
import uuid

from django.views import View
from django.http import JsonResponse


from backend.models import ClusterTimelineItem

class ClusterTimelineItemCreate(View):
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

            if "cluster_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if "timeline_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if not isinstance(data.get("name"), str):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            try:
                cluster_timeline_item = ClusterTimelineItem.objects.create(
                    cluster_id=uuid.UUID(data.get("cluster_id")).hex,
                    timeline_id=data.get("timeline_id"),
                    name=data.get("name"),
                )
            except ClusterTimelineItem.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            cluster_timeline_item.save()
            return JsonResponse({"status": "ok", "entry": cluster_timeline_item.to_dict()})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})

class ClusterTimelineItemRename(View):
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

            if "id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if "name" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if not isinstance(data.get("name"), str):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            try:
                cti = ClusterTimelineItem.objects.get(id=data.get("id"))
            except ClusterTimelineItem.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            cti.name = data.get("name")
            cti.save()
            return JsonResponse({"status": "ok", "entry": cti.to_dict()})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})

class ClusterTimelineItemFetch(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})
            entries = []
            for video in ClusterTimelineItem.objects.all():
                entries.append(video.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})