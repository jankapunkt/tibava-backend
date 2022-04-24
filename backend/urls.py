from django.contrib import admin
from django.urls import path

from . import views

urlpatterns = [
    path("user/csrf", views.get_csrf_token, name="get_csrf_token"),
    path("user/login", views.login, name="login"),
    path("user/logout", views.logout, name="logout"),
    path("user/register", views.register, name="register"),
    path("user/get", views.UserGet.as_view(), name="user_get"),
    #
    path("video/upload", views.VideoUpload.as_view(), name="video_upload"),
    path("video/list", views.VideoList.as_view(), name="video_list"),
    path("video/get", views.VideoGet.as_view(), name="video_get"),
    path("video/delete", views.VideoDelete.as_view(), name="video_delete"),
    #
    path("video/export/csv", views.VideoExportCSV.as_view(), name="video_export_csv"),
    path("video/export/json", views.VideoExportJson.as_view(), name="video_export_json"),
    #
    path("analyser/list", views.AnalyserList.as_view(), name="analyser_list"),
    #
    path("timeline/list", views.TimelineList.as_view(), name="timeline_list"),
    path("timeline/duplicate", views.TimelineDuplicate.as_view(), name="timeline_duplicate"),
    path("timeline/rename", views.TimelineRename.as_view(), name="timeline_rename"),
    path("timeline/delete", views.TimelineDelete.as_view(), name="timeline_delete"),
    #
    path("timeline/segment/get", views.TimelineSegmentGet.as_view(), name="timeline_segment_get"),
    path("timeline/segment/list", views.TimelineSegmentList.as_view(), name="timeline_segment_list"),
    path("timeline/segment/merge", views.TimelineSegmentList.as_view(), name="timeline_segment_list"),
    path("timeline/segment/split", views.TimelineSegmentList.as_view(), name="timeline_segment_list"),
    path("timeline/segment/annotate", views.TimelineSegmentAnnotate.as_view(), name="timeline_segment_annotate"),
    #
    path(
        "timeline/segment/annotation/list",
        views.TimelineSegmentAnnoatationList.as_view(),
        name="timeline_segment_annotation_list",
    ),
    path(
        "timeline/segment/annotation/create",
        views.TimelineSegmentAnnoatationCreate.as_view(),
        name="timeline_segment_annotation_create",
    ),
    path(
        "timeline/segment/annotation/delete",
        views.TimelineSegmentAnnoatationDelete.as_view(),
        name="timeline_segment_annotation_delete",
    ),
    #
    path("annotation/category/list", views.AnnoatationCategoryList.as_view(), name="annotation_category_list"),
    path("annotation/category/create", views.AnnoatationCategoryCreate.as_view(), name="annotation_category_create"),
    path("annotation/category/update", views.AnnoatationCategoryCreate.as_view(), name="annotation_category_create"),
    path("annotation/category/delete", views.AnnoatationCategoryCreate.as_view(), name="annotation_category_create"),
    #
    path("annotation/list", views.AnnoatationList.as_view(), name="annotation_list"),
    path("annotation/create", views.AnnoatationCreate.as_view(), name="annotation_create"),
    path("annotation/update", views.AnnoatationChange.as_view(), name="annotation_change"),
    path("annotation/delete", views.AnnoatationChange.as_view(), name="annotation_change"),
    #
    path("shortcut/list", views.ShortcutList.as_view(), name="shortcut_list"),
    path("shortcut/create", views.ShortcutCreate.as_view(), name="shortcut_create"),
    #
    path("annotation/shortcut/list", views.AnnotationShortcutList.as_view(), name="annotation_shortcut_list"),
    path("annotation/shortcut/create", views.AnnotationShortcutCreate.as_view(), name="annotation_shortcut_create"),
    path("annotation/shortcut/update", views.AnnotationShortcutUpdate.as_view(), name="annotation_shortcut_update"),
    
]
