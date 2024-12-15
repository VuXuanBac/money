from cmdapp.parser import TableMeta
from .var import IMPORT_SCOPES
import json

TABLE_ACCOUNT = TableMeta(
    name="account",
    columns={
        "name": "* (*str): unique name for reference",
        "description": "i, bio (str[telex]): bio information",
    },
    meta_columns=["created_at", "updated_at", "deleted_at"],
    constraints=["UNIQUE(name)"],
)

TABLE_WALLET = TableMeta(
    name="wallet",
    columns={
        "name": "* (*str): unique name for reference",
        "account": "[account_id] a (*int): owned account",
        "description": "i (str[telex]): detail information for the wallet like account's id, bank's name,...",
    },
    meta_columns=["created_at", "updated_at", "deleted_at"],
    constraints=["UNIQUE(name)"],
)

TABLE_LIQUIDITY = TableMeta(
    name="liquidity",
    plural="liquidities",
    columns={
        "wallet": "[wallet_id] w (*int): wallet",
        "balance": "v, value (*float): balance (amount of money)",
        "calculate": "(float): calculated balance based on saved transactions",
    },
    meta_columns=["created_at", "deleted_at"],
)

TABLE_TAG = TableMeta(
    name="tag",
    columns={
        "name": "* (*str): unique name for reference",
        "description": "i (str[telex]): describe the context to use it",
    },
    meta_columns=["created_at", "updated_at", "deleted_at"],
    constraints=["UNIQUE(name)"],
)


TABLE_TRANSACTION = TableMeta(
    name="tx",
    singular="transaction",
    columns={
        "amount": "* (*float): transaction value (amount of money)",
        "currency": "u (*str): currency unit",
        "message": "m (*str[telex]): describe the context of the transaction",
        "payer": "[wallet_id] p (int): wallet used to pay",
        "receiver": "[wallet_id] r (int): wallet that receive",
        "category": "[tag_id] t (int): assign category for statistics",
        "timestamp": "[timestamp] at (datetime): happen time, recommended for statistics",
    },
    meta_columns=["created_at", "updated_at", "deleted_at"],
)

TABLE_ORDER = TableMeta(
    name="shopping",
    singular="order",
    columns={
        "tx": "[transaction_id] (*int): paying transaction",
        "items": "p (*array[telex]): buy products",
        "shop": "(str[telex]): name of the shop",
        "platform": "(str[telex]): name of selling platform, like shopee, tiki,...",
        "review": "(str[telex]): review for received products",
        "tag": "[tag_id] (*int): tag for filtering",
        "complete": "(datetime): received date",
    },
    meta_columns=["created_at", "updated_at", "deleted_at"],
    constraints=["UNIQUE(tx)"],
)

TABLE_SHARING = TableMeta(
    name="sharing",
    columns={
        "tx": "[transaction_id] (*int): paying transaction",
        "people": "[account_ids] (*array[int]): people sharing the expense",
        "shares": "(array[float]): the proportion of the expense that each person should pays. By default (set null), everyone splits the expense equally",
        "tag": "[tag_id] (int): tag for filtering",
    },
    meta_columns=["created_at", "updated_at", "deleted_at"],
    constraints=["UNIQUE(tx)"],
)

TABLE_EVENT = TableMeta(
    name="event",
    columns={
        "name": "n (*str[telex]): name for reference",
        "tag": "[tag_id] t (*int): tag that represent an event, used to filter sharing transactions",
        "bills": "(*array[json]): how much each person joining the event paid, received and needs to paided",
        "sharings": "(*array[int]): sharings belong to this event",
        "currency": "c (*str): chosen currency for the calculation",
        "rates": "r (json): exchange rates from other currencies to chosen currency",
    },
    meta_columns=["created_at", "updated_at", "deleted_at"],
    constraints=["UNIQUE(name)"],
)

TABLE_REPORT = TableMeta(
    name="report",
    columns={
        "name": "n (*str[telex]): name for reference",
        "filters": "(json): filters apply on transactions",
        "txs": "[transaction_ids] (*array[int]): transactions belongs to this report",
        "data": "(json): report data",
    },
    meta_columns=["created_at", "deleted_at"],
    constraints=["UNIQUE(name)"],
)

TABLE_NOTE_RESOURCE = TableMeta(
    name="resource",
    columns={
        "name": "* (*str): unique name for reference",
        "link": "l, url (*str): link to fetch new notes",
        "option": "(json): options to parse notes: `{'format': '.csv'}`",
        "scope": f"t, type (str: {json.dumps(IMPORT_SCOPES)} = tx): what data is inside each note: pure transaction, sharing or order",
        "currency": "c (str): default currency unit for importing",
        "scale": "s (float): default scale level for transaction value",
        "last_import": "(datetime): last imported timestamp",
        "last_record": "(json): last record from last importing, used to find new notes for next importing",
    },
    meta_columns=["created_at", "updated_at", "deleted_at"],
    constraints=["UNIQUE(name)"],
)

TABLE_LISTS = [
    TABLE_ACCOUNT,
    TABLE_WALLET,
    TABLE_LIQUIDITY,
    TABLE_TAG,
    TABLE_TRANSACTION,
    TABLE_REPORT,
    TABLE_ORDER,
    TABLE_SHARING,
    TABLE_EVENT,
    TABLE_NOTE_RESOURCE,
]
