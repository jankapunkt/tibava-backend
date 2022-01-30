import os
import sys
import json
import uuid
import logging
import traceback

import dateutil.parser

import zipfile
import tarfile

from pathlib import Path


import csv
import json

from django.views import View
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.db.models import Count

from frontend.models import Image, ImageUserRelation


class BookmarkAdd(View):
    def parse_request(self, request):
        if "id" in request:
            image_id = request["id"]
        else:
            return None

        return {"image_id": image_id}

    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "error": {"type": "not_authenticated"}})

        try:
            body = request.body.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            body = request.body

        try:
            data = json.loads(body)
        except Exception as e:
            return JsonResponse({"status": "error"})

        parsed_request = self.parse_request(data)
        if parsed_request is None:
            return JsonResponse({"status": "error"})

        image_db, created = Image.objects.get_or_create(hash_id=parsed_request["image_id"])

        image_user_db, created = ImageUserRelation.objects.get_or_create(user=request.user, image=image_db)

        image_user_db.library = True
        image_user_db.save()

        return JsonResponse({"status": "ok"})


class BookmarkRemove(View):
    def parse_request(self, request):
        if "id" in request:
            image_id = request["id"]
        else:
            return None

        return {"image_id": image_id}

    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "error": {"type": "not_authenticated"}})

        try:
            body = request.body.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            body = request.body

        try:
            data = json.loads(body)
        except Exception as e:
            return JsonResponse({"status": "error"})

        parsed_request = self.parse_request(data)
        if parsed_request is None:
            return JsonResponse({"status": "error"})

        image_db = Image.objects.get(hash_id=parsed_request["image_id"])

        print(image_db, flush=True)

        image_user_db = ImageUserRelation.objects.filter(user=request.user, image=image_db)
        image_user_db.update(library=False)

        return JsonResponse({"status": "ok"})


class BookmarkList(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "error": {"type": "not_authenticated"}})

        image_user_db = ImageUserRelation.objects.filter(user=request.user, library=True)

        result = []
        for x in image_user_db:
            result.append({"id": x.image.hash_id})

        return JsonResponse({"status": "ok", "data": result})
