# Repository agent instructions

> `CLAUDE.md` is a local symlink to this file (gitignored) — edit `AGENTS.md`.

Agent assets live under `.agents/` (the source of truth): `skills/`, `workflows/` (commands), `agents/`, and `memory/` (Claude's per-project memory). `.claude/` is a real directory: its `settings.json` is Claude-specific and tracked; its per-item symlinks into `.agents/` (`skills`, `commands` → `workflows`, `agents`) and `settings.local.json` are local-only, as is the `CLAUDE.md` → `AGENTS.md` symlink.

This file briefs coding agents on the conventions and load-bearing facts of `ha-pweb-amano`. Read this before making changes.

## What this integration is

A HACS custom integration for **PWEB** (Amano Korea) apartment/officetel management portals — sites like `https://a17589.pweb.kr` that run the 아마노코리아 관리사무소 시스템. There is no public API; the portal is a legacy JSP-style site (`*.do` endpoints, `JSESSIONID` cookies) meant to be driven through a browser, so this integration logs in and parses HTML.

- **Login:** `POST {base_url}/login` with form fields `userId` (plaintext) and `userPwd` (**sha256 hex digest of the plaintext password** — the site's own login page hashes client-side before submitting, see `login.js`/`sha256-0.9.0.min.js`). Success is any 2xx response; failure is HTTP 500 with a JSON `errorMsg`, or HTTP 401 (personal-info agreement required — not handled).
- **Session:** the login response sets a `JSESSIONID` cookie; every subsequent page fetch must reuse the same `aiohttp.ClientSession` (cookie jar) or the site treats you as logged out.
- **Dashboard scraping is intentionally unimplemented.** Nobody has inspected an authenticated `/` (post-login landing) page yet — the field layout (주차/공지/관리비 등) is unknown. `api.py:async_fetch_dashboard` fetches and returns the raw page; extracting real fields into `coordinator.py`/`sensor.py` requires an authenticated user to share that HTML (view source while logged in, or the devcontainer against a real account) before more sensors can be added. Don't invent sensor fields without seeing the real markup.
- **`robots.txt` on this host disallows crawling** (`Disallow: /`). That's aimed at search engines. This integration only ever fetches pages behind the user's own login, at a normal HA polling cadence (not a crawler) — keep it that way; don't add multi-page crawling or high-frequency polling.

## Repository layout

```
ha-pweb-amano/
├── custom_components/pweb_amano/
│   ├── __init__.py        ← async_setup_entry/async_unload_entry, creates the coordinator
│   ├── const.py            ← DOMAIN, CONF_* keys, default scan interval
│   ├── api.py               ← PwebAmanoApiClient: login + raw page fetch (aiohttp)
│   ├── exceptions.py       ← PwebAmanoAuthError / PwebAmanoConnectionError
│   ├── coordinator.py       ← DataUpdateCoordinator, calls api.py
│   ├── config_flow.py       ← single step: host, userId, userPwd
│   ├── sensor.py            ← one placeholder sensor (login/last-sync status)
│   ├── manifest.json
│   ├── strings.json         ← English source of truth for translations
│   └── translations/en.json, ko.json
├── .devcontainer/
├── scripts/
│   ├── setup                ← installs HA + dev deps in the container
│   └── develop               ← runs HA from this checkout for live testing
├── hacs.json
└── README.md
```

## Hard rules

1. **Never set `_attr_name` on an entity that has `_attr_translation_key`.** HA's `Entity._name_internal` returns `_attr_name` first and never consults the translation map afterwards — this silently breaks non-English UI. Pick one.
2. **Translations live in two places.** `strings.json` is the English source of truth; `translations/<lang>.json` must share the same key tree — update both together.
3. **The coordinator owns all network I/O.** Entities read `self.coordinator.data[...]`; they never call `api.py` directly.
4. **`manifest.json` declares `iot_class: cloud_polling`.** Don't add push/websocket behavior.
5. **Password never leaves memory as plaintext longer than needed.** Hash with `hashlib.sha256` right before the login POST; don't log the raw password or the hash.
6. **`brand/` assets are Amano Korea's official CI marks** (downloaded from amano.co.kr's public brand page: `icon.png` = the AMANO triangle mark padded to a square, `logo.png`/`dark_logo.png` = the "Time & Air / AMANO" wordmark, light/dark variants). Used solely to identify the integrated service — this is an unofficial, community-maintained integration, not published or endorsed by Amano Korea.

## Testing

```bash
scripts/develop          # boots HA on :8123 with this integration mounted
```

No automated test suite. Validate by adding the integration via Settings → Devices & Services with a real account and watching `home-assistant.log`.

## When in doubt

- Login fails with 500? Read the JSON body's `errorMsg` — the site returns a human-readable reason.
- Need new sensors? Get authenticated HTML from the user first (browser dev tools, "view source" after login) — don't guess field names.
