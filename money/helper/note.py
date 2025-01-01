import re
import os
from datetime import datetime

from cmdapp.core import Response
from cmdapp.utils import URI, Hash
from cmdapp.parser import COLUMN_ID, COLUMN_DELETE, COLUMN_CREATE, COLUMN_UPDATE
from cmdapp.database import SQLCondition

from cmdapp.base import Alias

from ..constants.schema import *
from ..constants.var import SCOPE_ORDER, SCOPE_SHARING, SCOPE_TX, SHARE_NOTE_PATTERN
from ..notes import *

from ..app import MoneyApp

from .app import AppHelper


NOTE_ALLOW_FIELDS = set(
    list(TABLE_TRANSACTION.columns)
    + list(TABLE_SHARING.columns)
    + list(TABLE_ORDER.columns)
).difference([COLUMN_ID, COLUMN_DELETE, COLUMN_UPDATE, COLUMN_CREATE, "tx"])


class NoteHelper:
    def eval_amount(input: str):
        expression = input.replace("^", "**").replace(",", "")
        if re.fullmatch(r"[\d\.\+\-*/%()]+", expression):
            try:
                return eval(expression)
            except:
                pass
        raise ValueError(
            f"Invalid 'amount' [{input}], expect a float or a math expression"
        )

    def parse_from_url(url, last_record=None, format=None):
        path, is_remote = URI.resolve(url)
        if not is_remote:
            data = LocalParser.parse(path, format or None)
        elif path.startswith("https://monogr.ph/"):
            data = NotesnookParser.parse(path)
        new_data = data if not last_record else NotesParser.find_new(data, last_record)
        return new_data

    def sanitize_transaction(aliases: Alias, note: dict):
        note["payer"] = aliases.resolve(TABLE_WALLET.name, note.get("payer"))
        note["receiver"] = aliases.resolve(TABLE_WALLET.name, note.get("receiver"))
        note["category"] = aliases.resolve(TABLE_TAG.name, note.get("category"))
        note["amount"] = NoteHelper.eval_amount(note["amount"])

        sanitized_note: dict = TABLE_TRANSACTION.sanitize_data(note)
        if not (sanitized_note.get("payer") or sanitized_note.get("receiver")):
            raise ValueError("Missing both payer and receiver")

        return sanitized_note

    def sanitize_order(aliases: Alias, note: dict):
        items = note.pop("items", "")
        if isinstance(items, (list, tuple)):
            note["items"] = items
        else:
            note["items"] = str(items).splitlines()
        note["tag"] = aliases.resolve(TABLE_TAG.name, note.get("tag"))
        sanitized_note: dict = TABLE_ORDER.sanitize_data(note)
        if not (sanitized_note.get("items")):
            raise ValueError("Missing order items")
        return sanitized_note

    def sanitize_sharing(aliases: Alias, note: dict):
        shares = note.get("shares", "")
        if not isinstance(shares, (list, tuple)):
            items = re.findall(SHARE_NOTE_PATTERN, str(shares))
            people, shares = [], []
            for item in items:
                people.append(item[0])
                shares.append(item[1] or 1.0)
        else:
            people = note.get("people", [])
        note["tag"] = aliases.resolve(TABLE_TAG.name, note.get("tag"))
        note["people"] = aliases.resolve(TABLE_ACCOUNT.name, people) or []
        note["shares"] = [float(sh) for sh in shares] + [1.0] * (
            len(note["people"]) - len(shares)  # empty array if negative
        )
        sanitized_note: dict = TABLE_SHARING.sanitize_data(note)
        if not (sanitized_note.get("people")):
            raise ValueError("Missing shared people")
        return sanitized_note

    def parse_notes(
        aliases: Alias,
        note_entries: list[dict],
        scope: str = None,
        options: dict = None,
        rename: dict[str, str] = None,
    ):
        result = []
        error_with_indices = []
        options = options or {}
        scale = float(options.pop("scale", 1.0))
        for index, note in enumerate(note_entries):
            try:
                _note = Hash.filter(note, *NOTE_ALLOW_FIELDS, rename=rename or {})
                _note = Hash.merge(_note, options)
                transaction_data = NoteHelper.sanitize_transaction(aliases, _note)
                transaction_data["amount"] *= scale
                if scope == SCOPE_ORDER:
                    scope_data = {scope: NoteHelper.sanitize_order(aliases, _note)}
                elif scope == SCOPE_SHARING:
                    scope_data = {scope: NoteHelper.sanitize_sharing(aliases, _note)}
                else:
                    scope_data = {}

                result.append({SCOPE_TX: transaction_data} | scope_data)
            except Exception as err:
                error_with_indices.append((index, err))
        return result, error_with_indices

    def update_last_record(app: MoneyApp, resource_id: int, last_record: dict):
        updated_value = dict(last_import=datetime.now(), last_record=last_record)
        success = app.database[TABLE_RESOURCE.name].update(
            updated_value, SQLCondition.with_id(resource_id)
        )
        response = Response(app)
        if not success:
            return (
                response.on("error")
                .message(
                    "action",
                    style="warning",
                    action="SAVE",
                    what=TABLE_RESOURCE.human_name(),
                    argument=COLUMN_ID,
                    value=resource_id,
                    result=updated_value,
                )
                .concat(AppHelper.get_database_errors(app))
            )
        return response

    def get_error_log_file(dir: str):
        return os.path.join(dir, f'{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}.json')
