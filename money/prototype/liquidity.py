from cmdapp.core import Prototype, Response, as_command
from cmdapp.parser import COLUMN_ID, COLUMN_CREATE

from ..constants.var import *
from ..constants.schema import *

from ..helper import AppHelper
from ..app import MoneyApp


class LiquidityPrototype(Prototype):
    @as_command(
        description="Update the wallet balance and check the difference with balance from transactions",
        epilog="This command should be used to set current (real) balance of a wallet and summarize the balance calculated from saved transactions, then notify the difference",
        arguments={
            "wallet": "* (*str): wallet to check the balance",
            "balance": "v, value (float): actual current balance of the wallet",
            "currency": "c (str): currency unit. require to save into database",
        },
    )
    def do_check(app: MoneyApp, args):
        currency = args.currency
        current_balance = args.balance
        response = Response(app)
        wallet = AppHelper.get_record_by_name_or_id(
            app.database[TABLE_WALLET.name], args.wallet
        )
        if not wallet:
            return response.on("error").message(
                "found",
                style="error",
                negative=True,
                what=TABLE_WALLET.human_name(),
                field="alias",
                items=args.wallet,
            )
        wallet_id = wallet[COLUMN_ID]
        last_saved_liquidity = AppHelper.get_last_saved_liquidity(
            app, wallet_id, currency
        )
        last_saved_timestamp = last_saved_liquidity.get(COLUMN_CREATE)
        balance_by_currency = AppHelper.get_wallet_balance_from_transactions(
            app, wallet_id, currency, last_saved_timestamp if currency else None
        )

        response.message(
            None,
            f"Total received from transactions for the wallet [{wallet['name']}] ({COLUMN_ID.upper()}: {wallet_id}):",
            style="info",
        ).message(
            None,
            "\n".join(
                [
                    f"* {key}".upper() + f": {value:,.0f}"
                    for key, value in balance_by_currency.items()
                ]
            )
            + "\n",
        )

        if current_balance is None or not currency:
            return response.on("error").message(
                "argument",
                style="warning",
                argument="currency and balance",
                status="missing",
                result="The liquidity can not be saved into database",
            )

        last_saved_balance = last_saved_liquidity.get("balance", 0)
        calculated_balance = last_saved_balance + balance_by_currency.get(currency, 0)
        response.message(
            None,
            f"The previous saved     balance is {last_saved_balance:,.0f} {currency}\n"
            f"The calculated         balance is {calculated_balance:,.0f} {currency}\n"
            + f"The current (provided) balance is {current_balance:,.0f} {currency}\n",
            style="info",
        )
        difference = current_balance - calculated_balance
        message_kwargs = {"style": None, "message": "NO DIFFERENCE"}
        if difference < -1e-6:
            message_kwargs = {"style": "error", "message": "LEAK"}
        elif difference > 1e-6:
            message_kwargs = {"style": "success", "message": "REDUNDANT"}
        response.message(
            None,
            f"==> {message_kwargs['message']}: {abs(difference):,.0f} {currency}\n",
            style=message_kwargs["style"],
        )

        return response.concat(
            AppHelper.save_record(
                app,
                TABLE_LIQUIDITY,
                dict(
                    wallet=wallet_id,
                    currency=currency,
                    balance=float(current_balance),
                    calculate=float(calculated_balance),
                ),
            )
        )
