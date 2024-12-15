from cmdapp.core import Prototype, Response, as_command

from ..constants.schema import *
from ..constants.var import CONFIG_EVENT_FIELDNAMES
from ..notes import *

from .helper import AppHelper, EventHelper, MoneyApp


class EventPrototype(Prototype):
    @as_command(
        description="Close an event (labeld with a tag) and summarize sharing transactions within that event",
        arguments={
            "event": "o, open (str[telex]): review saved event",
            "tag": TABLE_EVENT["tag"].metadata
            | {"dtype": "str", "metavar": "tag", "required": False},
            "currency": TABLE_EVENT["currency"].metadata | {"required": False},
            "rates": "[currency=rate] r (json[float]): conversion rates from other currencies to chosen currency.\nExample: `usd=23500` means convert 1 usd to 23500 chosen currency",
            "ignore": "(bool = 0): set to ignore transactions with unexpected currencies\n(not provide conversion rates), otherwise raise error",
            "name": "n (str[telex]): name (title) of the report",
            "export": "[file] p (str): save sharing transactions into invoice file",
            "format": "f (str = html): invoice file format",
            "rename": "[name=new_name] q (json[str]): rename invoice fields. The orders are important",
            "save": "(bool = 0): set to create event for this summarization",
        },
    )
    def do_event(app: MoneyApp, args):
        response = Response(app)
        if not (args.event or (args.tag and args.currency)):
            return response.on("error").message(
                "action",
                stype="error",
                action="SUMMARIZE",
                what="event",
                reason="missing both 'event' and 'tag'",
            )
        if args.event:
            event_attributes = AppHelper.get_record_by_name_or_id(
                app.database[TABLE_EVENT.name], args.event
            )
            if not event_attributes:
                return response.on("error").message(
                    "found",
                    stype="error",
                    negative=True,
                    what=TABLE_EVENT.human_name(),
                    field="alias",
                    items=args.event,
                )
            tag_id = event_attributes["tag"]
            event_name = event_attributes["name"]
        else:
            conversion_rates = dict(args.rates or {})
            event_name = args.name
            # filter sharings
            sharings = AppHelper.get_sharings(app, args.tag)

            count = len(sharings)
            if not count:
                return response.on("error").message(
                    "found",
                    style="info",
                    negative=True,
                    what=TABLE_SHARING.human_name(),
                    field="tag",
                    items=args.tag,
                )
            response.message(
                "found", style="info", count=count, what=TABLE_SHARING.human_name(count)
            )
            tag_id = sharings[0]["tag"]
            # parse sharings to get event attributes
            try:
                event_attributes = EventHelper.analyze_sharing(
                    sharings, args.currency, conversion_rates, args.ignore
                )
            except Exception as err:
                return response.on("error").message(
                    "action",
                    style="error",
                    action="ANALYZE",
                    what=TABLE_SHARING.human_name(2),
                    reason=err,
                )

        # make report
        event_tag = app.database[TABLE_TAG.name].get(tag_id) or {}
        response.concat(EventHelper.make_report(app, event_attributes, event_tag))

        # create new event
        if not args.event and args.save:
            response.concat(
                AppHelper.save_record(
                    app, TABLE_EVENT, event_attributes | {"name": event_name}
                )
            )

        # export invoices
        if not args.export:
            return response
        invoices = EventHelper.get_sharing_invoices(app, event_attributes["sharings"])

        fieldnames = app.config.get(CONFIG_EVENT_FIELDNAMES) or dict(args.rename or {})
        return response.concat(
            AppHelper.export_to_file(
                app,
                invoices,
                args.export,
                args.format,
                title=f"{event_name} Invoices",
                description=event_tag["description"],
                rename=fieldnames,
                what="invoices",
            )
        )
