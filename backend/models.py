from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class Video(models.Model):
    owner = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    license = models.CharField(max_length=256)
    hash_id = models.CharField(max_length=256)
    ext = models.CharField(max_length=256)
    date = models.DateTimeField(auto_now_add=True)
    # some extracted meta information
    fps = models.FloatField(blank=True, null=True)
    duration = models.FloatField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    width = models.IntegerField(blank=True, null=True)

    def to_dict(self):
        return {
            "name": self.name,
            "license": self.license,
            "hash_id": self.hash_id,
            "ext": self.ext,
            "date": self.date,
            "fps": self.fps,
            "duration": self.duration,
            "height": self.height,
            "width": self.width,
        }


class VideoAnalyse(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=256)
    hash_id = models.CharField(max_length=256)
    results = models.BinaryField(null=True)
    progres = models.FloatField(default=0.0)
    status = models.CharField(
        max_length=2, choices=[("Q", "Queued"), ("R", "Running"), ("D", "Done"), ("E", "Error")], default="U"
    )

    def to_dict(self):
        return {
            "type": self.type,
            "date": self.date,
            "update_date": self.update_date,
            "progres": self.progres,
            "status": self.status,
        }
