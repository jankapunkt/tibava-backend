from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


# class Collection(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     hash_id = models.CharField(max_length=256)
#     name = models.CharField(max_length=256)
#     visibility = models.CharField(
#         max_length=2, choices=[("V", "Visible"), ("A", "Authenticated"), ("U", "User")], default="U"
#     )
#     status = models.CharField(max_length=2, choices=[("U", "Upload"), ("R", "Ready"), ("E", "Error")], default="U")
#     progress = models.FloatField(default=0.0)
#     date = models.DateTimeField(auto_now_add=True)


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


class VideoAnalyse(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=256)
    hash_id = models.CharField(max_length=256)
    results = models.CharField(max_length=256)
    status = models.CharField(
        max_length=2, choices=[("Q", "Queued"), ("R", "Running"), ("D", "Done"), ("E", "Error")], default="U"
    )


# class UploadedImage(models.Model):
#     date = models.DateTimeField(auto_now_add=True)
#     name = models.CharField(max_length=256)
#     hash_id = models.CharField(max_length=256)


# class ImageUserRelation(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     image = models.ForeignKey(Image, on_delete=models.CASCADE)
#     date = models.DateTimeField(auto_now_add=True)
#     # TODO on delete
#     library = models.BooleanField(default=False)

#     def __str__(self):
#         return f"{self.user} {self.image.hash_id} {self.library}"


# class ImageUserTag(models.Model):
#     name = models.CharField(max_length=256)
#     ImageUserRelation = models.ForeignKey(ImageUserRelation, on_delete=models.CASCADE)
