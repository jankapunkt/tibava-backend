import logging
import json

from django.views import View
from django.http import JsonResponse
from django.conf import settings

# from django.core.exceptions import BadRequest

from backend.models import Video, VideoAnalysisState, Timeline


logger = logging.getLogger(__name__)


class VideoAnalysisStateGet(View):
    def get(self, request):
        print("WWWWWWWWW", flush=True)
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error"}, status=500)

        try:
            video_db = Video.objects.get(id=request.GET.get("video_id"))
        except Video.DoesNotExist:
            return JsonResponse({"status": "error", "type": "not_exist"}, status=500)

        video_analysis_state_db, _ = VideoAnalysisState.objects.get_or_create(
            video=video_db
        )

        return JsonResponse(
            {"status": "ok", "entry": video_analysis_state_db.to_dict()}
        )


class VideoAnalysisStateSetSelectedShots(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error"}, status=500)

        try:
            body = request.body.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            body = request.body

        try:
            data = json.loads(body)
        except Exception as e:
            return JsonResponse({"status": "error"}, status=500)
        print(data)
        if "video_id" not in data:
            return JsonResponse(
                {"status": "error", "type": "missing_values"}, status=500
            )

        if "timeline_id" not in data:
            return JsonResponse(
                {"status": "error", "type": "missing_values"}, status=500
            )

        video_analysis_state_db, _ = VideoAnalysisState.objects.get_or_create(
            video__id=data["video_id"]
        )

        try:
            annotation_timeline_db = Timeline.objects.get(
                video__id=data["video_id"], id=data["timeline_id"]
            )
        except Timeline.DoesNotExist:
            return JsonResponse({"status": "error", "type": "not_exist"}, status=500)

        video_analysis_state_db.selected_shots = annotation_timeline_db
        video_analysis_state_db.save()

        return JsonResponse({"status": "ok"})
