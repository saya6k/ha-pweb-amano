"""LLM tools platform for PWEB Amano.

Discovered lazily by Home Assistant's `llm` integration the first time any
LLM API collects tools. Answers only for this integration's own per-entry
API ids (see `..llm_api`) - never `assist` or any other API.
"""
from __future__ import annotations

from homeassistant.components.llm import LLMTools
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import LLMContext

from ..const import DOMAIN
from .tools import TOOLS

_API_ID_PREFIX = f"{DOMAIN}__"

API_PROMPT = (
    "Amano Parking manages a Korean apartment/officetel parking lot through "
    "the resident's PWEB (아마노코리아) portal account: discount balance, "
    "registering parking discounts (주차 할인 등록) for currently-parked cars "
    "(the resident's own, family, or visitors), and discount/parking history. "
    "Korean plates look like '12가3456' or '123가4567'."
)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return this entry's tools, or None for any other API id."""
    if not api_id.startswith(_API_ID_PREFIX):
        return None

    entry_id = api_id[len(_API_ID_PREFIX) :]
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        return None

    return LLMTools(tools=[cls(entry_id) for cls in TOOLS], prompt=API_PROMPT)
