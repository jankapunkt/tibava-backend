from random import random
import uuid

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from backend.utils.color import rgb_to_hex, random_rgb


def random_color_string():
    return rgb_to_hex(random_rgb())


class Video(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    license = models.CharField(max_length=256)
    ext = models.CharField(max_length=256)
    date = models.DateTimeField(auto_now_add=True)
    # some extracted meta information
    fps = models.FloatField(blank=True, null=True)
    duration = models.FloatField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    width = models.IntegerField(blank=True, null=True)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):

        return {
            "name": self.name,
            "license": self.license,
            "id": self.id.hex,
            "ext": self.ext,
            "date": self.date,
            "fps": self.fps,
            "duration": self.duration,
            "height": self.height,
            "width": self.width,
        }


class Plugin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
        }
        return result


class PluginRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=256)
    progress = models.FloatField(default=0.0)
    STATUS_UNKNOWN = "U"
    STATUS_ERROR = "E"
    STATUS_DONE = "D"
    STATUS_RUNNING = "R"
    STATUS_QUEUED = "Q"
    STATUS_WAITING = "W"
    STATUS = {
        STATUS_UNKNOWN: "UNKNOWN",
        STATUS_ERROR: "ERROR",
        STATUS_DONE: "DONE",
        STATUS_RUNNING: "RUNNING",
        STATUS_QUEUED: "QUEUED",
        STATUS_WAITING: "WAITING",
    }

    status = models.CharField(max_length=2, choices=[(k, v) for k, v in STATUS.items()], default=STATUS_UNKNOWN)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "type": self.type,
            "date": self.date,
            "update_date": self.update_date,
            "progress": self.progress,
            "status": self.STATUS[self.status],
        }
        if include_refs_hashes:
            result["video_id"] = self.video.id.hex
        return result


class PluginRunResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plugin_run = models.ForeignKey(PluginRun, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    data_id = models.CharField(null=True, max_length=64)
    TYPE_VIDEO = "V"
    TYPE_IMAGES = "I"
    TYPE_SCALAR = "S"
    TYPE_HIST = "H"
    TYPE_SHOTS = "SH"
    TYPE_RGB_HIST = "R"
    TYPE = {
        TYPE_VIDEO: "VIDEO",
        TYPE_IMAGES: "IMAGES",
        TYPE_SCALAR: "SCALAR",
        TYPE_HIST: "HIST",
        TYPE_SHOTS: "SHOTS",
        TYPE_RGB_HIST: "RGB_HIST",
    }

    type = models.CharField(
        max_length=2,
        choices=[(k, v) for k, v in TYPE.items()],
        default=TYPE_SCALAR,
    )

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "type": self.TYPE[self.type],
            "data_id": self.data_id,
        }
        if include_refs_hashes:
            result["plugin_run_id"] = self.plugin_run.id.hex
        return result


class Timeline(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    plugin_run_result = models.ForeignKey(PluginRunResult, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=256)

    TYPE_ANNOTATION = "A"
    TYPE_PLUGIN_RESULT = "R"
    TYPE = {
        TYPE_ANNOTATION: "ANNOTATION",
        TYPE_PLUGIN_RESULT: "PLUGIN_RESULT",
    }

    type = models.CharField(
        max_length=2,
        choices=[(k, v) for k, v in TYPE.items()],
        default=TYPE_ANNOTATION,
    )
    order = models.IntegerField(default=-1)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True)
    collapse = models.BooleanField(default=False)

    VISUALIZATION_COLOR = "C"
    VISUALIZATION_CATEGORY_COLOR = "CC"
    VISUALIZATION_SCALAR_COLOR = "SC"
    VISUALIZATION_SCALAR_LINE = "SL"
    VISUALIZATION_HIST = "H"
    VISUALIZATION = {
        VISUALIZATION_COLOR: "COLOR",
        VISUALIZATION_CATEGORY_COLOR: "CATEGORY_COLOR",
        VISUALIZATION_SCALAR_COLOR: "SCALAR_COLOR",
        VISUALIZATION_SCALAR_LINE: "SCALAR_LINE",
        VISUALIZATION_HIST: "HIST",
    }
    visualization = models.CharField(
        max_length=2,
        choices=[(k, v) for k, v in VISUALIZATION.items()],
        default=VISUALIZATION_COLOR,
    )

    def save(self, *args, **kwargs):

        if self.order < 0:
            self.order = Timeline.objects.filter(video=self.video).count()

        super(Timeline, self).save(*args, **kwargs)

    class Meta:
        ordering = ["order"]

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "video_id": self.video.id.hex,
            "name": self.name,
            "type": self.TYPE[self.type],
            "visualization": self.VISUALIZATION[self.visualization],
            "order": self.order,
            "collapse": self.collapse,
        }

        if self.parent:
            result["parent_id"] = self.parent.id.hex
        else:
            result["parent_id"] = None

        if include_refs_hashes:
            result["timeline_segment_ids"] = [x.id.hex for x in self.timelinesegment_set.all()]
            if self.plugin_run_result:
                result["plugin_run_result_id"] = self.plugin_run_result.id.hex

        elif include_refs:
            result["timeline_segments"] = [
                x.to_dict(include_refs_hashes=include_refs_hashes, include_refs=include_refs, **kwargs)
                for x in self.timelinesegment_set.all()
            ]
        return result

    def clone(self, video=None, includeannotations=True):
        if not video:
            video = self.video
        new_timeline_db = Timeline.objects.create(video=video, name=self.name, type=self.type)

        for segment in self.timelinesegment_set.all():
            segment.clone(new_timeline_db, includeannotations)

        return new_timeline_db


class AnnotationCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    color = models.CharField(max_length=256, default=random_color_string)

    def to_dict(self, **kwargs):
        result = {
            "id": self.id.hex,
            "name": self.name,
            "color": self.color,
        }
        return result


class Annotation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(AnnotationCategory, on_delete=models.CASCADE, null=True)
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    color = models.CharField(max_length=256, default=random_color_string)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "name": self.name,
            "color": self.color,
        }
        if include_refs_hashes and self.category:
            result["category_id"] = self.category.id.hex
        elif include_refs and self.category:
            result["category"] = self.category.to_dict(include_refs_hashes=True, include_refs=False, **kwargs)
        return result


class TimelineSegment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timeline = models.ForeignKey(Timeline, on_delete=models.CASCADE)
    annotations = models.ManyToManyField(Annotation, through="TimelineSegmentAnnotation")
    color = models.CharField(max_length=256, null=True)
    start = models.FloatField(default=0)
    end = models.FloatField(default=0)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "timeline_id": self.timeline.id.hex,
            "color": self.color,
            "start": self.start,
            "end": self.end,
        }
        if include_refs_hashes:
            result["annotation_ids"] = [x.id.hex for x in self.annotations.all()]
        if include_refs:
            result["annotations"] = [
                x.to_dict(include_refs_hashes=True, include_refs=False, **kwargs) for x in self.annotations.all()
            ]
        return result

    def clone(self, timeline=None, includeannotations=True):
        if not timeline:
            timeline = self.timeline
        new_timeline_segment_db = TimelineSegment.objects.create(
            timeline=timeline, color=self.color, start=self.start, end=self.end
        )

        if not includeannotations:
            return new_timeline_segment_db

        for annotation in self.timelinesegmentannotation_set.all():
            annotation.clone(new_timeline_segment_db)

        return new_timeline_segment_db


# This is basically a many to many connection
class TimelineSegmentAnnotation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timeline_segment = models.ForeignKey(TimelineSegment, on_delete=models.CASCADE)
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.id.hex,
            "date": self.date,
        }
        if include_refs_hashes:
            result["annotation_id"] = self.annotation.id.hex
            result["timeline_segment_id"] = self.timeline_segment.id.hex
        return result

    def clone(self, timeline_segment):

        new_timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
            timeline_segment=timeline_segment,
            annotation=self.annotation,
        )
        return new_timeline_segment_annotation_db


class Shortcut(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    type = models.CharField(max_length=256, null=True)
    keys = models.JSONField(null=True)
    keys_string = models.CharField(max_length=256, null=True)

    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.id.hex,
            "date": self.date,
            "type": self.type,
            "keys": self.keys,
        }
        if include_refs_hashes:
            result["video_id"] = self.video.id.hex
        return result

    @classmethod
    def generate_keys_string(cls, keys):
        keys = set([x.lower() for x in keys])
        keys_string = []
        if "ctrl" in keys:
            keys_string.append("ctrl")
            keys.remove("ctrl")
        if "shift" in keys:
            keys_string.append("shift")
            keys.remove("shift")
        for key in keys:
            keys_string.append(key)

        return "+".join(keys_string)


class AnnotationShortcut(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shortcut = models.ForeignKey(Shortcut, on_delete=models.CASCADE)
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.id.hex,
            "date": self.date,
        }
        if include_refs_hashes:
            result["shortcut_id"] = self.shortcut.id.hex
            result["annotation_id"] = self.annotation.id.hex
        return result
