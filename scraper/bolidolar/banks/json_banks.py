"""Banks that expose their price through a JSON call made by their own website.

BEC (Banco Económico): GET /GetTipoCambio -> {"Compra": 10.7, "Venta": 12.05, ...}
BMSC (Mercantil Santa Cruz): GET backportal.bmsc.com.bo:1443/api/bmscservices/tipotre
-> {"compra": 10.6, "venta": 12, "oficial": 11.7, ...} (the call its own website makes).
FIE: POST /api/tcl -> sentence 'Dólar Compra: 10,80 Dólar Venta: 11,80' plus a date.
BGA (Banco Ganadero): sell only, read from the Next.js data embedded in the home page
(never from its /api/, which robots.txt disallows).
"""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from bolidolar.banks.common import BankSpec, prices_from_text
from bolidolar.models import BankQuote, LayoutChanged
from bolidolar.numbers import parse_decimal, parse_spanish_date, price

BEC_URL = "https://www.baneco.com.bo/GetTipoCambio"
FIE_URL = "https://www.bancofie.com.bo/api/tcl"
FIE_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.bancofie.com.bo",
    "Referer": "https://www.bancofie.com.bo/",
}
BGA_URL = "https://www.bg.com.bo/personas/"
BMSC_URL = "https://backportal.bmsc.com.bo:1443/api/bmscservices/tipotre"
BMSC_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.bmsc.com.bo",
    "Referer": "https://www.bmsc.com.bo/",
}

_FIE_SENTENCE = re.compile(
    r"D[óo]lar\s+Compra:?\s*([\d.,]+)\s*D[óo]lar\s+Venta:?\s*([\d.,]+)", re.IGNORECASE
)


def _loads(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LayoutChanged(f"{what}: response is not JSON") from exc


def _json_price(value: object, what: str) -> Decimal:
    try:
        return price(Decimal(str(value)))
    except (InvalidOperation, ValueError) as exc:
        raise LayoutChanged(f"{what}: bad number {value!r}") from exc


def parse_bec(text: str) -> BankQuote:
    data = _loads(text, "BEC")
    if not isinstance(data, dict) or "Compra" not in data or "Venta" not in data:
        raise LayoutChanged("BEC: keys Compra/Venta missing")
    return BankQuote(
        "BEC",
        "Banco Económico",
        _json_price(data["Compra"], "BEC"),
        _json_price(data["Venta"], "BEC"),
    )


def parse_bmsc(text: str) -> BankQuote:
    data = _loads(text, "BMSC")
    if not isinstance(data, dict) or "compra" not in data or "venta" not in data:
        raise LayoutChanged("BMSC: keys compra/venta missing")
    return BankQuote(
        "BMSC",
        "Banco Mercantil Santa Cruz",
        _json_price(data["compra"], "BMSC"),
        _json_price(data["venta"], "BMSC"),
    )


def parse_fie(text: str) -> BankQuote:
    data = _loads(text, "FIE")
    try:
        result = data["resultado"]
        document = result["documento"]
    except (KeyError, TypeError) as exc:
        raise LayoutChanged("FIE: resultado.documento missing") from exc
    buy, sell = prices_from_text(_FIE_SENTENCE, str(document), "FIE")
    source_date = None
    try:
        source_date = parse_spanish_date(str(result.get("fecha", "")))
    except ValueError:
        pass
    return BankQuote("FIE", "Banco FIE", buy, sell, source_date=source_date)


def _find_key(node: object, key: str) -> object | None:
    if isinstance(node, dict):
        if key in node:
            value: object = node[key]
            return value
        for child in node.values():
            found = _find_key(child, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _find_key(child, key)
            if found is not None:
                return found
    return None


def parse_bga(html: str) -> BankQuote:
    script = HTMLParser(html).css_first("script#__NEXT_DATA__")
    if script is None:
        raise LayoutChanged("BGA: __NEXT_DATA__ missing")
    indicators = _find_key(_loads(script.text(), "BGA"), "indicadores")
    if not isinstance(indicators, list):
        raise LayoutChanged("BGA: indicadores missing")
    for item in indicators:
        if isinstance(item, dict) and item.get("key") == "refVenta":
            try:
                sell = price(parse_decimal(str(item.get("valor", ""))))
            except ValueError as exc:
                raise LayoutChanged(f"BGA: unreadable refVenta ({exc})") from exc
            return BankQuote("BGA", "Banco Ganadero", None, sell)
    raise LayoutChanged("BGA: refVenta missing")


BEC = BankSpec(
    "BEC",
    "Banco Económico",
    lambda f: parse_bec(f.get_text(BEC_URL, headers={"Accept": "application/json"})),
)
FIE = BankSpec(
    "FIE", "Banco FIE", lambda f: parse_fie(f.post_json(FIE_URL, {}, headers=FIE_HEADERS))
)
BGA = BankSpec("BGA", "Banco Ganadero", lambda f: parse_bga(f.get_text(BGA_URL)))
BMSC = BankSpec(
    "BMSC",
    "Banco Mercantil Santa Cruz",
    lambda f: parse_bmsc(f.get_text(BMSC_URL, headers=BMSC_HEADERS)),
)
