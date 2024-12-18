from cmdapp.base import BasePrototype
from cmdapp.core import start_app
from cmdapp.database import Database


def prepare_database(path: str):
    try:
        from .constants.schema import DATABASE_SCHEMA
    except ImportError:
        import os
        from cmdapp.generator import generate_schema
        from .constants.schema_def import TABLE_LISTS

        file_directory = os.path.dirname(os.path.abspath(__file__))
        generate_schema(
            TABLE_LISTS,
            os.path.join(file_directory, "constants", "schema.py"),
            format="python",
        )
        from .constants.schema import DATABASE_SCHEMA

    database = Database(path, DATABASE_SCHEMA)
    good = database.prepare()
    return database, good


import os
from .constants.var import ENV_DATABASE_PATH, ENV_CONFIG_PATH

DATABASE_FILE_PATH = os.environ.get(ENV_DATABASE_PATH, "money.db")
CONFIG_PATH = os.environ.get(ENV_CONFIG_PATH, "config.txt")

database, good = prepare_database(DATABASE_FILE_PATH)

if not good:
    errors = database.get_errors()
    print(
        "Failed to initialize the database. Check the SQLite syntax!\n"
        + "\n".join(
            [
                f"[{error['table']}] ERROR [{error['type']}] '{error['message']}' on executing\n{error['sql']}"
                for error in errors
            ]
        )
    )
else:
    from .prototype import *
    from .prototype.app import MoneyApp
    from .constants.template import RESPONSE_FORMATTER

    start_app(
        app_prototypes=[
            BasePrototype(database, category="Database Commands"),
            NotePrototype(category="Expense Commands"),
            ReportPrototype(category="Expense Commands"),
            EventPrototype(category="Expense Commands"),
        ],
        app_class=MoneyApp,
        builtin_command_category="Builtin Commands",
        app_name="Money",
        database=database,
        response_formatter=RESPONSE_FORMATTER,
        config_path=CONFIG_PATH,
    )
