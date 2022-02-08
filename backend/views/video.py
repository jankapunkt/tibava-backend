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
from backend.analyser import Analyser

import wand.image as wimage

from backend.utils import download_url, download_file, media_url_to_video

from django.views import View
from django.http import HttpResponse, JsonResponse
from django.conf import settings

# from django.core.exceptions import BadRequest


from backend.models import Video


class VideoUpload(View):
    def submit_analyse(self, video, plugins):

        Analyser()(video, plugins)

    def post(self, request):
        try:
            if request.method != "POST":
                return JsonResponse({"status": "error"})

            video_id = uuid.uuid4().hex
            if "file" in request.FILES:
                output_dir = os.path.join(settings.MEDIA_ROOT)

                download_result = download_file(
                    output_dir=output_dir,
                    output_name=video_id,
                    file=request.FILES["file"],
                    max_size=200 * 1024 * 1024,
                    extensions=(".mkv", ".mp4", ".ogv"),
                )

                if download_result["status"] != "ok":
                    return JsonResponse(download_result)

                path = Path(request.FILES["file"].name)
                ext = "".join(path.suffixes)

                reader = imageio.get_reader(download_result["path"])
                fps = reader.get_meta_data()["fps"]
                duration = reader.get_meta_data()["duration"]
                size = reader.get_meta_data()["size"]
                meta = {
                    "name": request.POST.get("title"),
                    "license": request.POST.get("license"),
                    "width": size[0],
                    "height": size[1],
                    "ext": ext,
                    "fps": fps,
                    "duration": duration,
                }
                print(f"Video created {video_id}")
                video_db, created = Video.objects.get_or_create(
                    name=meta["name"],
                    hash_id=video_id,
                    license=meta["license"],
                    ext=meta["ext"],
                    fps=meta["fps"],
                    duration=meta["duration"],
                    width=meta["width"],
                    height=meta["height"],
                )
                if not created:
                    return JsonResponse({"status": "error"})

                analyers = request.POST.get("analyser").split(",")
                self.submit_analyse(video_db, plugins=["thumbnail"] + analyers)

                return JsonResponse(
                    {
                        "status": "ok",
                        "entries": [
                            {
                                "id": video_id,
                                **meta,
                                "url": media_url_to_video(video_id, meta["ext"]),
                            }
                        ],
                    }
                )

            return JsonResponse({"status": "error"})

        except Exception as e:
            print(e)
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoList(View):
    def get(self, request):
        try:
            entries = []
            for video in Video.objects.all():
                entries.append(
                    {
                        "id": video.hash_id,
                        "name": video.name,
                        "license": video.license,
                        "width": video.width,
                        "height": video.height,
                        "ext": video.ext,
                        "fps": video.fps,
                        "duration": video.duration,
                    }
                )
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoGet(View):
    def get(self, request):
        try:
            entries = []
            for video in Video.objects.filter(hash_id=request.GET.get("id")):
                entries.append(
                    {
                        "id": video.id,
                        "hash_id": video.hash_id,
                        "name": video.name,
                        "license": video.license,
                        "width": video.width,
                        "height": video.height,
                        "ext": video.ext,
                        "fps": video.fps,
                        "duration": video.duration,
                        "url": media_url_to_video(video.hash_id, video.ext),
                    }
                )
            if len(entries) != 1:

                return JsonResponse({"status": "error"})
            return JsonResponse({"status": "ok", "entry": entries[0]})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoDelete(View):
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
