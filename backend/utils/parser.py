import logging
from typing import Dict, List


class Parser:
    def __init__(self):
        self.valid_parameter = {}

    def __call__(self, parameters: Dict = None, **kwargs) -> Dict:
        if not parameters:
            parameters = []

        task_parameter = {}
        for k, v in self.valid_parameter.items():
            if v.get("default"):
                task_parameter[k] = v.get("default")

        for p in parameters:
            if p["name"] not in self.valid_parameter:
                logging.error(f"[Parser] {p['name']} unknown")
                return None

            try:
                parser = self.valid_parameter[p["name"]].get("parser", lambda x: x)

                value = parser(p["value"])
                task_parameter[p["name"]] = value

            except Exception as e:
                logging.error(f"[Parser] {p['name']} could not parse ({e})")
                return None
        print(f"Task Parameter {task_parameter}", flush=True)
        for k, v in self.valid_parameter.items():
            if v.get("required", None):
                if k not in task_parameter:
                    logging.error(f"[Parser] {k} is required")
                    return None

        return task_parameter
