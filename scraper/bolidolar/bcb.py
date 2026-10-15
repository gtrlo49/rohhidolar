"""Official exchange rate (TCO) from the BCB public page."""

import re

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from bolidolar.http import Fetcher
from bolidolar.models import LayoutChanged, OfficialRate
from bolidolar.numbers import parse_decimal, parse_spanish_date, price

BCB_URL = "https://www.bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php"


def parse(html: str) -> OfficialRate:
    tree = HTMLParser(html)
    value = tree.css_first(".tco-public-value")
    vigencia = tree.css_first(".tco-public-vigencia")
    cutoff = tree.css_first(".tco-public-date")
    table = tree.css_first("table.tco-daily-table")
    if value is None or vigencia is None or cutoff is None or table is None:
        raise LayoutChanged("BCB: expected TCO elements missing")

    number = re.search(r"[\d.,]*\d", value.text())
    if not number:
        raise LayoutChanged("BCB: TCO value unreadable")
    headers = [th.text().strip().lower() for th in table.css("thead th")]
    if len(headers) < 2 or not headers[0].startswith("fecha") or not headers[1].startswith("valor"):
        raise LayoutChanged("BCB: daily table headers changed")

    try:
        rate = price(parse_decimal(number.group(0)))
        effective = parse_spanish_date(vigencia.text())
        cutoff_date = parse_spanish_date(cutoff.text())
        series = []
        for row in table.css("tbody tr"):
            cells = row.css("td")
            if len(cells) < 2:
                continue
            series.append(
                (parse_spanish_date(cells[0].text()), price(parse_decimal(cells[1].text())))
            )
    except ValueError as exc:
        raise LayoutChanged(f"BCB: unreadable value ({exc})") from exc
    if not series:
        raise LayoutChanged("BCB: daily series empty")
    return OfficialRate(rate, effective, cutoff_date, sorted(series))


def fetch(fetcher: Fetcher) -> OfficialRate:
    return parse(fetcher.get_text(BCB_URL, headers={"Accept": "text/html"}))
