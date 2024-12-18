import re
from datetime import datetime
from cmdapp.core import Response
from cmdapp.utils import URI, Hash, Terminal, Platform
from cmdapp.parser import COLUMN_ID, COLUMN_DELETE, COLUMN_CREATE, COLUMN_UPDATE
from cmdapp.database import SQLCondition, SQLOperators
from cmdapp.base import Alias, BasePrototype
from cmdapp.render.table import Tabling

from ..constants.schema import *
from ..constants.var import *
from ..notes import *

from .app import MoneyApp

NOTE_ALLOW_FIELDS = set(
    list(TABLE_TRANSACTION.columns)
    + list(TABLE_SHARING.columns)
    + list(TABLE_ORDER.columns)
).difference([COLUMN_ID, COLUMN_DELETE, COLUMN_UPDATE, COLUMN_CREATE, "tx"])


class AppHelper:
    def get_record_by_name_or_id(table, value: str, column: str = "name"):
        record = table.query(
            condition=SQLCondition(COLUMN_ID, SQLOperators.EQUAL, value).OR(
                column, SQLOperators.EQUAL, value
            )
        )
        return None if not record else record[0]

    def save_record(app: MoneyApp, table_meta: TableMeta, data: dict):
        record_id = app.database[table_meta.name].insert(data)
        response = Response(app)
        if not record_id:
            response.on("error").message(
                "action", style="error", action="CREATE", what=table_meta.human_name()
            ).concat(BasePrototype.print_database_errors(app))
        else:
            response.message(
                "action",
                style="success",
                action="CREATE",
                what=table_meta.human_name(),
                argument=COLUMN_ID,
                value=record_id,
            )
        return response

    def export_to_file(
        app: MoneyApp,
        data: list[dict],
        path: str,
        format: str,
        **options,
    ):
        if not hasattr(app.response_formatter, format):
            return (
                Response(app)
                .on("error")
                .message(
                    "action",
                    style="error",
                    argument="format",
                    value=format,
                    reason=f"this format is not supported. Use following formats: {app.response_formatter.support_file_formats}",
                )
            )
        options.setdefault("indent", 2)
        return (
            Response(app)
            .on("output")
            .__getattr__(format)(data, path=path, **options)
            .message(
                "action",
                style="success",
                action="EXPORT",
                what=options.pop("what", "item"),
                result=f"Check the file at [{Platform.abs(path)}]",
            )
        )

    def transaction_aliases(app: MoneyApp, full_record: bool = False):
        table_names = [TABLE_ACCOUNT.name, TABLE_TAG.name, TABLE_WALLET.name]
        return Alias(app.database, table_names, full_record=full_record)

    def save_transaction_in_scope(app: MoneyApp, data: dict[str, dict]) -> int:
        transaction_data = data[SCOPE_TX]
        tx_id = app.database[TABLE_TRANSACTION.name].insert(transaction_data)
        if not tx_id:
            return False
        order_data = data.get(SCOPE_ORDER)
        if order_data:
            order_data["tx"] = tx_id
            order_id = app.database[TABLE_ORDER.name].insert(order_data)
            return order_id > 0
        sharing_data = data.get(SCOPE_SHARING)
        if sharing_data:
            sharing_data["tx"] = tx_id
            sharing_id = app.database[TABLE_SHARING.name].insert(sharing_data)
            return sharing_id > 0
        return True

    def save_transactions_in_scope(
        app: MoneyApp, data: list[dict[str, dict]]
    ) -> list[int]:
        error_indices = []
        for index, data_item in enumerate(data):
            handler = lambda conn: AppHelper.save_transaction_in_scope(app, data_item)
            success = app.database.with_transaction(handler=handler)
            if not success:
                error_indices.append(index)
        return error_indices

    def get_sharings(
        app: MoneyApp, tag: int | str = None, sharing_ids: list[int] = None
    ):
        if sharing_ids:
            condition = SQLCondition(
                f"sharing.{COLUMN_ID}", SQLOperators.IN, sharing_ids
            )
        else:
            condition = SQLCondition(
                f"tx.{COLUMN_DELETE}", SQLOperators.IS_NULL
            ).AND_GROUP(
                SQLCondition("tag.name", SQLOperators.EQUAL, tag).OR(
                    "tag.id", SQLOperators.EQUAL, tag
                )
            )
        sql = f"""
        select sharing.id, sharing.people, sharing.shares, sharing.tag,
                   sharing.tx, tx.amount, tx.currency,
                   payer_wallet.account as payer, receiver_wallet.account as receiver
        from sharing
        join tx on tx.id = sharing.tx
        left join tag on tag.id = sharing.tag
        left join wallet as payer_wallet on payer_wallet.id = tx.payer
        left join wallet as receiver_wallet on receiver_wallet.id = tx.receiver
        where {condition.build()}
        """

        return app.database.query(sql)

    def get_sharing_invoices(app: MoneyApp, sharing_ids: list[int]):
        condition = SQLCondition(f"sharing.id", SQLOperators.IN, sharing_ids)
        sql = f"""
        select tx.id, tx.timestamp, tx.amount, tx.message, tx.currency,
                   payer_wallet.account as payer, receiver_wallet.account as receiver,
                   sharing.people, sharing.shares, tag.name as tag
        from sharing
        join tx on tx.id = sharing.tx
        left join tag on tag.id = sharing.tag
        left join wallet as payer_wallet on payer_wallet.id = tx.payer
        left join wallet as receiver_wallet on receiver_wallet.id = tx.receiver
        where {condition.build()}
        """

        return app.database.query(sql)

    def filter_transactions(
        app: MoneyApp,
        start_time=None,
        end_time=None,
        currencies: list[str] = None,
        categories: list[str] = None,
        wallets: list[str] = None,
        accounts: list[str] = None,
        ids: list[int] = None,
    ):
        if ids:
            condition = SQLCondition(f"tx.id", SQLOperators.IN, ids)
        else:
            condition = SQLCondition(f"tx.{COLUMN_DELETE}", SQLOperators.IS_NULL)
            if start_time:
                condition.AND(
                    f"tx.timestamp", SQLOperators.GREATER_THAN_OR_EQUAL, start_time
                )
            if end_time:
                condition.AND(
                    f"tx.timestamp", SQLOperators.LESS_THAN_OR_EQUAL, end_time
                )
            if currencies:
                condition.AND(f"tx.currencies", SQLOperators.IN, currencies)
            if categories:
                condition.AND_GROUP(
                    SQLCondition(f"tag.name", SQLOperators.IN, categories).OR(
                        f"tag.id", SQLOperators.IN, categories
                    )
                )
            if wallets:
                condition.AND_GROUP(
                    SQLCondition(f"payer_wallet.name", SQLOperators.IN, wallets)
                    .OR(f"payer_wallet.id", SQLOperators.IN, wallets)
                    .OR(f"receiver_wallet.name", SQLOperators.IN, wallets)
                    .OR(f"receiver_wallet.id", SQLOperators.IN, wallets)
                )
            if accounts:
                condition.AND_GROUP(
                    SQLCondition(f"payer_account.name", SQLOperators.IN, accounts)
                    .OR(f"payer_account.id", SQLOperators.IN, accounts)
                    .OR(f"receiver_account.name", SQLOperators.IN, accounts)
                    .OR(f"receiver_account.id", SQLOperators.IN, accounts)
                )
        sql = f"""
        select tx.id, tx.timestamp, tx.amount, tx.message, tx.currency,
                  payer_account.name as payer, receiver_account.name as receiver,
                  payer_wallet.name as source, receiver_wallet.name as destination,
                  tag.name as category
        from tx
        left join tag on tag.id = tx.category
        left join wallet as payer_wallet on payer_wallet.id = tx.payer
        left join wallet as receiver_wallet on receiver_wallet.id = tx.receiver
        left join account as payer_account on payer_account.id = payer_wallet.account
        left join account as receiver_account on receiver_account.id = receiver_wallet.account
        where {condition.build()}
        """

        return app.database.query(sql)


class NoteHelper:
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
        note["people"] = aliases.resolve(TABLE_ACCOUNT.name, people)
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
        scale: int = None,
        currency: str = None,
        rename: dict[str, str] = None,
    ):
        result = []
        error_with_indices = []
        for index, note in enumerate(note_entries):
            try:
                _note = Hash.filter(note, *NOTE_ALLOW_FIELDS, rename=rename or {})
                transaction_data = NoteHelper.sanitize_transaction(aliases, _note)
                if scale:
                    transaction_data["amount"] *= scale
                if currency:
                    transaction_data["currency"] = currency
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


class EventHelper:
    def get_initial_bill():
        return {BILL_PAID: 0.0, BILL_RECEIVED: 0.0, BILL_NEEDS: 0.0}

    def group_bills_with_least_transfer(
        positive: dict[str, float], negative: dict[str, float]
    ) -> list[tuple]:
        sorted_negative = sorted(negative.items(), key=lambda item: -item[1])
        sorted_positive = sorted(positive.items(), key=lambda item: -item[1])
        transfers = []
        nindex = 0
        for pkey, pvalue in sorted_positive:
            while pvalue > 0 and nindex < len(sorted_negative):
                nkey, nvalue = sorted_negative[nindex]
                if nvalue > pvalue:
                    transfers.append((nkey, pkey, pvalue))
                    sorted_negative[nindex] = (nkey, nvalue - pvalue)
                    break
                else:
                    transfers.append((nkey, pkey, nvalue))
                    pvalue = pvalue - nvalue
                nindex = nindex + 1
        return transfers

    def report_bills(response: Response, bills: list[dict], name_resolver):
        column_width = Tabling.get_single_column_width(6)
        formatted_bills = []
        for bill_item in bills:
            format_bill = {}
            row_person = bill_item[BILL_PERSON]
            for key, value in bill_item.items():
                if key == BILL_PERSON:
                    value = name_resolver(row_person)
                else:
                    value = f"{value:,.0f}".rjust(column_width)
                format_bill[key.upper()] = value
            formatted_bills.append(format_bill)
        formatted_bills = sorted(formatted_bills, key=lambda x: x[BILL_REFUND.upper()])
        return response.table(formatted_bills)

    def report_transfers(response: Response, bills: list[dict], name_resolver):
        response.message(
            None,
            f"\n\nTransfers to refund\n",
            style="info",
        )
        column_width = Tabling.get_single_column_width(3)
        refund_by_person = {bill[BILL_PERSON]: bill[BILL_REFUND] for bill in bills}
        positive_refund = {
            key: value for key, value in refund_by_person.items() if value >= 0
        }
        negative_refund = {
            key: -value for key, value in refund_by_person.items() if value < 0
        }
        transfers = EventHelper.group_bills_with_least_transfer(
            positive_refund, negative_refund
        )
        formatted_transfers = []
        for transfer in transfers:
            payer, receiver, amount = transfer
            formatted_transfers.append(
                {
                    BILL_TRANSFER_FROM.upper(): name_resolver(payer).center(
                        column_width
                    ),
                    BILL_TRANSFER_TO.upper(): name_resolver(receiver).center(
                        column_width
                    ),
                    BILL_TRANSFER_AMOUNT.upper(): f"{amount:,.0f}".rjust(column_width),
                }
            )

        return response.table(formatted_transfers)

    def make_report(app: MoneyApp, event: dict, tag: dict):
        target_currency = event.get("currency") or ""
        conversion_rates = event.get("rates") or {}
        bills = event.get("bills") or []
        people = app.database[TABLE_ACCOUNT.name].get_columns(
            ["name"], [bill.get(BILL_PERSON) for bill in bills]
        )
        header = f'   {event.get("name") or tag.get("name") or ""}   '
        response = Response(app).message(
            None,
            "\n".join(
                [
                    header.center(Terminal.width() - 30, "-"),
                    f"- {'Description':<20}: {(tag.get('description') or 'Summary')}",
                    f"- {'Total transactions':<20}: {len(event.get('sharings') or [])}",
                    f"- {'Currency':<20}: {target_currency}",
                    f"- {'Conversion rates':<20}:" if conversion_rates else "",
                ]
                + [
                    f"  + {currency} = {rate} {target_currency}"
                    for currency, rate in conversion_rates.items()
                ]
            )
            + "\n",
        )
        if not bills:
            return response
        for bill_item in bills:
            bill_item[BILL_REFUND] = bill_item[BILL_PAID] - bill_item[BILL_NEEDS]
        name_resolver = lambda key: people.get(key) or ANONYMOUS_NAME
        EventHelper.report_bills(response, bills, name_resolver)
        EventHelper.report_transfers(response, bills, name_resolver)
        return response

    def get_sharing_invoices(app: MoneyApp, sharing_ids: list[int]):
        account_names = app.database[TABLE_ACCOUNT.name].get_columns(["name"])
        name_resolver = lambda key: account_names.get(key, key) or ""

        invoice_transactions = AppHelper.get_sharing_invoices(app, sharing_ids)
        for record in invoice_transactions:
            record["people"] = [name_resolver(key) for key in record["people"]]
            record["payer"] = name_resolver(record["payer"])
            record["receiver"] = name_resolver(record["receiver"])
        return invoice_transactions

    def analyze_sharing(
        sharings: list[dict],
        target_currency: str,
        conversion_rates: dict = {},
        ignore_unknown_currency: bool = False,
    ) -> dict:
        event = {}
        if not sharings:
            return {}
        event["currency"] = target_currency
        event["rates"] = conversion_rates or None
        event["tag"] = sharings[0]["tag"]
        event["sharings"] = []
        bills = {}
        for sharing in sharings:
            amount = sharing.get("amount", 0.0)
            currency = sharing.get("currency", None)
            if currency != target_currency:
                if currency in conversion_rates:
                    amount *= conversion_rates[currency]
                elif ignore_unknown_currency:
                    continue
                else:
                    raise ValueError(
                        f'Missing conversion from currency `{currency}` into `{target_currency}` in transaction {COLUMN_ID} = {sharing["tx"]}'
                    )
            people, shares, payer, receiver = Hash.get(
                sharing, people=[], shares=[], payer=None, receiver=None
            )
            payer_bill = bills.setdefault(payer, EventHelper.get_initial_bill())
            receiver_bill = bills.setdefault(receiver, EventHelper.get_initial_bill())
            payer_bill[BILL_PAID] += amount
            receiver_bill[BILL_RECEIVED] += amount
            shares = (shares or []) + [1.0] * (len(people) - len(shares))
            total_shares = sum(shares)
            for share, person in zip(shares, people):
                person_bill = bills.setdefault(person, EventHelper.get_initial_bill())
                person_bill[BILL_NEEDS] += amount * share / total_shares
            event["sharings"].append(sharing[COLUMN_ID])
        event["bills"] = [{BILL_PERSON: key} | value for key, value in bills.items()]
        return event

    def parse_conversion_rates(rates: list[str]):
        conversion_rates = {}
        for rate in rates:
            matched = re.match(CONVERSION_RATE_PATTERN, rate)
            if not matched:
                raise ValueError(f"Can not convert the rate `{rate}`")
            currency, value = matched.groups()
            conversion_rates[currency] = float(value)
        return conversion_rates


class ReportHelper:
    def get_group_keys_parser(has_wallet: bool = True, has_account: bool = True):
        if not has_wallet:
            return lambda tx: (tx["payer"], tx["receiver"])
        if not has_account:
            return lambda tx: (tx["source"], tx["destination"])
        return lambda tx: (
            (tx["source"], tx["payer"]),
            (tx["destination"], tx["receiver"]),
        )

    def group_by_categories_currency(transactions: list[dict], group_keys_parser):
        categories = {}
        keys = set()
        for tx in transactions:
            amount = tx["amount"]
            category_data = categories.setdefault((tx["category"], tx["currency"]), {})
            key_out, key_in = group_keys_parser(tx)
            payer_data = category_data.setdefault(
                key_out, {REPORT_IN: 0.0, REPORT_OUT: 0.0}
            )
            payer_data[REPORT_OUT] += amount
            receiver_data = category_data.setdefault(
                key_in, {REPORT_IN: 0.0, REPORT_OUT: 0.0}
            )
            keys.update([key_in, key_out])
            receiver_data[REPORT_IN] += amount
        return categories, list(keys)

    def report_by_categories(
        transactions: list[dict],
        show_wallet: bool = True,
        show_account: bool = True,
    ):
        group_keys_parser = ReportHelper.get_group_keys_parser(
            show_wallet, show_account
        )
        categories_data, group_keys = ReportHelper.group_by_categories_currency(
            transactions, group_keys_parser
        )
        display_data = []

        multiple_key = isinstance(group_keys[0], tuple) if group_keys else False
        row_header_name = (
            f"Account"
            if not show_wallet
            else ("Wallet" if not show_account else "Wallet (Account)")
        )
        for category_currency, data in categories_data.items():
            category, currency = category_currency
            row_header = f"{category.title():<10} ({currency})"
            formatted_data = {}
            for key in group_keys:
                inout = data.get(key, {})
                fkey = (
                    f"{key[0]} (owner: {key[1]})"
                    if multiple_key
                    else key or ANONYMOUS_NAME
                )
                formatted_data[fkey] = (
                    f"(+{inout.get(REPORT_IN, 0):,.0f}, -{inout.get(REPORT_OUT, 0):,.0f})"
                )
            display_data.append({row_header_name: row_header} | formatted_data)
        return display_data

    def report_description(filters):
        print_array = lambda values: (
            ", ".join([str(v) for v in values]) if values else "-"
        )
        return "\n".join(
            [
                f"- {'Time Period':<30}: {filters['start_time'] or '-'} -> {filters['end_time'] or datetime.now()}",
                f"- {'Categories':<30}: {print_array(filters['categories'])}",
                f"- {'Wallets':<30}: {print_array(filters['wallets'])}",
                f"- {'Related People':<30}: {print_array(filters['accounts'])}",
                f"- {'Currencies':<30}: {print_array(filters['currencies'])}",
            ]
        )
