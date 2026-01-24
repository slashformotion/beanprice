"""Tests for Boursorama source."""

import datetime
import unittest
from decimal import Decimal

from unittest import mock
from dateutil import tz

import requests

from beanprice import source
from beanprice.sources import boursorama


def response(contents, status_code=requests.codes.ok):
    """Return a context manager to patch a JSON response."""
    response = mock.Mock()
    response.status_code = status_code
    response.text = ""
    response.json.return_value = contents
    return mock.patch("requests.get", return_value=response)


MOCK_RESPONSE = {
    "d": {
        "Name": "OVHCLOUD",
        "SymbolId": "1rPOVH",
        "Xperiod": -1,
        "qv": {
            "d": 20475,
            "o": "8.97",
            "h": "9.00",
            "l": "8.61",
            "c": "8.69",
            "v": 167251,
        },
        "qd": {
            "d": 20476,
            "o": "8.715",
            "h": "9.15",
            "l": "8.65",
            "c": "9.135",
            "v": 179009,
        },
        "QuoteTab": [],
    }
}

MOCK_HISTORICAL_RESPONSE = {
    "d": {
        "Name": "OVHCLOUD",
        "SymbolId": "1rPOVH",
        "QuoteTab": [
            {
                "d": 1706659200,
                "o": "8.65",
                "h": "8.70",
                "l": "8.60",
                "c": "8.65",
                "v": 100000,
            },
            {
                "d": 1706745600,
                "o": "8.65",
                "h": "8.75",
                "l": "8.65",
                "c": "8.70",
                "v": 120000,
            },
            {
                "d": 1706832000,
                "o": "8.70",
                "h": "8.80",
                "l": "8.70",
                "c": "8.75",
                "v": 110000,
            },
        ],
    }
}


class BoursoramaPriceFetcher(unittest.TestCase):
    def test_valid_response(self):
        """Test fetching latest price from Boursorama."""
        with response(MOCK_RESPONSE):
            srcprice = boursorama.Source().get_latest_price("1rPOVH")
            self.assertIsInstance(srcprice, source.SourcePrice)
            self.assertEqual(Decimal("9.135"), srcprice.price)
            self.assertEqual("EUR", srcprice.quote_currency)
            self.assertIsNotNone(srcprice.time)

    def test_historical_price(self):
        """Test fetching historical price from Boursorama."""
        with response(MOCK_HISTORICAL_RESPONSE):
            time = datetime.datetime(2024, 2, 1, 12, 0, 0, tzinfo=tz.tzutc())
            srcprice = boursorama.Source().get_historical_price("1rPOVH", time)
            self.assertIsInstance(srcprice, source.SourcePrice)
            self.assertEqual(Decimal("8.70"), srcprice.price)
            self.assertEqual("EUR", srcprice.quote_currency)
            self.assertIsNotNone(srcprice.time.tzinfo)

    def test_error_response(self):
        """Test handling of invalid response from Boursorama."""
        with response(None, 404):
            with self.assertRaises(ValueError):
                boursorama.Source().get_latest_price("INVALID")

    def test_no_data(self):
        """Test handling of response with no data."""
        with response({"d": {}}):
            with self.assertRaises(ValueError):
                boursorama.Source().get_latest_price("1rPOVH")


if __name__ == "__main__":
    unittest.main()
