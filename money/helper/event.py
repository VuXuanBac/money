import re

from cmdapp.core import Response
from cmdapp.parser import COLUMN_ID
from cmdapp.render.table import Tabling
from cmdapp.utils import Hash, Terminal

from ..constants.schema import *
from ..constants.var import *
from ..app import MoneyApp

from .app import AppHelper


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
