import logging
import traceback
import json

from django.views import View
from django.http import JsonResponse


from backend.models import Place, Video

class PlaceFetch(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error_user_auth"})
            
            entries = []
            video = Video.objects.get(id=request.GET.get("video_id"))
            for place in Place.objects.filter(video=video):
                entries.append(place.to_dict())
            
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})

class PlaceSetDeleted(View):
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
            
            if "place_ref_list" not in data:
                return JsonResponse({"status": "error", "type": "missing_values_place_ref_list"})
            if "cluster_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values_place_cluster_id"})
            
            place_ref_list = list(data.get("place_ref_list"))
            for place_ref in place_ref_list:
                places = Place.objects.filter(place_ref=place_ref) # TODO change filter to "get" as soon as old clusters are deleted
                if (len(places) > 1):
                    places = [f for f in places if f.cti.cluster_id.hex == data.get("cluster_id")]
                assert len(places) == 1, f"still more than one place: {places} \n {data}"
                places[0].deleted = True
                places[0].save()
            
            return JsonResponse({"status": "ok", "entries": place_ref_list})
            
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error_place_set_deleted"})