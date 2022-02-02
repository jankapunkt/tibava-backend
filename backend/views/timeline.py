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


class TimelineDuplicate(View):
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
            print(data)
            # get timeline entry to duplicate
            timeline_db = Timeline.objects.get(hash_id=data.get("hash_id"))

            # create new hash
            hash_id = uuid.uuid4().hex

            # TODO: store duplicated timeline with new hash into db
            new_timeline_db = Timeline.objects.create(video=timeline_db.video, hash_id=hash_id, name=timeline_db.name, type=timeline_db.type)

        # timeline_segment = TimelineSegment.objects.create(
        #     timeline=timeline,
        #     hash_id=segment_hash_id,
        #     start=shot["start_time_sec"],
        #     end=shot["end_time_sec"],
        #     color="#bababa",
        # # )
            entry = new_timeline_db.to_dict()
            entry["segments"] = []
            for segment in timeline_db.timelinesegment_set.all():
                segment_hash_id = uuid.uuid4().hex
                segment_db = TimelineSegment.objects.create(timeline=new_timeline_db, hash_id=segment_hash_id, start=segment.start,  end=segment.end, color=segment.color)
                entry["segments"].append(segment_db.to_dict())

            return JsonResponse({"status": "ok", "entry": entry})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineRename(View):
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
            # count, _ = Timeline.objects.filter(hash_id=data.get("hash_id")).delete()
            # if count:
            #     return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error"})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})

class TimelineDelete(View):
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
