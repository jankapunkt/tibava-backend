import logging
import traceback
import json

from django.views import View
from django.http import JsonResponse


from backend.models import Face, Video

class FaceFetch(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error_user_auth"})
            
            entries = []
            video = Video.objects.get(id=request.GET.get("video_id"))
            for face in Face.objects.filter(video=video):
                entries.append(face.to_dict())
            
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})

class FaceSetDeleted(View):
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
            
            if "face_ref_list" not in data:
                return JsonResponse({"status": "error", "type": "missing_values_face_ref_list"})
            
            face_ref_list = list(data.get("face_ref_list"))
            for face_ref in face_ref_list:
                face = Face.objects.get(face_ref=face_ref)
                face.deleted = True
                face.save()
            
            return JsonResponse({"status": "ok", "entries": face_ref_list})
            
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error_cti_set_timeline"})