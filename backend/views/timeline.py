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


from backend.models import Video, Timeline, TimelineSegment, TimelineSegmentAnnotation


class TimelineList(View):
    def get(self, request):
        try:

            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})
            video_id = request.GET.get("video_id")
            if video_id:
                video_db = Video.objects.get(id=video_id)
                timelines = Timeline.objects.filter(video=video_db)
            else:
                timelines = Timeline.objects.all()
            timelines = (
                timelines.select_related("video")
                .select_related("plugin_run_result")
                .prefetch_related("timelinesegment_set")
            )

            entries = []
            for timeline in timelines:
                result = timeline.to_dict()
                entries.append(result)
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineDuplicate(View):
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
            # get timeline entry to duplicate
            timeline_db = Timeline.objects.get(id=data.get("id"))
            if not timeline_db:
                return JsonResponse({"status": "error"})

            includeannotations = True
            if data.get("includeannotations") is not None and isinstance(data.get("includeannotations"), bool):
                includeannotations = data.get("includeannotations")

            new_timeline_db = timeline_db.clone(includeannotations=includeannotations)

            if data.get("name") and isinstance(data.get("name"), str):
                new_timeline_db.name = data.get("name")
                new_timeline_db.save()

            # create new hash
            return JsonResponse({"status": "ok", "entry": new_timeline_db.to_dict()})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineCreate(View):
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

            if "video_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            create_args = {"type": "A"}
            try:
                video_db = Video.objects.get(id=data.get("video_id"))
                create_args["video"] = video_db
                create_args["order"] = Timeline.objects.filter(video=video_db).count()
            except Video.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            if "name" not in data:
                create_args["name"] = "timeline"
            elif not isinstance(data.get("name"), str):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})
            else:
                create_args["name"] = data.get("name")
            timeline_db = Timeline.objects.create(**create_args)
            timeline_added = [timeline_db.to_dict()]
            timeline_segment_added = [
                TimelineSegment.objects.create(timeline=timeline_db, start=0.0, end=video_db.duration).to_dict()
            ]

            return JsonResponse(
                {
                    "status": "ok",
                    # "entry": timeline_db.to_dict()
                    "timeline_added": timeline_added,
                    "timeline_segment_added": timeline_segment_added,
                }
            )
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineRename(View):
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
                timeline_db = Timeline.objects.get(id=data.get("id"))
            except Timeline.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            timeline_db.name = data.get("name")
            timeline_db.save()
            return JsonResponse({"status": "ok", "entry": timeline_db.to_dict()})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineChangeVisualization(View):
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
            if "visualization" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if not isinstance(data.get("visualization"), str):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            try:
                timeline_db = Timeline.objects.get(id=data.get("id"))
            except Timeline.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            timeline_db.visualization = data.get("visualization")
            timeline_db.save()
            return JsonResponse({"status": "ok", "entry": timeline_db.to_dict()})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineSetParent(View):
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

            if "timelineId" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if "parentId" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                timeline_db = Timeline.objects.get(id=data.get("timelineId"))
            except Timeline.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            parent_timeline_db = None
            if data.get("parentId"):
                try:
                    parent_timeline_db = Timeline.objects.get(id=data.get("parentId"))
                except Timeline.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

            timeline_db.parent = parent_timeline_db
            timeline_db.save()
            return JsonResponse({"status": "ok", "entry": timeline_db.to_dict()})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineSetCollapse(View):
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

            if "timelineId" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if "collapse" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                timeline_db = Timeline.objects.get(id=data.get("timelineId"))

            except Timeline.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            timeline_db.collapse = data.get("collapse")
            timeline_db.save()
            return JsonResponse({"status": "ok"})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineSetOrder(View):
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

            if "order" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            for idx, timelineId in enumerate(data.get("order")):
                print(idx, timelineId)
                try:
                    timeline_db = Timeline.objects.get(id=timelineId)
                except Timeline.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

                timeline_db.order = idx
                timeline_db.save()
            return JsonResponse({"status": "ok"})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class TimelineDelete(View):
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
            count, _ = Timeline.objects.filter(id=data.get("id")).delete()
            if count:
                return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error"})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
