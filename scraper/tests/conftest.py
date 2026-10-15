from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeFetcher:
    """Serves the saved real pages of 2026-10-14 instead of using the network."""

    def __init__(self, overrides: dict[str, str | Exception] | None = None) -> None:
        self.pages: dict[str, str | Exception] = {
            "https://www.bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php": fixture_text(
                "bcb_2026-10-14.html"
            ),
            "https://www.bnb.com.bo/PortalBNB/Principal/BancaPersonas": fixture_text(
                "bnb_2026-10-14.html"
            ),
            "https://www.bisa.com/home": fixture_text("bisa_2026-10-14.html"),
            "https://www.bcp.com.bo/": fixture_text("bcp_2026-10-14.html"),
            "https://www.bancounion.com.bo/": fixture_text("bun_2026-10-14.html"),
            "https://www.baneco.com.bo/GetTipoCambio": fixture_text("bec_2026-10-14.json"),
            "https://www.bancofie.com.bo/api/tcl": fixture_text("fie_2026-10-14.json"),
            "https://www.bg.com.bo/personas/": fixture_text("bga_2026-10-14.html"),
            "https://backportal.bmsc.com.bo:1443/api/bmscservices/tipotre": fixture_text(
                "bmsc_2026-10-14.json"
            ),
        }
        self.pages.update(overrides or {})
        self.requests: list[str] = []

    def _serve(self, url: str) -> str:
        self.requests.append(url)
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return page

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        return self._serve(url)

    def post_json(
        self, url: str, payload: dict[str, object], headers: dict[str, str] | None = None
    ) -> str:
        return self._serve(url)


@pytest.fixture
def fake_fetcher() -> FakeFetcher:
    return FakeFetcher()
