# PWEB Amano — Home Assistant Integration

[![Built with Claude Code](https://img.shields.io/badge/Built%20with%20Claude%20Code-D97757?style=for-the-badge&logo=claude&logoColor=white)](https://claude.ai/code)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-41BDF5?style=for-the-badge&logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

A Home Assistant custom integration for **PWEB** (아마노코리아 관리사무소 시스템) apartment/officetel management portals — sites like `https://a12345.pweb.kr`. These portals have no public API, so this integration logs in with your ID/password and parses the site's HTML.

## Status

Early scaffold. Login/session handling works; **dashboard data parsing is not implemented yet** — the authenticated page layout (parking, notices, management fees, etc.) hasn't been inspected. Currently exposes a single sensor reflecting login/last-sync status. See `AGENTS.md` for details.

## Installation (HACS)

1. HACS → Integrations → ⋮ → Custom repositories → add this repo as an "Integration".
2. Install **PWEB Amano**, restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **PWEB Amano**.
4. Enter your portal host (e.g. `a12345.pweb.kr`), ID, and password.

## Development

```bash
scripts/setup     # first time — installs HA + deps into config/
scripts/develop   # boots HA on :8123 with this integration mounted
```

## Security note

Your password is hashed (SHA-256) client-side before being sent to the portal, matching the site's own login page behavior. It is never logged or stored in plaintext beyond the config entry.
