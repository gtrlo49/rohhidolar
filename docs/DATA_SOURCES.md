# Data Sources

Verified on **2026-10-14** by fetching the live pages (one request each).

## Context: the exchange-rate regime changed in 2026

- 2011 – ~June 2026: official rate fixed at **Bs 6.96** (sell) / 6.86 (buy); a large parallel market.
- From ~29 June 2026: flexible regime. The BCB publishes a **new official rate (TCO) every day**; it jumped (≈9.7 → ≈12.5 by Sept) and has eased since. Weekend/holiday values are published ahead (e.g. Fri publishes Sat–Mon).
- Each bank now sets its **own counter price** (compra / venta). Posted prices differ a lot from the official rate and from each other (see snapshot). That spread is the whole point of the "best buy / best sell" widget.
- Do not hardcode 6.96 or any rate; treat articles still quoting it as stale.

### Terminology used everywhere in this project (bank's point of view)

| Term | Meaning | "Best" is |
|---|---|---|
| **Compra** | Price the bank **pays** when you sell it a dollar | the **highest** value |
| **Venta** | Price the bank **charges** when you buy a dollar from it | the **lowest** value |
| **Oficial (TCO)** | BCB reference: weighted median of banks' real purchase transactions | n/a (shown as reference) |

## Source A — Banks' own public pages (primary for buy/sell)

Snapshot 2026-10-14:

| Code | Bank | Compra | Venta | Method | Parser difficulty |
|---|---|---|---|---|---|
| **BNB** | Banco Nacional de Bolivia | 11.20 | 12.00 | HTML, labels `Dólar Compra` / `Dólar Venta` / `Dólar Oficial` in the home page (`https://www.bnb.com.bo/PortalBNB/Principal/BancaPersonas`) | Easy. Needs a browser-like User-Agent (default curl gets an empty reply) |
| **BISA** | Banco BISA | 11.00 | 12.00 | HTML marquee on `https://www.bisa.com/home`: `Dólar Compra 11,00 \| Dólar Venta 12,00` (also USDT and Panamá lines — ignore) | Easy; decimal comma |
| **BCP** | Banco de Crédito | 11.20 | 12.00 | HTML marquee on `https://www.bcp.com.bo/`: `Dólar Compra: 11.20` / `Dólar Venta: 12.00` | Easy; decimal dot |
| **BUN** | Banco Unión | 10.20 | 12.00 | HTML text on `https://www.bancounion.com.bo/`: `Compra BOB: 10,20 / Venta 12,00` | Easy; regex on a sentence |
| **BEC** | Banco Económico | 10.70 | 12.05 | JSON `GET https://www.baneco.com.bo/GetTipoCambio` → `{"Oficial":11.7,"Compra":10.7,"Venta":12.05,...}` | Trivial |
| **FIE** | Banco FIE | 10.80 | 11.80 | JSON `POST https://www.bancofie.com.bo/api/tcl` (the site's own front-end call; GET returns 405; needs `Origin`/`Referer` of the site). Response: `{"resultado":{"documento":"Dólar Oficial: 11,70 Dólar Compra: 10,80 Dólar Venta: 11,80 ...","fecha":"14 de octubre 2026"}}` | Easy; parse sentence; includes a date |
| **BGA** | Banco Ganadero | — | 12.00 | Next.js `__NEXT_DATA__` JSON on `https://www.bg.com.bo/personas/`, key `refVenta` ("Valor Ref. Venta USD"). **No buy price published** | Sell only |
| **BMSC** | Banco Mercantil Santa Cruz | 10.60 | 12.00 | JSON `GET https://backportal.bmsc.com.bo:1443/api/bmscservices/tipotre` → `{"compra":10.6,"venta":12,"oficial":11.7,...}` (the call its own site makes; found by the project owner in the browser's network tab; send `Origin`/`Referer` of `www.bmsc.com.bo`). No robots.txt on that host (404) | Trivial |

Notes:
- None of the pages publishes a **timestamp** (only FIE gives a date). The scraper records its own `fetchedAt`; the widget shows "Leído hoy 15:10".
- Prices were identical across banks for *venta* (12.00 ×4), which makes **ties the normal case** — see tie rule in WIDGET_SPEC.
- Selectors/labels live in **one parser module per bank** (`scraper/bolidolar/banks/<code>.py`). A bank failing must never fail the others.
- Reading only the home page / one endpoint per bank, once per hour.

### robots.txt / terms review (2026-10-14)

| Site | Result |
|---|---|
| bcb.gob.bo | `Crawl-delay: 10`; rate page not disallowed. Keep ≥ 10 s between requests |
| bancofie.com.bo | `Disallow:` (empty) → allowed |
| baneco.com.bo | Only `/mapa-del-sitio-*` disallowed → allowed |
| bg.com.bo | `Disallow: /api/` → use the HTML `__NEXT_DATA__`, **never** their `/api/` |
| bancounion.com.bo | Disallows images/pdf/xml/cache; home page allowed |
| backportal.bmsc.com.bo | `/robots.txt` returns 404 → no restrictions published |
| bnb.com.bo, bisa.com, bcp.com.bo | No robots.txt returned (error / SPA fallback) → treat as unrestricted but be conservative |
| Terms of use | **Not reviewed yet** — Phase 0 task per bank |

## Source B — BCB official rate page (reference + history)

- URL: `https://www.bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php` — public HTML fragment, no API, `cache-control: no-store`.
- TCO = amount-weighted median of dollar purchases by banks with their customers. 2026-10-14: **Bs 11.70**, cut-off 2026-10-13, effective ("vigencia") 2026-10-14.

| Data | Selector / pattern |
|---|---|
| Latest TCO | `.tco-public-value` → `Bs 11,70/$us` |
| Cut-off date | `.tco-public-date` → `FECHA DE CORTE: MARTES 13 DE OCTUBRE DE 2026` |
| Effective date | `.tco-public-vigencia` → `VIGENCIA: MIÉRCOLES 14 DE OCTUBRE DE 2026` |
| Per-bank actual purchase rates | `table.tco-public-table tbody tr` → `td`: entity, rate, amount $us, #transactions |
| Daily series | `table.tco-daily-table tbody tr` → `td`: Spanish long date, value (from 2026-06-27) |

Parsing rules: decimal comma / thousands dot (`10.243.603,61`); Spanish month map, never device locale; the **effective date** is the key, not the scrape date.

Daily-series fixture saved at `scraper/tests/fixtures/bcb_2026-10-14.html`.

## Source C — Backfill / fallback

`https://www.bcb.gob.bo/tiposDeCambioHistorico/index.php?anio=2026` (PDF/XLS/ODS) to seed history beyond ~110 days.

## Out of scope for v1 (decided)

- Parallel/digital dollar (Binance P2P, USDT): unofficial endpoints and ToS risk. Revisit in backlog.
- Exchanges houses / casas de cambio.

## Open questions

1. ~~BMSC endpoint~~ — found 2026-10-14.
2. Review each bank's website **terms of use** (robots.txt is not the full picture).
3. Is hourly enough for BCB's publish time? (Assumed yes: hourly covers any afternoon publication within an hour.)
4. Add more banks later (BPR/Prodem, BSO, BFO, BPY…)? Each is one more parser.
