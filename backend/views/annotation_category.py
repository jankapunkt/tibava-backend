import json
import logging
import traceback


from django.views import View
from django.http import JsonResponse

from backend.models import AnnotationCategory

# from django.core.exceptions import BadRequest
class AnnoatationCategoryCreate(View):
    def post(self, request):
        try:

            # decode data
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            if "name" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                annotation_category_db = AnnotationCategory.objects.get(name=data.get("name"))
            except AnnotationCategory.DoesNotExist:
                if "color" in data:
                    annotation_category_db = AnnotationCategory.objects.create(
                        name=data.get("name"), color=data.get("color")
                    )
                else:
                    annotation_category_db = AnnotationCategory.objects.create(name=data.get("name"))

            return JsonResponse({"status": "ok", "entry": annotation_category_db.to_dict()})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class AnnoatationCategoryList(View):
    def get(self, request):
        try:
            query_results = AnnotationCategory.objects.all()

            entries = []
            for annotation_category in query_results:
                entries.append(annotation_category.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
