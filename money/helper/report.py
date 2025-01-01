from datetime import datetime

from ..constants.var import REPORT_IN, REPORT_OUT, ANONYMOUS_NAME


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
