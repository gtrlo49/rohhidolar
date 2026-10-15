# RohhiDolar — Bolivia USD widget for iPhone & iPad

A WidgetKit widget that shows, for the US dollar in Bolivia (Bs/$us), the **best compra** and **best venta** among the main banks (with the bank's code, e.g. `BNB +1`, `FIE`) next to the **official BCB rate**. Data is read **every hour** from the banks' own public pages (BNB, BISA, BCP, Unión, Económico, FIE, Ganadero, Mercantil) and from the BCB page.

> Status: **scraper done** (94 tests, 8 of 8 banks read live; published on GitHub Pages 4 times a day). iOS app and widget not started.

## Why the design looks like this

- Since mid-2026 Bolivia moved from the fixed 6.96 rate to a **flexible regime**: a new official rate every day (TCO, 2026-10-14: **Bs 11.70/$us**) and **each bank posts its own compra/venta** (on that day compra 10.20–11.20, venta 11.80–12.05). Comparing banks is now genuinely useful.
- A widget **cannot scrape reliably on its own**: iOS gives it a small, system-controlled refresh budget and no background HTML parsing guarantees. So scraping runs on a tiny **backend job**, which publishes a small static `rate.json`; the widget only downloads that JSON.

```
BCB page + 8 bank pages ──(scrape 4×/day, GitHub Actions)──▶ rate.json (static host/CDN)
                                                          │
                                  iOS app + Widget extension ◀┘  (App Group cache, WidgetKit timeline)
```

## Document map

| File | Purpose |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, repo layout, decisions |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Verified sources, HTML structure, parsing rules |
| [docs/SCRAPER_SPEC.md](docs/SCRAPER_SPEC.md) | Backend scraper + `rate.json` contract + CI schedule |

## Quick decisions (change in ARCHITECTURE.md if you disagree)

- **Sources:** each bank's public page for compra/venta; BCB page for the official rate and history.
- **Display:** best compra = highest, best venta = lowest; ties show one deterministic pick per day plus `+N`; tapping opens the free app.
- **Distribution:** free app (widget lives inside it); dev with free Apple ID → TestFlight → App Store (US$99/yr).
- **Stack:** Swift 6 / SwiftUI / WidgetKit (iOS 17+, iPadOS 17+); scraper in **Python 3.12** (`httpx` + `selectolax`/`BeautifulSoup`) run by **GitHub Actions cron**, output hosted on **GitHub Pages** (free, HTTPS, CDN).
- **No user accounts, no tracking, no secrets in the app.**

## License and data

- **Code and docs:** [MIT](LICENSE), © 2026 Jose Carlos Rueda Garcia.
- **Data:** prices come from the Banco Central de Bolivia and from each bank's public website. They are informational references, belong to their publishers, and are not licensed by this project.
- **Fixtures** in `scraper/tests/fixtures/` are saved third-party pages used only for testing (see the README there).
- Not affiliated with the BCB or any bank. Not financial advice.
