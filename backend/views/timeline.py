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


from backend.models import Video, Timeline, TimelineSegment


class TimelineList(View):
    def get(self, request):
        try:
            print(request.GET)
            hash_id = request.GET.get("hash_id")
            if hash_id:
                video_db = Video.objects.get(hash_id=hash_id)
                timelines = Timeline.objects.filter(video=video_db)
            else:
                timelines = Timeline.objects.all()

            entries = []
            for timeline in timelines:
                result = timeline.to_dict()
                timeline_segments = TimelineSegment.objects.filter(timeline=timeline)
                result["segments"] = []
                for segment in timeline_segments:
                    result["segments"].append(segment.to_dict())
                entries.append(result)

            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
