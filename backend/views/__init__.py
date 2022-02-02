from .video import VideoUpload, VideoList, VideoGet, VideoDelete
from .timeline import TimelineList, TimelineDuplicate, TimelineDelete
from .analyser import AnalyserList
from .user import get_csrf_token, login, logout, register, GetUser

# TODO this is not the best way to do it
from backend.tasks import *
