import io
import json
import urllib.request
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from albert import Action, Item, Query, QueryHandler, configLocation, setClipboardText  # pylint: disable=import-error


md_iid = '0.5'
md_version = '1.0'
md_name = 'Currency Converter Steven'
md_description = 'Convert currencies'
md_url = 'https://github.com/stevenxxiu/albert_currency_converter_steven'
md_maintainers = '@stevenxxiu'

TRIGGER = 'cc'
ICON_PATH = '/usr/share/icons/elementary/apps/128/accessories-calculator.svg'


class EuropeanCentralBank:
    URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
    CACHE_TIME = timedelta(hours=3)

    def __init__(self):
        self.last_update: datetime = datetime.fromtimestamp(0, timezone.utc)
        self.euro_to_currency: dict[str, float] = {}

    def update_exchange_rates(self) -> None:
        cur_time = datetime.now(timezone.utc)
        if cur_time - self.last_update <= self.CACHE_TIME:
            return

        self.euro_to_currency.clear()
        self.euro_to_currency['EUR'] = 1.0

        with urllib.request.urlopen(EuropeanCentralBank.URL) as response:
            response_bytes = response.read()

            namespaces = {
                prefix: namespace
                for _, (prefix, namespace) in ET.iterparse(io.BytesIO(response_bytes), events=['start-ns'])
            }
            namespace = namespaces['']

            root = ET.parse(io.BytesIO(response_bytes))
            for leaf in root.findall(f'./{{{namespace}}}Cube/{{{namespace}}}Cube/{{{namespace}}}Cube'):
                self.euro_to_currency[leaf.attrib['currency']] = float(leaf.attrib['rate'])

        self.last_update = datetime.now(timezone.utc)

    def get_amount_in_dest_currency(self, src_amount: float, src_currency: str, dest_currency: str) -> float:
        self.update_exchange_rates()

        if src_currency not in self.euro_to_currency or dest_currency not in self.euro_to_currency:
            raise ValueError

        return src_amount / self.euro_to_currency[src_currency] * self.euro_to_currency[dest_currency]


european_central_bank = EuropeanCentralBank()


class Plugin(QueryHandler):
    def __init__(self):
        super().__init__()
        # `{ alias: currency_name }`
        self.aliases: dict[str, str] = {}
        # `[currency_name]`
        self.defaults_dests: list[str] = []

    def id(self) -> str:
        return __name__

    def name(self) -> str:
        return md_name

    def description(self) -> str:
        return md_description

    def initialize(self) -> None:
        with suppress(FileNotFoundError):
            with (Path(configLocation()) / __name__ / 'settings.json').open() as sr:
                settings = json.load(sr)

            if 'aliases' in settings:
                for currency_name, aliases in settings['aliases'].items():
                    for alias in aliases:
                        self.aliases[alias.lower()] = currency_name.upper()
            if 'defaults' in settings:
                self.defaults_dests = settings['defaults']

    def defaultTrigger(self) -> str:
        return f'{TRIGGER} '

    def synopsis(self) -> str:
        return '<amount> <src> [<dest>]'

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
            query.add(
                Item(
                    id=md_name,
                    text=dest_amount_str,
                    subtext=f'Value of {src_amount:.2f} {src_currency} in {dest_currency}',
                    icon=[ICON_PATH],
                    actions=[Action(md_name, md_name, lambda: setClipboardText(dest_amount_str))],
                )
            )
        except ValueError:
            return

    def handleQuery(self, query: Query) -> None:
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
