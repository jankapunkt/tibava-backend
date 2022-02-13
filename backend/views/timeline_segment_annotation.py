import os
import shutil
import sys
import json
from time import time
import uuid
import logging
import traceback
import tempfile
from pathlib import Path

from urllib.parse import urlparse
import imageio

import wand.image as wimage

from backend.utils import download_url, download_file, media_url_to_video

from django.views import View
from django.http import HttpResponse, JsonResponse
from django.conf import settings

from backend.models import TimelineSegment, TimelineSegmentAnnotation, Annotation, AnnotationCategory

# from django.core.exceptions import BadRequest
class TimelineSegmentAnnoatationCreate(View):
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

            # get segment
            try:
                segment_db = TimelineSegment.objects.get(hash_id=data.get("timeline_segment_id"))
            except TimelineSegment.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            # link existing annotation
            if "annotation_id" in data:
                try:
                    annotation_db = Annotation.objects.get(hash_id=data.get("annotation_id"))
                except Annotation.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

                timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
                    timeline_segment=segment_db, annotation=annotation_db
                )
                # if not created:
                #     return JsonResponse({"status": "error", "type": "creation_failed"})
                return JsonResponse({"status": "ok", "entry": timeline_segment_annotation_db.to_dict()})

            # create a annotation from exisitng categories
            elif "annotation_name" in data and "annotation_category_id" in data:
                try:
                    annotation_category_db = AnnotationCategory.objects.get(hash_id=data.get("annotation_category_id"))
                except AnnotationCategory.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

                if "annotation_color" in data:

                    annotation_db = Annotation.objects.create(
                        category=annotation_category_db,
                        name=data.get("annotation_name"),
                        color=data.get("annotation_color"),
                    )
                else:
                    annotation_db = Annotation.objects.create(
                        category=annotation_category_db,
                        name=data.get("annotation_name"),
                    )

                timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
                    timeline_segment=segment_db, annotation=annotation_db
                )
                # if not created:
                #     return JsonResponse({"status": "error", "type": "creation_failed"})
                return JsonResponse({"status": "ok", "entry": timeline_segment_annotation_db.to_dict()})

            elif "annotation_name" in data and "annotation_category_name" in data:
                if "annotation_category_color" in data:

                    annotation_category_db = AnnotationCategory.objects.create(
                        name=data.get("annotation_category_name"),
                        color=data.get("annotation_category_color"),
                    )
                else:
                    annotation_category_db = AnnotationCategory.objects.create(
                        name=data.get("annotation_category_name"),
                    )

                if "annotation_color" in data:
                    annotation_db = Annotation.objects.create(
                        category=annotation_category_db,
                        name=data.get("annotation_name"),
                        color=data.get("annotation_color"),
                    )
                else:
                    annotation_db = Annotation.objects.create(
                        category=annotation_category_db,
                        name=data.get("annotation_name"),
                    )

                timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
                    timeline_segment=segment_db, annotation=annotation_db
                )
                # if not created:
                #     return JsonResponse({"status": "error", "type": "creation_failed"})
                return JsonResponse({"status": "ok", "entry": timeline_segment_annotation_db.to_dict()})

            return JsonResponse({"status": "error", "type": "missing_values"})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineSegmentAnnoatationList(View):
    def get(self, request):
        try:
            query_args = {}

            if "timeline_segment_id" in request.GET:
                query_args["timeline_segment_set__id"] = request.GET.get("timeline_segment_id")

            query_results = TimelineSegmentAnnotation.objects.filter(**query_args)

            entries = []
            for timeline_segment_annotation in query_results:
                entries.append(timeline_segment_annotation.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


# from django.core.exceptions import BadRequest
class TimelineSegmentAnnoatationDelete(View):
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

            # get segment
            num_deleted = 0
            try:
                num_deleted, _ = TimelineSegmentAnnotation.objects.get(
                    hash_id=data.get("timeline_segment_annotation_id")
                ).delete()
            except TimelineSegment.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})
            print(num_deleted)
            if num_deleted == 1:
                return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error"})

        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
