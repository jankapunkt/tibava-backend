import json
import logging
import traceback
import logging
import sys
import io
import csv
import base64

from numpy import isin

import wand.image as wimage


from django.views import View
from django.http import JsonResponse, HttpResponse
from django.conf import settings

from pympi.Elan import Eaf, to_eaf
from xml.etree import cElementTree as etree
from io import StringIO
import pandas as pd

import zipfile

from backend.utils.color import get_closest_color
from backend.models import (
    Video,
    Annotation,
    AnnotationCategory,
    Timeline,
    TimelineSegment,
    PluginRunResult,
)
from analyser.data import DataManager, Shot
import numpy as np


logger = logging.getLogger(__name__)


def json_to_csv(json_obj):
    df = pd.DataFrame(json_obj)
    return df.to_csv(index=False, sep="\t")


def time_to_string(sec, loc="en"):
    sec, sec_frac = divmod(sec, 1)
    min, sec = divmod(sec, 60)
    hours, min = divmod(min, 60)

    sec_frac = round(1000 * sec_frac)
    hours = (2 - len(str(int(hours)))) * "0" + str(int(hours))
    min = (2 - len(str(int(min)))) * "0" + str(int(min))
    sec = (2 - len(str(int(sec)))) * "0" + str(int(sec))

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
                    for (
                        segment_annotation_db
                    ) in segment_db.timelinesegmentannotation_set.all():
                        category = segment_annotation_db.annotation.category
                        name = segment_annotation_db.annotation.name
                        anno = f"{name} {category}"
                        eaf.add_annotation(
                            tier, start=start_time, end=end_time, value=anno
                        )
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
            logger.error(traceback.format_exc())
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
                    for (
                        segment_annotation_db
                    ) in segment_db.timelinesegmentannotation_set.all():
                        annotation_id = segment_annotation_db.annotation.id
                        if annotation_id not in annotations_headers:
                            annotations_headers[annotation_id] = {
                                **annotations[annotation_id],
                                "times": [],
                            }
                        annotations_headers[annotation_id]["times"].append(
                            {"start": segment_db.start, "end": segment_db.end}
                        )
                timeline_headers[timeline_db.id] = {
                    "name": timeline_db.name,
                    "annotations": annotations_headers,
                }
            # 0, video_db.duration
            time_duration = sorted(list(set(zip(times, durations))), key=lambda x: x[0])
            # print(time_duration, flush=True)
            # print(len(time_duration), flush=True)
            cols = []

            # first col
            cols.append(
                ["start hh:mm:ss.ms", "", ""] + [str(t[0]) for t in time_duration]
            )
            cols.append(
                ["start in seconds", "", ""]
                + [time_to_string(t[0], loc="en") for t in time_duration]
            )
            cols.append(
                ["duration hh:mm:ss.ms", "", ""] + [str(t[1]) for t in time_duration]
            )
            cols.append(
                ["duration in seconds", "", ""]
                + [time_to_string(t[1], loc="en") for t in time_duration]
            )
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
            buffer = io.StringIO()
            with csv.writer(buffer, quoting=csv.QUOTE_ALL) as f:
                for line in rows:
                    f.writerow(line)
                # result = "\n".join([",".join(r) for r in rows])
            return JsonResponse({"status": "ok", "file": buffer})
        except Exception as e:
            logger.error(traceback.format_exc())
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
            timelines = [
                x.to_dict(include_refs_hashes=False, include_refs=True)
                for x in video_db.timeline_set.all()
            ]

            result = json.dumps({"annotations": annotations, "timelines": timelines})

            return JsonResponse({"status": "ok", "file": result})
        except Exception as e:
            logger.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


class VideoExport(View):
    def export_merged_csv(self, parameters, video_db):
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

        split_places = False
        if "split_places" in parameters:
            split_places = parameters.get("split_places")

        num_header_lines = 1
        if not merge_timeline:
            if include_category:
                num_header_lines = 3
            else:
                num_header_lines = 2

        times = []
        durations = []
        end_times = []
        diffs = []
        for timeline_db in video_db.timeline_set.all():
            annotations_headers = {}
            timeline_segments = timeline_db.timelinesegment_set.all()
            for index, segment_db in enumerate(timeline_segments):
                # if (segment_db.end - segment_db.start) > 1:
                times.append(segment_db.start)
                end_times.append(segment_db.end)
                if index < len(timeline_segments)-1:
                    diff = timeline_segments[index+1].start - segment_db.end
                else:
                    diff = 0
                diffs.append(diff)
                durations.append(segment_db.end - segment_db.start + diff)

        # d = {"starts": times, "durations": durations, "end_times": end_times, "diffs": diffs}
        # import pandas as pd

        # df = pd.DataFrame.from_dict(d)
        # df.to_csv("data.csv", index=False)
                    
        # 0, video_db.duration
        time_duration = sorted(list(set(zip(times, durations))), key=lambda x: x[0])
        cols = []

        # logger.error(time_duration)

        # shot number column
        # also extract shots for aggregation later
        shot_number_col = ["Shot Number"]
        shot_timeline = video_db.timeline_set.filter(name="Shots")[0]

        for start, duration in time_duration:
            end = start + duration
            # logger.error(f"{start} - {end}")
            for shot_index, shot in enumerate(shot_timeline.timelinesegment_set.all()):
                shot_number_col.append(shot_index) 

        cols.append(shot_number_col)

        # start time column
        if use_timestamps:
            cols.append(
                ["start hh:mm:ss.ms"]
                + ["" for x in range(num_header_lines - 1)]
                + [time_to_string(t[0], loc="en") for t in time_duration]
            )
        if use_seconds:
            cols.append(
                ["start in seconds"]
                + ["" for x in range(num_header_lines - 1)]
                + [str(round(t[0],3)) for t in time_duration]
            )

        # duration column
        if use_timestamps:
            cols.append(
                ["duration hh:mm:ss.ms"]
                + ["" for x in range(num_header_lines - 1)]
                + [time_to_string(t[1], loc="en") for t in time_duration]
            )
        if use_seconds:
            cols.append(
                ["duration in seconds"]
                + ["" for x in range(num_header_lines - 1)]
                + [str(round(t[1],3)) for t in time_duration]
            )

        annotations = {}
        for annotation in Annotation.objects.filter(video=video_db):
            annotation_dict = annotation.to_dict()
            if annotation.category:
                annotation_dict["category"] = annotation.category.to_dict()
            annotations[annotation.id] = annotation_dict

        # result columns
        data_manager = DataManager("/predictions/")

        if merge_timeline:
            for timeline_db in video_db.timeline_set.all():
                PRresult = timeline_db.plugin_run_result

                if PRresult is not None:
                    # SCALAR TYPE
                    if PRresult.type == PluginRunResult.TYPE_SCALAR:
                        col = [timeline_db.name]
                        min_col = [f"{timeline_db.name}_min"]
                        max_col = [f"{timeline_db.name}_max"]
                        std_col = [f"{timeline_db.name}_std"]
                        var_col = [f"{timeline_db.name}_var"]

                        scalar_data = data_manager.load(
                            timeline_db.plugin_run_result.data_id
                        )
                        with scalar_data:
                            y = np.asarray(scalar_data.y)
                            time = np.asarray(scalar_data.time)
                            for start, duration in time_duration:
                                end = start + duration
                                shot_y_data = y[
                                    np.logical_and(time >= start, time <= end)
                                ]

                                if len(shot_y_data) <= 0:
                                    continue

                                y_agg = np.sqrt(np.mean(shot_y_data))

                                anno = round(float(y_agg), 3)
                                col.append(anno)
                                # logger.error(shot_y_data)
                                min_col.append(round(float(np.min(shot_y_data)), 7))
                                max_col.append(round(float(np.max(shot_y_data)), 7))
                                std_col.append(round(float(np.std(shot_y_data)), 7))
                                var_col.append(round(float(np.var(shot_y_data)), 7))
                                # logger.error(f"{min_col[-1], max_col[-1], std_col[-1], var_col[-1],}")
                        
                        cols.append(col)
                        cols.append(min_col)
                        cols.append(max_col)
                        cols.append(std_col)
                        cols.append(var_col)

                    # RGB HIST TYPE
                    if PRresult.type == PluginRunResult.TYPE_RGB_HIST:
                        col = [timeline_db.name]
                        rgb_data = data_manager.load(
                            timeline_db.plugin_run_result.data_id
                        )

                        with rgb_data:
                            colors = rgb_data.colors
                            time = rgb_data.time

                            for start, duration in time_duration:
                                end = start + duration
                                shot_colors = colors[
                                    np.logical_and(time >= start, time <= end)
                                ]
                                avg_color = np.mean(shot_colors, axis=0)
                                col.append(get_closest_color(avg_color))

                        cols.append(col)

                # Annotation Timelines
                else:
                    segments = []
                    places = False # NOTE small Hack to detect if that Timeline is a places_classification
                    for segment_db in timeline_db.timelinesegment_set.all():
                        annotations = []
                        for segment_annotation_db in segment_db.timelinesegmentannotation_set.all():
                            if  not places\
                                and segment_annotation_db.annotation.name[0] == ("/")\
                                and segment_annotation_db.annotation.name[2] == ("/"):
                                places = True

                            if (include_category and segment_annotation_db.annotation.category):
                                annotations.append(
                                    segment_annotation_db.annotation.category.name
                                    + "::"
                                    + segment_annotation_db.annotation.name
                                )
                            else:
                                annotations.append(segment_annotation_db.annotation.name)
                        
                        if len(annotations) > 0:
                            segments.append({
                                    "annotation": "+".join(annotations),
                                    "start": segment_db.start,
                                    "end": segment_db.end,
                                })
                        else:
                            segments.append({
                                "annotation": "None",
                                "start": segment_db.start,
                                "end": segment_db.end,
                            })

                    if len(segments) == 0:
                        continue

                    if places and split_places:
                        for index, places_class in enumerate(["place365", "place16", "place3"]):
                            col = [places_class]
                            for s, d in time_duration:
                                col_text = ""

                                for segment in segments:
                                    splitted = segment["annotation"].split("+")
                                    if segment["start"] >= s and segment["end"] <= (s + d):
                                        if len(splitted) > 1:
                                            col_text = splitted[index]
                                        else:
                                            col_text = "None"

                                col.append(col_text)
                                        
                            cols.append(col)
                    else:
                        col = [timeline_db.name]

                        for s, d in time_duration:
                            col_text = ""

                            for segment in segments:
                                # print(f'####### {timeline_db.name} {segment["start"]} {segment["end"]} {segment["annotation"]} {s} {d}')
                                if segment["start"] >= s and segment["end"] <= (s + d):
                                    col_text = segment["annotation"]
                            if col_text == "":
                                col_text = "None"
                            
                            # print(f'################ {col_text} {segment["end"]} {segment["annotation"]} {s} {d}')
                            col.append(col_text)


                        cols.append(col)
        else:
            timeline_headers = {}

            for timeline_db in video_db.timeline_set.all():
                annotations_headers = {}
                for segment_db in timeline_db.timelinesegment_set.all():
                    for (segment_annotation_db) in segment_db.timelinesegmentannotation_set.all():
                        annotation_id = segment_annotation_db.annotation.id
                        if annotation_id not in annotations_headers:
                            annotations_headers[annotation_id] = {
                                **annotations[annotation_id],
                                "times": [],
                            }
                        annotations_headers[annotation_id]["times"].append(
                            {"start": segment_db.start, "end": segment_db.end}
                        )
                timeline_headers[timeline_db.id] = {
                    "name": timeline_db.name,
                    "annotations": annotations_headers,
                }

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
                        label = 0
                        for anno_t in annotation["times"]:
                            if anno_t["start"] <= t and t < anno_t["end"]:
                                label = 1
                        col.append(str(label))
                    cols.append(col)
        # Transpose
        rows = list(map(list, zip(*cols)))

        buffer = io.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in rows:
            writer.writerow(line)

        return buffer.getvalue()

    def export_individual_csv(self, parameters, video_db):
        include_category = True
        if "include_category" in parameters:
            include_category = parameters.get("include_category")

        use_timestamps = True
        if "use_timestamps" in parameters:
            use_timestamps = parameters.get("use_timestamps")

        use_seconds = True
        if "use_seconds" in parameters:
            use_seconds = parameters.get("use_seconds")

        timeline_annotations = []
        timeline_names = []

        data_manager = DataManager("/predictions/")

        for timeline_db in Timeline.objects.filter(video=video_db):
            annotations = {}
            tl_type = timeline_db.plugin_run_result
            # print(f"{timeline_db.name} --> {tl_type=}")

            # if the type of the timeline is scalar convert it to elan format
            if tl_type is not None:
                annotations["start in seconds"] = []
                if use_timestamps:
                    annotations["start hh:mm:ss.ms"] = []
                annotations["annotations"] = []

                data = data_manager.load(timeline_db.plugin_run_result.data_id)

                # if it is not of type SCALAR, skip it
                with data:
                    if tl_type.type == PluginRunResult.TYPE_SCALAR:
                        y = np.asarray(data.y)
                        # print(f"Data {len(y)}\n {y}")
                        time = np.asarray(data.time)
                        # print(f"Data {len(time)}\n {time}")
                        for i, time_stamp in enumerate(time):
                            annotations["start in seconds"].append(time_stamp)
                            annotations["annotations"].append(round(float(y[i]), 5))
                            if use_timestamps:
                                annotations["start hh:mm:ss.ms"].append(
                                    time_to_string(time_stamp, loc="en")
                                )
                    elif tl_type.type == PluginRunResult.TYPE_RGB_HIST:
                        colors = np.asarray(data.colors)
                        # print(f"Data {len(colors)}\n {colors}")
                        time = np.asarray(data.time)
                        # print(f"Data {len(time)}\n {time}")
                        for i, time_stamp in enumerate(time):
                            annotations["start in seconds"].append(time_stamp)
                            annotations["annotations"].append(colors[i])
                            if use_timestamps:
                                annotations["start hh:mm:ss.ms"].append(
                                    time_to_string(time_stamp, loc="en")
                                )
                    else:
                        continue

            else:
                times = []
                durations = []

                shot_timeline_segments = TimelineSegment.objects.filter(
                    timeline=timeline_db
                )

                for segment in shot_timeline_segments:
                    times.append(segment.start)
                    durations.append(segment.end - segment.start)

                time_duration = sorted(
                    list(set(zip(times, durations))), key=lambda x: x[0]
                )

                # start
                if use_timestamps:
                    annotations["start hh:mm:ss.ms"] = [
                        time_to_string(t[0], loc="en") for t in time_duration
                    ]

                if use_seconds:
                    annotations["start in seconds"] = [str(t[0]) for t in time_duration]

                # duration
                if use_timestamps:
                    annotations["duration hh:mm:ss.ms"] = [
                        time_to_string(t[1], loc="en") for t in time_duration
                    ]

                if use_seconds:
                    annotations["duration in seconds"] = [
                        str(t[1]) for t in time_duration
                    ]

                annotations["annotations"] = []

                for segment in shot_timeline_segments:
                    if len(segment.timelinesegmentannotation_set.all()) > 0:
                        all_annotations = []
                        for (
                            segment_annotation_db
                        ) in segment.timelinesegmentannotation_set.all():
                            if (
                                include_category
                                and segment_annotation_db.annotation.category
                            ):
                                all_annotations.append(
                                    segment_annotation_db.annotation.category.name
                                    + "::"
                                    + segment_annotation_db.annotation.name
                                )
                            else:
                                all_annotations.append(
                                    segment_annotation_db.annotation.name
                                )
                        annotations["annotations"].append(all_annotations)
                    else:
                        annotations["annotations"].append("")

            timeline_annotations.append(annotations)
            timeline_names.append(timeline_db.name)

        # print(len(timeline_annotations))

        # Create a temporary in-memory file to store the zip
        buffer = io.BytesIO()
        zip_file = zipfile.ZipFile(buffer, "w")

        # print(timeline_annotations)

        for index, json_obj in enumerate(timeline_annotations):
            csv_data = json_to_csv(json_obj)
            filename = f"{timeline_names[index]}.tsv"

            # Write the CSV data to the individual file
            zip_file.writestr(filename, csv_data)

        # Close the zip file
        zip_file.close()

        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def export_elan(self, parameters, video_db):
        eaf = Eaf(author="")
        eaf.remove_tier("default")
        eaf.add_linked_file(file_path=f"{video_db.id.hex}.mp4", mimetype="video/mp4")

        # get the boundary information from the timeline selected in parameters
        try:
            shot_timeline_db = Timeline.objects.get(
                id=parameters.get("shot_timeline_id")
            )
        except Timeline.DoesNotExist:
            raise Exception

        aggregation = ["max", "min", "mean"][parameters.get("aggregation")]

        # if the timeline is not of type annotation, raise an Exception
        if shot_timeline_db.type != Timeline.TYPE_ANNOTATION:
            raise Exception

        # get the shots from the boundary timeline
        shots = []
        shot_timeline_segments = TimelineSegment.objects.filter(
            timeline=shot_timeline_db
        )
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
                        shot_y_data = y[
                            np.logical_and(time >= shot.start, time <= shot.end)
                        ]
                        # print(f"{shot.start} - {shot.end}")

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
                            eaf.add_annotation(
                                tier,
                                start=start_time,
                                end=end_time,
                                value=", ".join(annotations),
                            )
            # if it is an annotation timeline already, just export it
            else:
                for id, segment_db in enumerate(timeline_db.timelinesegment_set.all()):
                    start_time = int(segment_db.start * 1000)
                    end_time = int(segment_db.end * 1000)
                    # print(f"{start_time} - {end_time}")
                    # TODO: check why this occurs
                    if start_time == end_time:
                        continue
                    annotations = []
                    # if the timeline contains annotations, export them
                    if len(segment_db.timelinesegmentannotation_set.all()) > 0:
                        annotations = []
                        for (
                            segment_annotation_db
                        ) in segment_db.timelinesegmentannotation_set.all():
                            category = segment_annotation_db.annotation.category
                            name = segment_annotation_db.annotation.name
                            if category is not None:
                                anno = f"{category.name}:{name}"
                            else:
                                anno = f"{name}"
                            annotations.append(anno)
                        if len(annotations) > 0:
                            eaf.add_annotation(
                                tier,
                                start=start_time,
                                end=end_time,
                                value="; ".join(annotations),
                            )
                    else:
                        # if it does not contain annotations, export the boundaries with placeholder values (here: shot number)
                        eaf.add_annotation(
                            tier, start=start_time, end=end_time, value=f"value:{id}"
                        )

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
                        return JsonResponse(
                            {"status": "error", "type": "wrong_request_body"}
                        )
                elif isinstance(request.POST.get("parameters"), (list, set)):
                    input_parameters = request.POST.get("parameters")
                else:
                    return JsonResponse(
                        {"status": "error", "type": "wrong_request_body"}
                    )

                for p in input_parameters:
                    if "name" not in p:
                        return JsonResponse(
                            {"status": "error", "type": "missing_values"}
                        )
                    if "value" not in p:
                        return JsonResponse(
                            {"status": "error", "type": "missing_values"}
                        )
                    parameters[p["name"]] = p["value"]

            if request.POST.get("format") == "merged_csv":
                result = self.export_merged_csv(parameters, video_db)
                return JsonResponse(
                    {"status": "ok", "file": result, "extension": "csv"}
                )

            elif request.POST.get("format") == "individual_csv":
                result = self.export_individual_csv(parameters, video_db)
                return JsonResponse(
                    {"status": "ok", "file": result, "extension": "zip"}
                )

            elif request.POST.get("format") == "elan":
                result = self.export_elan(parameters, video_db)
                return JsonResponse(
                    {"status": "ok", "file": result, "extension": "eaf"}
                )

            return JsonResponse({"status": "error", "type": "unknown_format"})
        except Exception as e:
            logger.error(traceback.format_exc())
            return JsonResponse({"status": "error"})
