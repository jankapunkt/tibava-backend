import os
import shutil
import sys
import json
import uuid
import logging
import traceback
import tempfile
import logging
from pathlib import Path

from urllib.parse import urlparse
import imageio
from backend.plugin_manager import PluginManager

import wand.image as wimage

from backend.utils import download_url, download_file, media_url_to_video

from django.views import View
from django.http import HttpResponse, JsonResponse
from django.conf import settings

# from django.core.exceptions import BadRequest


from backend.models import Video


class VideoUpload(View):
    def submit_analyse(self, video, plugins):

        plugin_manager = PluginManager()
        for plugin in plugins:
            plugin_manager(video, plugin)

    def post(self, request):
        try:
            if not request.user.is_authenticated:
                logging.error("VideoUpload::not_authenticated")
                return JsonResponse({"status": "error"})

            if request.method != "POST":
                logging.error("VideoUpload::wrong_method")
                return JsonResponse({"status": "error"})
            video_id_uuid = uuid.uuid4()
            video_id = video_id_uuid.hex
            if "file" in request.FILES:
                output_dir = os.path.join(settings.MEDIA_ROOT)

                download_result = download_file(
                    output_dir=output_dir,
                    output_name=video_id,
                    file=request.FILES["file"],
                    max_size=10 * 1024 * 1024 * 1024,
                    extensions=(".mkv", ".mp4", ".ogv"),
                )

                if download_result["status"] != "ok":
                    logging.error("VideoUpload::download_failed")
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
                video_db, created = Video.objects.get_or_create(
                    name=meta["name"],
                    id=video_id_uuid,
                    license=meta["license"],
                    ext=meta["ext"],
                    fps=meta["fps"],
                    duration=meta["duration"],
                    width=meta["width"],
                    height=meta["height"],
                    owner=request.user,
                )
                if not created:
                    logging.error("VideoUpload::database_create_failed")
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
            print(e, flush=True)
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoList(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})
            entries = []
            for video in Video.objects.filter(owner=request.user):
                entries.append(video.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoGet(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            entries = []
            for video in Video.objects.filter(id=request.GET.get("id"), owner=request.user):
                entries.append(
                    {
                        **video.to_dict(),
                        "url": media_url_to_video(video.id.hex, video.ext),
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
            count, _ = Video.objects.filter(id=data.get("id"), owner=request.user).delete()
            if count:
                return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error"})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
