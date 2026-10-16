"""Banks that print 'Dólar Compra X ... Dólar Venta Y' in their public home page.

BNB (static HTML), BISA and BCP (marquee strips) share the same anchor text.
Banco Unión prints a sentence: 'Dólar Oficial 11,70 Compra BOB: 10,20 / Venta 12,00'
(since 2026-10-16 with colons: 'Dólar Oficial: 11,68 Compra BOB: 10,18 / Venta: 11,83').
"""

import re

from rohhidolar.banks.common import BankSpec, page_text, prices_from_text
from rohhidolar.http import Fetcher
from rohhidolar.models import BankQuote

_DOLAR_COMPRA_VENTA = re.compile(
    r"D[óo]lar\s+Compra:?\s*([\d.,]+)\s*\|?\s*D[óo]lar\s+Venta:?\s*([\d.,]+)", re.IGNORECASE
)
_UNION = re.compile(
    r"D[óo]lar\s+Oficial:?\s*[\d.,]+\s*Compra\s+BOB:?\s*([\d.,]+)\s*/\s*Venta:?\s*([\d.,]+)",
    re.IGNORECASE,
)

BNB_URL = "https://www.bnb.com.bo/PortalBNB/Principal/BancaPersonas"
BISA_URL = "https://www.bisa.com/home"
BCP_URL = "https://www.bcp.com.bo/"
BUN_URL = "https://www.bancounion.com.bo/"


def parse_bnb(html: str) -> BankQuote:
    buy, sell = prices_from_text(_DOLAR_COMPRA_VENTA, page_text(html), "BNB")
    return BankQuote("BNB", "Banco Nacional de Bolivia", buy, sell)


def parse_bisa(html: str) -> BankQuote:
    buy, sell = prices_from_text(_DOLAR_COMPRA_VENTA, page_text(html), "BISA")
    return BankQuote("BISA", "Banco BISA", buy, sell)


def parse_bcp(html: str) -> BankQuote:
    buy, sell = prices_from_text(_DOLAR_COMPRA_VENTA, page_text(html), "BCP")
    return BankQuote("BCP", "Banco de Crédito", buy, sell)


def parse_bun(html: str) -> BankQuote:
    buy, sell = prices_from_text(_UNION, page_text(html), "BUN")
    return BankQuote("BUN", "Banco Unión", buy, sell)


def _fetch_html(url: str, fetcher: Fetcher) -> str:
    return fetcher.get_text(url, headers={"Accept": "text/html"})


BNB = BankSpec("BNB", "Banco Nacional de Bolivia", lambda f: parse_bnb(_fetch_html(BNB_URL, f)))
BISA = BankSpec("BISA", "Banco BISA", lambda f: parse_bisa(_fetch_html(BISA_URL, f)))
BCP = BankSpec("BCP", "Banco de Crédito", lambda f: parse_bcp(_fetch_html(BCP_URL, f)))
BUN = BankSpec("BUN", "Banco Unión", lambda f: parse_bun(_fetch_html(BUN_URL, f)))
