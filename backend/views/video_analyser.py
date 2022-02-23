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


from backend.models import Video, VideoAnalyse
from backend.analyser import Analyser


class AnalyserRun(View):
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

            count, _ = Video.objects.filter(hash_id=data.get("hash_id")).delete()
            if count:
                return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error"})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class AnalyserList(View):
    def get(self, request):
        analyser = Analyser()
        try:
            video_id = request.GET.get("video_id")
            if video_id:
                video_db = Video.objects.get(hash_id=video_id)
                analyses = VideoAnalyse.objects.filter(video=video_db)
            else:
                analyses = VideoAnalyse.objects.all()

            add_results = request.GET.get("add_results")
            if add_results:
                entries = []
                for x in analyses:
                    results = analyser.get_results(x)
                    if results:
                        entries.append({**x.to_dict(), "results": results})
                    else:
                        entries.append({**x.to_dict()})
            else:
                entries = [x.to_dict() for x in analyses]

            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
