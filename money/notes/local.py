import csv
import json
from pathlib import Path

import yaml
from .parser import NotesParser


class LocalParser(NotesParser):
    def parse(file_path: str, format: str = None) -> list:
        if format and not format.startswith("."):
            format = "." + format
        extension = format or Path(file_path).suffix
        with open(file_path, "r", encoding="utf-8") as file:
            data = []
            if extension == ".csv":
                data = list(csv.DictReader(file))
            elif extension == ".json":
                data = json.load(file)
            elif extension in [".yaml", ".yml"]:
                data = yaml.safe_load(file)

        return data
