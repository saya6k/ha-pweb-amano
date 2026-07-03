# PWEB Amano — Home Assistant Integration

A Home Assistant custom integration for **PWEB** (Amano Korea apartment/officetel management portals) — sites like `https://a17589.pweb.kr`. These portals have no public API, so this integration logs in with your ID/password and parses the site's HTML.

## Status

Early scaffold. Login/session handling works; dashboard data parsing (parking, notices, management fees, etc.) is not implemented yet — the authenticated page layout hasn't been inspected. Currently exposes a single sensor reflecting login/last-sync status.

## Installation (HACS)

1. HACS → Integrations → ⋮ → Custom repositories → add this repo as an "Integration".
2. Install **PWEB Amano**, restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **PWEB Amano**.
4. Enter your portal host (e.g. `a17589.pweb.kr`), ID, and password.

## Security

Your password is hashed (SHA-256) client-side before being sent to the portal, matching the site's own login page behavior. It is never logged or stored in plaintext beyond the config entry.
