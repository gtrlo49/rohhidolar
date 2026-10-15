# Test fixtures

These files are fragments of responses from the public websites of the Banco Central de Bolivia and of Bolivian banks, taken on 2026-10-14. They exist only so the parsers can be tested against real markup.

- They are **third-party material** and are not covered by this repository's MIT license. They remain the property of their owners.
- Each file is **trimmed to the smallest fragment the parser needs** (the exchange-rate strip, the JSON response, the embedded `indicadores` data, or the BCB summary and daily table). Do not commit whole pages.
- Third-party site keys that appeared in the original pages were removed with the rest of the page.
- Do not add content that contains personal data, cookies or session tokens.
- When a bank changes its page, add a new dated fixture instead of editing an old one, so old layouts stay covered.
- A comment at the top of each HTML file says where the fragment came from.
