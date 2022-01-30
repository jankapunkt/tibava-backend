import os
import sys
import json

from frontend.utils import media_url_to_preview, media_url_to_image
from frontend.models import UploadedImage, ImageUserRelation

from django.views import View
from django.http import JsonResponse
from django.conf import settings

import grpc
from iart_indexer import indexer_pb2, indexer_pb2_grpc
from iart_indexer.utils import meta_from_proto, classifier_from_proto, feature_from_proto


class Get(View):
    def rpc_get(self, id):

        host = settings.GRPC_HOST  # "localhost"
        port = settings.GRPC_PORT  # 50051
        channel = grpc.insecure_channel(
            "{}:{}".format(host, port),
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )
        stub = indexer_pb2_grpc.IndexerStub(channel)
        try:
            response = stub.get(indexer_pb2.GetRequest(id=id))

            entry = {"id": response.id}

            entry["meta"] = meta_from_proto(response.meta)
            entry["origin"] = meta_from_proto(response.origin)
            entry["classifier"] = classifier_from_proto(response.classifier)
            entry["feature"] = feature_from_proto(response.feature)

            entry["preview"] = media_url_to_preview(response.id)
            entry["path"] = media_url_to_image(response.id)

            return {"status": "ok", "entry": entry}

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                return {"status": "error"}

            if e.code() == grpc.StatusCode.NOT_FOUND:
                return {"status": "error"}

        return {"status": "error"}

    def add_user_data(self, entries, user):
        ids = [x["id"] for x in entries["entries"]]

        images = ImageUserRelation.objects.filter(image__hash_id__in=ids, user=user)

        user_lut = {x.image.hash_id: {"bookmarked": x.library} for x in images}

        def map_user_data(entry):
            if entry["id"] in user_lut:
                return {**entry, "user": user_lut[entry["id"]]}
            return {**entry, "user": {"bookmarked": False}}

        entries["entries"] = list(map(map_user_data, entries["entries"]))

        return entries

    def post(self, request):
        try:
            body = request.body.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            body = request.body

        try:
            data = json.loads(body)
        except Exception as e:
            print("Search: JSON error: {}".format(e))
            return JsonResponse({"status": "error"})

        if not data.get("id"):
            return JsonResponse({"status": "error"})

        response = self.rpc_get(data.get("id"))
        if response["status"] != "ok":
            try:
                image_db = UploadedImage.objects.get(hash_id=data["id"])

                image_path = os.path.join(
                    settings.UPLOAD_ROOT, image_db.hash_id[0:2], image_db.hash_id[2:4], image_db.hash_id + ".jpg"
                )

                return JsonResponse(
                    {
                        "status": "ok",
                        "entry": {
                            "id": image_db.hash_id,
                            "path": image_path,
                            "preview": image_path,
                            "meta": [{"name": "title", "value_str": image_db.name}],
                        },
                    }
                )
            except UploadedImage.DoesNotExist:
                return JsonResponse({"status": "error"})

        return JsonResponse(response)
