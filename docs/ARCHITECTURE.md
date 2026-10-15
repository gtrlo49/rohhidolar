# Architecture

## Components

```
┌────────────────────┐
│ BCB official page  │──┐
├────────────────────┤  │ 4×/day cron   ┌──────────────┐  deploy  ┌───────────────────────┐
│ Bank pages ×8      │──┼──────────────▶│ GitHub Action │─────────▶│ GitHub Pages (CDN)    │
│ BNB BISA BCP BUN   │  │ fetch+parse   │ Python scraper│          │ /v1/rate.json         │
│ BEC FIE BGA BMSC   │──┘ per-bank      │ rank + tie    │          │ /v1/history.json      │
└────────────────────┘    isolation     └──────────────┘          └──────────┬────────────┘
                                                                             │ HTTPS GET (ETag)
                                          ┌──────────────────────────────────▼───────────────┐
                                          │ iOS/iPadOS app + Widget extension (RohhiDolarKit)  │
                                          │ App Group cache · WidgetKit timeline · BGTask     │
                                          └───────────────────────────────────────────────────┘
```

## Key decisions (ADR summary)

| # | Decision | Why | Alternatives rejected |
|---|---|---|---|
| 1 | Scrape on a **server-side job**, not on device | Widgets have tiny, uncontrolled refresh/runtime budgets; parsing HTML on-device breaks silently when markup changes and cannot be fixed without an App Store release | On-device scrape (fragile, slow review cycle) |
| 2 | Publish **static JSON** | Free, cacheable, trivially reliable, no server to run, no keys | Custom API/DB (over-engineered for one number/day) |
| 3 | **Banks' own pages** for compra/venta (BNB, BISA, BCP, BUN, BEC, FIE, BGA, BMSC) + **BCB TCO** as official reference | Since the 2026 float each bank posts its own prices and they differ a lot; BCB only publishes a purchase median. Seven of eight pages are plain HTML or a tiny JSON | BCB only (no sell price, hides the spread); headless browser for every bank (heavy) |
| 7 | **4×/day** scrape, per-bank isolation, deterministic daily tie pick | 4 runs a day is enough for prices that change a few times a day; isolation keeps one broken page from breaking the widget; determinism avoids flicker | Real-time push; random on-device pick |
| 8 | Widget tap opens the **free app** | Works offline from cache, shows all banks | Open a web page (needs network, adds nothing) |
| 4 | **GitHub Actions + Pages** | $0, auditable history in git, easy alerts | Cloudflare Workers/AWS Lambda (good Phase 2 if cron reliability matters) |
| 5 | **WidgetKit + App Group cache**, deploy target iOS 17 | Native, supports Lock Screen/StandBy/iPad | Third-party widget frameworks (don't exist for iOS) |
| 6 | Versioned contract (`/v1/`) | Old app builds keep working when the scraper evolves | Unversioned JSON |

## Repository layout (monorepo)

```
rohhidolar/
  README.md
  docs/                     # scraper-related docs (app/plan docs are kept local, outside the repo)
  scraper/                  # Python: bcb.py + banks/<code>.py + ranking.py (see SCRAPER_SPEC.md)
  site/                     # published JSON (GitHub Pages)
  .github/workflows/        # scrape.yml, ci-scraper.yml, ci-ios.yml
  ios/
    RohhiDolar.xcodeproj
    RohhiDolar/              # app target
    RohhiDolarWidget/        # widget extension
    Packages/RohhiDolarKit/  # models, RateService, RateStore, formatters (+ tests)
```

## Cross-cutting concerns

- **Time zone:** the business day is `America/La_Paz` (UTC−4, no DST). All "today" logic uses it on both sides.
- **Precision:** `Decimal` on device, 2-decimal numbers in JSON.
- **Privacy:** no analytics SDKs, no identifiers, only a GET of a public file. App Privacy label: *Data Not Collected*.
- **Observability:** CI failure e-mail; a "stale data" watchdog workflow; optional status badge in README.
- **Cost:** $0 now. Paid Apple Developer Program ($99/yr) needed only to ship on TestFlight/App Store (free personal team can sideload for 7 days).
- **Bus factor / continuity:** the JSON host URL is baked into the app → use a stable domain you control (custom domain on Pages) so the backend can move without an app update.
