"""Fetch prices from Boursorama.

Valid tickers are Boursorama symbol IDs, such as "1rPOVH".

IMPORTANT: Boursorama only provides prices denominated in EUR. When using this
source, you must specify "EUR" as the currency prefix, e.g.:
    bean-price -e 'EUR:boursorama/1rPOVH'

Attempting to use this source with any other currency (e.g., "USD:boursorama/...")
will not work as expected, since all prices returned are in EUR.

Here is the API:
https://www.boursorama.com/bourse/action/graph/ws/GetTicksEOD?symbol=1rPOVH&length=1&period=0&guid=

The API returns JSON with:
- qv: Previous quote
- qd: Current day quote
- QuoteTab: Historical tick data (array of price entries with timestamps)

The `length` parameter controls how many days of historical data to return.
We fetch data in batches to avoid making one request per day. Instead, we fetch
multiple days in a single request and use cached results.

Timezone information: Boursorama uses European timezone (Paris/Europe).
"""

__copyright__ = "Copyright (C) 2015-2020  Martin Blais"
__license__ = "GNU GPLv2"

import datetime
from decimal import Decimal
from typing import Optional

import requests
from dateutil.tz import tz

from beanprice import source


class BoursoramaError(ValueError):
    "An error from the Boursorama API."


def fetch_quote(
    ticker: str, time: Optional[datetime.datetime] = None
) -> source.SourcePrice:
    """Fetch a quote from Boursorama."""
    url = "https://www.boursorama.com/bourse/action/graph/ws/GetTicksEOD"
    params = {
        "symbol": ticker,
        "length": "1",
        "period": "0",
        "guid": "",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) "
            "Gecko/20100101 Firefox/145.0"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": f"https://www.boursorama.com/cours/{ticker}/",
        "Content-Type": "application/json;charset=UTF-8",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive",
    }

    response = requests.get(url, params=params, headers=headers)
    if response.status_code != requests.codes.ok:
        raise BoursoramaError(
            f"Invalid response ({response.status_code}): {response.text}"
        )
    result = response.json()

    data = result.get("d", {})
    if not data:
        raise BoursoramaError("No data returned from Boursorama")

    quote_data = data.get("qd")
    if not quote_data:
        raise BoursoramaError("No quote data returned from Boursorama")

    price = Decimal(str(quote_data["c"]))

    if time is None:
        time = datetime.datetime.now(tz.tzutc())
    else:
        time = time.replace(tzinfo=tz.tzutc())

    currency = "EUR"

    return source.SourcePrice(price, time, currency)


def fetch_price_series(
    ticker: str, days: int = 365
) -> list[tuple[datetime.datetime, Decimal]]:
    """Fetch a series of historical prices from Boursorama.

    Args:
        ticker: Boursorama symbol ID.
        days: Number of days of historical data to fetch.

    Returns:
        List of (datetime, Decimal) tuples with prices sorted by date.
    """
    url = "https://www.boursorama.com/bourse/action/graph/ws/GetTicksEOD"
    params = {
        "symbol": ticker,
        "length": str(days),
        "period": "0",
        "guid": "",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) "
            "Gecko/20100101 Firefox/145.0"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": f"https://www.boursorama.com/cours/{ticker}/",
        "Content-Type": "application/json;charset=UTF-8",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive",
    }

    response = requests.get(url, params=params, headers=headers)
    if response.status_code != requests.codes.ok:
        raise BoursoramaError(
            f"Invalid response ({response.status_code}): {response.text}"
        )
    result = response.json()

    data = result.get("d", {})
    if not data:
        raise BoursoramaError("No data returned from Boursorama")

    quote_tab = data.get("QuoteTab", [])
    if not quote_tab:
        raise BoursoramaError("No quote tab data returned from Boursorama")

    series = []
    for entry in quote_tab:
        timestamp = entry.get("d")
        close_price = entry.get("c")
        if timestamp is None or close_price is None:
            continue

        date = datetime.datetime.fromtimestamp(timestamp, tz=tz.tzutc())
        price = Decimal(str(close_price))
        series.append((date, price))

    return series


class Source(source.Source):
    "Boursorama API price extractor."

    def __init__(self) -> None:
        self._cache: dict[
            tuple[str, str], list[tuple[datetime.datetime, Decimal]]
        ] = {}

    def get_latest_price(self, ticker: str) -> Optional[source.SourcePrice]:
        """See contract in beanprice.source.Source."""
        return fetch_quote(ticker)

    def get_historical_price(
        self, ticker: str, time: datetime.datetime
    ) -> Optional[source.SourcePrice]:
        """See contract in beanprice.source.Source."""
        cache_key = (ticker, time.strftime("%Y-%m-%d"))

        if cache_key not in self._cache:
            days = (datetime.datetime.now(tz.tzutc()) - time).days + 10
            days = min(max(days, 10), 730)
            self._cache[cache_key] = fetch_price_series(ticker, days)

        series = self._cache[cache_key]

        latest = None
        for data_dt, price in sorted(series):
            if data_dt.date() > time.date():
                break
            latest = (data_dt, price)

        if latest is None:
            raise BoursoramaError(f"Could not find price before {time}")

        data_dt, price = latest
        return source.SourcePrice(price, data_dt, "EUR")
