# from backend.tasks import *


class Analyser:
    _analyser = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def export(cls, name):
        def export_helper(plugin):
            cls._analyser[name] = plugin
            return plugin

        return export_helper

    def __contains__(self, plugin):
        return plugin in self._analyser

    def __call__(self, video, plugins=None):
        if plugins is None:
            plugins = list(self._analyser.keys())
        
        for plugin in plugins:
            if plugin not in self._analyser:
                print(f"Analyser: {plugin} not found")
                continue

            self._analyser[plugin]()(video)

        # print(self._analyser)
        # print(video)
        # print(plugins)
