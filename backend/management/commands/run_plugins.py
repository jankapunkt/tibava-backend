import json
from django.core.management.base import BaseCommand, CommandError
from backend.models import Video

from backend.plugin_manager import PluginManager


class Command(BaseCommand):
    help = "Closes the specified poll for voting"

    def add_arguments(self, parser):
        parser.add_argument("--video_ids", nargs="+", type=str)
        parser.add_argument("--plugin", type=str)
        parser.add_argument("--parameters", type=str)

    def handle(self, *args, **options):
        for video_id in options["video_ids"]:

            try:
                video_db = Video.objects.get(pk=video_id)
                user_db = video_db.owner
            except Video.DoesNotExist:
                raise CommandError('Poll "%s" does not exist' % video_id)

            plugin_manager = PluginManager()
            parameters = []
            if options["parameters"]:
                parameters = json.loads(options["parameters"])

            plugin_manager(options["plugin"], parameters, user=user_db, video=video_db)

            self.stdout.write(self.style.SUCCESS('Successfully start plugin "%s"' % video_id))
