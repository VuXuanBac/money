from cmdapp.core import Response
from cmdapp.utils import Platform
from cmdapp.parser import COLUMN_ID, COLUMN_CREATE, COLUMN_DELETE
from cmdapp.database import SQLCondition, SQLOperators, SQLOrderByDirection, Table
from cmdapp.base import Alias, BasePrototype

from ..constants.schema import *
from ..constants.var import SCOPE_ORDER, SCOPE_SHARING, SCOPE_TX


from ..app import MoneyApp


class AppHelper:
    def get_record_by_name_or_id(table: Table, value: str, column: str = "name"):
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
            ).concat(AppHelper.get_database_errors(app))
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

    def get_database_errors(app: MoneyApp):
        return BasePrototype.print_database_errors(app)

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

    def get_wallet_balance_from_transactions(
        app: MoneyApp, wallet_id: int, currency: str = None, created_later=None
    ):
        sql = f"""
        SELECT 
            currency,
            (SUM(CASE WHEN receiver = :wallet_id THEN amount ELSE 0 END) - 
            SUM(CASE WHEN payer = :wallet_id THEN amount ELSE 0 END)) AS balance
        FROM {TABLE_TRANSACTION.name}
        WHERE 1
        """
        data = dict(wallet_id=wallet_id)
        if currency:
            sql += f" AND currency = :currency"
            data |= dict(currency=currency)
        if created_later:
            sql += f" AND {COLUMN_CREATE} > :timestamp"
            data |= dict(timestamp=created_later)

        sql += " GROUP BY currency"
        result = app.database.query(sql, data)

        balance_by_currency = {}
        for group in result:
            balance_by_currency[group["currency"]] = group["balance"]
        return balance_by_currency

    def get_last_saved_liquidity(app: MoneyApp, wallet_id: int, currency: str = None):
        condition = SQLCondition.with_id(wallet_id)
        if currency:
            condition.AND("currency", SQLOperators.EQUAL, currency)
        liquidity = app.database[TABLE_LIQUIDITY.name].query(
            condition=condition,
            order_by=[(COLUMN_CREATE, SQLOrderByDirection.DESC)],
            page_size=1,
        )
        return liquidity[0] if liquidity else {}
