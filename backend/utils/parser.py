from typing import Dict, List


class Parser:
    def __init__(self):
        self.valid_parameter = {}

    def __call__(self, parameters: Dict = None, **kwargs) -> Dict:
        if not parameters:
            parameters = []

        task_parameter = {}
        for k, v in self.valid_parameter.itmes():
            if v.get("default"):
                task_parameter[k] = v.get("default")

        for p in parameters:
            if p["name"] not in self.valid_parameter:
                return None

            try:
                parser = self.valid_parameter[p["name"]].get("parser")

                value = parser(p["value"])
                task_parameter[k] = value

            except:
                return None

        for k, v in self.valid_parameter.itmes():
            if v.get("required", None):
                if k not in task_parameter:
                    return None

        return task_parameter
