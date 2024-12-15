from .parser import NotesParser
import requests
from bs4 import BeautifulSoup


class NotesnookParser(NotesParser):
    def parse(monograph_url: str) -> list:
        response = requests.get(monograph_url)
        if not response.status_code == 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        tables = soup.find_all("table")

        data = []
        for table in tables:
            data.extend(NotesParser.parse_table(table))

        return data
