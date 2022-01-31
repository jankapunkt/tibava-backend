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


from backend.models import Video


class VideoUpload(View):
    def post(self, request):
        try:
            if request.method != "POST":
                return JsonResponse({"status": "error"})

            image = None
            video_hash_id = uuid.uuid4().hex
            title = ""
            if "file" in request.FILES:
                output_dir = os.path.join(settings.MEDIA_ROOT)

                download_result = download_file(
                    output_dir=output_dir,
                    output_name=video_hash_id,
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
                    "height": size[0],
                    "ext": ext,
                    "fps": fps,
                    "duration": duration,
                }

                video_db, created = Video.objects.get_or_create(
                    name=meta["name"],
                    hash_id=video_hash_id,
                    license=meta["license"],
                    ext=meta["ext"],
                    fps=meta["fps"],
                    duration=meta["duration"],
                    width=meta["width"],
                    height=meta["height"],
                )
                if not created:
                    return JsonResponse({"status": "error"})

                return JsonResponse(
                    {
                        "status": "ok",
                        "entries": [
                            {
                                "id": video_db.id,
                                "hash_id": video_hash_id,
                                "meta": meta,
                                "url": media_url_to_video(video_hash_id, meta["ext"]),
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
                        "id": video.id,
                        "hash_id": video.hash_id,
                        "meta": {
                            "name": video.name,
                            "license": video.license,
                            "width": video.width,
                            "height": video.height,
                            "ext": video.ext,
                            "fps": video.fps,
                            "duration": video.duration,
                        },
                    }
                )
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoGet(View):
    def get(self, request):
        try:
            # print(request)
            # print(request.GET)
            # print(request.GET.get("hash_id"))
            entries = []
            for video in Video.objects.filter(hash_id=request.GET.get("hash_id")):
                entries.append(
                    {
                        "id": video.id,
                        "hash_id": video.hash_id,
                        "meta": {
                            "name": video.name,
                            "license": video.license,
                            "width": video.width,
                            "height": video.height,
                            "ext": video.ext,
                            "fps": video.fps,
                            "duration": video.duration,
                        },
                        "url": media_url_to_video(video.hash_id, video.ext),
                    }
                )
            if len(entries) != 1:

                return JsonResponse({"status": "error"})
            return JsonResponse({"status": "ok", "entry": entries[0]})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
