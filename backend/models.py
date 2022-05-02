import uuid

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


def gen_hash_id():
    return uuid.uuid4().hex


class Video(models.Model):
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
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
            "id": self.hash_id,
            "ext": self.ext,
            "date": self.date,
            "fps": self.fps,
            "duration": self.duration,
            "height": self.height,
            "width": self.width,
        }


class VideoAnalyse(models.Model):
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=256)
    results = models.BinaryField(null=True)
    progress = models.FloatField(default=0.0)
    status = models.CharField(
        max_length=2, choices=[("Q", "Queued"), ("R", "Running"), ("D", "Done"), ("E", "Error")], default="U"
    )

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.hash_id,
            "type": self.type,
            "date": self.date,
            "update_date": self.update_date,
            "progress": self.progress,
            "status": self.status,
        }
        if include_refs_hashes:
            result["video_id"] = self.video.hash_id
        return result


class Timeline(models.Model):
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    type = models.CharField(max_length=256, null=True)
    order = models.IntegerField(default=0)
    collapse = models.BooleanField(default=False)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.hash_id,
            "video_id": self.video.hash_id,
            "name": self.name,
            "type": self.type,
            "order": self.order,
            "collapse": self.collapse,
        }
        if include_refs_hashes:
            result["timeline_segment_ids"] = [x.hash_id for x in self.timelinesegment_set.all()]
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
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    color = models.CharField(max_length=256, null=True)

    def to_dict(self, **kwargs):
        result = {
            "id": self.hash_id,
            "name": self.name,
            "color": self.color,
        }
        return result


class Annotation(models.Model):
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
    category = models.ForeignKey(AnnotationCategory, on_delete=models.CASCADE, null=True)
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    color = models.CharField(max_length=256, null=True)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.hash_id,
            "name": self.name,
            "color": self.color,
        }
        if include_refs_hashes and self.category:
            result["category_id"] = self.category.hash_id
        elif include_refs and self.category:
            result["category"] = self.category.to_dict(include_refs_hashes=True, include_refs=False, **kwargs)
        return result


class TimelineSegment(models.Model):
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
    timeline = models.ForeignKey(Timeline, on_delete=models.CASCADE)
    annotations = models.ManyToManyField(Annotation, through="TimelineSegmentAnnotation")
    color = models.CharField(max_length=256, null=True)
    start = models.FloatField(default=0)
    end = models.FloatField(default=0)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.hash_id,
            "timeline_id": self.timeline.hash_id,
            "color": self.color,
            "start": self.start,
            "end": self.end,
        }
        if include_refs_hashes:
            result["annotation_ids"] = [x.hash_id for x in self.annotations.all()]
        elif include_refs:
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
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
    timeline_segment = models.ForeignKey(TimelineSegment, on_delete=models.CASCADE)
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.hash_id,
            "date": self.date,
        }
        if include_refs_hashes:
            result["annotation_id"] = self.annotation.hash_id
            result["timeline_segment_id"] = self.timeline_segment.hash_id
        return result

    def clone(self, timeline_segment):

        new_timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
            timeline_segment=timeline_segment,
            annotation=self.annotation,
        )
        return new_timeline_segment_annotation_db


class TimelineAnalyse(models.Model):
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
    timeline = models.ForeignKey(Timeline, on_delete=models.CASCADE)
    video_analyse = models.ForeignKey(VideoAnalyse, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.hash_id,
            "date": self.date,
        }
        if include_refs_hashes:
            result["video_analyse_id"] = self.video_analyse.hash_id
            result["timeline_id"] = self.timeline.hash_id
        return result


class Shortcut(models.Model):
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    type = models.CharField(max_length=256, null=True)
    keys = models.JSONField(null=True)
    keys_string = models.CharField(max_length=256, null=True)

    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.hash_id,
            "date": self.date,
            "type": self.type,
            "keys": self.keys,
        }
        if include_refs_hashes:
            result["video_id"] = self.video.hash_id
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
    hash_id = models.CharField(max_length=256, default=gen_hash_id)
    shortcut = models.ForeignKey(Shortcut, on_delete=models.CASCADE)
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.hash_id,
            "date": self.date,
        }
        if include_refs_hashes:
            result["shortcut_id"] = self.shortcut.hash_id
            result["annotation_id"] = self.annotation.hash_id
        return result
