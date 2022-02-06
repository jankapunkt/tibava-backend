import os
import shutil
import sys
import json
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

# from django.core.exceptions import BadRequest


from backend.models import TimelineSegment

class TimelineSegmentList(View):
    def get(self, request):
        try:
            timeline_id = request.GET.get("timeline_id")
            if timeline_id:
                timeline_segments = TimelineSegment.objects.filter(timeline__hash_id=timeline_id)
            else:
                timeline_segments = TimelineSegment.objects.all()

            entries = []
            for segment in timeline_segments:
                entries.append(segment.to_dict())
            print(entries)
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineSegmentDelete(View):
    def post(self, request):
        try:
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error"})
            count, _ = Timeline.objects.filter(hash_id=data.get("hash_id")).delete()
            if count:
                return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error"})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
