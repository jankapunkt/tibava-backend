import json
import logging
import traceback
import uuid

from django.views import View
from django.http import JsonResponse

from backend.models import ClusterTimelineItem, Timeline, Video


logger = logging.getLogger(__name__)


class ClusterTimelineItemCreate(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error", "type": "user_auth"})
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error", "type": "data_load"})

            if "cluster_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values_cluster_id"})
            if "video_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values_video"})
            if not isinstance(data.get("name"), str):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            try:
                video = Video.objects.get(id=data.get("video_id"))
                cluster_timeline_item = ClusterTimelineItem.objects.create(
                    cluster_id=uuid.UUID(data.get("cluster_id")).hex,
                    name=data.get("name"),
                    video=video,
                )
                cluster_timeline_item.save()
            except ClusterTimelineItem.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            return JsonResponse({"status": "ok", "entry": cluster_timeline_item.to_dict()})
        except Exception:
            logger.exception('Failed to create cluster timeline item')
            return JsonResponse({"status": "error", "type" : "general"})
        
class ClusterTimelineItemDelete(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error", "type": "user_auth"})
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error", "type": "data_load"})
            count, _ = ClusterTimelineItem.objects.filter(id=data.get("id")).delete()
            if count:
                return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error", "type": "delete_op"})
        except Exception:
            logger.exception('Failed to delete cluster timeline item')
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
                return JsonResponse({"status": "error", "type": "dataload"})

            if "cti_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if "name" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if not isinstance(data.get("name"), str):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            try:
                cti = ClusterTimelineItem.objects.get(id=data.get("cti_id"))
            except ClusterTimelineItem.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            cti.name = data.get("name")
            cti.save()
            return JsonResponse({"status": "ok", "entry": cti.to_dict()})
        except Exception:
            logger.exception('Failed to rename cluster timeline item')
            return JsonResponse({"status": "error"})

class ClusterTimelineItemFetch(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error_user_auth"})
            
            print('cluster id', request.GET.get('cluster_id'))
            print(request.GET)
            run_id = uuid.UUID(hex=request.GET.get('cluster_id'))  # adds dashes
            entries = []
            for cti in ClusterTimelineItem.objects.filter(plugin_run_id=run_id):
                entry = cti.to_dict()
                entries.append(entry)

                entry['items'] = []
                for item in cti.items.all():
                    entry['items'].append(item.to_dict())

            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception('Failed to fetch cluster timeline item')
            return JsonResponse({"status": "error"})
