import os
import sys
import json
import uuid
import logging
import traceback
import tempfile

from urllib.parse import urlparse
import imageio

import wand.image as wimage


from backend.utils import image_normalize, upload_url_to_image, download_url, download_file

from django.views import View
from django.http import HttpResponse, JsonResponse
from django.conf import settings


from backend.models import Video
from backend.utils import image_normalize, download_file


class VideoUpload(View):
    def post(self, request):
        try:
            if request.method != "POST":
                return JsonResponse({"status": "error"})

            image = None
            video_hash_id = uuid.uuid4().hex
            title = ""
            if "file" in request.FILES:
                tmpdir = tempfile.mkdtemp()

                download_result = download_file(
                    output_dir=tmpdir,
                    output_name=video_hash_id,
                    file=request.FILES["file"],
                    max_size=200 * 1024 * 1024,
                    extensions=(".mkv", ".mp4", ".ogv"),
                )
                if download_result["status"] != "ok":
                    return JsonResponse(download_result)
                # try:
                output_dir = os.path.join(settings.UPLOAD_ROOT)
                os.makedirs(output_dir, exist_ok=True)
                # except:
                #     return JsonResponse({"status": "error", "error": {"type": "file_is_not_readable"}})

                reader = imageio.get_reader(download_result["path"])
                fps = reader.get_meta_data()["fps"]
                title = download_result["origin"]
                print(fps)
                print(reader.get_meta_data())
                print(title)

            if "url" in request.POST:
                tmpdir = tempfile.mkdtemp()

                image_result = download_url(
                    output_dir=tmpdir,
                    output_name=image_id,
                    url=request.POST["url"],
                    max_size=4 * 1024 * 1024,
                    extensions=(".gif", ".jpg", ".png", ".tif", ".tiff", ".bmp"),
                )
                if image_result["status"] != "ok":
                    return JsonResponse(image_result)
                try:
                    output_dir = os.path.join(settings.UPLOAD_ROOT, image_id[0:2], image_id[2:4])
                    os.makedirs(output_dir, exist_ok=True)
                    wimage.Image(filename=image_result["path"]).save(
                        filename=os.path.join(output_dir, image_id + ".jpg")
                    )
                except:
                    return JsonResponse({"status": "error", "error": {"type": "file_is_not_readable"}})

                image = imageio.imread(image_result["path"])
                image = image_normalize(image)
                title = image_result["origin"]

            if image is not None:
                output_dir = os.path.join(settings.UPLOAD_ROOT, image_id[0:2], image_id[2:4])
                os.makedirs(output_dir, exist_ok=True)
                imageio.imwrite(os.path.join(output_dir, image_id + ".jpg"), image)

                image_db, created = UploadedImage.objects.get_or_create(name=title, hash_id=image_id)

                return JsonResponse(
                    {
                        "status": "ok",
                        "entries": [{"id": image_id, "meta": {"title": title}, "path": upload_url_to_image(image_id)}],
                    }
                )

            return JsonResponse({"status": "error"})

        except Exception as e:
            print(e)
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
