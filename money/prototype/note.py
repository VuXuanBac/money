import os
from datetime import datetime

from cmdapp.core import Prototype, Response, as_command
from cmdapp.parser import COLUMN_ID
from cmdapp.database import SQLCondition
from cmdapp.base import BasePrototype
from cmdapp.utils import Hash

from .helper import AppHelper, NoteHelper, MoneyApp
from ..constants.var import *
from ..constants.schema import *


class NotePrototype(Prototype):
    @as_command(
        description="Import transactions from a note resource",
        epilog="\n".join(
            [
                "By default, last imported record from note resource will be saved, regardless of importing outcome.",
                "It is used as a mark to not import duplicated records",
                "Use `--force` to ignore this check on this importing",
            ]
        ),
        arguments={
            "resource": "r (str[telex]): reference a saved resource by id or name",
            "force": "f (bool = 0): force to import all notes from resource and by pass all duplicating checks",
            "reserved": "s, save (str = .): folder to store notes that are not imported successfully (due to errors)",
        }
        | {
            k: TABLE_RESOURCE[k].metadata | {"required": False}
            for k in ["scope", "link", "option"]
        },
    )
    def do_import(app: MoneyApp, args):
        response = Response(app)
        if not (args.resource or args.link):
            return response.on("error").message(
                "action",
                stype="error",
                action="IMPORT",
                what="notes",
                reason="missing both 'resource' and 'link'",
            )
        # get configuration for importing: link, currency, scale,...
        if args.resource:
            metadata = AppHelper.get_record_by_name_or_id(
                app.database[TABLE_RESOURCE.name], args.resource
            )
            if not metadata:
                return response.on("error").message(
                    "found",
                    stype="error",
                    negative=True,
                    what=TABLE_RESOURCE.human_name(),
                    field="alias",
                    items=args.resource,
                )
        else:
            metadata = {}
        resource_link, note_scope, last_import_record, options = Hash.get(
            metadata,
            link=args.link,
            scope=args.scope,
            last_record=None,
            option=dict(args.option or {}),
        )

        # get new notes
        new_data = NoteHelper.parse_from_url(
            resource_link,
            None if args.force else last_import_record,
            (options or {}).get("format"),
        )
        count = len(new_data)
        if not count:
            return response.message(
                "found", style="info", negative=True, what="new notes"
            )

        # save last record to note resource database
        if args.resource:
            updated_value = dict(last_import=datetime.now(), last_record=new_data[-1])
            success = app.database[TABLE_RESOURCE.name].update(
                updated_value, SQLCondition.with_id(metadata[COLUMN_ID])
            )
            if not success:
                response.on("error").message(
                    "action",
                    style="warning",
                    action="SAVE",
                    what=TABLE_RESOURCE.human_name(),
                    argument=COLUMN_ID,
                    value=metadata[COLUMN_ID],
                    result=updated_value,
                ).concat(BasePrototype.print_database_errors(app))

        aliases = AppHelper.transaction_aliases(app)
        field_to_name = app.config.get(CONFIG_NOTE_FIELDNAMES, default={})
        # parse notes to get data to save
        sanitized_data, error_with_indices = NoteHelper.parse_notes(
            aliases,
            new_data,
            scope=note_scope,
            options=options,
            rename={v: k for k, v in field_to_name.items()},
        )

        # print invalid records
        invalid_data = []
        error_log_file = os.path.join(
            args.reserved, f'{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}.json'
        )
        response.on("error")
        for index, error in error_with_indices:
            response.message(
                "action",
                style="error",
                action="PARSE",
                what="notes to transactions",
                argument=f"notes[{index + 1}]",
                value=new_data[index],
                reason=error,
            )
            invalid_data.append(new_data[index] | {"error": str(error)})

        count = len(sanitized_data)
        # if no valid data, save errors to log or return due to no further processing
        if not count:
            return (
                response.json(invalid_data, path=error_log_file)
                if args.reserved
                else response
            )

        # print valid record - which about to saved
        response.on("output").message(
            "found",
            style="info",
            count=count,
            what="new notes",
            result="Prepare to import following notes:",
        )
        response.json(sanitized_data, separator=" | ", indent=1, allow_unicode=True)

        # save into database
        error_indices = AppHelper.save_transactions_in_scope(app, sanitized_data)
        message_kwargs = dict(action="IMPORT", what="notes")
        if not error_indices:
            response.on("output").message(
                "action",
                style="success",
                result=f"{len(sanitized_data)} notes were saved",
                **message_kwargs,
            )
        else:
            response.on("error").message("action", style="error", **message_kwargs)
            # save all invalid data: parse error, save error,...
            if args.reserved:
                invalid_data.extend(
                    [
                        sanitized_data[index] | {"error": "save error"}
                        for index in error_indices
                    ]
                )
                response.json(invalid_data, path=error_log_file)
        return response.concat(BasePrototype.print_database_errors(app))
