class NotesParser:
    def parse_table(table):
        rows = table.find_all("tr")
        if not rows:
            return []

        headers = table.find_all("th") or rows[0]
        headers_text = [header.get_text(strip=True) for header in headers]

        headers_text = [h for h in headers_text if h]
        table_data = []

        for row in rows[1:]:
            row_text = row.get_text(strip=True)
            if not row_text:
                continue
            cells = row.find_all("td")

            cells_text = [cell.get_text("\n", strip=True) or None for cell in cells]

            table_data.append(dict(zip(headers_text, cells_text)))

        return table_data

    def find_new(records: list[dict], last_value: dict):
        for index, record in enumerate(records):
            if all(record.get(k) == v for k, v in last_value.items()):
                return records[index + 1 :]
        return records
