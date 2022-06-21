# from backend.tasks import *


class PluginManager:
    _plugins = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def export(cls, name):
        def export_helper(plugin):
            cls._plugins[name] = plugin
            return plugin

        return export_helper

    def __contains__(self, plugin):
        return plugin in self._plugins

    def __call__(self, video, plugin, parameters=None):
        print(f"[PluginManager] {plugin}: {parameters}", flush=True)
        if plugin not in self._plugins:
            print(f"Plugin: {plugin} not found")

        self._plugins[plugin]()(video, parameters)

    def get_results(self, analyse):
        if not hasattr(analyse, "type"):
            return None
        if analyse.type not in self._plugins:
            return None
        analyser = self._plugins[analyse.type]()
        if not hasattr(analyser, "get_results"):
            return {}
        return analyser.get_results(analyse)
