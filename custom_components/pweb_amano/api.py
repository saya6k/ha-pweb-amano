"""API client for PWEB (Amano Korea) management portals.

There is no public API — this logs in the same way the portal's own web page
does (POST userId + sha256(password) to /login, then reuse the resulting
JSESSIONID cookie) and hands back raw HTML for parsing.

Each client owns a private aiohttp session (not HA's shared session) so that
two config entries logged into two different portals/accounts never mix
cookies.
"""
from __future__ import annotations

import hashlib
import logging

import aiohttp

from .exceptions import PwebAmanoAuthError, PwebAmanoConnectionError

_LOGGER = logging.getLogger(__name__)


def normalize_base_url(host: str) -> str:
    """Turn a bare host ("a17589.pweb.kr") or full URL into a base URL."""
    host = host.strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"
    return host


class PwebAmanoApiClient:
    """Thin client for login + raw page fetch against a PWEB portal."""

    def __init__(self, base_url: str, user_id: str, password: str) -> None:
        self._base_url = normalize_base_url(base_url)
        self._user_id = user_id
        self._password = password
        self._session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())

    async def async_close(self) -> None:
        """Close the underlying session."""
        await self._session.close()

    async def async_login(self) -> None:
        """Log in, raising PwebAmanoAuthError / PwebAmanoConnectionError on failure."""
        password_hash = hashlib.sha256(self._password.encode()).hexdigest()
        url = f"{self._base_url}/login"
        try:
            async with self._session.post(
                url,
                data={"userId": self._user_id, "userPwd": password_hash},
            ) as response:
                if response.status == 500:
                    try:
                        body = await response.json()
                        message = body.get("errorMsg", "login rejected")
                    except (aiohttp.ContentTypeError, ValueError):
                        message = "login rejected"
                    raise PwebAmanoAuthError(message)
                if response.status == 401:
                    raise PwebAmanoAuthError(
                        "portal requires accepting a personal-info agreement "
                        "before this account can log in"
                    )
                response.raise_for_status()
        except aiohttp.ClientError as err:
            raise PwebAmanoConnectionError(str(err)) from err

    async def async_fetch_dashboard(self) -> str:
        """Fetch the authenticated landing page and return the raw HTML.

        Field-specific parsing is not implemented yet — the authenticated
        page layout hasn't been inspected. See AGENTS.md.
        """
        try:
            async with self._session.get(self._base_url) as response:
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as err:
            raise PwebAmanoConnectionError(str(err)) from err
