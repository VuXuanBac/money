from cmdapp.core import Prototype, Response, as_command
from cmdapp.utils import Hash
from cmdapp.parser import COLUMN_ID

from ..constants.schema import *
from ..constants.var import CONFIG_REPORT_FIELDNAMES

from .helper import AppHelper, ReportHelper, MoneyApp


class ReportPrototype(Prototype):
    @as_command(
        description="Report for transactions filtered by some criteria",
        arguments={
            "report": "o, open (str[telex]): review saved report",
            "start": "[timestamp] s (datetime): filter by datetime that not earlier than provided timestamp",
            "end": "[timestamp] e (datetime): filter by datetime that not later than provided timestamp",
            "categories": "[tags] t (array[telex]): filter by one or many categories",
            "wallets": "[wallets] w (array[telex]): filter by one or many wallets",
            "relates": "[accounts] a, account (array[telex]): filter by one or many related accounts",
            "currencies": "c (list[str]): filter by one or many currencies",
            "name": "n (str[telex]): name (title) of the report",
            "export": "[file] p (str): save transactions into invoice file",
            "format": "f (str = html): invoice file format",
            "rename": "[name=new_name] q (json[telex]): rename invoice fields. The orders are important",
            "save": "(bool = 0): set to save report into database",
        },
    )
    def do_report(app: MoneyApp, args):
        response = Response(app)
        if args.report:
            report_attributes = AppHelper.get_record_by_name_or_id(
                app.database[TABLE_REPORT.name], args.report
            )
            if not report_attributes:
                return response.on("error").message(
                    "found",
                    stype="error",
                    negative=True,
                    what=TABLE_REPORT.human_name(),
                    field="alias",
                    items=args.report,
                )
            filters = report_attributes["filters"]
            use_filters = dict(ids=report_attributes["txs"])
            report_name = report_attributes["name"]
        else:
            filters = Hash.filter(
                vars(args),
                "categories",
                "wallets",
                "currencies",
                relates="accounts",
                start="start_time",
                end="end_time",
            )
            use_filters = filters
            report_name = args.name
        try:
            transactions = AppHelper.filter_transactions(app, **use_filters)
        except Exception as error:
            return response.on("error").message(
                "exception", style="error", message=error
            )
        count = len(transactions)
        response.message(
            "found", style="info", count=count, what=TABLE_TRANSACTION.human_name(count)
        )
        if not count:
            return response
        report_description = ReportHelper.report_description(filters)

        response.message(
            None, f"{report_name.upper()}\n{report_description}\n", style="info"
        )
        report_data = ReportHelper.report_by_categories(
            transactions, bool(args.wallets), bool(args.relates)
        )
        response.table(report_data)

        # create new report
        if not args.report and args.save:
            report_attributes = {
                "name": report_name,
                "filters": filters,
                "txs": [tx[COLUMN_ID] for tx in transactions],
                "data": report_data,
            }
            response.concat(AppHelper.save_record(app, TABLE_REPORT, report_attributes))

        # export invoices
        if not args.export:
            return response

        fieldnames = app.config.get(CONFIG_REPORT_FIELDNAMES) or dict(args.rename or {})
        print(fieldnames)
        return response.concat(
            AppHelper.export_to_file(
                app,
                transactions,
                args.export,
                args.format,
                title=report_name,
                description=report_description,
                rename=fieldnames,
                what="invoices",
            )
        )
