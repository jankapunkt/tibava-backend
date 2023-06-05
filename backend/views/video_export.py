import json
import logging
import traceback
import logging
import sys

from numpy import isin

import wand.image as wimage


from django.views import View
from django.http import JsonResponse
from django.conf import settings

from pympi.Elan import Eaf, to_eaf
from xml.etree import cElementTree as etree
from io import StringIO


from backend.models import Video, Annotation, AnnotationCategory, Timeline, TimelineSegment, PluginRunResult
from analyser.data import DataManager, Shot
import numpy as np

def time_to_string(sec, loc="en"):
    sec, sec_frac = divmod(sec, 1)
    min, sec = divmod(sec, 60)
    hours, min = divmod(min, 60)

    sec_frac = round(1000 * sec_frac)
    hours = int(hours)
    min = int(min)
    sec = int(sec)

    if loc == "de":
        return f"{hours}:{min}:{sec},{sec_frac}"
    return f"{hours}:{min}:{sec}.{sec_frac}"


class VideoExportElan(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            if "video_id" not in request.GET:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                video_db = Video.objects.get(id=request.GET.get("video_id"))
            except Video.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            annotations = {}
            for annotation in Annotation.objects.filter(video=video_db):
                annotation_dict = annotation.to_dict()
                if annotation.category:
                    annotation_dict["category"] = annotation.category.to_dict()
                annotations[annotation.id] = annotation_dict
            eaf = Eaf(author="")
            # specific timeline
            for timeline_id in request.GET.get("timeline_ids"):
                timeline_db = Timeline.objects.get(id=timeline_id)
                tier = timeline_db.name
                # ignore timelines with the same name TODO: check if there is a better way
                if tier in list(eaf.tiers.keys()):
                    continue
                eaf.add_tier(tier_id=tier)
                # store all annotations
                for segment_db in timeline_db.timelinesegment_set.all():
                    start_time = int(segment_db.start * 1000)
                    end_time = int(segment_db.end * 1000)
                    for segment_annotation_db in segment_db.timelinesegmentannotation_set.all():
                        category = segment_annotation_db.annotation.category
                        name = segment_annotation_db.annotation.name
                        anno = f"{name} ({category}"
                        eaf.add_annotation(tier, start=start_time, end=end_time, value=anno)
            # if request.GET.get("format") == "textgrid":
            #    textgrid = eaf.to_textgrid()
            # else:
            stdout = sys.stdout
            sys.stdout = str_out = StringIO()
            to_eaf(file_path="-", eaf_obj=eaf)
            sys.stdout = stdout
            result = str_out.getvalue()
            return JsonResponse({"status": "ok", "file": result})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoExportCSV(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            if "video_id" not in request.GET:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                video_db = Video.objects.get(id=request.GET.get("video_id"))
            except Video.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            annotations = {}
            for annotation in Annotation.objects.filter(video=video_db):
                annotation_dict = annotation.to_dict()
                if annotation.category:
                    annotation_dict["category"] = annotation.category.to_dict()
                annotations[annotation.id] = annotation_dict

            times = []
            durations = []
            timeline_headers = {}
            for timeline_db in video_db.timeline_set.all():
                annotations_headers = {}
                for segment_db in timeline_db.timelinesegment_set.all():
                    times.append(segment_db.start)
                    durations.append(segment_db.end - segment_db.start)
                    for segment_annotation_db in segment_db.timelinesegmentannotation_set.all():
                        annotation_id = segment_annotation_db.annotation.id
                        if annotation_id not in annotations_headers:
                            annotations_headers[annotation_id] = {**annotations[annotation_id], "times": []}
                        annotations_headers[annotation_id]["times"].append(
                            {"start": segment_db.start, "end": segment_db.end}
                        )
                timeline_headers[timeline_db.id] = {"name": timeline_db.name, "annotations": annotations_headers}
            # 0, video_db.duration
            time_duration = sorted(list(set(zip(times, durations))), key=lambda x: x[0])
            # print(time_duration, flush=True)
            # print(len(time_duration), flush=True)
            cols = []

            # first col
            cols.append(["start", "", ""] + [str(t[0]) for t in time_duration])
            cols.append(["start", "", ""] + [time_to_string(t[0], loc="en") for t in time_duration])
            cols.append(["duration", "", ""] + [str(t[1]) for t in time_duration])
            cols.append(["duration", "", ""] + [time_to_string(t[1], loc="en") for t in time_duration])
            for _, timeline in timeline_headers.items():
                for _, annotation in timeline["annotations"].items():
                    col = [timeline["name"]]
                    col.append(annotation["name"])
                    if "category" in annotation:
                        col.append(annotation["category"]["name"])
                    else:
                        col.append("")
                    for t, _ in time_duration:
                        print(t, flush=True)
                        label = 0
                        for anno_t in annotation["times"]:
                            if anno_t["start"] <= t and t < anno_t["end"]:
                                label = 1
                        col.append(str(label))
                        # cols.append([timeline["name"], "", ""] + times)
                    cols.append(col)
            # print(cols, flush=True)
            # Transpose
            rows = list(map(list, zip(*cols)))

            # Back to a single string
            result = "\n".join([",".join(r) for r in rows])

            return JsonResponse({"status": "ok", "file": result})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoExportJson(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            if "video_id" not in request.GET:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                video_db = Video.objects.get(id=request.GET.get("video_id"))
            except Video.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            annotations = [
                x.to_dict(include_refs_hashes=False, include_refs=True)
                for x in Annotation.objects.filter(video=video_db)
            ]
            timelines = [x.to_dict(include_refs_hashes=False, include_refs=True) for x in video_db.timeline_set.all()]

            result = json.dumps({"annotations": annotations, "timelines": timelines})

            return JsonResponse({"status": "ok", "file": result})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoExport(View):
    def export_csv(self, parameters, video_db):
        include_category = True
        if "include_category" in parameters:
            include_category = parameters.get("include_category")

        use_timestamps = True
        if "use_timestamps" in parameters:
            use_timestamps = parameters.get("use_timestamps")

        use_seconds = True
        if "use_seconds" in parameters:
            use_seconds = parameters.get("use_seconds")

        merge_timeline = True
        if "merge_timeline" in parameters:
            merge_timeline = parameters.get("merge_timeline")

        num_header_lines = 1
        if not merge_timeline:
            if include_category:
                num_header_lines = 3
            else:
                num_header_lines = 2

        times = []
        durations = []
        for timeline_db in video_db.timeline_set.all():
            annotations_headers = {}
            for segment_db in timeline_db.timelinesegment_set.all():
                times.append(segment_db.start)
                durations.append(segment_db.end - segment_db.start)
        # 0, video_db.duration
        time_duration = sorted(list(set(zip(times, durations))), key=lambda x: x[0])
        # print(time_duration, flush=True)
        # print(len(time_duration), flush=True)
        cols = []

        # start
        if use_timestamps:
            cols.append(
                ["start"]
                + ["" for x in range(num_header_lines - 1)]
                + [time_to_string(t[0], loc="en") for t in time_duration]
            )
        if use_seconds:
            cols.append(["start"] + ["" for x in range(num_header_lines - 1)] + [str(t[0]) for t in time_duration])

        # duration
        if use_timestamps:
            cols.append(
                ["duration"]
                + ["" for x in range(num_header_lines - 1)]
                + [time_to_string(t[1], loc="en") for t in time_duration]
            )
        if use_seconds:
            cols.append(["duration"] + ["" for x in range(num_header_lines - 1)] + [str(t[1]) for t in time_duration])

        annotations = {}
        for annotation in Annotation.objects.filter(video=video_db):
            annotation_dict = annotation.to_dict()
            if annotation.category:
                annotation_dict["category"] = annotation.category.to_dict()
            annotations[annotation.id] = annotation_dict

        if merge_timeline:
            for timeline_db in video_db.timeline_set.all():
                segments = []
                for segment_db in timeline_db.timelinesegment_set.all():
                    annotations = []
                    for segment_annotation_db in segment_db.timelinesegmentannotation_set.all():
                        if include_category and segment_annotation_db.annotation.category:
                            annotations.append(
                                segment_annotation_db.annotation.category.name
                                + "::"
                                + segment_annotation_db.annotation.name
                            )
                        else:
                            annotations.append(segment_annotation_db.annotation.name)
                    if len(annotations) > 0:
                        segments.append(
                            {"annotation": "+".join(annotations), "start": segment_db.start, "end": segment_db.end}
                        )

                if len(segments) == 0:
                    continue

                col = [timeline_db.name]

                for s, d in time_duration:
                    col_text = ""

                    for segment in segments:
                        if segment["start"] >= s and segment["end"] <= (s + d):
                            col_text = segment["annotation"]

                    col.append(col_text)

                cols.append(col)

        else:
            timeline_headers = {}
            for timeline_db in video_db.timeline_set.all():
                annotations_headers = {}
                for segment_db in timeline_db.timelinesegment_set.all():
                    for segment_annotation_db in segment_db.timelinesegmentannotation_set.all():
                        annotation_id = segment_annotation_db.annotation.id
                        if annotation_id not in annotations_headers:
                            annotations_headers[annotation_id] = {**annotations[annotation_id], "times": []}
                        annotations_headers[annotation_id]["times"].append(
                            {"start": segment_db.start, "end": segment_db.end}
                        )
                timeline_headers[timeline_db.id] = {"name": timeline_db.name, "annotations": annotations_headers}

            for _, timeline in timeline_headers.items():
                for _, annotation in timeline["annotations"].items():
                    col = [timeline["name"]]
                    col.append(annotation["name"])
                    if include_category:
                        if "category" in annotation:
                            col.append(annotation["category"]["name"])
                        else:
                            col.append("")
                    for t, _ in time_duration:
                        print(t, flush=True)
                        label = 0
                        for anno_t in annotation["times"]:
                            if anno_t["start"] <= t and t < anno_t["end"]:
                                label = 1
                        col.append(str(label))
                        # cols.append([timeline["name"], "", ""] + times)
                    cols.append(col)
        # print(cols, flush=True)
        # Transpose
        rows = list(map(list, zip(*cols)))

        # Back to a single string
        result = "\n".join([",".join(r) for r in rows])

        return result

    def export_elan(self, parameters, video_db):
        eaf = Eaf(author="")
        eaf.remove_tier("default")
        eaf.add_linked_file(file_path=f"{video_db.id.hex}.mp4", mimetype="video/mp4")
        
        # get the boundary information from the timeline selected in parameters
        try:
            shot_timeline_db = Timeline.objects.get(id=parameters.get("shot_timeline_id"))
        except Timeline.DoesNotExist:
            raise Exception
        
        aggregation = ["max", "min", "mean"][parameters.get("aggregation")]

        # if the timeline is not of type annotation, raise an Exception
        if shot_timeline_db.type != Timeline.TYPE_ANNOTATION:
            raise Exception
        
        # get the shots from the boundary timeline
        shots = []
        shot_timeline_segments = TimelineSegment.objects.filter(timeline=shot_timeline_db)
        for x in shot_timeline_segments:
            shots.append(Shot(start=x.start, end=x.end))

        data_manager = DataManager("/predictions/")

        # for all timelines
        for timeline_db in Timeline.objects.filter(video=video_db):
            tier = timeline_db.name

            # ignore timelines with the same name TODO: check if there is a better way
            if tier in list(eaf.tiers.keys()):
                continue
            eaf.add_tier(tier_id=tier)
            # store all annotations
            
            tl_type = timeline_db.plugin_run_result
            
            # if the type of the timeline is scalar convert it to elan format
            if tl_type is not None:
                # if it is not of type SCALAR, skip it
                if tl_type.type != PluginRunResult.TYPE_SCALAR:
                    continue

                scalar_data = data_manager.load(timeline_db.plugin_run_result.data_id)
                with scalar_data:
                    y = np.asarray(scalar_data.y)
                    time = np.asarray(scalar_data.time)
                    for i, shot in enumerate(shots):
                        annotations = []
                        shot_y_data = y[np.logical_and(time >= shot.start, time <= shot.end)]

                        if len(shot_y_data) <= 0:
                            continue

                        y_agg = 0
                        
                        if aggregation == "mean":
                            y_agg = np.mean(shot_y_data)
                        if aggregation == "max":
                            y_agg = np.max(shot_y_data)
                        if aggregation == "min":
                            y_agg = np.min(shot_y_data)
                        
                        start_time = int(shot.start * 1000)
                        end_time = int(shot.end * 1000)
                        anno = str(round(float(y_agg), 3))

                        annotations.append(f"value:{anno}")
                        if len(annotations) > 0:
                            eaf.add_annotation(tier, start=start_time, end=end_time, value=", ".join(annotations))
            # if it is an annotation timeline already, just export it
            else:
                for segment_db in timeline_db.timelinesegment_set.all():
                    start_time = int(segment_db.start * 1000)
                    end_time = int(segment_db.end * 1000)
                    annotations = []
                    # if the timeline contains annotations, export them
                    if len(segment_db.timelinesegmentannotation_set.all()) > 0:
                        for segment_annotation_db in segment_db.timelinesegmentannotation_set.all():
                            category = segment_annotation_db.annotation.category
                            name = segment_annotation_db.annotation.name
                            if category is not None:
                                anno = f"{category.name}:{name}"
                            else:
                                anno = f"{name}"
                            annotations.append(anno)
                            # check why this occurs
                            if start_time == end_time: 
                                continue
                            eaf.add_annotation(tier, start=start_time, end=end_time, value=", ".join(annotations))
                    else:
                        # if it does not contain annotations, export the boundaries with placeholder values (here: shot number)
                        for i, shot in enumerate(shots):
                            annotations = []
                            start_time = int(shot.start * 1000)
                            end_time = int(shot.end * 1000)
                            annotations.append(f"value:{i}")
                            # check why this occurs
                            if start_time == end_time: 
                                continue
                            eaf.add_annotation(tier, start=start_time, end=end_time, value=", ".join(annotations))

        # if request.GET.get("format") == "textgrid":
        #    textgrid = eaf.to_textgrid()
        # else:
        stdout = sys.stdout
        sys.stdout = str_out = StringIO()
        to_eaf(file_path="-", eaf_obj=eaf)
        sys.stdout = stdout
        result = str_out.getvalue()

        return result

    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            if "video_id" not in request.POST:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                video_db = Video.objects.get(id=request.POST.get("video_id"))
            except Video.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            if "format" not in request.POST:
                return JsonResponse({"status": "error", "type": "missing_values"})

            parameters = {}
            if "parameters" in request.POST:
                if isinstance(request.POST.get("parameters"), str):
                    try:
                        input_parameters = json.loads(request.POST.get("parameters"))
                    except:
                        return JsonResponse({"status": "error", "type": "wrong_request_body"})
                elif isinstance(request.POST.get("parameters"), (list, set)):
                    input_parameters = request.POST.get("parameters")
                else:
                    return JsonResponse({"status": "error", "type": "wrong_request_body"})

                for p in input_parameters:
                    if "name" not in p:
                        return JsonResponse({"status": "error", "type": "missing_values"})
                    if "value" not in p:
                        return JsonResponse({"status": "error", "type": "missing_values"})
                    parameters[p["name"]] = p["value"]

            if request.POST.get("format") == "csv":
                result = self.export_csv(parameters, video_db)
                return JsonResponse({"status": "ok", "file": result, "extension": "csv"})

            elif request.POST.get("format") == "elan":
                result = self.export_elan(parameters, video_db)
                return JsonResponse({"status": "ok", "file": result, "extension": "eaf"})

            return JsonResponse({"status": "error", "type": "unknown_format"})
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
