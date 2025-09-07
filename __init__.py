import io
import json
import urllib.request
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from http.client import HTTPResponse
from typing import Callable, TypedDict, override
from xml.etree import ElementTree as ET

from albert import setClipboardText  # pyright: ignore[reportUnknownVariableType]
from albert import (
    Action,
    PluginInstance,
    Query,
    StandardItem,
    TriggerQueryHandler,
)

setClipboardText: Callable[[str], None]

md_iid = '3.0'
md_version = '1.4'
md_name = 'Currency Converter Steven'
md_description = 'Convert currencies'
md_license = 'MIT'
md_url = 'https://github.com/stevenxxiu/albert_currency_converter_steven'
md_authors = ['@stevenxxiu']

ICON_URL = 'file:/usr/share/icons/elementary/apps/128/accessories-calculator.svg'


class EuropeanCentralBank:
    URL: str = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
    CACHE_TIME: timedelta = timedelta(hours=3)

    def __init__(self) -> None:
        self.last_update: datetime = datetime.fromtimestamp(0, UTC)
        self.euro_to_currency: dict[str, float] = {}

    def update_exchange_rates(self) -> None:
        cur_time = datetime.now(UTC)
        if cur_time - self.last_update <= self.CACHE_TIME:
            return

        self.euro_to_currency.clear()
        self.euro_to_currency['EUR'] = 1.0

        with urllib.request.urlopen(EuropeanCentralBank.URL) as response:  # pyright: ignore[reportAny]
            assert isinstance(response, HTTPResponse)
            response_bytes = response.read()

            namespaces: dict[str, ET.Element[str]] = {
                prefix: namespace
                for _, (prefix, namespace) in ET.iterparse(io.BytesIO(response_bytes), events=['start-ns'])
                if isinstance(prefix, str)
            }
            namespace = namespaces['']

            root = ET.parse(io.BytesIO(response_bytes))
            for leaf in root.findall(f'./{{{namespace}}}Cube/{{{namespace}}}Cube/{{{namespace}}}Cube'):
                self.euro_to_currency[leaf.attrib['currency']] = float(leaf.attrib['rate'])

        self.last_update = datetime.now(UTC)

    def get_amount_in_dest_currency(self, src_amount: float, src_currency: str, dest_currency: str) -> float:
        self.update_exchange_rates()

        if src_currency not in self.euro_to_currency or dest_currency not in self.euro_to_currency:
            raise ValueError

        return src_amount / self.euro_to_currency[src_currency] * self.euro_to_currency[dest_currency]


european_central_bank = EuropeanCentralBank()


class CurrencyConverterSettings(TypedDict):
    aliases: dict[str, list[str]]
    defaults: list[str]


class Plugin(PluginInstance, TriggerQueryHandler):
    def __init__(self) -> None:
        PluginInstance.__init__(self)
        TriggerQueryHandler.__init__(self)
        # `{ alias: currency_name }`
        self.aliases: dict[str, str] = {}
        # `[currency_name]`
        self.defaults_dests: list[str] = []

        with suppress(FileNotFoundError):
            with (self.configLocation() / 'settings.json').open() as sr:
                settings: CurrencyConverterSettings = json.load(sr)  # pyright: ignore[reportAny]

            if 'aliases' in settings:
                for currency_name, aliases in settings['aliases'].items():
                    for alias in aliases:
                        self.aliases[alias.lower()] = currency_name.upper()
            if 'defaults' in settings:
                self.defaults_dests = settings['defaults']

    @override
    def synopsis(self, _query: str) -> str:
        return '<amount> <src> [<dest>]'

    @override
    def defaultTrigger(self):
        return 'cc '

    def get_alias(self, currency_name: str) -> str:
        # Lower case first, as aliases are in lower case
        currency_name = currency_name.lower()
        currency_name = self.aliases.get(currency_name, currency_name)
        # Currencies are in upper case
        return currency_name.upper()

    @staticmethod
    def add_item(query: Query, src_amount: float, src_currency: str, dest_currency: str) -> None:
        try:
            dest_amount = european_central_bank.get_amount_in_dest_currency(src_amount, src_currency, dest_currency)
            dest_amount_str = f'{dest_amount:.2f} {dest_currency}'
            query.add(  # pyright: ignore[reportUnknownMemberType]
                StandardItem(
                    id=md_name,
                    text=dest_amount_str,
                    subtext=f'Value of {src_amount:.2f} {src_currency} in {dest_currency}',
                    iconUrls=[ICON_URL],
                    actions=[Action(md_name, md_name, lambda: setClipboardText(dest_amount_str))],
                )
            )
        except ValueError:
            pass

    @override
    def handleTriggerQuery(self, query: Query) -> None:
        try:
            parts = query.string.split()
            match len(parts):
                case 2:
                    src_amount, src_currency = parts
                    dest_currency = None
                case 3:
                    src_amount, src_currency, dest_currency = parts
                case _:
                    raise ValueError
            src_amount = float(src_amount)
            src_currency = self.get_alias(src_currency)
            if dest_currency is not None:
                dest_currency = self.get_alias(dest_currency)
        except ValueError:
            return

        if dest_currency is not None:
            self.add_item(query, src_amount, src_currency, dest_currency)
        else:
            for dest_currency in self.defaults_dests:
                if dest_currency != src_currency:
                    self.add_item(query, src_amount, src_currency, dest_currency)
