# Scraper & Data Contract

## Responsibilities

1. Four times a day fetch: the BCB page + one page/endpoint per bank (see [DATA_SOURCES.md](DATA_SOURCES.md)).
2. Parse each source independently (a failing bank never fails the others).
3. Validate; compute **best compra**, **best venta** (with ties) and the official rate delta.
4. Write `rate.json` + `history.json`; publish. On total failure keep the last good file and fail CI.

## Repo layout (backend)

```
scraper/
  pyproject.toml
  rohhidolar/
    numbers.py       # Spanish numbers/dates, price rounding
    http.py          # httpx client: UA, timeout, retries, per-host delay (BCB ≥ 10 s)
    models.py        # BankQuote, OfficialRate, LayoutChanged, ValidationError
    banks/           # one BankSpec per bank (fetch + pure parse function); isolated failures
      common.py      # BankSpec, page_text, prices_from_text
      text_banks.py  # BNB, BISA, BCP, BUN (anchor text in HTML)
      json_banks.py  # BEC, BMSC (JSON), FIE (POST JSON), BGA (__NEXT_DATA__, sell only)
      __init__.py    # BANKS registry (8 banks)
    bcb.py           # official TCO + daily series
    ranking.py       # best compra/venta, ties, deterministic pick
    validate.py      # sanity rules
    publish.py       # build rate/history JSON, atomic writes, idempotency
    run.py           # one run: collect → validate → rank → build
    __main__.py      # CLI: --out --previous-url --dry-run --accept-jump
    watchdog.py      # fails when the live rate.json is too old
  tests/
    fixtures/        # saved real responses of 2026-10-14 per source
    test_*.py        # numbers, banks, bcb, ranking, validate, run/publish, http, contract (JSON Schema), failures
schema/rate.v1.schema.json  schema/history.v1.schema.json   # frozen v1 contract
.github/workflows/scrape.yml      # scrape 4×/day + Pages deploy
.github/workflows/watchdog.yml    # stale-data alert
.github/workflows/ci-scraper.yml  # ruff, mypy, pytest on PRs
site/v1/rate.json  site/v1/history.json
```

Bank interface:

```python
class BankQuote:  code: str; name: str; buy: Decimal | None; sell: Decimal | None
                  fetched_at: datetime; source_date: date | None   # FIE only
```

## `rate.json` contract (v1)

```json
{
  "schema": 1,
  "fetchedAt": "2026-10-14T19:10:04Z",
  "official": {
    "source": "BCB", "rate": 11.70,
    "effectiveDate": "2026-10-14", "previousRate": 11.70, "previousDate": "2026-10-13",
    "change": 0.00, "changePct": 0.0,
    "upcoming": [ { "date": "2026-10-15", "rate": 11.70 } ]
  },
  "banks": [
    { "code": "BNB",  "name": "Banco Nacional de Bolivia", "buy": 11.20, "sell": 12.00, "ok": true },
    { "code": "BCP",  "name": "Banco de Crédito",          "buy": 11.20, "sell": 12.00, "ok": true },
    { "code": "BISA", "name": "Banco BISA",                "buy": 11.00, "sell": 12.00, "ok": true },
    { "code": "FIE",  "name": "Banco FIE",                 "buy": 10.80, "sell": 11.80, "ok": true },
    { "code": "BEC",  "name": "Banco Económico",           "buy": 10.70, "sell": 12.05, "ok": true },
    { "code": "BUN",  "name": "Banco Unión",               "buy": 10.20, "sell": 12.00, "ok": true },
    { "code": "BGA",  "name": "Banco Ganadero",            "buy": null,  "sell": 12.00, "ok": true },
    { "code": "BMSC", "name": "Banco Mercantil Santa Cruz","buy": 10.60, "sell": 12.00, "ok": true }
  ],
  "bestBuy":  { "value": 11.20, "pick": "BNB", "others": ["BCP"],  "tieCount": 2 },
  "bestSell": { "value": 11.80, "pick": "FIE", "others": [],       "tieCount": 1 },
  "sourceUrls": { "official": "https://www.bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php" }
}
```

`history.json`: `{ "schema":1, "official":[{"date":"2026-06-27","rate":9.73}], "bestBuy":[{"date":"…","value":…}], "bestSell":[…] }`. The official series is seeded from the BCB page; bank series start accumulating from the first run (one point per La_Paz day = the day's last good snapshot). Cap 400 points.

The contract is frozen as JSON Schema in `schema/rate.v1.schema.json` and `schema/history.v1.schema.json`; `tests/test_contract.py` validates every run against them (the iOS tests should reuse the same files).

Contract rules: additive changes only inside `v1`; breaking change → `v2/` beside it. Dates ISO in `America/La_Paz`; `fetchedAt` UTC. Cache `max-age=300`.

## Ranking rules (`ranking.py`)

- **bestBuy** = max `buy` among banks with `ok` and non-null buy. **bestSell** = min `sell`.
- Compare as `Decimal`, 2-decimals; equal values are a **tie**.
- **Tie pick must be deterministic per day** (stable across runs and across devices): sort tied codes, then `pick = tied[hash(date_iso + side) % len(tied)]`. It looks random from day to day but never flickers between refreshes. `others` lists the remaining tied codes; widgets render `pick` + `+len(others)`.
- If the best value changes mid-day, recompute the pick with the same formula.

## Validation (a source failing validation is marked `ok:false`, not published)

- Each price in **[3, 50]**; `sell ≥ buy` when both exist; |change vs last good| ≤ **15 %** per bank (else `ok:false`, reason `jump`).
- Official rate: same range; effective date ≥ previous and ≤ today+4 days.
- Publish only if **official OK and ≥ 4 banks OK**; otherwise keep last file and fail the workflow.
- A bank failing **8 consecutive runs** (2 days at 4 runs/day) is flagged as a GitHub warning and in the job summary (parser probably broken). The streak travels in `rate.json` as `banks[].failStreak` (present only while > 0).

## Schedule (`scrape.yml`)

- **4 runs/day**: `cron: "10 0,6,12,18 * * *"` (UTC, + `workflow_dispatch`). GitHub's cron may drift ±15 min — acceptable.
- Per run ≈ 9 requests spaced ≥ 10 s apart (BCB `Crawl-delay`), well under a minute of total traffic; 4 runs/day.
- Skip commit/deploy when payload is unchanged except `fetchedAt` older than 3 h (so freshness stays visible).
- Alerts: workflow failure e-mail; watchdog cron fails if `fetchedAt` is > 4 h old, checked 1.5 h after each scrape.
- Deploy to GitHub Pages with `actions/deploy-pages`.

## Implementation notes (2026-10-14)

- State between runs: the Pages site is the database. Each run reads the previous `rate.json`/`history.json` from the live URL (`--previous-url`), so there are no scheduled commits. First run (404) starts empty.
- Idempotency: if the new payload equals the previous one (ignoring `fetchedAt`) and the previous is < 3 h old, the old `rate.json` is kept as is.
- `www.bcp.com.bo` resets TLS connections that use Python's default cipher policy (curl works). Only for that host the client uses OpenSSL security level 1 (`LEGACY_TLS_HOSTS` in `http.py`); certificate verification stays on. Prices are range-checked, so a tampered page would be rejected as `out_of_range`/`jump` in most cases. Revisit if BCP updates its TLS.
- `selectolax` ≥ 1.0 dropped the Modest backend; the code uses the Lexbor parser.
- Live run (2026-10-14): **8 of 8 banks OK**, best compra 11.20 (BNB/BCP tie), best venta 11.80 (FIE). BMSC was added the same day from the endpoint its website calls.

## Hardening

- Identifiable UA that looks like a browser plus contact: `Mozilla/5.0 (…) Safari/605.1.15 RohhiDolar/1.0 (+contact-url)` — BNB rejects non-browser UAs.
- Each bank parser asserts its anchor text (`Dólar Compra`, `Compra BOB`, JSON keys); missing anchor → `LayoutChanged` → `ok:false`, never a guess.
- Never call endpoints disallowed in `robots.txt` (BG `/api/`). FIE `/api/tcl` is the site's own public front-end call (robots allows all); re-check if it starts requiring tokens.
- Fixtures for every bank per month to detect markup drift.
